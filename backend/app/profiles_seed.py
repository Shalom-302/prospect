"""Données initiales des deux profils.

Source de vérité :
- Profil A : CV de novembre 2026, rôle de fondateur (CEPICI), produits et stacks vérifiés dans les dépôts de code.
- Profil B : certificat CEPICI, pack institutionnel KORTEX et cahier des charges.
Tout est modifiable depuis l'écran Paramètres > Profils.
"""

import json
from pathlib import Path

# Profil A : maintenu dans profile_shalom.json (CV de novembre 2026 + rôle de CEO + produits, stacks vérifiées dans le code).
SHALOM = json.loads((Path(__file__).with_name("profile_shalom.json")).read_text(encoding="utf-8"))

KORTEX = {
    "legal_name": "KORTEX DIGITAL",
    "legal_form": "SARL",
    "idu": "CI-2026-0078032 H",
    "rccm": "CI-ABJ-03-2026-B13-15546",
    "capital": "1 000 000 FCFA",
    "registered_on": "13 octobre 2026",
    "address": "Abidjan, Cocody, Angré Extension Château-Latrille, Bessikoi 2",
    "manager": "TEHE Nomansoh Shalom, Gérant",
    "contact": {"email": "contact@kortexdigital.net", "phone": "+225 07 12 11 62 58", "website": "https://www.kortexdigital.net"},
    "pitch": (
        "KORTEX DIGITAL est une entreprise ivoirienne spécialisée dans les technologies numériques, le développement "
        "logiciel et l'intelligence artificielle. Elle conçoit des applications métier, des solutions SaaS et des "
        "agents IA pour les entreprises et organisations, en Côte d'Ivoire et à l'international."
    ),
    "services": [
        "Développement web et applications métier",
        "Backend engineering et API",
        "Solutions SaaS",
        "Intelligence artificielle et agents IA",
        "Automatisation des processus",
        "Intégration de LLM et RAG",
        "Audit de sécurité informatique",
        "Design et identité visuelle",
        "Formation et accompagnement technique",
        "Maintenance et externalisation de développement",
    ],
    "products": [
        {"name": "KORTEX DEFENDER", "url": "https://www.defender.kortex.sbs",
         "description": "SaaS d'audit de sécurité des sites web et API : classement des failles par gravité, analyse assistée par IA, explications en français, score de sécurité et rapport PDF. Conçu, développé et exploité par KORTEX."},
        {"name": "STOODENT", "url": "https://www.stoodent.kortex.sbs",
         "description": "Réseau d'entraide étudiante gratuit : questions / réponses votées, professeurs vérifiés, laboratoire virtuel 3D, communautés par filière. Conçu par KORTEX."},
        {"name": "FOODY", "description": "Plateforme e-commerce (gastronomie) avec connexion par code WhatsApp. Conçue par KORTEX."},
        {"name": "SHAAPI", "description": "Framework backend FastAPI open source publié sur PyPI (CLI, PostgreSQL, Redis, MinIO, JWT, RBAC, Docker)."},
    ],
    "client_sectors": ["Santé", "Énergie", "Sport"],
    "client_references": [
        {"name": "Telcosanté", "sector": "Santé (télémédecine)", "citable": False,
         "realisation": "Site web d'une plateforme de télémédecine : téléconsultation 24h/24, rendez-vous en ligne, médecins, spécialités, tarifs, lien vers l'application mobile."},
        {"name": "SEV-OIL", "sector": "Énergie (distribution de produits pétroliers)", "citable": False,
         "realisation": "Site web bilingue FR/EN présentant les activités (stations-service, sites miniers, soutage maritime) avec demande de devis en ligne."},
        {"name": "OISSU Connect", "sector": "Sport scolaire et universitaire", "citable": False,
         "realisation": "Plateforme web de suivi des athlètes : fiches, historique des compétitions, indicateurs de progression, tableaux de bord, comptes sécurisés, six disciplines."},
    ],
    "context": "Société créée en 2026 : pas encore d'états financiers. Privilégier rendez-vous, référencement fournisseur, sous-traitance et consortiums.",
    "signature": "Shalom Tehe\nFondateur & Gérant — KORTEX DIGITAL\ncontact@kortexdigital.net · +225 07 12 11 62 58\nwww.kortexdigital.net",
    "signature_en": "Shalom Tehe\nFounder & Managing Director — KORTEX DIGITAL\ncontact@kortexdigital.net · +225 07 12 11 62 58\nwww.kortexdigital.net",
    "rules": [
        "Ne jamais inventer de client, de référence, de chiffre ou de réalisation.",
        "Les références clients dont 'citable' vaut false ne sont citées que par secteur (« un acteur de la santé »), jamais par nom, tant que l'accord du client n'est pas obtenu.",
        "Ne jamais revendiquer d'ancienneté, d'agrément ou de certification non listés.",
        "Une réalisation se décrit EXACTEMENT comme dans son champ 'realisation' ou 'description' : ne jamais lui attribuer un autre type de travail (ex. un site web n'est pas de l'automatisation de processus).",
    ],
}

SEED = [
    {"key": "shalom", "display_name": "Shalom Tehe", "kind": "individual", "data": SHALOM},
    {"key": "kortex", "display_name": "KORTEX DIGITAL", "kind": "company", "data": KORTEX},
]
