"""Export PDF / DOCX des lettres et propositions — sobre, noir et blanc, Times New Roman."""
import io
from datetime import date
from pathlib import Path

from docx import Document as Docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt
from fpdf import FPDF

from ..models import GeneratedDocument, Profile

FONT_CANDIDATES = [
    ("C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/timesbd.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"),
]

MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def _today(lang: str) -> str:
    d = date.today()
    return d.strftime("%B %d, %Y") if lang == "en" else f"{d.day} {MONTHS_FR[d.month - 1]} {d.year}"


def _sender_lines(profile: Profile) -> list[str]:
    d = profile.data
    if profile.key == "kortex":
        c = d.get("contact", {})
        return [d.get("legal_name", "KORTEX DIGITAL") + " " + d.get("legal_form", ""), d.get("address", ""),
                f"{c.get('email', '')} · {c.get('phone', '')}", c.get("website", ""),
                f"RCCM {d.get('rccm', '')} · IDU {d.get('idu', '')}"]
    c = d.get("contact", {})
    return [d.get("full_name", profile.display_name), d.get("location", ""), f"{c.get('email', '')} · {c.get('phone', '')}", c.get("website", "")]


def _blocks(doc: GeneratedDocument, profile: Profile, recipient: str):
    lang = doc.language
    city = "Abidjan, " if lang == "fr" else "Abidjan, "
    subject_label = "Subject: " if lang == "en" else "Objet : "
    return _sender_lines(profile), recipient, city + _today(lang), subject_label + doc.subject if doc.subject else "", doc.content


def to_docx(doc: GeneratedDocument, profile: Profile, recipient: str = "") -> bytes:
    sender, rcpt, dateline, subject, body = _blocks(doc, profile, recipient)
    d = Docx()
    sec = d.sections[0]
    sec.left_margin = sec.right_margin = Cm(2.3)
    sec.top_margin = sec.bottom_margin = Cm(2)
    style = d.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(11.5)
    for i, line in enumerate(l for l in sender if l.strip()):
        p = d.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(line)
        r.bold = i == 0
    if rcpt:
        for line in rcpt.splitlines():
            p = d.add_paragraph(line)
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            p.paragraph_format.space_after = Pt(0)
    p = d.add_paragraph(dateline)
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.paragraph_format.space_before = Pt(14)
    if subject:
        p = d.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.add_run(subject).bold = True
    for para in body.split("\n\n"):
        p = d.add_paragraph(para.strip())
        p.paragraph_format.space_after = Pt(8)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


class _PDF(FPDF):
    pass


def to_pdf(doc: GeneratedDocument, profile: Profile, recipient: str = "") -> bytes:
    sender, rcpt, dateline, subject, body = _blocks(doc, profile, recipient)
    pdf = _PDF(format="A4")
    pdf.set_margins(23, 20, 23)
    pdf.set_auto_page_break(True, 20)
    pdf.add_page()
    family = "Times"
    for reg, bold in FONT_CANDIDATES:
        if Path(reg).exists() and Path(bold).exists():
            pdf.add_font("Serif", "", reg)
            pdf.add_font("Serif", "B", bold)
            family = "Serif"
            break
    clean = (lambda s: s) if family == "Serif" else (lambda s: s.encode("latin-1", "replace").decode("latin-1"))
    lines = [l for l in sender if l.strip()]
    for i, line in enumerate(lines):
        pdf.set_font(family, "B" if i == 0 else "", 12 if i == 0 else 10)
        pdf.cell(0, 5.2, clean(line), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(family, "", 11)
    pdf.ln(6)
    for line in rcpt.splitlines():
        pdf.cell(0, 5.5, clean(line), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.cell(0, 5.5, clean(dateline), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    if subject:
        pdf.set_font(family, "B", 11)
        pdf.multi_cell(0, 5.5, clean(subject))
        pdf.ln(3)
    pdf.set_font(family, "", 11)
    for para in body.split("\n\n"):
        pdf.multi_cell(0, 5.6, clean(para.strip()), align="J" if "\n" not in para.strip() else "L")
        pdf.ln(2.5)
    return bytes(pdf.output())
