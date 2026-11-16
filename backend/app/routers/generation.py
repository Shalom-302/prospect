import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Company, GeneratedDocument, Opportunity, Profile
from ..services import llm
from ..services.exporter import to_docx, to_pdf
from ..services.generator import generate
from .common import change_status, gen_out, get_or_404, log

router = APIRouter(prefix="/api/generated", tags=["génération"])


class GenerateIn(BaseModel):
    doc_type: str  # cover_letter | b2b_proposal | email
    profile_key: str | None = None
    opportunity_id: int | None = None
    company_id: int | None = None
    language: str = "fr"
    recipient_name: str = ""
    instructions: str = ""
    letter_id: int | None = None  # pour un email : lettre/proposition à résumer


@router.post("")
def create(body: GenerateIn, db: Session = Depends(get_db)):
    if not (body.opportunity_id or body.company_id):
        raise HTTPException(422, "Choisir une opportunité ou une entreprise : aucune lettre générique.")
    opp = get_or_404(db, Opportunity, body.opportunity_id) if body.opportunity_id else None
    company = get_or_404(db, Company, body.company_id) if body.company_id else (opp.company if opp else None)
    key = body.profile_key or ("kortex" if body.doc_type == "b2b_proposal" else (opp.profile_key if opp else "kortex"))
    profile = db.query(Profile).filter_by(key=key).one_or_none()
    if profile is None:
        raise HTTPException(404, f"Profil {key} introuvable")
    letter_text = ""
    if body.letter_id:
        letter_text = get_or_404(db, GeneratedDocument, body.letter_id).content
    try:
        out = generate(body.doc_type, profile, opp, company, body.language, body.recipient_name, body.instructions, letter_text)
    except llm.LLMNotConfigured as e:
        raise HTTPException(503, f"{e}. La génération personnalisée nécessite un LLM.")
    except Exception as e:
        raise HTTPException(502, f"Échec de la génération : {type(e).__name__}: {e}")
    g = GeneratedDocument(doc_type=body.doc_type, profile_key=key, language=body.language, opportunity_id=opp.id if opp else None,
                          company_id=company.id if company else None, subject=out["subject"], content=out["content"],
                          model_used=llm.model_name())
    db.add(g)
    labels = {"cover_letter": "Lettre de motivation", "b2b_proposal": "Proposition commerciale", "email": "Email"}
    log(db, "generated", f"{labels.get(body.doc_type, body.doc_type)} générée ({body.language})",
        company_id=g.company_id, opportunity_id=g.opportunity_id)
    target = opp or company
    if target and target.status in ("decouverte", "a_qualifier", "pertinent", "lettre_a_generer"):
        change_status(db, target, "pret_a_postuler")
    db.commit()
    return gen_out(g)


@router.get("")
def list_generated(opportunity_id: int | None = None, company_id: int | None = None, doc_type: str | None = None,
                   limit: int = 100, db: Session = Depends(get_db)):
    q = db.query(GeneratedDocument)
    if opportunity_id:
        q = q.filter_by(opportunity_id=opportunity_id)
    if company_id:
        q = q.filter_by(company_id=company_id)
    if doc_type:
        q = q.filter(GeneratedDocument.doc_type.in_(doc_type.split(",")))
    return [gen_out(g) for g in q.order_by(GeneratedDocument.created_at.desc()).limit(limit)]


@router.get("/{gen_id}")
def get_generated(gen_id: int, db: Session = Depends(get_db)):
    return gen_out(get_or_404(db, GeneratedDocument, gen_id))


class GenPatch(BaseModel):
    subject: str | None = None
    content: str | None = None


@router.put("/{gen_id}")
def update_generated(gen_id: int, body: GenPatch, db: Session = Depends(get_db)):
    g = get_or_404(db, GeneratedDocument, gen_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(g, k, v)
    g.edited = True
    db.commit()
    return gen_out(g)


@router.delete("/{gen_id}")
def delete_generated(gen_id: int, db: Session = Depends(get_db)):
    db.delete(get_or_404(db, GeneratedDocument, gen_id))
    db.commit()
    return {"ok": True}


def recipient_block(db: Session, g: GeneratedDocument) -> str:
    company = db.get(Company, g.company_id) if g.company_id else None
    opp = db.get(Opportunity, g.opportunity_id) if g.opportunity_id else None
    name = company.name if company else (opp.company_name if opp else "")
    if not name:
        return ""
    lines = [name]
    if company and company.address:
        lines.append(company.address)
    elif company and (company.city or company.country):
        lines.append(", ".join(x for x in [company.city, company.country] if x))
    return "\n".join(lines)


def export_bytes(db: Session, g: GeneratedDocument, fmt: str) -> tuple[bytes, str, str]:
    profile = db.query(Profile).filter_by(key=g.profile_key).one()
    rcpt = recipient_block(db, g)
    base = {"cover_letter": "Lettre_motivation", "b2b_proposal": "Proposition_KORTEX_DIGITAL", "email": "Email"}.get(g.doc_type, "Document")
    who = re.sub(r"[^A-Za-z0-9]+", "_", rcpt.splitlines()[0] if rcpt else "")[:40].strip("_")
    filename = f"{base}{'_' + who if who else ''}_{'Shalom_Tehe' if g.profile_key == 'shalom' else 'KORTEX'}.{fmt}"
    if fmt == "pdf":
        return to_pdf(g, profile, rcpt), "application/pdf", filename
    if fmt == "docx":
        return to_docx(g, profile, rcpt), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename
    raise HTTPException(422, "Format : pdf ou docx")


@router.get("/{gen_id}/export")
def export(gen_id: int, format: str = "pdf", db: Session = Depends(get_db)):
    data, mime, filename = export_bytes(db, get_or_404(db, GeneratedDocument, gen_id), format)
    return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
