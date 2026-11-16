"""Envoi par lots — conçu pour arriver en boîte de réception, pas en spam.

Principes de délivrabilité appliqués :
- chaque email est personnalisé (aucun envoi si l'entreprise est trop peu décrite pour l'être) ;
- texte brut, court, sans pièce jointe par défaut, un seul lien, pas de pixel de suivi ;
- montée en charge progressive (warm-up) et plafond quotidien global pour la boîte ;
- envois espacés aléatoirement, en heures ouvrées d'Abidjan, jours ouvrés ;
- désinscription en un clic (en-têtes List-Unsubscribe + lien) et liste d'exclusion permanente ;
- pas de recontact d'une même entreprise avant N jours, arrêt immédiat en cas de réponse ;
- suivi des rebonds par IMAP, pause automatique si le taux de rebond dépasse 5 %.
L'utilisateur relit et valide chaque lot avant tout envoi.
"""
import email
import imaplib
import json
import logging
import random
import re
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from zoneinfo import ZoneInfo

import httpx
import jwt
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Activity, Application, Campaign, Company, Document, InboxSeen, Opportunity, Profile, Suppression, now
from . import llm

log = logging.getLogger("prospect.outreach")
ABIDJAN = ZoneInfo("Africa/Abidjan")

# ---------- Désinscription ----------


def unsubscribe_token(email_addr: str) -> str:
    s = get_settings()
    return jwt.encode({"e": email_addr.lower(), "p": "unsub"}, s.secret_key or s.token_secret_key, algorithm="HS256")


def email_from_token(token: str) -> str | None:
    s = get_settings()
    try:
        data = jwt.decode(token, s.secret_key or s.token_secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return data.get("e") if data.get("p") == "unsub" else None


def unsubscribe_url(email_addr: str) -> str:
    return f"{get_settings().public_url.rstrip('/')}/u/{unsubscribe_token(email_addr)}"


def suppress(db: Session, email_addr: str, reason: str, note: str = "") -> None:
    e = email_addr.strip().lower()
    if not db.query(Suppression).filter_by(email=e).first():
        db.add(Suppression(email=e, reason=reason, note=note))


def is_suppressed(db: Session, email_addr: str) -> bool:
    return db.query(Suppression).filter_by(email=email_addr.strip().lower()).first() is not None


# ---------- Délivrabilité : DNS, warm-up, contrôle du contenu ----------


def _dns_txt(name: str, rtype: str = "TXT") -> list[str]:
    try:
        r = httpx.get("https://dns.google/resolve", params={"name": name, "type": rtype}, timeout=10)
        return [a["data"].strip('"').replace('" "', "") for a in r.json().get("Answer", [])]
    except (httpx.HTTPError, ValueError):
        return []


def dns_report(domain: str) -> list[dict]:
    checks = []
    spf = [t for t in _dns_txt(domain) if t.startswith("v=spf1")]
    checks.append({"key": "spf", "label": "SPF", "ok": bool(spf) and "zoho" in spf[0], "value": spf[0] if spf else "",
                   "advice": "OK : Zoho est autorisé à envoyer pour le domaine." if spf and "zoho" in spf[0] else "Ajouter « v=spf1 include:zohomail.com ~all » en TXT."})
    if len(spf) > 1:
        checks[-1].update(ok=False, advice="Plusieurs enregistrements SPF : n'en garder qu'un seul.")
    dkim = [t for t in _dns_txt(f"zmail._domainkey.{domain}") if "DKIM1" in t or "p=" in t]
    key = re.search(r"p=([A-Za-z0-9+/=]+)", dkim[0]).group(1) if dkim and "p=" in dkim[0] else ""
    bits = 1024 if 150 < len(key) < 300 else 2048 if len(key) >= 300 else 0
    checks.append({"key": "dkim", "label": "DKIM (zmail)", "ok": bool(key), "value": f"clé RSA ~{bits} bits" if key else "",
                   "advice": ("OK. Conseillé : régénérer une clé 2048 bits dans Zoho Admin › Domaines › DKIM." if bits == 1024 else "OK.")
                   if key else "Activer DKIM dans Zoho Mail Admin › Domaines et publier l'enregistrement TXT."})
    dmarc = [t for t in _dns_txt(f"_dmarc.{domain}") if t.startswith("v=DMARC1")]
    pol = re.search(r"p=(\w+)", dmarc[0]).group(1) if dmarc else ""
    checks.append({"key": "dmarc", "label": "DMARC", "ok": bool(dmarc), "value": dmarc[0] if dmarc else "",
                   "advice": ("Présent en mode surveillance (p=none). Après 2 à 4 semaines d'envois propres, passer à p=quarantine."
                              if pol == "none" else "OK.") if dmarc else "Ajouter _dmarc TXT « v=DMARC1; p=none; rua=mailto:contact@… »."})
    mx = _dns_txt(domain, "MX")
    checks.append({"key": "mx", "label": "MX", "ok": any("zoho" in m for m in mx), "value": ", ".join(mx),
                   "advice": "OK : les réponses arrivent dans Zoho." if any("zoho" in m for m in mx) else "MX non Zoho : vérifier la réception."})
    return checks


def sent_today(db: Session) -> int:
    start = datetime.now(ABIDJAN).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    return db.query(func.count(Application.id)).filter(Application.campaign_id.isnot(None), Application.status == "envoyee",
                                                        Application.sent_at >= start).scalar() or 0


def daily_limit(db: Session) -> tuple[int, str]:
    """Warm-up : 10/jour la 1re semaine d'envois, 20 la 2e, puis le plafond configuré (30 par défaut)."""
    cap = get_settings().campaign_daily_max
    first = db.query(func.min(Application.sent_at)).filter(Application.campaign_id.isnot(None), Application.status == "envoyee").scalar()
    if not first:
        return min(10, cap), "semaine 1 de montée en charge"
    first = first if first.tzinfo else first.replace(tzinfo=timezone.utc)
    days = (now() - first).days
    if days < 7:
        return min(10, cap), f"montée en charge : jour {days + 1}/7 à 10 emails"
    if days < 14:
        return min(20, cap), f"montée en charge : semaine 2 à 20 emails"
    return cap, "rythme de croisière"


def in_send_window(at: datetime | None = None) -> bool:
    local = (at or now()).astimezone(ABIDJAN)
    start, end = (int(x) for x in get_settings().campaign_hours.split("-"))
    return local.weekday() < 5 and start <= local.hour < end


SPAM_WORDS = ["gratuit", "100%", "garanti", "urgent", "offre spéciale", "offre exceptionnelle", "cliquez ici", "promotion",
              "meilleur prix", "sans engagement", "gagnez", "argent", "free", "act now", "winner", "guarantee", "limited time",
              "click here", "risk-free", "$$$", "€€€", "!!!", "révolutionnaire", "incroyable"]


def lint(subject: str, body: str, company_name: str = "") -> list[str]:
    w = []
    text = f"{subject}\n{body}".lower()
    hits = [s for s in SPAM_WORDS if s in text]
    if hits:
        w.append(f"Mots souvent filtrés : {', '.join(hits)}")
    allowed_caps = {"KORTEX", "DIGITAL", "IA", "AI", "API", "PME", "RH", "DSI"} | {t.upper() for t in re.findall(r"\w+", company_name)}
    shouting = [t for t in re.findall(r"\w+", subject) if len(t) >= 3 and t.isupper() and t not in allowed_caps]
    if len(shouting) >= 2:
        w.append(f"Mots en majuscules dans l'objet : {', '.join(shouting)}")
    if "!" in subject:
        w.append("Point d'exclamation dans l'objet")
    if len(subject) > 70:
        w.append("Objet trop long (> 70 caractères)")
    links = re.findall(r"https?://", body)
    if len(links) > 2:
        w.append(f"{len(links)} liens (2 maximum conseillés)")
    words = len(body.split())
    if words > 220:
        w.append(f"Message long ({words} mots) : viser 80 à 160")
    if company_name and company_name.split()[0].lower() not in body.lower():
        w.append("Le nom de l'entreprise n'apparaît pas : personnalisation à vérifier")
    if "[à compléter]" in text or "[a completer]" in text:
        w.append("Champ [À COMPLÉTER] restant")
    return w


# ---------- Constitution du lot ----------

CONF_RANK = {"verified": 0, "found_unverified": 1}
LABEL_RANK = {"partenariat": 0, "direction": 1, "it": 2, "general": 3, "rh": 4}
LABEL_RANK_JOB = {"rh": 0, "direction": 1, "general": 2, "it": 3, "partenariat": 4}


def pick_recipient(company: Company, job: bool) -> tuple[str, str]:
    """Meilleure adresse publique. Les adresses « estimées » ne sont jamais utilisées en envoi par lots."""
    ranks = LABEL_RANK_JOB if job else LABEL_RANK
    emails = [c for c in company.contacts if c.kind == "email" and c.confidence in CONF_RANK]
    if not emails:
        return "", ""
    c = sorted(emails, key=lambda x: (CONF_RANK[x.confidence], ranks.get(x.label, 5)))[0]
    return c.value, c.confidence


def eligibility(db: Session, company: Company | None, recipient: str) -> str | None:
    """Raison d'exclusion, ou None si l'envoi est possible."""
    s = get_settings()
    if not recipient:
        return "Aucune adresse email publique (vérifiée ou trouvée) : passer par le formulaire de contact."
    if is_suppressed(db, recipient):
        return "Adresse dans la liste d'exclusion (désinscription, rebond ou refus)."
    since = now() - timedelta(days=s.recontact_days)
    q = db.query(Application).filter(Application.status == "envoyee", Application.sent_at >= since)
    if q.filter(Application.recipient.ilike(recipient)).first():
        return f"Déjà contactée il y a moins de {s.recontact_days} jours."
    if company:
        if q.filter(Application.company_id == company.id).first():
            return f"Entreprise déjà contactée il y a moins de {s.recontact_days} jours."
        if company.status in ("refuse", "gagne", "negociation", "rdv_programme", "reponse_recue", "entretien_realise"):
            return "Échange déjà en cours ou clos avec cette entreprise : écrire manuellement."
        if db.query(Activity).filter_by(company_id=company.id, type="reply").first():
            return "L'entreprise a déjà répondu : poursuivre l'échange manuellement."
        if len((company.description or "").strip()) < 60 and not company.analysis:
            return "Trop peu d'informations pour personnaliser : scanner le site ou qualifier l'entreprise d'abord."
    return None


COLD_SYSTEM = """Tu écris des emails de prospection B2B à froid, en texte brut, qui doivent arriver en boîte de réception
et donner envie de répondre. Règles :
- 80 à 150 mots, 3 à 4 paragraphes très courts, ton humain et sobre, aucune formule marketing ;
- 1re phrase spécifique à l'entreprise (un fait réel tiré de sa description ou de son site) — jamais générique ;
- un seul besoin probable, présenté comme une hypothèse (« je me demandais si… »), jamais comme un fait ;
- 1 ou 2 services ou réalisations pertinents, uniquement tirés du PROFIL ; une réalisation est décrite EXACTEMENT comme
  dans le profil (champ « realisation » / « description »), sans changer sa nature ; clients non citables : par secteur seulement ;
  si aucune réalisation ne correspond vraiment, cite plutôt un service ou un produit KORTEX ;
- appel à l'action : une question simple proposant 15 à 20 minutes d'échange ;
- AUCUN lien, AUCUNE pièce jointe mentionnée, pas de point d'exclamation, pas de majuscules d'insistance, pas de mots
  « gratuit », « offre », « promotion », « garanti », « urgent », « sans engagement » ;
- objet : 3 à 7 mots, naturel, sans majuscules d'insistance ni ponctuation commerciale, idéalement avec le nom de l'entreprise ;
- n'invente rien sur l'entreprise ni sur l'expéditeur ; pas de signature (ajoutée automatiquement)."""


def generate_cold_email(profile: Profile, company: Company | None, opp: Opportunity | None, language: str, instructions: str) -> dict:
    target = {}
    if company:
        target["entreprise"] = {"nom": company.name, "secteur": company.sector, "ville": company.city, "pays": company.country,
                                "site": company.website, "description": (company.description or "")[:3500],
                                "analyse": {k: (company.analysis or {}).get(k) for k in ("matched", "approach", "summary")}}
    if opp:
        target["opportunite"] = {"intitule": opp.title, "entreprise": opp.company_name, "description": (opp.description or "")[:4000]}
    role = ("candidature spontanée / réponse à l'offre de Shalom Tehe (ingénieur backend & IA)" if profile.key == "shalom"
            else "proposition de collaboration de KORTEX DIGITAL")
    user = f"""PROFIL EXPÉDITEUR (source de vérité) :\n{json.dumps(profile.data, ensure_ascii=False)}\n\nCIBLE :\n{json.dumps(target, ensure_ascii=False)}
Type : {role}. Langue : {'anglais' if language == 'en' else 'français'}.{(' Consignes : ' + instructions) if instructions else ''}
Réponds en JSON : {{"subject": str, "body": "texte sans signature"}}"""
    data = llm.chat_json(COLD_SYSTEM, user, max_tokens=1200)
    return {"subject": str(data.get("subject", "")).strip(), "body": str(data.get("body", "")).strip()}


def signature(profile: Profile, language: str) -> str:
    return profile.data.get("signature_en" if language == "en" else "signature", profile.display_name)


def footer(language: str, recipient: str) -> str:
    url = unsubscribe_url(recipient)
    if language == "en":
        return f"\n\n--\nIf you would rather not hear from us again, reply \"stop\" or use this link: {url}"
    return f"\n\n--\nSi vous préférez ne plus recevoir de message de notre part, répondez « stop » ou utilisez ce lien : {url}"


# ---------- SMTP ----------


class MailNotConfigured(RuntimeError):
    pass


def build_message(to: str, subject: str, body: str, language: str) -> EmailMessage:
    s = get_settings()
    msg = EmailMessage()
    msg["From"] = f"{s.sender_name} <{s.sender_email}>"
    msg["To"] = to
    msg["Reply-To"] = s.sender_email
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=s.sender_email.split("@")[1])
    api_unsub = f"{s.public_url.rstrip('/')}/api/public/unsubscribe/{unsubscribe_token(to)}"
    msg["List-Unsubscribe"] = f"<mailto:{s.sender_email}?subject=unsubscribe>, <{api_unsub}>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg.set_content(body + footer(language, to), charset="utf-8")
    return msg


def smtp_send(msg: EmailMessage, attachments: list[tuple[str, bytes]] | None = None) -> str:
    s = get_settings()
    if not s.mail_configured:
        raise MailNotConfigured("MAIL_USER / MAIL_PASSWORD absents : envoi par lots désactivé.")
    for filename, data in attachments or []:
        msg.add_attachment(data, maintype="application", subtype="octet-stream", filename=filename)
    with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, context=ssl.create_default_context(), timeout=60) as smtp:
        smtp.login(s.mail_user, s.mail_password)
        smtp.send_message(msg)
    return msg["Message-ID"]


def smtp_check() -> dict:
    s = get_settings()
    if not s.mail_configured:
        return {"ok": False, "message": "MAIL_USER / MAIL_PASSWORD non renseignés."}
    try:
        with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, context=ssl.create_default_context(), timeout=30) as smtp:
            smtp.login(s.mail_user, s.mail_password)
        with imaplib.IMAP4_SSL(s.imap_host, s.imap_port, timeout=30) as imap:
            imap.login(s.mail_user, s.mail_password)
        return {"ok": True, "message": f"Connexion SMTP ({s.smtp_host}) et IMAP ({s.imap_host}) réussie."}
    except Exception as e:
        return {"ok": False, "message": f"{type(e).__name__}: {e}"}


# ---------- File d'envoi (appelée chaque minute par le worker) ----------


def _log(db, type_, summary, a: Application):
    db.add(Activity(type=type_, summary=summary, company_id=a.company_id, opportunity_id=a.opportunity_id, application_id=a.id))


def tick(db: Session) -> dict:
    """Envoie AU PLUS un email (le prochain du lot validé le plus ancien) si toutes les conditions sont réunies."""
    s = get_settings()
    if not s.mail_configured:
        return {"sent": 0, "reason": "mail non configuré"}
    if not in_send_window():
        return {"sent": 0, "reason": "hors fenêtre d'envoi"}
    limit, _ = daily_limit(db)
    if sent_today(db) >= limit:
        return {"sent": 0, "reason": f"plafond du jour atteint ({limit})"}
    camp = (db.query(Campaign).filter(Campaign.status == "sending", (Campaign.next_send_at.is_(None)) | (Campaign.next_send_at <= now()))
            .order_by(Campaign.approved_at).first())
    if not camp:
        return {"sent": 0, "reason": "aucun lot prêt"}
    item = db.query(Application).filter_by(campaign_id=camp.id, status="approuvee").order_by(Application.id).first()
    if not item:
        camp.status = "done"
        db.commit()
        return {"sent": 0, "reason": "lot terminé"}
    company = db.get(Company, item.company_id) if item.company_id else None
    reason = eligibility(db, company, item.recipient)
    if reason:
        item.status, item.error = "ignoree", reason
        db.commit()
        return {"sent": 0, "reason": f"ignoré : {reason}"}
    msg = build_message(item.recipient, item.subject, item.body, camp.language)
    attachments = []
    for doc_id in camp.attachment_ids or []:
        d = db.get(Document, doc_id)
        if d:
            attachments.append((d.filename, open(d.stored_path, "rb").read()))
    try:
        item.message_id = smtp_send(msg, attachments)
    except Exception as e:
        item.status, item.error = "echec", f"{type(e).__name__}: {e}"[:1000]
        fails = db.query(Application).filter_by(campaign_id=camp.id, status="echec").count()
        if fails >= 3:
            camp.status, camp.paused_reason = "paused", f"3 échecs d'envoi — dernier : {item.error}"
        db.commit()
        return {"sent": 0, "reason": item.error}
    item.status, item.sent_at = "envoyee", now()
    _log(db, "email_sent", f"Envoyé (lot « {camp.name} ») à {item.recipient} : {item.subject}", item)
    for model, id_ in ((Opportunity, item.opportunity_id), (Company, item.company_id)):
        obj = db.get(model, id_) if id_ else None
        if obj:
            obj.status = "envoyee_manuellement"
            obj.next_action, obj.next_action_date = "Relancer si pas de réponse", now() + timedelta(days=7)
    camp.next_send_at = now() + timedelta(seconds=random.randint(s.campaign_min_interval_s, s.campaign_max_interval_s))
    db.commit()
    return {"sent": 1, "to": item.recipient}


# ---------- IMAP : réponses et rebonds ----------

BOUNCE_FROM = ("mailer-daemon", "postmaster", "mail delivery")
BOUNCE_SUBJECT = ("undeliver", "delivery status", "returned mail", "non remis", "échec de la remise", "delivery failure", "failure notice")
STOP_WORDS = ("stop", "désinscri", "desinscri", "unsubscribe", "ne plus recevoir", "remove me", "pas intéressé", "not interested")


def _text_of(msg) -> str:
    parts = []
    for part in msg.walk():
        if part.get_content_type() in ("text/plain", "message/delivery-status") or part.get_content_type().startswith("text/rfc822"):
            try:
                parts.append(part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace"))
            except Exception:
                pass
    return "\n".join(parts)[:20000]


def scan_inbox(db: Session, days: int = 14) -> dict:
    s = get_settings()
    if not s.mail_configured:
        return {"replies": 0, "bounces": 0, "reason": "mail non configuré"}
    sent = db.query(Application).filter(Application.campaign_id.isnot(None), Application.status == "envoyee").all()
    by_email = {a.recipient.lower(): a for a in sent}
    by_msgid = {a.message_id: a for a in sent if a.message_id}
    replies = bounces = 0
    since = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
    with imaplib.IMAP4_SSL(s.imap_host, s.imap_port, timeout=60) as imap:
        imap.login(s.mail_user, s.mail_password)
        imap.select("INBOX", readonly=True)  # lecture seule : rien n'est marqué comme lu
        _, ids = imap.search(None, f'(SINCE "{since}")')
        for num in ids[0].split()[-500:]:
            _, data = imap.fetch(num, "(BODY.PEEK[])")
            msg = email.message_from_bytes(data[0][1])
            mid = (msg.get("Message-ID") or "").strip()
            if not mid or db.query(InboxSeen).filter_by(message_id=mid).first():
                continue
            frm = parseaddr(msg.get("From", ""))[1].lower()
            subject = str(make_header(decode_header(msg.get("Subject", ""))))
            text = _text_of(msg)
            kind = "other"
            if any(b in frm for b in BOUNCE_FROM) or any(b in subject.lower() for b in BOUNCE_SUBJECT):
                target = next((a for e, a in by_email.items() if e in text.lower()), None)
                if target and target.delivery != "bounced":
                    target.delivery, kind = "bounced", "bounce"
                    suppress(db, target.recipient, "bounce", subject[:200])
                    _log(db, "note", f"Rebond : {target.recipient} n'existe pas ou refuse les messages", target)
                    bounces += 1
            else:
                ref = " ".join([msg.get("In-Reply-To", ""), msg.get("References", "")])
                target = next((a for m, a in by_msgid.items() if m in ref), None) or by_email.get(frm)
                if target:
                    kind = "reply"
                    if target.delivery != "replied":
                        target.delivery = "replied"
                        replies += 1
                        db.add(Activity(type="reply", summary=f"Réponse de {frm} : {subject}", company_id=target.company_id,
                                        opportunity_id=target.opportunity_id, application_id=target.id))
                        for model, id_ in ((Opportunity, target.opportunity_id), (Company, target.company_id)):
                            obj = db.get(model, id_) if id_ else None
                            if obj and obj.status in ("envoyee_manuellement", "relance_necessaire"):
                                obj.status = "reponse_recue"
                                obj.next_action, obj.next_action_date = "Répondre à l'email reçu", now()
                    first_lines = "\n".join(l for l in text.splitlines()[:8] if not l.startswith(">")).lower()
                    if any(w in first_lines for w in STOP_WORDS):
                        target.delivery = "unsubscribed"
                        suppress(db, target.recipient, "stop", subject[:200])
            db.add(InboxSeen(message_id=mid[:400], kind=kind))
        imap.logout()
    # Pause automatique d'un lot dont le taux de rebond dépasse 5 %
    for camp in db.query(Campaign).filter(Campaign.status == "sending"):
        n = db.query(Application).filter_by(campaign_id=camp.id, status="envoyee").count()
        b = db.query(Application).filter_by(campaign_id=camp.id, delivery="bounced").count()
        if n >= 10 and b / n > 0.05:
            camp.status, camp.paused_reason = "paused", f"Taux de rebond {b}/{n} > 5 % : nettoyer les adresses avant de reprendre."
    db.commit()
    return {"replies": replies, "bounces": bounces}
