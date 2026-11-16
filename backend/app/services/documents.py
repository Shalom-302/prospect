"""Bibliothèque documentaire : stockage, extraction de texte, recommandations de pièces jointes.

Les recommandations ne sont que des suggestions : aucune pièce n'est jointe sans validation explicite.
"""
import io
import re
import uuid
from pathlib import Path

from docx import Document as Docx
from pypdf import PdfReader

from ..config import get_settings
from ..models import Company, Document, Opportunity

CATEGORIES = {
    "cv_fr": "CV français",
    "cv_en": "CV anglais",
    "portfolio": "Portfolio",
    "plaquette": "Plaquette KORTEX DIGITAL",
    "presentation": "Présentation institutionnelle",
    "certificat": "Certificat d'immatriculation",
    "administratif": "Document administratif",
    "diplome": "Certificat / diplôme",
    "reference": "Référence de projet",
    "autre": "Autre",
}


def extract_text(data: bytes, filename: str) -> str:
    name = filename.lower()
    try:
        if name.endswith(".pdf"):
            return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)[:60000]
        if name.endswith(".docx"):
            d = Docx(io.BytesIO(data))
            return "\n".join(p.text for p in d.paragraphs)[:60000]
        if name.endswith((".txt", ".md")):
            return data.decode("utf-8", "replace")[:60000]
    except Exception:  # document illisible : on garde le fichier, sans texte
        return ""
    return ""


def store_file(data: bytes, filename: str) -> Path:
    folder = get_settings().storage_dir / "documents"
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)[-120:]
    path = folder / f"{uuid.uuid4().hex[:10]}_{safe}"
    path.write_bytes(data)
    return path


def copy_into_storage(src: Path) -> Path:
    return store_file(src.read_bytes(), src.name)


TENDER_HINTS = ("appel d'offres", "appel d offres", "tender", "rfp", "référencement", "referencement", "fournisseur", "vendor", "dossier administratif", "soumission")


def recommend(docs: list[Document], profile_key: str, language: str, opp: Opportunity | None, company: Company | None) -> list[dict]:
    """Retourne les documents recommandés avec la raison. Rien n'est sélectionné automatiquement."""
    lang = language if language in ("fr", "en") else "fr"
    text = " ".join([(opp.title + " " + opp.description) if opp else "", company.description if company else ""]).lower()
    analysis = (opp.analysis if opp else None) or (company.analysis if company else None) or {}
    suggested = set(analysis.get("documents_to_attach") or [])
    recs: list[dict] = []

    def pick(category: str, reason: str, prefer_lang: bool = True):
        cands = [d for d in docs if d.category == category and (d.profile_key in (None, profile_key))]
        if prefer_lang:
            same = [d for d in cands if d.language == lang]
            cands = same or cands
        if cands:
            d = sorted(cands, key=lambda x: x.created_at, reverse=True)[0]
            recs.append({"document_id": d.id, "title": d.title, "category": category, "reason": reason})
        else:
            recs.append({"document_id": None, "title": CATEGORIES[category], "category": category, "reason": reason + " — document absent de la bibliothèque"})

    if profile_key == "shalom":
        pick("cv_en" if lang == "en" else "cv_fr", f"CV {'anglais' if lang == 'en' else 'français'} : langue de l'annonce", prefer_lang=False)
        if (opp and opp.kind == "freelance") or "portfolio" in suggested or "portfolio" in text:
            pick("portfolio", "Mission freelance / portfolio demandé")
    else:
        pick("plaquette", "Plaquette : pièce standard d'un premier contact B2B")
        if "presentation" in suggested or (company and company.score and company.score >= 70):
            pick("presentation", "Prospect prioritaire : présentation institutionnelle")
        if "certificat" in suggested or any(h in text for h in TENDER_HINTS):
            pick("certificat", "Appel d'offres / référencement fournisseur : justificatif d'immatriculation exigé")
    return recs


def delete_file(path: str) -> None:
    p = Path(path)
    if p.exists() and get_settings().storage_dir in p.resolve().parents:
        p.unlink()

