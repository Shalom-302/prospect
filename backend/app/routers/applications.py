"""Préparation des candidatures / démarches. Rien n'est envoyé par l'application :
on produit un brouillon (.eml, mailto, ou brouillon Zoho) que l'utilisateur relit et envoie lui-même,
puis il confirme l'envoi manuellement pour le suivi."""
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Application, Company, Document, GeneratedDocument, Opportunity, now
from ..services.documents import recommend
from ..services.mail import SENDER, ZohoError, build_eml, mailto_link, read_attachment, zoho_create_draft
from .common import app_out, change_status, get_or_404, log
from .generation import export_bytes

router = APIRouter(prefix="/api/applications", tags=["candidatures"])

CONF_RANK = {"verified": 0, "found_unverified": 1, "estimated": 2}
LABEL_RANK_JOB = {"rh": 0, "direction": 1, "general": 2, "it": 3, "partenariat": 4}
LABEL_RANK_B2B = {"partenariat": 0, "direction": 1, "it": 2, "general": 3, "rh": 4}


def best_email(company: Company | None, b2b: bool) -> tuple[str, str]:
    if not company:
        return "", ""
    emails = [c for c in company.contacts if c.kind == "email"]
    if not emails:
        return "", ""
    ranks = LABEL_RANK_B2B if b2b else LABEL_RANK_JOB
    c = sorted(emails, key=lambda x: (CONF_RANK.get(x.confidence, 3), ranks.get(x.label, 5)))[0]
    return c.value, c.confidence


class AppIn(BaseModel):
    opportunity_id: int | None = None
    company_id: int | None = None
    profile_key: str | None = None
    language: str = "fr"


@router.post("")
def create_application(body: AppIn, db: Session = Depends(get_db)):
    opp = get_or_404(db, Opportunity, body.opportunity_id) if body.opportunity_id else None
    company = get_or_404(db, Company, body.company_id) if body.company_id else (opp.company if opp else None)
    if not (opp or company):
        raise HTTPException(422, "Une candidature concerne une opportunité ou une entreprise.")
    key = body.profile_key or (opp.profile_key if opp else "kortex")
    b2b = key == "kortex" or (opp is not None and opp.kind == "b2b")
    recipient, confidence = best_email(company, b2b)
    gq = db.query(GeneratedDocument).filter(GeneratedDocument.opportunity_id == opp.id) if opp else db.query(GeneratedDocument).filter(GeneratedDocument.company_id == company.id)
    letter = gq.filter(GeneratedDocument.doc_type.in_(["cover_letter", "b2b_proposal"])).order_by(GeneratedDocument.created_at.desc()).first()
    email = gq.filter(GeneratedDocument.doc_type == "email").order_by(GeneratedDocument.created_at.desc()).first()
    channel = "email" if recipient else ("platform" if opp and opp.apply_url else "email")
    a = Application(profile_key=key, opportunity_id=opp.id if opp else None, company_id=company.id if company else None,
                    channel=channel, recipient=recipient, subject=email.subject if email else "", body=email.content if email else "",
                    letter_id=letter.id if letter else None, attachment_ids=[], attach_letter_format="pdf" if letter else "none")
    db.add(a)
    db.flush()
    log(db, "note", "Candidature préparée (brouillon)", company_id=a.company_id, opportunity_id=a.opportunity_id, application_id=a.id)
    db.commit()
    out = app_out(a)
    out["recipient_confidence"] = confidence
    return out


@router.get("")
def list_applications(status: str | None = None, profile_key: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Application)
    if status:
        q = q.filter(Application.status.in_(status.split(",")))
    if profile_key:
        q = q.filter_by(profile_key=profile_key)
    items = []
    for a in q.order_by(Application.updated_at.desc()).limit(300):
        d = app_out(a)
        o = db.get(Opportunity, a.opportunity_id) if a.opportunity_id else None
        c = db.get(Company, a.company_id) if a.company_id else None
        d["target_title"] = o.title if o else (c.name if c else "")
        d["target_company"] = (c.name if c else "") or (o.company_name if o else "")
        items.append(d)
    return items


@router.get("/{app_id}")
def get_application(app_id: int, db: Session = Depends(get_db)):
    a = get_or_404(db, Application, app_id)
    d = app_out(a)
    opp = db.get(Opportunity, a.opportunity_id) if a.opportunity_id else None
    company = db.get(Company, a.company_id) if a.company_id else None
    d["opportunity"] = {"id": opp.id, "title": opp.title, "apply_url": opp.apply_url, "language": opp.language, "kind": opp.kind} if opp else None
    d["company"] = {"id": company.id, "name": company.name,
                    "emails": [{"value": c.value, "label": c.label, "confidence": c.confidence, "source_url": c.source_url} for c in company.contacts if c.kind == "email"],
                    "forms": [c.value for c in company.contacts if c.kind in ("contact_form", "careers_page")]} if company else None
    lang = (opp.language if opp and opp.language else None) or "fr"
    docs = db.query(Document).all()
    d["recommendations"] = recommend(docs, a.profile_key, lang, opp, company)
    letter = db.get(GeneratedDocument, a.letter_id) if a.letter_id else None
    d["letter"] = {"id": letter.id, "subject": letter.subject, "doc_type": letter.doc_type, "language": letter.language} if letter else None
    return d


class AppPatch(BaseModel):
    recipient: str | None = None
    cc: str | None = None
    subject: str | None = None
    body: str | None = None
    channel: str | None = None
    letter_id: int | None = None
    attachment_ids: list[int] | None = None
    attach_letter_format: str | None = None
    status: str | None = None


@router.patch("/{app_id}")
def patch_application(app_id: int, body: AppPatch, db: Session = Depends(get_db)):
    a = get_or_404(db, Application, app_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("status") == "envoyee":
        raise HTTPException(422, "Utiliser « Confirmer l'envoi manuel » pour enregistrer un envoi.")
    if "attachment_ids" in data:
        existing = {d.id for d in db.query(Document.id).filter(Document.id.in_(data["attachment_ids"] or []))}
        data["attachment_ids"] = [i for i in data["attachment_ids"] if i in existing]
    for k, v in data.items():
        setattr(a, k, v)
    db.commit()
    return app_out(a)


@router.delete("/{app_id}")
def delete_application(app_id: int, db: Session = Depends(get_db)):
    db.delete(get_or_404(db, Application, app_id))
    db.commit()
    return {"ok": True}


def _attachments(db: Session, a: Application) -> list[tuple[str, bytes]]:
    files = []
    for doc_id in a.attachment_ids or []:
        d = db.get(Document, doc_id)
        if d:
            files.append((d.filename, read_attachment(d.stored_path)))
    if a.letter_id and a.attach_letter_format in ("pdf", "docx"):
        g = db.get(GeneratedDocument, a.letter_id)
        if g:
            data, _, filename = export_bytes(db, g, a.attach_letter_format)
            files.append((filename, data))
    return files


def _check_ready(a: Application):
    problems = []
    if not a.recipient or not re.fullmatch(r"[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+", a.recipient.strip()):
        problems.append("destinataire manquant ou invalide (une seule adresse)")
    if not a.subject.strip():
        problems.append("objet vide")
    if not a.body.strip():
        problems.append("corps de l'email vide")
    if problems:
        raise HTTPException(422, "Brouillon incomplet : " + ", ".join(problems))


@router.get("/{app_id}/eml")
def download_eml(app_id: int, db: Session = Depends(get_db)):
    """Fichier .eml non envoyé : s'ouvre en mode composition dans Outlook / Thunderbird."""
    a = get_or_404(db, Application, app_id)
    _check_ready(a)
    data = build_eml(SENDER, a.recipient, a.cc, a.subject, a.body, _attachments(db, a))
    a.status, a.draft_provider = "draft_cree", "eml"
    db.commit()
    return Response(data, media_type="message/rfc822", headers={"Content-Disposition": f'attachment; filename="brouillon_candidature_{a.id}.eml"'})


@router.get("/{app_id}/mailto")
def get_mailto(app_id: int, db: Session = Depends(get_db)):
    a = get_or_404(db, Application, app_id)
    _check_ready(a)
    return {"url": mailto_link(a.recipient, a.cc, a.subject, a.body),
            "warning": "Le lien mailto ne transporte pas les pièces jointes : ajoutez-les dans votre messagerie."}


@router.post("/{app_id}/zoho-draft")
def create_zoho_draft(app_id: int, db: Session = Depends(get_db)):
    """Crée un BROUILLON dans Zoho Mail. L'utilisateur l'ouvre, vérifie et clique lui-même sur Envoyer."""
    a = get_or_404(db, Application, app_id)
    _check_ready(a)
    try:
        ref = zoho_create_draft(db, a.recipient, a.cc, a.subject, a.body, _attachments(db, a))
    except ZohoError as e:
        raise HTTPException(422, str(e))
    a.status, a.draft_provider, a.draft_ref = "draft_cree", "zoho", ref
    log(db, "note", "Brouillon créé dans Zoho Mail (non envoyé)", company_id=a.company_id, opportunity_id=a.opportunity_id, application_id=a.id)
    db.commit()
    return {"ok": True, "draft_ref": ref, "open_url": "https://mail.zoho.com/zm/#mail/folder/drafts"}


class SentIn(BaseModel):
    sent_at: datetime | None = None
    follow_up_days: int = 7
    note: str = ""


@router.post("/{app_id}/mark-sent")
def mark_sent(app_id: int, body: SentIn, db: Session = Depends(get_db)):
    """L'utilisateur confirme avoir envoyé LUI-MÊME la candidature."""
    a = get_or_404(db, Application, app_id)
    a.status = "envoyee"
    a.sent_at = body.sent_at or now()
    follow = a.sent_at + timedelta(days=body.follow_up_days)
    for model, id_ in ((Opportunity, a.opportunity_id), (Company, a.company_id)):
        obj = db.get(model, id_) if id_ else None
        if obj:
            change_status(db, obj, "envoyee_manuellement")
            obj.next_action, obj.next_action_date = "Relancer si pas de réponse", follow
    log(db, "email_sent", f"Envoyé manuellement à {a.recipient or a.channel}. {body.note}".strip(),
        company_id=a.company_id, opportunity_id=a.opportunity_id, application_id=a.id, when=a.sent_at)
    db.commit()
    return app_out(a)
