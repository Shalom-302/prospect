"""Architecture de connecteurs indépendants : ajouter une source = ajouter une classe
qui implémente `search()` et l'enregistrer dans `registry.py`."""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SearchParams:
    keywords: list[str] = field(default_factory=list)
    country: str = ""
    city: str = ""
    sector: str = ""
    contract_type: str = ""
    remote: bool | None = None
    language: str = ""
    min_salary: float | None = None
    profile_key: str = "shalom"
    kind: str = "job"  # job | freelance | b2b
    limit: int = 30
    include_domains: list[str] = field(default_factory=list)

    @property
    def query(self) -> str:
        return " ".join(self.keywords)


@dataclass
class RawOpportunity:
    title: str
    company_name: str
    source: str
    source_url: str
    apply_url: str
    external_id: str = ""
    description: str = ""
    skills: list[str] = field(default_factory=list)
    contract_type: str = ""
    salary: str = ""
    currency: str = ""
    location: str = ""
    remote: bool | None = None
    language: str = ""
    published_at: datetime | None = None
    deadline: datetime | None = None
    kind: str = "job"
    needs_verification: bool = False


@dataclass
class RawCompany:
    name: str
    website: str | None
    source: str
    source_url: str
    sector: str = ""
    country: str = ""
    city: str = ""
    description: str = ""


class OpportunityConnector:
    name: str = "base"
    label: str = "Base"
    requires: str | None = None  # nom de la clé de config requise

    def available(self) -> bool:
        return True

    def search(self, params: SearchParams) -> list[RawOpportunity]:
        raise NotImplementedError
