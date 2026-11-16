"""Génération des lettres de motivation, propositions commerciales et emails.

Règles non négociables, injectées dans chaque prompt :
- uniquement des faits présents dans le profil ; rien d'inventé ;
- personnalisation réelle (entreprise, poste, secteur, destinataire) ;
- une information manquante devient un champ [À COMPLÉTER] visible, jamais une invention.
Sans LLM configuré, aucune lettre n'est produite : on ne présente pas un modèle générique comme personnalisé.
"""
import json
from datetime import date

from ..models import Company, Opportunity, Profile
from . import llm

COMMON_RULES = """RÈGLES ABSOLUES :
1. N'utilise QUE les faits du PROFIL fourni. N'invente aucun diplôme, poste, client, chiffre, certification, résultat ni outil.
2. Relie explicitement les exigences de l'annonce / les besoins de l'entreprise à des éléments réels du profil.
3. Si une information indispensable manque (nom du destinataire, référence de l'offre…), écris [À COMPLÉTER] — ne devine pas.
4. Pas de formules creuses ni de superlatifs vagues (« passionné », « dynamique », « leader ») ; des faits précis.
5. Ton adapté au pays et à la culture de l'entreprise : formel et structuré pour la Côte d'Ivoire / l'Afrique francophone
   et les institutions ; direct et concis pour les startups et le remote international anglophone.
6. Pas de puces dans une lettre ; paragraphes courts. Ne mets aucune signature ni nom en bas : elle est ajoutée automatiquement.
7. N'affirme RIEN sur l'équipement, la connexion internet, les horaires, la disponibilité, le visa, la relocalisation,
   le salaire souhaité ou la vie personnelle : ces informations ne sont pas dans le profil.
8. Formule d'appel : si le destinataire est inconnu, « Madame, Monsieur, » (FR) ou « Dear Hiring Team, » (EN) — jamais de [À COMPLÉTER] dans la formule.
9. Avant de répondre, relis chaque phrase : toute affirmation sur Shalom ou KORTEX doit correspondre à un élément précis du PROFIL, sinon supprime-la."""

KORTEX_RULES = """RÈGLES KORTEX :
- Les références clients marquées "citable": false ne sont JAMAIS nommées : parle d'« un acteur du secteur de la santé / de l'énergie / du sport ».
- Société créée en 2026 : ne revendique ni ancienneté, ni chiffre d'affaires, ni agrément.
- Termine par une demande de rendez-vous de 15 à 20 minutes, en présentiel à Abidjan ou en visioconférence."""


def _target_block(opp: Opportunity | None, company: Company | None) -> str:
    parts = []
    if opp:
        parts.append(f"""ANNONCE :
Intitulé : {opp.title}\nEntreprise : {opp.company_name}\nLieu : {opp.location} | Remote : {opp.remote}
Contrat : {opp.contract_type}\nSource : {opp.source} {opp.source_url}\nCompétences : {', '.join(opp.skills or [])}
Description :\n{opp.description[:8000]}""")
        if opp.analysis:
            parts.append("ANALYSE PRÉALABLE : " + json.dumps({k: opp.analysis.get(k) for k in ("matched", "approach", "summary")}, ensure_ascii=False))
    if company:
        contacts = [f"{c.label}: {c.value}" + (f" ({c.person_name})" if c.person_name else "") for c in company.contacts if c.kind == "email"]
        parts.append(f"""ENTREPRISE :
Nom : {company.name}\nSite : {company.website}\nSecteur : {company.sector}\nPays / ville : {company.country} {company.city}
Description : {company.description[:4000]}\nContacts : {contacts}""")
        if company.analysis:
            parts.append("ANALYSE PRÉALABLE : " + json.dumps({k: company.analysis.get(k) for k in ("matched", "approach", "contact_to_target", "summary")}, ensure_ascii=False))
    return "\n\n".join(parts)


def _lang_label(lang: str) -> str:
    return "anglais (English)" if lang == "en" else "français"


def generate(doc_type: str, profile: Profile, opp: Opportunity | None, company: Company | None,
             language: str, recipient_name: str = "", instructions: str = "", letter_text: str = "") -> dict:
    """Retourne {"subject": str, "content": str}."""
    profile_json = json.dumps(profile.data, ensure_ascii=False)
    target = _target_block(opp, company)
    extra = f"\nCONSIGNES DE L'UTILISATEUR : {instructions}" if instructions else ""
    dest = f"\nDestinataire : {recipient_name}" if recipient_name else "\nDestinataire : inconnu (utiliser une formule neutre adaptée)"
    rules = COMMON_RULES + ("\n" + KORTEX_RULES if profile.key == "kortex" else "")

    if doc_type == "cover_letter":
        system = f"Tu rédiges des lettres de motivation sur mesure pour {profile.display_name}.\n{rules}"
        task = f"""Rédige une lettre de motivation en {_lang_label(language)} (250 à 380 mots) pour cette candidature.
Structure : accroche liée à l'entreprise/au poste → 2 paragraphes de preuves tirées du profil (expériences, Shaapi, projets
pertinents) qui répondent aux exigences → motivation pour CETTE entreprise → proposition d'échange. Formule de politesse finale incluse."""
    elif doc_type == "b2b_proposal":
        system = f"Tu rédiges des propositions de collaboration B2B pour KORTEX DIGITAL.\n{rules}"
        task = f"""Rédige une proposition commerciale courte en {_lang_label(language)} (300 à 450 mots), sous forme de lettre.
Structure : présentation de KORTEX DIGITAL en 2 phrases → besoins POTENTIELS identifiés pour cette entreprise (présentés comme
des hypothèses à valider, jamais comme des faits) → 2 à 3 services KORTEX pertinents et ce qu'ils apportent concrètement →
réalisations ou produits pertinents (en respectant les règles de citation) → proposition de collaboration (prestation,
sous-traitance, référencement fournisseur) → demande de rendez-vous de 15 à 20 minutes. Formule de politesse finale incluse."""
    elif doc_type == "email":
        system = f"Tu rédiges des emails professionnels courts pour {profile.display_name}.\n{rules}"
        attached = "\nLETTRE / PROPOSITION JOINTE (à résumer, pas à recopier) :\n" + letter_text[:3000] if letter_text else ""
        task = f"""Rédige un email d'accompagnement en {_lang_label(language)} (90 à 160 mots) : objet précis, formule d'appel,
présentation en une phrase, motivation ou proposition en 2-3 phrases spécifiques à l'entreprise, appel à l'action clair,
formule de politesse. Mentionne les pièces jointes de façon générique (« vous trouverez ci-joint… »).{attached}"""
    else:
        raise ValueError(f"Type de document inconnu : {doc_type}")

    user = f"""PROFIL (source de vérité) :\n{profile_json}\n\n{target}{dest}{extra}\nDate du jour : {date.today().isoformat()}

{task}

Réponds en JSON : {{"subject": "objet (ligne 'Objet :' de la lettre, ou objet de l'email)", "content": "texte complet, paragraphes séparés par une ligne vide, sans signature"}}"""
    data = llm.chat_json(system, user, max_tokens=2500)
    content = str(data.get("content", "")).strip()
    signature = profile.data.get("signature_en" if language == "en" else "signature", profile.display_name)
    return {"subject": str(data.get("subject", "")).strip(), "content": f"{content}\n\n{signature}"}
