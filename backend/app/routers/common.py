from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import PIPELINE_LABELS, Activity, Application, Company, Contact, GeneratedDocument, Opportunity, Profile


def get_or_404(db: Session, model, id_: int):
    obj = db.get(model, id_)
    if obj is None:
        raise HTTPException(404, f"{model.__name__} {id_} introuvable")
    return obj


def profiles_map(db: Session) -> dict[str, Profile]:
    return {p.key: p for p in db.query(Profile).all()}


def log(db: Session, type_: str, summary: str, company_id=None, opportunity_id=None, application_id=None, when: datetime | None = None):
    a = Activity(type=type_, summary=summary, company_id=company_id, opportunity_id=opportunity_id, application_id=application_id)
    if when:
        a.occurred_at = when
    db.add(a)


def change_status(db: Session, obj, new_status: str):
    if new_status not in PIPELINE_LABELS:
        raise HTTPException(422, f"Statut inconnu : {new_status}")
    if obj.status != new_status:
        old = PIPELINE_LABELS.get(obj.status, obj.status)
        kw = {"company_id": obj.id} if isinstance(obj, Company) else {"opportunity_id": obj.id, "company_id": obj.company_id}
        log(db, "status_change", f"{old} → {PIPELINE_LABELS[new_status]}", **kw)
        obj.status = new_status


def iso(d):
    return d.isoformat() if d else None


def contact_out(c: Contact) -> dict:
    return {"id": c.id, "kind": c.kind, "value": c.value, "label": c.label, "person_name": c.person_name,
            "confidence": c.confidence, "source_url": c.source_url, "found_at": iso(c.found_at)}


def opp_out(o: Opportunity, full: bool = False) -> dict:
    d = {"id": o.id, "kind": o.kind, "profile_key": o.profile_key, "title": o.title, "company_name": o.company_name,
         "company_id": o.company_id, "contract_type": o.contract_type, "salary": o.salary, "currency": o.currency,
         "location": o.location, "remote": o.remote, "language": o.language, "published_at": iso(o.published_at),
         "deadline": iso(o.deadline), "apply_url": o.apply_url, "source": o.source, "source_url": o.source_url,
         "needs_verification": o.needs_verification, "status": o.status, "score": o.score,
         "score_method": (o.analysis or {}).get("method"), "skills": o.skills, "next_action": o.next_action,
         "next_action_date": iso(o.next_action_date), "collected_at": iso(o.collected_at), "last_checked_at": iso(o.last_checked_at)}
    if full:
        d.update({"description": o.description, "analysis": o.analysis, "notes": o.notes})
    else:
        d["excerpt"] = (o.description or "")[:280]
    return d


def company_out(c: Company, full: bool = False) -> dict:
    d = {"id": c.id, "name": c.name, "domain": c.domain, "website": c.website, "sector": c.sector, "country": c.country,
         "city": c.city, "status": c.status, "score": c.score, "score_method": (c.analysis or {}).get("method"),
         "profile_key": c.profile_key, "source_url": c.source_url, "source_name": c.source_name,
         "collected_at": iso(c.collected_at), "verified_at": iso(c.verified_at), "next_action": c.next_action,
         "next_action_date": iso(c.next_action_date),
         "emails": sum(1 for x in c.contacts if x.kind == "email"),
         "verified_emails": sum(1 for x in c.contacts if x.kind == "email" and x.confidence == "verified")}
    if full:
        d.update({"description": c.description, "address": c.address, "notes": c.notes, "analysis": c.analysis,
                  "contacts": [contact_out(x) for x in c.contacts]})
    return d


def gen_out(g: GeneratedDocument) -> dict:
    return {"id": g.id, "doc_type": g.doc_type, "profile_key": g.profile_key, "language": g.language,
            "opportunity_id": g.opportunity_id, "company_id": g.company_id, "subject": g.subject, "content": g.content,
            "model_used": g.model_used, "edited": g.edited, "created_at": iso(g.created_at), "updated_at": iso(g.updated_at)}


def app_out(a: Application) -> dict:
    return {"id": a.id, "profile_key": a.profile_key, "opportunity_id": a.opportunity_id, "company_id": a.company_id,
            "channel": a.channel, "recipient": a.recipient, "cc": a.cc, "subject": a.subject, "body": a.body,
            "letter_id": a.letter_id, "attachment_ids": a.attachment_ids, "attach_letter_format": a.attach_letter_format,
            "status": a.status, "draft_provider": a.draft_provider, "draft_ref": a.draft_ref, "sent_at": iso(a.sent_at),
            "created_at": iso(a.created_at), "updated_at": iso(a.updated_at)}


def activity_out(a: Activity) -> dict:
    return {"id": a.id, "type": a.type, "summary": a.summary, "company_id": a.company_id, "opportunity_id": a.opportunity_id,
            "application_id": a.application_id, "occurred_at": iso(a.occurred_at)}
