"""Tests du parcours : opportunité → qualification → lettre → email → candidature → brouillon .eml → envoi manuel.
Le LLM est simulé UNIQUEMENT dans les tests (aucune donnée fictive n'est jamais produite par l'application)."""
import email
import inspect
import json
import os
import tempfile

TMP = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{TMP}/test.db"
os.environ["STORAGE_DIR"] = f"{TMP}/storage"
os.environ["LLM_BASE_URL"] = "http://llm.test/v1"
os.environ["LLM_API_KEY"] = "test"
os.environ["LLM_MODEL"] = "test-model"
os.environ["TAVILY_API_KEY"] = ""
os.environ["ADMIN_PHONES"] = ""
os.environ["ENVIRONMENT"] = "dev"
os.environ["MAIL_USER"] = "contact@kortexdigital.net"
os.environ["MAIL_PASSWORD"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-for-unit-tests-0123456789"
os.environ["PUBLIC_URL"] = "https://prospect.example"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402,F401
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import llm, mail  # noqa: E402

Base.metadata.create_all(engine)


def fake_chat_json(system, user, max_tokens=2000):
    if "qualifies" in system or "Grille" in system:
        return {"relevant_shalom": True, "relevant_kortex": False, "recommended_profile": "shalom", "matched": ["FastAPI", "RAG"],
                "criteria": {k: {"score": 99, "reason": "test"} for k in ("skills", "sector", "geography", "contract", "experience")},
                "documents_to_attach": ["cv_en"], "approach": "Direct", "language": "en", "red_flags": [], "summary": "ok"}
    if "froid" in system:
        return {"subject": "Acme et l'automatisation", "body": "Bonjour,\n\nJ'ai vu qu'Acme distribue du matériel médical à Abidjan."}
    if "email" in system.lower():
        return {"subject": "Application – Backend Engineer", "content": "Dear team,\n\nShort email."}
    return {"subject": "Backend Engineer (FastAPI)", "content": "Dear Hiring Manager,\n\nParagraph one.\n\nParagraph two."}


@pytest.fixture(scope="module")
def client():
    llm.chat_json = fake_chat_json  # monkeypatch module-level
    import app.services.generator as g
    import app.services.qualification as q
    g.llm.chat_json = fake_chat_json
    q.llm.chat_json = fake_chat_json
    with TestClient(app) as c:
        yield c


def test_draft_module_never_sends():
    # Le module des candidatures individuelles ne fait que des brouillons ; l'envoi n'existe que
    # dans outreach.tick(), qui ne traite que des emails de lots validés par l'utilisateur.
    src = inspect.getsource(mail)
    for forbidden in ("smtplib", "send_message", "sendmail", '"mode": "send"'):
        assert forbidden not in src
    assert '"mode": "draft"' in src


def test_full_flow(client):
    r = client.post("/api/opportunities/import", json={"text": "Backend Engineer at Acme. Python FastAPI RAG LLM. Remote worldwide. Full-time.",
                                                       "url": "https://acme.example/jobs/1", "profile_key": "shalom"})
    assert r.status_code == 200, r.text
    opp = r.json()["opportunity"]

    c = client.post("/api/companies", json={"name": "Acme", "website": None, "scan": False}).json()["company"]
    client.patch(f"/api/opportunities/{opp['id']}", json={"company_id": c["id"]})
    client.post(f"/api/companies/{c['id']}/contacts", json={"kind": "email", "value": "jobs@acme.example", "label": "rh",
                                                           "confidence": "found_unverified", "source_url": "https://acme.example"})

    q = client.post(f"/api/opportunities/{opp['id']}/qualify").json()
    assert q["score"] == 100  # scores plafonnés au maximum de chaque critère
    assert q["analysis"]["criteria"]["skills"]["max"] == 30

    letter = client.post("/api/generated", json={"doc_type": "cover_letter", "opportunity_id": opp["id"], "language": "en"}).json()
    assert "Shalom Tehe" in letter["content"]  # signature ajoutée
    em = client.post("/api/generated", json={"doc_type": "email", "opportunity_id": opp["id"], "language": "en", "letter_id": letter["id"]}).json()

    for fmt, magic in (("pdf", b"%PDF"), ("docx", b"PK")):
        r = client.get(f"/api/generated/{letter['id']}/export?format={fmt}")
        assert r.status_code == 200 and r.content[:4].startswith(magic)

    app_ = client.post("/api/applications", json={"opportunity_id": opp["id"]}).json()
    assert app_["recipient"] == "jobs@acme.example"
    assert app_["attachment_ids"] == []  # rien n'est joint sans validation
    assert app_["subject"] == em["subject"]

    detail = client.get(f"/api/applications/{app_['id']}").json()
    cv = next(x for x in detail["recommendations"] if x["category"] in ("cv_en", "cv_fr"))
    assert "absent" in cv["reason"]  # bibliothèque vide dans le test

    r = client.get(f"/api/applications/{app_['id']}/eml")
    msg = email.message_from_bytes(r.content)
    assert msg["X-Unsent"] == "1" and msg["To"] == "jobs@acme.example"
    assert any(p.get_filename() and p.get_filename().endswith(".pdf") for p in msg.walk())

    sent = client.post(f"/api/applications/{app_['id']}/mark-sent", json={}).json()
    assert sent["status"] == "envoyee"
    o = client.get(f"/api/opportunities/{opp['id']}").json()
    assert o["status"] == "envoyee_manuellement" and o["next_action_date"]

    dash = client.get("/api/dashboard").json()["stats"]
    assert dash["applications_sent"] == 1 and dash["letters_generated"] == 1


def test_generation_requires_target(client):
    r = client.post("/api/generated", json={"doc_type": "cover_letter"})
    assert r.status_code == 422


def test_fraud_is_rejected(client):
    r = client.post("/api/opportunities/import", json={"text": "Job! Frais de dossier 20 000 FCFA à payer par Western Union.",
                                                       "title": "Agent", "company_name": "X"})
    assert r.status_code == 422


def test_verified_contact_needs_source(client):
    c = client.post("/api/companies", json={"name": "Beta SA", "scan": False}).json()["company"]
    r = client.post(f"/api/companies/{c['id']}/contacts", json={"value": "a@beta.ci", "confidence": "verified"})
    assert r.status_code == 422


def test_contact_extraction_offline():
    from bs4 import BeautifulSoup
    from app.services.contact_extractor import _emails_in, _phones_in, label_for_email
    html = '<a href="mailto:recrutement@ex.ci">x</a> contact [at] ex.ci (+225) 27 21 23 33 00 logo@2x.png'
    soup = BeautifulSoup(html, "lxml")
    emails = _emails_in(soup, soup.get_text(" "))
    assert emails == {"recrutement@ex.ci", "contact@ex.ci"}
    assert label_for_email("recrutement@ex.ci") == "rh"
    assert "+225 27 21 23 33 00" in _phones_in(soup, soup.get_text(" "))


def test_heuristic_off_stack():
    from app.models import Opportunity
    from app.services.qualification import heuristic_opportunity
    o = Opportunity(title="Senior Magento Developer", description="PHP Magento, some python scripts", skills=[], contract_type="full_time",
                    location="Worldwide", remote=True, kind="job", needs_verification=False)
    assert heuristic_opportunity(o, "shalom")["total"] < 60
    json.dumps(heuristic_opportunity(o, "shalom"))


def test_campaign_flow(client, monkeypatch):
    from app.db import SessionLocal
    from app.services import outreach as o

    o.llm.chat_json = fake_chat_json
    c = client.post("/api/companies", json={"name": "Acme Medical", "scan": False, "city": "Abidjan",
                                            "description": "Distributeur de matériel médical à Abidjan, 3 agences, catalogue en ligne."}).json()["company"]
    client.post(f"/api/companies/{c['id']}/contacts", json={"value": "info@acme-medical.ci", "confidence": "verified", "source_url": "https://acme-medical.ci"})
    bare = client.post("/api/companies", json={"name": "Sans Email SA", "scan": False, "description": "x" * 80}).json()["company"]

    camp = client.post("/api/campaigns", json={"name": "Test", "company_ids": [c["id"], bare["id"]]}).json()
    detail = client.get(f"/api/campaigns/{camp['id']}").json()
    assert detail["status"] == "review"
    items = {i["target"]: i for i in detail["items"]}
    assert items["Sans Email SA"]["status"] == "ignoree"
    ok = items["Acme Medical"]
    assert ok["status"] == "brouillon" and "KORTEX" in ok["body"]  # signature ajoutée

    r = client.post(f"/api/campaigns/{camp['id']}/approve")
    assert r.status_code == 200, r.text

    sent = []
    monkeypatch.setattr(o, "in_send_window", lambda at=None: True)
    monkeypatch.setattr(o, "smtp_send", lambda msg, att=None: sent.append(msg) or "<1@kortexdigital.net>")
    with SessionLocal() as db:
        assert o.tick(db)["sent"] == 1
        assert o.tick(db)["sent"] == 0  # intervalle aléatoire avant le suivant
    msg = sent[0]
    assert msg["To"] == "info@acme-medical.ci" and "List-Unsubscribe" in msg
    assert "/u/" in msg.get_content()  # lien de désinscription dans le corps

    token = o.unsubscribe_token("info@acme-medical.ci")
    assert client.post(f"/api/public/unsubscribe/{token}").json()["email"] == "info@acme-medical.ci"
    with SessionLocal() as db:
        company = db.get(models.Company, c["id"])
        assert o.eligibility(db, company, "info@acme-medical.ci")  # exclue désormais


def test_lint_flags_spammy_content():
    from app.services.outreach import lint
    assert not lint("Échange avec KORTEX DIGITAL", "Bonjour Acme, une question.", "Acme")
    w = lint("OFFRE GRATUITE !!!", "Cliquez ici http://a http://b http://c", "Acme")
    assert any("filtrés" in x for x in w) and any("majuscules" in x for x in w) and any("liens" in x for x in w)


def test_phone_normalization():
    from app.auth import _wa_candidates, normalize_phone
    assert normalize_phone("07 12 11 62 58") == "2250712116258"
    assert normalize_phone("+225 07 12 11 62 58") == "2250712116258"
    assert _wa_candidates("2250712116258") == ["2250712116258", "22512116258"]
