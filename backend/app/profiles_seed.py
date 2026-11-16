"""Données initiales des deux profils.

Source de vérité :
- Profil A : CV « Shalom_Tehe_FR.pdf » (novembre 2026). Rien n'est ajouté au-delà du CV.
- Profil B : certificat CEPICI, pack institutionnel KORTEX et cahier des charges.
Tout est modifiable depuis l'écran Paramètres > Profils.
"""

SHALOM = {
    "full_name": "Shalom Tehe",
    "headline": "Ingénieur Logiciel Backend & IA · Spécialiste FastAPI · Mainteneur Open Source",
    "headline_en": "Backend & AI Software Engineer · FastAPI Specialist · Open Source Maintainer",
    "location": "Abidjan, Côte d'Ivoire",
    "availability": "Ouvert aux opportunités à distance et internationales",
    "contact": {
        "email": "shalomtehe219@gmail.com",
        "phone": "+225 07 12 11 62 58",
        "website": "https://shalom.kortexai.dev",
        "github": "https://github.com/Shalom-302",
        "linkedin": "https://linkedin.com/in/shalomt",
    },
    "summary": (
        "Ingénieur logiciel backend et IA, spécialisé dans la conception de systèmes backend prêts pour la production, "
        "d'applications dopées à l'IA et d'outils pour développeurs. Créateur et mainteneur de Shaapi, framework FastAPI "
        "open source publié sur PyPI, et auteur d'un guide technique sur l'ingénierie de frameworks. Plus de 3 ans "
        "d'expérience avec Python, FastAPI et PostgreSQL, et dans la mise en production de systèmes à base de LLM : "
        "pipelines RAG, agents IA et intégrations MCP."
    ),
    "target_roles": [
        "Backend Software Engineer", "Python / FastAPI Developer", "AI Engineer / Generative AI Engineer",
        "LLM Engineer", "AI Agents Developer", "Software Engineer", "Freelance Backend Developer",
        "Technical Lead", "Consultant en intelligence artificielle",
    ],
    "contract_types": ["CDI", "CDD", "Remote international", "Freelance", "Consulting", "Contract", "Mission ponctuelle", "Sous-traitance"],
    "skills": {
        "Ingénierie backend": ["Python", "FastAPI", "API REST", "Architectures asynchrones", "Architecture logicielle", "Clean Architecture", "SQLAlchemy", "Alembic"],
        "Intelligence artificielle": ["IA générative", "Applications LLM", "RAG", "Agents IA", "MCP", "LangChain", "Prompt Engineering", "NLP & extraction intelligente de données"],
        "Bases de données": ["PostgreSQL", "Redis", "Qdrant", "Bases de données vectorielles"],
        "DevOps": ["Docker", "Linux", "Git", "CI/CD", "Déploiement sur VPS"],
        "Open Source": ["PyPI", "Publication de paquets", "Documentation", "Développement CLI"],
        "Frontend": ["React.js"],
    },
    "experiences": [
        {"title": "Développeur IA Générative", "company": "Kaanari", "period": "Sept. 2023 – aujourd'hui", "location": "Abidjan",
         "highlights": [
             "Conçoit et livre des services backend pour des produits pilotés par l'IA avec FastAPI, Python asynchrone et PostgreSQL, de l'architecture au déploiement conteneurisé (Docker / VPS).",
             "Construit et orchestre des agents IA et des pipelines LLM (LangChain) pour l'automatisation, le NLP et l'extraction intelligente de données dans des produits web en production.",
             "Intègre des capacités d'IA générative dans des produits clients, en transformant des cas d'usage IA ambigus en systèmes fiables, sécurisés et de niveau production.",
             "Collabore avec des équipes produit, data et ingénierie sur l'architecture et la livraison.",
         ]},
        {"title": "Lead Developer", "company": "IT Foundation Côte d'Ivoire", "period": "2026 – aujourd'hui", "location": "Abidjan",
         "highlights": [
             "Leadership technique : décisions d'architecture, choix technologiques et planification des livraisons.",
             "Bonnes pratiques : revue de code, workflows Git, clean architecture, standards de déploiement conteneurisé.",
             "Encadre les développeurs et traduit les besoins métier en feuilles de route techniques.",
         ]},
        {"title": "Professeur / Formateur technique", "company": "GEIGE (Grande École Informatique de Gestion Entreprise)", "period": "2026 – aujourd'hui", "location": "Abidjan",
         "highlights": [
             "Enseigne le génie logiciel, le développement backend et Python.",
             "Conçoit des cursus pratiques orientés projets.",
         ]},
        {"title": "Administrateur Réseaux & Sécurité (programme de formation)", "company": "Lemon Africa", "period": "Janv. 2022 – mai 2023", "location": "Abidjan",
         "highlights": ["Sensibilisations à la cybersécurité et appui à la mise en œuvre de protocoles de sécurité et d'opérations réseau."]},
        {"title": "Bénévole, appui aux compétences numériques", "company": "American Space", "period": "Août 2021 – janv. 2022", "location": "Abidjan",
         "highlights": ["Support technique et accompagnement des usagers sur les outils numériques."]},
    ],
    "projects": [
        {"name": "Shaapi", "role": "Créateur & mainteneur", "description": "Framework de scaffolding FastAPI open source prêt pour la production, distribué via PyPI, avec CLI complète ; PostgreSQL, Redis, MinIO, JWT, RBAC et déploiement Docker intégrés.", "key": True},
        {"name": "Build Your Own Shaapi", "role": "Auteur", "description": "Guide technique sur la conception, la sécurisation, le packaging et la distribution d'un framework FastAPI de niveau production."},
        {"name": "Plateforme Sevoil Industry", "role": "Lead Backend Engineer", "description": "Plateforme métier de vente et de gestion de produits pétroliers : architecture backend, conception des API, gestion des données, approche security-first."},
        {"name": "ShaAI", "role": "Fondateur", "description": "Initiative d'IA appliquée : architectures agentiques, RAG, intégrations MCP et automatisation."},
        {"name": "TRAAF", "role": "Backend", "description": "Gestion du transport urbain : backend FastAPI sécurisé, PostgreSQL, Docker sur VPS."},
        {"name": "Takawake", "role": "Backend / IA", "description": "Scraping intelligent dopé à l'IA : orchestration d'agents LangChain, extraction et structuration de données, services FastAPI."},
        {"name": "Teleco Health", "role": "Backend / IA", "description": "Plateforme e-santé à base d'IA générative : FastAPI + PostgreSQL, sécurité des données."},
    ],
    "education": [
        {"degree": "Licence en Programmation Web", "school": "ESMA, Riviera, Abidjan", "date": "Juillet 2022"},
        {"degree": "BTS (HND) Réseaux Informatiques", "school": "IFSM, Cocody, Abidjan", "date": "Septembre 2021"},
    ],
    "languages": [{"language": "Français", "level": "Courant (langue maternelle)"}, {"language": "Anglais", "level": "Professionnel"}],
    "signature": "Shalom Tehe\nIngénieur Logiciel Backend & IA\n+225 07 12 11 62 58 · shalomtehe219@gmail.com\nhttps://shalom.kortexai.dev · github.com/Shalom-302",
    "signature_en": "Shalom Tehe\nBackend & AI Software Engineer\n+225 07 12 11 62 58 · shalomtehe219@gmail.com\nhttps://shalom.kortexai.dev · github.com/Shalom-302",
    "rules": [
        "Ne jamais inventer de diplôme, d'expérience, de certification ou de compétence absente de ce profil.",
        "Ne pas citer de chiffres (utilisateurs, gains, revenus) qui ne figurent pas dans le profil.",
    ],
}

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
