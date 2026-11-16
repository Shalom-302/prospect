"""Modèles de données.

Principes : chaque information collectée garde sa source (URL) et sa date de collecte ;
les contacts portent un niveau de confiance explicite ; rien n'est envoyé automatiquement.
"""
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class ProfileKey(StrEnum):
    shalom = "shalom"
    kortex = "kortex"


class PipelineStatus(StrEnum):
    decouverte = "decouverte"
    a_qualifier = "a_qualifier"
    pertinent = "pertinent"
    lettre_a_generer = "lettre_a_generer"
    pret_a_postuler = "pret_a_postuler"
    envoyee_manuellement = "envoyee_manuellement"
    relance_necessaire = "relance_necessaire"
    reponse_recue = "reponse_recue"
    rdv_programme = "rdv_programme"
    entretien_realise = "entretien_realise"
    negociation = "negociation"
    gagne = "gagne"
    refuse = "refuse"
    archive = "archive"


PIPELINE_LABELS = {
    "decouverte": "Découverte",
    "a_qualifier": "À qualifier",
    "pertinent": "Pertinent",
    "lettre_a_generer": "Lettre à générer",
    "pret_a_postuler": "Prêt à postuler",
    "envoyee_manuellement": "Candidature envoyée manuellement",
    "relance_necessaire": "Relance nécessaire",
    "reponse_recue": "Réponse reçue",
    "rdv_programme": "Rendez-vous programmé",
    "entretien_realise": "Entretien réalisé",
    "negociation": "Négociation",
    "gagne": "Gagné",
    "refuse": "Refusé",
    "archive": "Archivé",
}


class ContactConfidence(StrEnum):
    verified = "verified"  # publié sur le site officiel de l'entreprise, domaine cohérent
    found_unverified = "found_unverified"  # trouvé sur une source tierce ou domaine différent
    estimated = "estimated"  # saisi/déduit manuellement — jamais présenté comme confirmé


class OpportunityKind(StrEnum):
    job = "job"
    freelance = "freelance"
    b2b = "b2b"


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(20), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))  # individual | company
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_key: Mapped[str | None] = mapped_column(String(20), nullable=True)  # None = commun
    category: Mapped[str] = mapped_column(String(40))
    language: Mapped[str] = mapped_column(String(5), default="fr")
    title: Mapped[str] = mapped_column(String(300))
    filename: Mapped[str] = mapped_column(String(300))
    stored_path: Mapped[str] = mapped_column(String(600))
    mime_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    normalized_name: Mapped[str] = mapped_column(String(300), index=True)
    domain: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sector: Mapped[str] = mapped_column(String(200), default="")
    country: Mapped[str] = mapped_column(String(100), default="")
    city: Mapped[str] = mapped_column(String(100), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(String(800), default="")
    source_name: Mapped[str] = mapped_column(String(100), default="")
    profile_key: Mapped[str] = mapped_column(String(20), default=ProfileKey.kortex)
    status: Mapped[str] = mapped_column(String(40), default=PipelineStatus.decouverte, index=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    next_action: Mapped[str] = mapped_column(String(500), default="")
    next_action_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    contacts: Mapped[list["Contact"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    opportunities: Mapped[list["Opportunity"]] = relationship(back_populates="company")


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("company_id", "kind", "value", name="uq_contact"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(30))  # email | phone | contact_form | careers_page | linkedin
    value: Mapped[str] = mapped_column(String(500))
    label: Mapped[str] = mapped_column(String(40), default="general")  # general | rh | it | direction | partenariat
    person_name: Mapped[str] = mapped_column(String(200), default="")
    confidence: Mapped[str] = mapped_column(String(30), default=ContactConfidence.found_unverified)
    source_url: Mapped[str] = mapped_column(String(800), default="")
    found_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    company: Mapped[Company] = relationship(back_populates="contacts")


class Opportunity(Base):
    __tablename__ = "opportunities"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), default=OpportunityKind.job, index=True)
    profile_key: Mapped[str] = mapped_column(String(20), default=ProfileKey.shalom)
    title: Mapped[str] = mapped_column(String(400))
    company_name: Mapped[str] = mapped_column(String(300), default="")
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    skills: Mapped[list] = mapped_column(JSON, default=list)
    contract_type: Mapped[str] = mapped_column(String(80), default="")
    salary: Mapped[str] = mapped_column(String(200), default="")
    currency: Mapped[str] = mapped_column(String(10), default="")
    location: Mapped[str] = mapped_column(String(300), default="")
    remote: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    apply_url: Mapped[str] = mapped_column(String(800), default="")
    source: Mapped[str] = mapped_column(String(100), default="")
    source_url: Mapped[str] = mapped_column(String(800), default="")
    external_id: Mapped[str] = mapped_column(String(200), default="")
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    needs_verification: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(40), default=PipelineStatus.decouverte, index=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    next_action: Mapped[str] = mapped_column(String(500), default="")
    next_action_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    company: Mapped[Company | None] = relationship(back_populates="opportunities")


class GeneratedDocument(Base):
    """Lettre, proposition commerciale ou email généré (modifiable)."""
    __tablename__ = "generated_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    doc_type: Mapped[str] = mapped_column(String(30))  # cover_letter | b2b_proposal | email
    profile_key: Mapped[str] = mapped_column(String(20))
    language: Mapped[str] = mapped_column(String(5), default="fr")
    opportunity_id: Mapped[int | None] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=True)
    subject: Mapped[str] = mapped_column(String(400), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    model_used: Mapped[str] = mapped_column(String(120), default="")
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Application(Base):
    """Candidature / démarche préparée. L'envoi est TOUJOURS fait par l'utilisateur."""
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_key: Mapped[str] = mapped_column(String(20))
    opportunity_id: Mapped[int | None] = mapped_column(ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    channel: Mapped[str] = mapped_column(String(30), default="email")  # email | platform | form
    recipient: Mapped[str] = mapped_column(String(400), default="")
    cc: Mapped[str] = mapped_column(String(400), default="")
    subject: Mapped[str] = mapped_column(String(400), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    letter_id: Mapped[int | None] = mapped_column(ForeignKey("generated_documents.id", ondelete="SET NULL"), nullable=True)
    attachment_ids: Mapped[list] = mapped_column(JSON, default=list)  # Document.id validés par l'utilisateur
    attach_letter_format: Mapped[str] = mapped_column(String(10), default="pdf")  # pdf | docx | none
    status: Mapped[str] = mapped_column(String(30), default="brouillon")
    # brouillon | draft_cree | approuvee (campagne, en file) | envoyee | echec | ignoree | annulee
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=True, index=True)
    message_id: Mapped[str] = mapped_column(String(300), default="", index=True)
    error: Mapped[str] = mapped_column(Text, default="")
    delivery: Mapped[str] = mapped_column(String(20), default="")  # "" | replied | bounced | unsubscribed
    draft_provider: Mapped[str] = mapped_column(String(30), default="")
    draft_ref: Mapped[str] = mapped_column(String(300), default="")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Activity(Base):
    """Historique : échanges, relances, rendez-vous, changements de statut."""
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=True)
    opportunity_id: Mapped[int | None] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=True)
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=True)
    type: Mapped[str] = mapped_column(String(40))  # status_change | note | email_sent | reply | meeting | follow_up | generated
    summary: Mapped[str] = mapped_column(Text, default="")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SearchRun(Base):
    __tablename__ = "search_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    target: Mapped[str] = mapped_column(String(20))  # opportunities | companies
    connector: Mapped[str] = mapped_column(String(50))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | done | error
    found: Mapped[int] = mapped_column(Integer, default=0)
    created: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SavedSearch(Base):
    """Recherche enregistrée, exécutable manuellement ou chaque matin (Celery beat)."""
    __tablename__ = "saved_searches"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    target: Mapped[str] = mapped_column(String(20))  # opportunities | companies
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    scheduled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Credential(Base):
    """Jetons OAuth chiffrés (Fernet). Jamais exposés au frontend."""
    __tablename__ = "credentials"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), unique=True)
    encrypted_payload: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Campaign(Base):
    """Envoi par lots : génération personnalisée, relecture, validation unique, envoi étalé."""
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    profile_key: Mapped[str] = mapped_column(String(20), default=ProfileKey.kortex)
    language: Mapped[str] = mapped_column(String(5), default="fr")
    instructions: Mapped[str] = mapped_column(Text, default="")
    attachment_ids: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="generating")
    # generating | review | sending | paused | done
    paused_reason: Mapped[str] = mapped_column(Text, default="")
    next_send_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Suppression(Base):
    """Adresses à ne plus jamais contacter (désinscription, rebond, refus, STOP)."""
    __tablename__ = "suppressions"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    reason: Mapped[str] = mapped_column(String(30))  # unsubscribe | bounce | stop | refus | manual
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class InboxSeen(Base):
    """Messages IMAP déjà analysés (réponses / rebonds)."""
    __tablename__ = "inbox_seen"
    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[str] = mapped_column(String(400), unique=True)
    kind: Mapped[str] = mapped_column(String(20), default="")  # reply | bounce | other
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
