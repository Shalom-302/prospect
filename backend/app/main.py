import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import auth
from .config import get_settings
from .db import SessionLocal
from .models import Profile
from .profiles_seed import SEED
from .routers import applications, campaigns, companies, core, documents, generation, opportunities, search

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def seed_profiles() -> None:
    with SessionLocal() as db:
        for p in SEED:
            if not db.query(Profile).filter_by(key=p["key"]).first():
                db.add(Profile(**p))
        db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_settings().check_production()  # refuse de démarrer en prod sans secrets ni numéros autorisés
    seed_profiles()
    yield


app = FastAPI(title="KORTEX Prospect", version="1.1.0", lifespan=lifespan,
              description="Recherche, qualification, candidatures et prospection par lots validés — Shalom Tehe & KORTEX DIGITAL.")
app.middleware("http")(auth.auth_middleware)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in get_settings().frontend_origin.split(",")],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"], expose_headers=["Content-Disposition"])

for r in (auth.router, core.router, opportunities.router, companies.router, companies.contacts_router, search.router,
          generation.router, documents.router, applications.router, campaigns.router, campaigns.outreach_router,
          campaigns.public_router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"ok": True}
