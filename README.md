# MyBacklog

*My backlog, locally, safely, anywhere.*

Une application locale, façon [Backloggd](https://backloggd.com/), pour gérer votre backlog de
jeux vidéo à partir de votre fichier Excel / CSV existant : dashboard personnalisable, grille
"Jeux complétés" / "Backlog", notes, avis en markdown, jaquettes, et export à tout moment vers
`.xlsx` ou `.csv` — vos données restent toujours en votre possession.

**Logiciel open-source et gratuit — personne ne devrait avoir à payer pour ça.**

Fonctionne à l'identique sous **Windows** et **Linux** (c'est une petite application web locale :
un serveur Python + une page qui s'ouvre dans votre navigateur), et peut aussi tourner via **Docker**.

## Fonctionnalités

### Import / export
- Import de votre `My_Backlog.xlsx` ou des 3 CSV (Backlog / Avis / Complété), en conservant la
  logique de votre fichier d'origine (marqueurs d'année, colonnes de résumé ignorées, gras/italique
  de vos avis convertis en markdown).
- Export à tout moment vers un classeur `.xlsx` mis en forme (en-têtes colorés, bandes d'année,
  gras/italique restitués) ou un zip de CSV équivalents.
- Démarrage possible sans import, via le bouton **"Start backlog"**.

### Dashboard personnalisable
- Widgets déplaçables (glisser-déposer), redimensionnables et masquables individuellement via le
  bouton **"✏️ Modifier"**.
- Statistiques : heures jouées, jeux complétés, note moyenne, jeux restants dans le backlog, jeu le
  plus long / le plus court / le mieux noté / le moins bien noté, progression par année (+ courbe
  cumulée), tendance mensuelle et répartition des notes (chacune filtrable par année), répartition
  "ça valait le coup ?", possession du backlog (le suivi de possession n'a plus de sens pour les
  jeux déjà finis, donc il ne s'applique qu'au backlog).
- **My Year Review** : résumé annuel façon "Wrapped" (jeu le mieux noté, le plus joué, le plus
  rapide, avis le plus long, avec jaquettes), consultable pour n'importe quelle année.

### Grille "Jeux complétés" / "Backlog"
- Jaquettes façon SteamGridDB, curseur de taille des vignettes, filtres par possession et par année.
- Tri d'affichage (chronologique, chronologique inverse, alphabétique, alphabétique inverse) — ce
  tri n'affecte jamais l'ordre réel stocké (issu de votre fichier d'origine), qui reste la
  référence pour les statistiques et les séparateurs d'année. Une flèche discrète sur le bord droit
  rappelle que l'ordre d'origine est conservé.
- Séparateurs d'année (activables/désactivables dans les Options).
- Badges DLC et "Abandonné" directement sur la jaquette.

### Jaquettes
- Recherche multi-sources : Steam Store, [RAWG.io](https://rawg.io/apidocs) et
  [IGDB](https://api-docs.igdb.com/) (clés gratuites optionnelles, à renseigner dans les
  Paramètres — IGDB en particulier élargit beaucoup la couverture aux jeux Nintendo et
  exclusivités console, absents de Steam), et Wikipedia en dernier recours.
- Dossier **`cover_art/`** à la racine du projet : déposez-y vos propres images (ex :
  `persona_5_royal.jpg`, `Persona5Royal.png`...), l'appli les détecte automatiquement par
  correspondance de nom (espaces/tirets/casse ignorés) et vous propose de les utiliser à la place
  ou en complément des résultats en ligne.
- Les jaquettes téléchargées/choisies sont stockées dans `data/covers/`, nommées d'après le titre
  du jeu pour s'y retrouver facilement.
- Toute image récupérée (recherche ou import manuel) est vérifiée avant d'être acceptée
  (protection contre un fichier exécutable déguisé en image).
- **Consentement explicite** : avant la toute première recherche en ligne, l'application vous
  informe des services utilisés et demande votre accord (case à cocher) — voir la section
  [Services externes utilisés](#services-externes-utilisés).

### Avis et notes
- Notes sur 10 avec demi-points (ex : 7.5), affichées avec 10 étoiles (cliquables par moitié).
- Zone d'édition large et épurée, sans retour markdown en direct — juste un grand espace agréable
  pour écrire, avec correction orthographique du navigateur activée. Le gras/italique importés
  depuis l'Excel d'origine restent affichés correctement une fois l'avis enregistré.
- Un jeu fini avec un avis enregistré ne peut pas être renvoyé au backlog par erreur (protection
  contre les fausses manipulations) ; sans avis, un simple bouton (volontairement discret) permet
  de le faire.
- Si l'import ne parvient pas à faire correspondre un avis à un jeu fini (faute de frappe entre
  l'onglet Avis et l'onglet Complété, par exemple), un bandeau d'avertissement le signale dans
  l'application plutôt que de perdre l'avis silencieusement.

### Personnalisation
- Thèmes : Violet, Émeraude, Ambre, Contraste, Rose, Océan, + une couleur d'accent personnalisée
  via color picker.
- Fond d'écran personnalisable (image, gif ou vidéo) avec opacité réglable.
- Langue FR/EN (détectée automatiquement à partir de la langue du système au premier lancement),
  nom du joueur (affiché en haut de l'app et inclus dans les exports), position des boutons
  "Ajouter" / "Jeu au hasard" (début/fin/masqué), renommage libre des onglets.

### Sauvegardes
- Déclenchées uniquement par une action explicite (nouveau jeu enregistré, avis modifié, ou
  import) — pas de sauvegarde périodique en tâche de fond.
- Chaque sauvegarde produit un `.xlsx` et un `.csv` (zip), horodatés et nommés avec votre nom,
  dans un dossier **`backup_backlog/`** à la racine du projet. Seules les 3 dernières versions de
  chaque format sont conservées.
- Restauration possible depuis les Paramètres.

### Tests
53 tests unitaires couvrant l'import/export (marqueurs d'année, formatage riche, avis orphelins),
les statistiques, les sauvegardes, la recherche de jaquettes (multi-source, dossier local,
sanitization d'image) et le remplissage en masse — pour garantir qu'aucune donnée n'est perdue.

## Démarrage rapide

### Windows / Linux (sans Docker)

Prérequis : [Python 3.10+](https://www.python.org/downloads/).

- **Linux / macOS** : ouvrez un terminal dans le dossier de l'application puis lancez :
  ```bash
  ./my_backlog_linux.sh
  ```
- **Windows** : double-cliquez sur `my_backlog_windows.bat` (ou lancez-le depuis une invite de
  commandes).

Le script crée un environnement virtuel, installe les dépendances, puis démarre le serveur et
ouvre automatiquement votre navigateur sur `http://127.0.0.1:5000`.

### Avec Docker

```bash
docker compose up -d --build
```

Puis ouvrez `http://localhost:5000`.

## Services externes utilisés

La recherche de jaquettes peut interroger, uniquement lorsque vous l'utilisez explicitement (et
après avoir donné votre accord) :
- **Steam Store** (store.steampowered.com) — recherche publique, aucune clé requise.
- **RAWG.io** (api.rawg.io) — nécessite une clé API gratuite que vous pouvez renseigner dans les
  Paramètres ; sans clé, cette source est simplement ignorée.
- **IGDB** (api.igdb.com, exploité par Twitch/Amazon) — nécessite un compte développeur Twitch
  gratuit (Client ID + Client Secret) ; offre une bien meilleure couverture des jeux Nintendo et
  exclusivités console que Steam ou RAWG. Sans identifiants, cette source est ignorée.
- **Wikipedia** (en.wikipedia.org) — utilisé en tout dernier recours si les sources précédentes ne
  trouvent rien.

*Steam est une marque de Valve Corporation. RAWG.io, IGDB et Wikipedia appartiennent à leurs
éditeurs respectifs. Les images et métadonnées récupérées via ces services appartiennent à leurs
propriétaires respectifs ; MyBacklog ne les redistribue pas et n'a aucun but commercial — elles
sont uniquement stockées localement, pour votre usage personnel.*

## Où sont mes données ?

- `data/backlog.db`, `data/covers/`, `data/config.json` : base de données, jaquettes, réglages
  (créé automatiquement à côté de `app.py`, ou dans `/app/data` avec Docker).
- `cover_art/` : vos propres jaquettes (à déposer manuellement), à la racine du projet.
- `backup_backlog/` : sauvegardes `.xlsx`/`.csv`, à la racine du projet.

Rien n'est envoyé à un serveur distant, à l'exception des recherches de jaquettes décrites
ci-dessus, et uniquement lorsque vous les déclenchez explicitement.

## Lancer les tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

## Structure du projet

```
mybacklog/
├── app.py                       # Serveur Flask + API REST
├── backend/
│   ├── db.py                     # Schéma SQLite, config, migrations
│   ├── importer.py                # Lecture des CSV/XLSX (+ rich text -> markdown)
│   ├── exporter.py                 # Régénération CSV/XLSX (mise en forme incluse)
│   ├── stats.py                     # Statistiques du dashboard + My Year Review
│   ├── dateutils.py                  # Dérivation mois/année depuis une date exacte
│   ├── covers.py                      # Recherche de jaquettes multi-source + local + sanitization
│   └── backup.py                       # Sauvegardes xlsx/csv déclenchées explicitement
├── static/                       # Frontend (HTML/CSS/JS, sans dépendance de build)
├── tests/                        # Tests unitaires
├── cover_art/                    # Vos jaquettes personnelles (à créer/remplir vous-même)
├── backup_backlog/               # Sauvegardes automatiques (créé au premier enregistrement)
├── Dockerfile / docker-compose.yml
├── my_backlog_linux.sh / my_backlog_windows.bat
└── requirements.txt
```
