"""Commandes utilitaires.

  python -m app.cli import-docs "<dossier kortex-docx>"   importe les documents de référence dans la bibliothèque
"""
import sys
from pathlib import Path

from .db import SessionLocal
from .models import Document
from .services.documents import copy_into_storage, extract_text

# (chemin relatif, catégorie, langue, profil, titre, note)
INITIAL = [
    ("Shalom_Tehe_FR(1).pdf", "cv_fr", "fr", "shalom", "CV Shalom Tehe (FR)", "Source de vérité du profil A"),
    ("KORTEX_DIGITAL_INSTITUTIONAL_PACK/05_CEO_EXECUTIVE_PROFILE/KORTEX_05_CEO_CV_EN.docx", "cv_en", "en", "shalom", "CV Shalom Tehe (EN)",
     "À RELIRE : rédigé sans le CV source — vérifier la conformité avec le CV FR avant envoi"),
    ("KORTEX_KIT_PME/A_ENVOYER_PDF_JPG/KORTEX_Plaquette.pdf", "plaquette", "fr", "kortex", "Plaquette KORTEX DIGITAL (PME)", ""),
    ("KORTEX_DIGITAL_INSTITUTIONAL_PACK/03_CAPABILITY_STATEMENT/KORTEX_03_Capability_Statement_FR.docx", "plaquette", "fr", "kortex", "Capability Statement FR", "Pièce jointe par défaut d'un premier contact institutionnel"),
    ("KORTEX_DIGITAL_INSTITUTIONAL_PACK/03_CAPABILITY_STATEMENT/KORTEX_03_Capability_Statement_EN.docx", "plaquette", "en", "kortex", "Capability Statement EN", ""),
    ("KORTEX_DIGITAL_INSTITUTIONAL_PACK/01_CORPORATE_PROFILE/KORTEX_01_Corporate_Profile_FR.docx", "presentation", "fr", "kortex", "Corporate Profile FR", ""),
    ("KORTEX_DIGITAL_INSTITUTIONAL_PACK/02_COMPANY_PROFILE_EN/KORTEX_02_Company_Profile_EN.docx", "presentation", "en", "kortex", "Company Profile EN", ""),
    ("KORTEX_DIGITAL_INSTITUTIONAL_PACK/04_TECHNICAL_PORTFOLIO/KORTEX_04_Technical_Portfolio_FR.docx", "portfolio", "fr", None, "Portfolio technique FR", "Références clients : accord de citation requis"),
    ("KORTEX_DIGITAL_INSTITUTIONAL_PACK/04_TECHNICAL_PORTFOLIO/KORTEX_04_Technical_Portfolio_EN.docx", "portfolio", "en", None, "Technical Portfolio EN", "Client references: citation approval required"),
    ("CERTIFICAT_IDU_CI-2026-0078032 H (1)(1).pdf", "certificat", "fr", "kortex", "Certificat d'immatriculation CEPICI", "À joindre uniquement si exigé (appel d'offres, référencement)"),
]


def import_docs(folder: str) -> None:
    root = Path(folder)
    with SessionLocal() as db:
        for rel, cat, lang, prof, title, note in INITIAL:
            src = root / rel
            if not src.exists():
                print(f"  absent : {rel}")
                continue
            if db.query(Document).filter_by(title=title).first():
                print(f"  déjà importé : {title}")
                continue
            dst = copy_into_storage(src)
            data = src.read_bytes()
            mime = "application/pdf" if src.suffix == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            db.add(Document(profile_key=prof, category=cat, language=lang, title=title, filename=src.name, stored_path=str(dst),
                            mime_type=mime, size_bytes=len(data), extracted_text=extract_text(data, src.name), notes=note))
            print(f"  importé : {title}")
        db.commit()


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "import-docs":
        import_docs(sys.argv[2])
    else:
        print(__doc__)
