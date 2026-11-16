# KORTEX Prospect

CRM de prospection pour **Shalom Tehe** (carrière) et **KORTEX DIGITAL** (B2B). L'outil sert à :
- trouver des offres et des entreprises ;
- qualifier chaque opportunité par l'IA, avec un score sur 100 expliqué ;
- rédiger des lettres et des emails personnalisés à partir des vrais documents ;
- préparer des candidatures, ou envoyer des lots validés à un rythme qui préserve la délivrabilité.

> **Rien ne part sans validation.** Pour une candidature individuelle, l'app prépare un brouillon (`.eml`, `mailto:` ou brouillon Zoho). Pour une campagne, le lot est relu puis validé une fois. Les emails partent ensuite un par un, espacés, dans la limite d'un plafond quotidien.

Production : **https://prospect.kortex.sbs** (Dokploy).

## Déploiement (Dokploy)

1. À chaque push sur `main`, GitHub Actions lance les tests puis construit et publie deux images :
   - `ghcr.io/shalom-302/prospect` (API et worker) ;
   - `ghcr.io/shalom-302/prospect-web` (interface).
2. Dans Dokploy, créer un service **Compose** à partir de ce dépôt, avec le fichier **`compose.image.yml`**.
3. Associer le domaine `prospect.kortex.sbs` au service **`web`**, port **3000**, en HTTPS. L'API n'est pas exposée : l'interface relaie `/api/*` en interne.
4. Renseigner l'onglet *Environment* (voir `.env.example`). Variables minimales :

```env
PUBLIC_DOMAIN=prospect.kortex.sbs
POSTGRES_PASSWORD=<lettres et chiffres>
TOKEN_SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(48))">
SECRET_KEY=<python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
ADMIN_PHONES=0712116258
GOWA_BASIC_USER=...            # passerelle WhatsApp partagée avec Foody
GOWA_BASIC_PASS=...
LLM_API_KEY=...                # DeepSeek par défaut
TAVILY_API_KEY=...
MAIL_USER=contact@kortexdigital.net
MAIL_PASSWORD=<mot de passe d'application Zoho>
```

Le réseau Docker `whatsapp-shared-network` existe déjà sur le VPS (Foody, SignalLab). La passerelle gowa est jointe à l'adresse `http://shalom-gowa:3080`.

Si les images GHCR sont privées, Dokploy doit avoir accès au registre `ghcr.io` (identifiant GitHub et jeton `read:packages`). Sinon, rendre les deux paquets publics.

## Connexion

Elle fonctionne comme sur Foody, avec un code à 6 chiffres envoyé sur WhatsApp par gowa. Seuls les numéros de `ADMIN_PHONES` reçoivent un code. La session est un cookie httpOnly valable 30 jours. En dev, si `ADMIN_PHONES` est vide, aucune connexion n'est demandée ; s'il est rempli sans gowa, le code s'affiche dans les logs de l'API.

## Campagnes et délivrabilité

1. **Campagnes** : sélectionner des entreprises qui ont un email public. L'IA rédige un email de prospection pour chacune, en texte brut, avec une accroche tirée du vrai site de l'entreprise.
2. **Écartés automatiquement**, avec la raison :
   - pas d'email public, ou seulement une adresse estimée ;
   - adresse dans la liste d'exclusion ;
   - déjà contacté depuis moins de 90 jours ;
   - échange déjà en cours ;
   - entreprise trop peu décrite pour personnaliser.
3. **Relecture** : chaque email est modifiable, peut être réécrit ou retiré. Des alertes signalent les mots filtrés, les majuscules, les liens en trop et la personnalisation absente.
4. **Validation** : un clic, puis le worker envoie au plus un email par minute :
   - montée en charge : 10/jour la 1re semaine, 20 la 2e, puis 30 maximum (`CAMPAIGN_DAILY_MAX`) ;
   - intervalle aléatoire de 3 à 7 minutes, de 8 h à 17 h (heure d'Abidjan), du lundi au vendredi ;
   - en-têtes `List-Unsubscribe` en un clic et lien de désinscription en pied de page.
5. **Suivi**, par lecture IMAP toutes les 10 minutes, en lecture seule :
   - une réponse met la fiche en « Réponse reçue » ;
   - « stop » ou un rebond ajoute l'adresse à la liste d'exclusion ;
   - au-delà de 5 % de rebonds, le lot passe en pause automatique.

DNS de `kortexdigital.net`, vérifié le 16/11/2026, avec contrôle en direct dans *Email et délivrabilité* :
- SPF Zoho : OK.
- DKIM : OK, mais la clé fait 1024 bits ; la passer à 2048 bits.
- DMARC : `p=none`. Passer à `p=quarantine` après 2 à 4 semaines d'envois propres.
- MX Zoho : OK.

## Développement local (Windows)

```powershell
docker compose up -d db redis
cd backend;  .venv\Scripts\alembic upgrade head;  .venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8010
cd frontend; pnpm dev -p 3100        # API_INTERNAL_URL=http://127.0.0.1:8010 dans frontend/.env.local
cd backend;  .venv\Scripts\celery -A app.worker worker -B --pool=solo --loglevel=info   # worker (envois, IMAP, recherches)
```

Importer les documents de référence : `.venv\Scripts\python -m app.cli import-docs "C:\Users\LEGION\Desktop\kortex-docx"`

Tests : `cd backend; .venv\Scripts\python -m pytest -q`

## Sources

- **Remotive** (API), **Remote OK** (API) et **We Work Remotely** (RSS) : offres en remote international.
- **Tavily** : découverte d'entreprises, offres en Côte d'Ivoire et en Afrique, et proposition de candidats pour le site officiel d'une entreprise.
- **Sites d'entreprises** : lecture des pages publiques autorisées par robots.txt (1,5 s entre deux requêtes, 5 pages au maximum).
- **Plateformes sans collecte** : LinkedIn, Indeed, Glassdoor, Emploi.ci, Upwork, Malt et Fiverr bloquent ou interdisent les robots. L'app propose des liens de recherche préremplis, la recherche via l'index web et l'import d'une annonce copiée-collée.

## Garanties

- **Contacts** : chacun a une source et un niveau de confiance (publié sur le site officiel / trouvé non vérifié / estimé). Aucune adresse n'est devinée, et les adresses estimées ne partent jamais en lot.
- **Profils** (Paramètres › Profils) : c'est la seule source de vérité pour l'IA.
  - Chaque réalisation est décrite exactement, avec son champ `realisation`.
  - Les clients non autorisés ne sont cités que par secteur.
- **Opportunités** : la source et la date de collecte sont conservées. Les doublons, les offres expirées et les annonces frauduleuses sont écartés.

## Architecture

```
backend/   FastAPI · SQLAlchemy 2 · Alembic · Celery · Redis · PostgreSQL
  app/auth.py              connexion WhatsApp (gowa) + session JWT
  app/connectors/          remotive, remoteok, weworkremotely, tavily, registre des plateformes
  app/services/outreach.py campagnes : éligibilité, rédaction, lint, warm-up, SMTP, IMAP, désinscription
  app/services/            qualification, generator, contact_extractor, exporter, documents, mail (brouillons)
  app/worker.py            beat : recherches 7 h, file d'envoi (1/min), IMAP (10 min)
frontend/  Next.js 15 · Tailwind v4 · shadcn/ui · SWR — proxy same-origin /api/* (src/lib/server/proxy.ts)
compose.image.yml          production Dokploy (images GHCR)
docker-compose.yml         développement
```
