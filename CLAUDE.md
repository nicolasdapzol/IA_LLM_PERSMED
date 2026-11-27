# PERS-RECO — Variabilité des décisions d'un LLM selon la persona médicale

Projet de groupe (3 étudiants, Master 2 IA, cours LLM). Rendu avant le **13 décembre 2026** : code + rapport (format ECAI, LaTeX) + vidéo.

## Objectif scientifique

Mesurer à quel point la décision d'un LLM « médecin » (hospitaliser ou non un patient) varie selon la persona qu'on lui donne dans le prompt.

**Priorité de recherche : la variabilité entre personas.**

**Sous-objectif : la performance des personas**, évaluée de deux façons :
- chaque persona **isolée** ;
- les personas combinées en **vote majoritaire**.

## Choix déjà validés (ne pas les remettre en cause sans demander)

- **Un seul LLM : MedGemma.** Un second modèle uniquement s'il reste du temps.
- **Données : vignettes issues de NHAMCS**, échantillon cible d'environ **2000 vignettes** si c'est raisonnable.
- **Personas construites à partir de la littérature uniquement** (pas de validation par des médecins).
- **24 personas** :
  - 18 en plan factoriel : expérience (junior / senior) × spécialité (urgentiste / généraliste / santé publique) × objectif (sécurité / coûts / neutre) ;
  - 1 persona neutre (contrôle) ;
  - 5 personas aléatoires (contrôle).
- **Démo interactive réelle, hébergée en ligne** (Gradio, Space Hugging Face).
- **Calcul** : Google Colab ou ordinateur portable personnel (Lenovo Legion Pro, GPU local).

## Structure du dépôt (à adapter si besoin)

```
.
├── CLAUDE.md
├── requirements.txt          # dépendances figées, identiques en local et sur Colab
├── config/
│   ├── personas.yaml         # définition des 24 personas + sources bibliographiques
│   └── experiment.yaml       # modèle, température, nb de vignettes, graine, chemins
├── data/                     # données brutes et vignettes (ne pas committer les gros fichiers)
├── src/
│   ├── data.py               # chargement NHAMCS, construction des vignettes
│   ├── personas.py           # génération des prompts à partir de personas.yaml
│   ├── inference.py          # boucle MedGemma, cache, reprise après crash
│   ├── parsing.py            # extraction de la décision depuis la sortie du modèle
│   └── analysis.py           # métriques de variabilité, figures, tableaux
├── tests/
├── results/                  # sorties brutes JSONL + figures + tableaux (régénérables)
├── demo/                     # app Gradio
└── report/                   # sources LaTeX, figures incluses depuis results/
```

## Commandes

À compléter au fur et à mesure que les scripts existent :

```bash
python -m venv .venv && source .venv/bin/activate
pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128   # torch CUDA (GPU)
pip install -r requirements.txt
hf auth login                                 # accès MedGemma (licence acceptée sur Hugging Face)
pytest                                        # tests unitaires
python -m src.parsing --in results/smoke      # re-parser un run sans relancer le modèle
python -m src.data --config config/experiment.yaml   # vignettes -> data/vignettes.jsonl (+ compte rendu, relecture)
python -m src.personas --config config/experiment.yaml   # 24 personas vérifiées -> results/personas_preview.md
python -m src.inference --n 20 --out results/smoke   # test rapide sur petit échantillon
python -m src.inference --n 2000 --out results/full  # run complet
python -m src.analysis --in results/full             # métriques et figures
python demo/app.py                                   # démo locale
```

## Conventions de code

- Python 3, typage et docstrings courtes. Code lisible avant code malin.
- **Reproductibilité** : graine fixée dans `config/experiment.yaml`, jamais en dur dans le code. Les prompts exacts et les paramètres de génération sont enregistrés avec chaque résultat.
- **Aucune valeur en dur** (chemins, nombre de vignettes, hyperparamètres) : tout passe par `config/`.
- **Inférence robuste** : écrire les résultats au fil de l'eau (JSONL), pouvoir reprendre là où on s'est arrêté, car les sessions Colab coupent.
- **Sorties du modèle** : demander un format strict (JSON), et gérer explicitement les sorties mal formées (les compter, ne jamais les ignorer en silence).
- Les résultats et figures du rapport doivent pouvoir être **régénérés par une commande** depuis `results/`.

## Façon de travailler avec Claude Code

- **Toujours proposer un plan avant de coder** et attendre la validation.
- **Une tâche à la fois**, petite et vérifiable. Tester sur un petit échantillon (par ex. 20 vignettes × quelques personas) avant tout run complet.
- Ne jamais lancer le run complet (2000 × 24) sans demande explicite.
- Ne pas modifier `config/personas.yaml` ni les choix scientifiques ci-dessus sans demander : ce sont des décisions du groupe.
- Ne jamais inventer de chiffre, de référence bibliographique ou de nom de colonne NHAMCS : si une information manque, le dire.
- Après chaque étape qui fonctionne, proposer un commit avec un message clair.
- Branche par personne ; ne pas committer sur `main` directement.

## Équipe et organisation

- 3 personnes, au moins 2 h par jour chacune ; bon niveau LaTeX ; débutants en montage vidéo.
- **Répartition des rôles : proposition à valider** (A, B, C = les trois membres, à nommer) :
  - A : données, vignettes et analyse ;
  - B : personas, inférence et parsing ;
  - C : démo, rapport et vidéo.
  Chacun relit le travail d'un autre.

## Plan et état d'avancement

Dates proposées, à ajuster. À mettre à jour à chaque session (cocher, dater, noter les blocages).

- [ ] **0. Cadrage** (27–28 nov) : trancher les « points à préciser », valider les rôles, environnement installé pour les trois
- [x] **1. Données** (28 nov – 1 déc) : NHAMCS, variables, vignettes, échantillon d'environ 2000 cas, vérification manuelle sur une dizaine
  - 27 nov : `src/data.py` + tests ; 2000 vignettes (1000/1000) générées. Libellés CIM-10-CM : fichier CDC `icd10cm_order_2022.txt` à placer dans `data/raw/icd10cm/` (URL dans `config/experiment.yaml`). Relecture manuelle des 10 vignettes de `data/manual_check.md` : validée (27 nov). PR : nicolasdapzol/IA_LLM_PERSMED#1. Limite : 123 libellés RFV sont tronqués (« ... ») dans le fichier Stata comme dans les formats SAS officiels.
- [ ] **2. Personas** (28 nov – 2 déc, en parallèle de 1) : sources, 18 factorielles + 1 neutre + 5 aléatoires, génération des prompts
  - 27 nov : blocs validés (`report/personas_blocks_draft.md`), inscrits dans `config/personas.yaml` ; `src/personas.py` + tests ; identités non médicales tirées (graine 42) : police officer, auctioneer, accountant, scientist, collector. Reste : vérification des 12 références par le groupe (champ `verified_by`, liste dans `report/personas_sources_candidates.md`).
- [ ] **3. Inférence et parsing** (2–5 déc) : MedGemma, reprise sur crash, sortie JSON stricte, test de fumée sur 20 vignettes ; mesurer le temps par appel
  - 27 nov : `src/inference.py`, `src/parsing.py` + tests. MedGemma 1.5 raisonne avant de répondre (`<unused94>thought … <unused95>`). Deux modes dans la config (`--mode`). Tests de fumée 20 × 24 : `no_thinking` (raisonnement vide pré-rempli) 0,107 s/appel, 0 invalide, mais 1,9 % d'hospitalisation (désaccord moyen 0,019) ; `thinking` 8,5 s/appel (~114 h pour 2000 × 24), 1 sortie tronquée sur 480, 74 % d'hospitalisation (désaccord moyen 0,158). **Choix du mode et de la taille d'échantillon à trancher par le groupe.**
- [ ] **4. Run complet** (5–8 déc) : 2000 × 24, en local ou sur Colab ; réduire l'échantillon avant de lancer si le temps estimé est trop long
- [ ] **5. Analyse** (8–10 déc) : variabilité entre personas (priorité), performance de chaque persona isolée, puis en vote majoritaire ; figures régénérables
- [ ] **6. Démo** (5–10 déc, en parallèle de 4–5) : Gradio, Space Hugging Face
- [ ] **7. Rapport** (1–12 déc, au fil de l'eau) : squelette LaTeX dès le début
- [ ] **8. Vidéo** (9–12 déc) : script, enregistrement, montage
- [ ] **9. Livraison** (12 déc, marge d'un jour avant le 13) : relecture croisée, tout se régénère depuis le dépôt

Dépendances : 1 et 2 sont indépendantes ; 3 a besoin des deux (code démarrable avec des données provisoires) ; 5 dépend des décisions de l'étape 0 (métrique, vérité terrain, règle du vote).

## Décisions de cadrage (27 nov 2026)

- **Décision du LLM : binaire**, hospitaliser / ne pas hospitaliser.
- **Vérité terrain : la décision réelle enregistrée dans NHAMCS.**
- **Vote majoritaire : sur les 24 personas.** En cas d'égalité (12–12), on retient « hospitaliser » (décision prudente). Compter et rapporter le nombre d'égalités.
- **Variabilité entre personas, mesurée par** :
  - le désaccord par vignette ;
  - l'accord global entre personas ;
  - l'écart de chaque persona aux contrôles (persona neutre et 5 aléatoires) ;
  - le taux d'hospitalisation par persona (et l'effet de chaque facteur : expérience, spécialité, objectif).
  Les formules exactes restent à fixer avant l'étape 5.

## Données NHAMCS (décidé le 27 nov 2026)

- **Source : NHAMCS, fichier des urgences (ED), année 2022** (dernière année de la survey). Fichier `ed2022.zip` et documentation `doc22-ed-508.pdf`, sur le FTP du CDC (`https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/NHAMCS/`). Fichiers SAS et Stata ; à convertir en CSV avec Python. Ne pas committer les données.
- **Variables retenues pour les vignettes** (noms issus de la documentation 2022, **à vérifier sur le fichier réel avant de coder**) :
  - patient : `AGE`, `SEX` ;
  - constantes initiales : `TEMPF`, `PULSE`, `RESPR`, `BPSYS`, `BPDIAS`, `POPCT` ;
  - motif de consultation : `RFV1` à `RFV5` ;
  - blessures : `INJPOISAD`, `INJURY72`, `INTENT15`, `INJURY_ENC`, `CAUSE1` ;
  - maladies chroniques : `ASTHMA`, `CANCER`, `CHF`, `CAD`, `COPD`, `CKD`, `ESRD`, `HTN`, `DIABTYP0/1/2`, `DEPRN`, `OBESITY`, `HYPLIPID`, `ALZHD`, `CEBVD`, `ETOHAB`, `SUBSTAB`, `EDHIV`, `OSA`, `OSTPRSIS`, `HPE` ;
  - diagnostics du médecin : `DIAG1` à `DIAG5` (et `PRDIAG1` à `PRDIAG5` si utile) ;
  - examens : variables de services diagnostiques (biologie, `EKG`, tests, imagerie).
- **Colonnes vérifiées sur le fichier réel (27 nov 2026, `df.columns`, 913 colonnes)** : toutes les variables retenues ci-dessus existent sous ces noms exacts. Le fichier contient aussi : `INJURY`, `CAUSE2`, `CAUSE3` (blessures), `RFV13D`, `RFV23D`, `RFV33D`, `RFV43D`, `RFV53D` (variantes des motifs de consultation ; **à examiner dans la documentation avant de choisir entre `RFV1`–`RFV5` et ces colonnes**), `TOTCHRON`, `NOCHRON`, `EPISODE`, `IMMEDR`, `PAINSCALE` (non retenues pour l'instant).
- **Variables exclues des vignettes** : tout ce qui révèle l'issue ou l'hospitalisation (`ADMIT`, `ADMTPHYS`, `LOS`, `HDDIAG*`, `HDSTAT`, `ADISP`, `OBSSTAY`, `STAY24`, `BOARDED`, `LOV`) et les variables d'issue de la visite (`NODISP`, `NOFU`, `RETRNED`, `RETREFFU`, `OBSDIS`, `TRANNH` et toutes les colonnes d'issue listées plus haut), ainsi que `NUMGIV`, `NUMDIS`, `GPMED1` à `GPMED30` (médicaments donnés ou prescrits), les gestes, médicaments, intervenants et variables du service (non retenus par le groupe).
- **Choix assumé à justifier dans le rapport** : les diagnostics du médecin et les examens sont enregistrés pendant ou à la fin de la visite ; les inclure rend la tâche plus facile que celle d'un médecin au moment de la décision. Le dire explicitement dans les limites.
- **Définition de la décision réelle (vérité terrain)** : « hospitalisation » = `ADMITHOS` **ou** `OBSHOS` (observation puis hospitalisation) **ou** transfert vers un autre hôpital (`TRANOTH`, `TRANPSYC`) (confirmé par le groupe). `TRANNH` (retour ou transfert en maison de retraite) n'est pas un transfert au sens de cette définition. Les issues ambiguës sont exclues (voir « Décisions complémentaires »).
- Conditions d'usage du fichier : usage statistique uniquement, pas de ré-identification, pas de croisement avec d'autres données identifiables ; les poids (`PATWT`) sont nécessaires pour des estimations nationales (à mentionner dans le rapport).

## Décisions complémentaires (27 nov 2026)

- **Issues ambiguës : exclues du jeu de vignettes** (`LWBS`, `LBTC`, `LEFTAMA`, `DOA`, `DIEDED`, `OTHDISP`, et valeurs manquantes sur les variables d'issue). Compter et rapporter le nombre de visites exclues.
- **Tirage : échantillon stratifié 50/50**, soit environ 1000 vignettes « hospitalisation » et 1000 « non hospitalisation » (graine dans `config/experiment.yaml`, poids non utilisés). Conséquences à écrire dans le rapport : la prévalence de l'échantillon n'est pas celle de la réalité ; la référence naïve est 50 % ; utiliser des métriques adaptées (sensibilité, spécificité, exactitude équilibrée) plutôt que la seule exactitude.
- **Désaccord par vignette** (métrique de variabilité principale) : pour une vignette, soit `p` la proportion des 24 personas qui répondent « hospitaliser » ; **désaccord = min(p, 1 − p)** (proportion de personas hors de la majorité, entre 0 et 0,5). L'accord global (kappa de Fleiss), l'écart aux contrôles et le taux d'hospitalisation par persona restent des mesures complémentaires.

## Décisions sur les personas (27 nov 2026)

- **Construction par blocs** : une persona factorielle = phrase « expérience » + phrase « spécialité » + phrase « objectif ». Deux personas voisines ne diffèrent que d'un bloc. 8 blocs à rédiger et sourcer (2 + 3 + 3).
- **Contrôle neutre = aucune persona** : le prompt contient seulement la consigne commune et la vignette.
- **5 personas aléatoires = identités non médicales** (par exemple enseignant, cuisinier), pour mesurer l'effet d'une persona sans compétence médicale.
- **Sortie du modèle : décision seule**, en JSON (`hospitalize` / `do_not_hospitalize`), sans justification.
- **Langue : anglais**, comme les vignettes.
- **Sources** : Claude propose des références candidates (avec lien ou DOI et passage justificatif) ; le groupe vérifie chacune avant de l'inscrire dans `config/personas.yaml`.

## Décisions sur l'inférence (27 nov 2026)

- **Modèle : `google/medgemma-1.5-4b-it`** (accès soumis à licence sur Hugging Face ; révision exacte figée dans la config).
- **Décodage glouton** (`do_sample=False`), un appel par couple (vignette, persona) : la variabilité mesurée vient des personas, pas du hasard.
- **Score continu enregistré** : probabilité de « hospitalize » face à « do_not_hospitalize » au moment de la décision.
- **Sorties invalides** : pas de nouvel essai ; comptées comme manquantes et rapportées (par persona).
- **Test de fumée : 20 vignettes (10/10) × 24 personas** = 480 appels, avant tout run complet.

## Consignes du cours (source : `report/consignes.md`, résumé)

**Partie 1 : vidéo de démonstration (5 minutes)**
- **Sans aucun son** : tout passe par des animations, des sous-titres ou des mises en évidence visuelles.
- **Publique** (par exemple sur YouTube), avec le lien déposé sur TOMUSS.
- Elle commence par : nom du projet, date, nom du cours, noms des étudiants.
- Structure libre ; pour un prototype : introduction, but, fonctionnalités principales (avantages, innovations), développement (architecture, techniques, technologies), démonstration.

**Partie 2 : code et rapport**
- Rapport au **format ECAI 2025, piste « démonstration »** (gabarit LaTeX sur le site de l'appel à contributions ECAI 2025). Conseil de l'enseignant : regarder les actes ECAI 2025 pour la structure et le contenu.
- Rédigé sur **Overleaf**, avec l'enseignant invité sur le projet (adresse dans `report/consignes.md`).
- **3 pages maximum + 1 page de références au plus.**
- Dépôt sur **TOMUSS** d'**un seul ZIP** : PDF du rapport + code source, avant la date limite. Le rapport doit contenir les **liens vers le code à jour et vers la vidéo**.
- Pour toute question : contacter directement l'enseignant coordinateur.

Conséquences pour le projet : la démo interactive en ligne est au centre du rapport et de la vidéo ; le rapport est très court (3 pages), donc résultats et figures choisis avec soin ; la vidéo se prépare comme des diapositives animées sous-titrées.

## Points à préciser (ne pas deviner)

- Règles sur l'usage d'outils d'IA : **non précisées** dans `report/consignes.md` ; à demander à l'enseignant si nécessaire.
- Date et heure exactes de la limite de dépôt sur TOMUSS (le 13 décembre 2026 est la date retenue par le groupe).
