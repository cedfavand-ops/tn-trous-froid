# Tn — Trous à froid de France (automatisation)

Ce dossier contient tout ce qu'il faut pour générer automatiquement, chaque
matin, la page HTML listant les Tn (températures minimales nocturnes) des
15 stations suivies.

## Fichiers

- `generate_tn_page.py` — le script qui va chercher les données et écrit `docs/index.html`
- `update-tn.yml` — le workflow GitHub Actions (à placer dans `.github/workflows/update-tn.yml`)
- Ce README

## Mise en place (10 minutes, une seule fois)

1. **Créer un dépôt GitHub** (public ou privé) et y copier ces fichiers :
   - `generate_tn_page.py` à la racine
   - `update-tn.yml` dans `.github/workflows/update-tn.yml`

2. **Activer GitHub Pages** : Settings → Pages → Source = "Deploy from a branch",
   branche `main`, dossier `/docs`. Votre page sera visible à une URL du type
   `https://<votre-compte>.github.io/<votre-repo>/`.

3. **Ajouter vos secrets** (Settings → Secrets and variables → Actions → New repository secret) :

   | Nom du secret            | Valeur |
   |---------------------------|--------|
   | `INFOCLIMAT_TOKEN`        | votre token API Infoclimat (généré sur infoclimat.fr/opendata) |
   | `ECOWITT_APPLICATION_KEY` | votre Application Key Ecowitt (ecowitt.net → User Center → Private Center → API Keys) |
   | `ECOWITT_API_KEY`         | votre API Key Ecowitt |
   | `ECOWITT_MAC`             | l'adresse MAC de la station Lussan La Lèque (visible dans l'app WS View / sur ecowitt.net) |
   | `DATACAKE_TOKENS_JSON`    | voir ci-dessous |

   **Pour `DATACAKE_TOKENS_JSON`** : comme vous avez plusieurs comptes Datacake,
   ce secret associe chaque station à son token. Générez un token par compte
   (Datacake → Account Settings → API → Access Tokens), puis construisez un
   JSON du type :

   ```json
   {
     "4141f1e8-3a9a-4503-a84d-eb6999f53171": "TOKEN_DU_COMPTE_A",
     "c21a6a3f-174d-46ff-8237-c61cedb15b45": "TOKEN_DU_COMPTE_A",
     "6158e91a-e71b-4280-be9e-d6842768c467": "TOKEN_DU_COMPTE_B",
     "d75df345-b0f9-4da5-bed2-74153c0ffd15": "TOKEN_DU_COMPTE_B",
     "49d8e76b-d3b1-4f96-9ce6-b6602bcf8036": "TOKEN_DU_COMPTE_B",
     "d4b23fdc-eca0-4658-9d0b-66829a0b9890": "TOKEN_DU_COMPTE_C",
     "08d595dc-2848-4b91-ab7c-2295f3df85c6": "TOKEN_DU_COMPTE_C",
     "1e79ad96-29b0-4c76-a7ed-7be780dac89c": "TOKEN_DU_COMPTE_C"
   }
   ```

   Collez ce JSON (sur une seule ligne, ça fonctionne aussi bien) comme valeur
   du secret `DATACAKE_TOKENS_JSON`. Vous n'avez donc jamais besoin de me
   communiquer vos tokens — ils restent uniquement dans les secrets GitHub,
   jamais dans le code ni dans nos conversations.

4. **Tester manuellement** : onglet "Actions" du dépôt → workflow
   "Mise à jour des Tn" → "Run workflow". Vérifiez `docs/index.html` et les
   logs (chaque station en échec affiche un message d'avertissement expliquant
   pourquoi).

## Notes techniques

- **Fenêtre "nuit"** : le script prend le minimum entre 18h la veille et
  l'heure d'exécution. Si le job tourne à 9h10, ça couvre bien la nuit.
- **Heure d'été/hiver** : le cron GitHub Actions est en UTC et ne s'ajuste pas
  automatiquement au changement d'heure française. Le fichier `update-tn.yml`
  est réglé pour viser ~9h10 en été ; en hiver la page sera générée vers 8h10.
  Si vous préférez viser 9h10 toute l'année, dupliquez la ligne cron avec les
  deux horaires (7h10 et 8h10 UTC) — le script ne fera simplement rien
  d'utile lors de l'exécution "en trop".
- **Champ température Datacake** : le script détecte automatiquement le nom
  du champ (`TEMPERATURE`, `TEMPC_SHT`, etc.) via une requête GraphQL avant
  de récupérer l'historique. Si un device utilise un nom de champ inhabituel
  et que ça ne fonctionne pas, dites-le-moi avec le nom exact vu dans le
  dashboard Datacake et j'ajusterai le script.
- Le site généré reprend exactement le même visuel (tableau, couleurs) que
  la version que je vous ai montrée en chat.
