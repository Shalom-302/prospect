"""Tâches planifiées (Celery beat, heure d'Abidjan) :
- 7 h : recherches enregistrées « chaque matin » ;
- chaque minute : envoi du prochain email d'un lot VALIDÉ par l'utilisateur (au plus un, rythme et plafonds respectés) ;
- toutes les 10 minutes : lecture IMAP (lecture seule) des réponses et rebonds."""
import logging

from celery import Celery
from celery.schedules import crontab

from .config import get_settings
from .db import SessionLocal
from .models import SavedSearch

log = logging.getLogger("prospect.worker")
celery = Celery("kortex", broker=get_settings().redis_url)
celery.conf.timezone = "Africa/Abidjan"
celery.conf.beat_schedule = {
    "morning-searches": {"task": "app.worker.run_scheduled_searches", "schedule": crontab(hour=7, minute=0)},
    "campaign-tick": {"task": "app.worker.campaign_tick", "schedule": 60.0},
    "inbox-scan": {"task": "app.worker.inbox_scan", "schedule": 600.0},
}


@celery.task(name="app.worker.run_scheduled_searches")
def run_scheduled_searches() -> dict:
    from .routers.search import execute_saved

    done = {}
    with SessionLocal() as db:
        for s in db.query(SavedSearch).filter_by(scheduled=True).all():
            try:
                done[s.name] = execute_saved(db, s)
            except Exception as e:  # une recherche en échec ne bloque pas les autres
                db.rollback()
                done[s.name] = f"erreur : {e}"
    return done


@celery.task(name="app.worker.campaign_tick")
def campaign_tick() -> dict:
    from .services.outreach import tick

    with SessionLocal() as db:
        res = tick(db)
    if res.get("sent"):
        log.info("Email envoyé à %s", res.get("to"))
    return res


@celery.task(name="app.worker.inbox_scan")
def inbox_scan() -> dict:
    from .services.outreach import scan_inbox

    with SessionLocal() as db:
        try:
            return scan_inbox(db)
        except Exception as e:
            log.warning("IMAP : %s", e)
            return {"error": str(e)}
