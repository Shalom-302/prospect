from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..connectors.base import SearchParams
from ..connectors.registry import CONNECTORS, PLATFORMS, platform_links
from ..db import get_db
from ..models import SavedSearch, SearchRun, now
from ..services.ingest import run_company_search, run_opportunity_search
from .common import get_or_404, iso

router = APIRouter(prefix="/api/search", tags=["recherche"])

GEO = {
    "cote_ivoire": {"label": "Côte d'Ivoire", "places": ["Abidjan", "Cocody", "Plateau", "Marcory", "Zone industrielle de Yopougon", "Treichville", "Bingerville", "Bouaké", "San Pedro", "Yamoussoukro", "Korhogo", "Daloa"]},
    "afrique": {"label": "Afrique", "places": ["Sénégal", "Ghana", "Nigeria", "Kenya", "Rwanda", "Afrique du Sud", "Maroc", "Bénin", "Togo", "Cameroun", "Burkina Faso", "Mali", "Gabon"]},
    "international": {"label": "International", "places": ["Arabie saoudite", "Émirats arabes unis", "Qatar", "France", "Allemagne", "Royaume-Uni", "Canada", "États-Unis", "Suisse", "Belgique", "Luxembourg", "Pays-Bas"]},
}

COMPANY_SOURCES = [
    {"name": "Annuaire IDU / CEPICI", "url": "https://www.cepici.gouv.ci", "note": "Consultation manuelle ; pas d'API publique connue."},
    {"name": "CGECI (membres)", "url": "https://www.cgeci.com", "domain": "cgeci.com"},
    {"name": "FIPME", "url": "https://www.fipme.ci", "domain": "fipme.ci"},
    {"name": "CCI Côte d'Ivoire", "url": "https://www.cci.ci", "domain": "cci.ci"},
    {"name": "Go Africa Online (annuaire)", "url": "https://www.goafricaonline.com/ci", "domain": "goafricaonline.com"},
]


def _run_out(r: SearchRun) -> dict:
    return {"id": r.id, "target": r.target, "connector": r.connector, "params": r.params, "status": r.status, "found": r.found,
            "created": r.created, "duplicates": r.duplicates, "message": r.message, "started_at": iso(r.started_at), "finished_at": iso(r.finished_at)}


@router.get("/meta")
def meta():
    return {
        "connectors": [{"name": c.name, "label": c.label, "available": c.available(), "requires": c.requires} for c in CONNECTORS.values()],
        "geo": GEO, "company_sources": COMPANY_SOURCES,
    }


@router.get("/platforms")
def platforms(q: str = "python fastapi", location: str = ""):
    return platform_links(q, location)


class SearchIn(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    country: str = ""
    city: str = ""
    sector: str = ""
    contract_type: str = ""
    remote: bool | None = None
    language: str = ""
    min_salary: float | None = None
    profile_key: str = "shalom"
    kind: str = "job"
    limit: int = 30
    include_domains: list[str] = Field(default_factory=list)
    connectors: list[str] = Field(default_factory=lambda: ["remotive", "remoteok", "weworkremotely"])


def _params(body: SearchIn) -> SearchParams:
    return SearchParams(**body.model_dump(exclude={"connectors"}))


@router.post("/opportunities")
def search_opportunities(body: SearchIn, db: Session = Depends(get_db)):
    if not body.connectors:
        raise HTTPException(422, "Choisir au moins une source.")
    runs = run_opportunity_search(db, body.connectors, _params(body))
    return {"runs": [_run_out(r) for r in runs]}


@router.post("/companies")
def search_companies(body: SearchIn, db: Session = Depends(get_db)):
    body.profile_key = "kortex"
    return {"run": _run_out(run_company_search(db, _params(body)))}


@router.get("/runs")
def runs(limit: int = 30, db: Session = Depends(get_db)):
    return [_run_out(r) for r in db.query(SearchRun).order_by(SearchRun.started_at.desc()).limit(limit)]


# ---------- Recherches enregistrées (exécution manuelle ou chaque matin) ----------

class SavedIn(BaseModel):
    name: str
    target: str = "opportunities"
    params: SearchIn
    scheduled: bool = False


def _saved_out(s: SavedSearch) -> dict:
    return {"id": s.id, "name": s.name, "target": s.target, "params": s.params, "scheduled": s.scheduled,
            "last_run_at": iso(s.last_run_at), "created_at": iso(s.created_at)}


@router.get("/saved")
def list_saved(db: Session = Depends(get_db)):
    return [_saved_out(s) for s in db.query(SavedSearch).order_by(SavedSearch.created_at)]


@router.post("/saved")
def create_saved(body: SavedIn, db: Session = Depends(get_db)):
    s = SavedSearch(name=body.name, target=body.target, params=body.params.model_dump(), scheduled=body.scheduled)
    db.add(s)
    db.commit()
    return _saved_out(s)


@router.patch("/saved/{saved_id}")
def patch_saved(saved_id: int, body: dict, db: Session = Depends(get_db)):
    s = get_or_404(db, SavedSearch, saved_id)
    for k in ("name", "scheduled", "params"):
        if k in body:
            setattr(s, k, body[k])
    db.commit()
    return _saved_out(s)


@router.delete("/saved/{saved_id}")
def delete_saved(saved_id: int, db: Session = Depends(get_db)):
    db.delete(get_or_404(db, SavedSearch, saved_id))
    db.commit()
    return {"ok": True}


def execute_saved(db: Session, s: SavedSearch) -> list[dict]:
    body = SearchIn(**s.params)
    if s.target == "companies":
        out = [_run_out(run_company_search(db, _params(body)))]
    else:
        out = [_run_out(r) for r in run_opportunity_search(db, body.connectors, _params(body))]
    s.last_run_at = now()
    db.commit()
    return out


@router.post("/saved/{saved_id}/run")
def run_saved(saved_id: int, db: Session = Depends(get_db)):
    return {"runs": execute_saved(db, get_or_404(db, SavedSearch, saved_id))}


__all__ = ["router", "execute_saved", "PLATFORMS"]
