import mimetypes

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Document
from ..services.documents import CATEGORIES, delete_file, extract_text, store_file
from .common import get_or_404, iso

router = APIRouter(prefix="/api/documents", tags=["documents"])
MAX_SIZE = 25 * 1024 * 1024


def doc_out(d: Document, text: bool = False) -> dict:
    out = {"id": d.id, "profile_key": d.profile_key, "category": d.category, "category_label": CATEGORIES.get(d.category, d.category),
           "language": d.language, "title": d.title, "filename": d.filename, "mime_type": d.mime_type, "size_bytes": d.size_bytes,
           "has_text": bool(d.extracted_text), "notes": d.notes, "created_at": iso(d.created_at)}
    if text:
        out["extracted_text"] = d.extracted_text
    return out


@router.get("/categories")
def categories():
    return CATEGORIES


@router.get("")
def list_documents(profile_key: str | None = None, category: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Document)
    if profile_key:
        q = q.filter((Document.profile_key == profile_key) | (Document.profile_key.is_(None)))
    if category:
        q = q.filter(Document.category.in_(category.split(",")))
    return [doc_out(d) for d in q.order_by(Document.category, Document.created_at.desc())]


@router.post("")
async def upload(file: UploadFile = File(...), category: str = Form(...), language: str = Form("fr"),
                 title: str = Form(""), profile_key: str = Form(""), notes: str = Form(""), db: Session = Depends(get_db)):
    if category not in CATEGORIES:
        raise HTTPException(422, f"Catégorie inconnue. Choix : {', '.join(CATEGORIES)}")
    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(413, "Fichier trop volumineux (25 Mo max).")
    path = store_file(data, file.filename or "document")
    d = Document(profile_key=profile_key or None, category=category, language=language, title=title or file.filename or "Document",
                 filename=file.filename or path.name, stored_path=str(path),
                 mime_type=file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream",
                 size_bytes=len(data), extracted_text=extract_text(data, file.filename or ""), notes=notes)
    db.add(d)
    db.commit()
    return doc_out(d)


@router.get("/{doc_id}")
def get_document(doc_id: int, db: Session = Depends(get_db)):
    return doc_out(get_or_404(db, Document, doc_id), text=True)


@router.get("/{doc_id}/download")
def download(doc_id: int, db: Session = Depends(get_db)):
    d = get_or_404(db, Document, doc_id)
    return FileResponse(d.stored_path, media_type=d.mime_type, filename=d.filename)


class DocPatch(BaseModel):
    title: str | None = None
    category: str | None = None
    language: str | None = None
    profile_key: str | None = None
    notes: str | None = None


@router.patch("/{doc_id}")
def patch_document(doc_id: int, body: DocPatch, db: Session = Depends(get_db)):
    d = get_or_404(db, Document, doc_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(d, k, (v or None) if k == "profile_key" else v)
    db.commit()
    return doc_out(d)


@router.delete("/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    d = get_or_404(db, Document, doc_id)
    delete_file(d.stored_path)
    db.delete(d)
    db.commit()
    return {"ok": True}
