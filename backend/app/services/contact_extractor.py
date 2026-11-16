"""Extraction des coordonnées PUBLIQUES publiées sur le site d'une entreprise.

- Aucune adresse n'est devinée : seules les adresses présentes dans les pages sont retenues.
- Confiance « verified » = publiée sur le site de l'entreprise ET domaine de l'email identique au site.
- Sinon « found_unverified » (ex. adresse gmail affichée, ou domaine différent).
"""
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .polite_http import FetchBlocked, fetch
from .textutil import domain_of

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,24}")
PHONE_RE = re.compile(r"(?:\+|00)\d{1,3}[\s.\-]?\(?\d{1,4}\)?(?:[\s.\-]?\d{2,4}){2,5}")
OBFUSCATED_AT = re.compile(r"\s*[\[\(\{]\s*(?:at|arobase|@)\s*[\]\)\}]\s*", re.I)
OBFUSCATED_DOT = re.compile(r"\s*[\[\(\{]\s*(?:dot|point)\s*[\]\)\}]\s*", re.I)

IGNORED_EMAIL_PARTS = ("example.", "sentry", "wixpress", "domain.com", "email.com", "yourdomain", "votre", "@2x", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")

PAGE_HINTS = {
    "contact": ("contact", "contactez", "nous-joindre", "joindre", "contact-us", "get-in-touch"),
    "careers": ("carriere", "carrière", "careers", "career", "recrutement", "emplois", "jobs", "join-us", "rejoignez", "nous-rejoindre", "talent"),
    "about": ("a-propos", "about", "qui-sommes-nous", "entreprise", "company"),
    "partners": ("partenaire", "partner", "fournisseur", "supplier", "vendor", "achats", "procurement"),
}

LABEL_RULES = [
    ("rh", ("rh", "hr", "recrut", "career", "carriere", "jobs", "job", "emploi", "talent", "candidature", "drh")),
    ("it", ("it", "dsi", "informatique", "tech", "digital", "si", "support", "webmaster")),
    ("partenariat", ("partenariat", "partner", "partners", "business", "commercial", "sales", "achat", "achats", "procurement", "fournisseur")),
    ("direction", ("direction", "dg", "ceo", "dga", "secretariat", "secretariat.dg", "president")),
]


@dataclass
class FoundContact:
    kind: str
    value: str
    label: str = "general"
    confidence: str = "found_unverified"
    source_url: str = ""


@dataclass
class SiteScan:
    website: str
    title: str = ""
    description: str = ""
    pages_visited: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    contacts: list[FoundContact] = field(default_factory=list)
    text_sample: str = ""


def label_for_email(email: str) -> str:
    local = email.split("@")[0].lower()
    tokens = re.split(r"[._\-+]", local)
    for label, keys in LABEL_RULES:
        if any(t in keys for t in tokens) or any(local.startswith(k) for k in keys if len(k) > 3):
            return label
    return "general"


def _clean_email(e: str) -> str | None:
    e = e.strip().strip(".").lower()
    if any(p in e for p in IGNORED_EMAIL_PARTS) or len(e) > 120:
        return None
    return e


def _emails_in(soup: BeautifulSoup, text: str) -> set[str]:
    found: set[str] = set()
    for a in soup.select('a[href^="mailto:"]'):
        addr = a["href"][7:].split("?")[0]
        if EMAIL_RE.fullmatch(addr.strip()):
            found.add(addr)
    deob = OBFUSCATED_DOT.sub(".", OBFUSCATED_AT.sub("@", text))
    found.update(EMAIL_RE.findall(deob))
    return {c for e in found if (c := _clean_email(e))}


def _phones_in(soup: BeautifulSoup, text: str) -> set[str]:
    phones = {re.sub(r"[^\d+]", "", a["href"][4:]) for a in soup.select('a[href^="tel:"]')}
    for m in PHONE_RE.findall(text):
        digits = re.sub(r"\D", "", m)
        if 9 <= len(digits) <= 15:
            phones.add(re.sub(r"\s+", " ", re.sub(r"[()]", " ", m)).strip())
    return {p for p in phones if len(re.sub(r"\D", "", p)) >= 9}


def _candidate_pages(soup: BeautifulSoup, base_url: str, site_domain: str) -> dict[str, str]:
    pages: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("#")[0]
        if domain_of(href) != site_domain or href.rstrip("/") == base_url.rstrip("/"):
            continue
        hay = (urlparse(href).path + " " + a.get_text(" ")).lower()
        for kind, hints in PAGE_HINTS.items():
            if kind not in pages and any(h in hay for h in hints):
                pages[kind] = href
    return pages


def scan_website(website: str, max_pages: int = 5) -> SiteScan:
    if "://" not in website:
        website = "https://" + website
    site_domain = domain_of(website) or ""
    scan = SiteScan(website=website)
    seen_values: set[tuple[str, str]] = set()

    def add(kind: str, value: str, source: str, label: str = "general", same_domain: bool = True):
        if (kind, value) in seen_values:
            return
        seen_values.add((kind, value))
        scan.contacts.append(FoundContact(kind, value, label, "verified" if same_domain else "found_unverified", source))

    def process(url: str, page_kind: str | None) -> BeautifulSoup | None:
        try:
            r = fetch(url)
        except FetchBlocked as e:
            scan.blocked.append(str(e))
            return None
        except Exception as e:  # réseau, SSL, 404…
            scan.blocked.append(f"{url} : {type(e).__name__}")
            return None
        if "html" not in r.headers.get("content-type", "html"):
            return None
        scan.pages_visited.append(str(r.url))
        soup = BeautifulSoup(r.text, "lxml")
        text = soup.get_text(" ")
        for email in _emails_in(soup, text):
            ed = email.split("@")[1]
            same = ed == site_domain or ed.endswith("." + site_domain) or site_domain.endswith("." + ed)
            label = label_for_email(email)
            if label == "general" and page_kind == "careers":
                label = "rh"
            add("email", email, str(r.url), label, same)
        for phone in _phones_in(soup, text):
            add("phone", phone, str(r.url))
        for a in soup.find_all("a", href=True):
            h = a["href"]
            if "linkedin.com/company/" in h:
                add("linkedin", h.split("?")[0], str(r.url))
        if page_kind == "contact" and soup.find("form"):
            add("contact_form", str(r.url), str(r.url))
        if page_kind == "careers":
            add("careers_page", str(r.url), str(r.url), "rh")
        return soup

    home = process(website, None)
    if home is None:
        return scan
    scan.title = (home.title.string or "").strip() if home.title and home.title.string else ""
    meta = home.find("meta", attrs={"name": "description"}) or home.find("meta", attrs={"property": "og:description"})
    scan.description = (meta.get("content") or "").strip() if meta else ""
    scan.text_sample = re.sub(r"\s+", " ", home.get_text(" "))[:4000]

    for kind, url in list(_candidate_pages(home, website, site_domain).items())[: max_pages - 1]:
        process(url, kind)
    return scan
