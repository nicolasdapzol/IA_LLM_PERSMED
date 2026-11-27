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
pip install -r requirements.txt
pytest                                        # tests unitaires
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
- [ ] **1. Données** (28 nov – 1 déc) : NHAMCS, variables, vignettes, échantillon d'environ 2000 cas, vérification manuelle sur une dizaine
- [ ] **2. Personas** (28 nov – 2 déc, en parallèle de 1) : sources, 18 factorielles + 1 neutre + 5 aléatoires, génération des prompts
- [ ] **3. Inférence et parsing** (2–5 déc) : MedGemma, reprise sur crash, sortie JSON stricte, test de fumée sur 20 vignettes ; mesurer le temps par appel
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
- **Vote majoritaire : sur les 24 personas.** (Règle d'égalité : voir « Points à préciser ».)
- **Variabilité entre personas, mesurée par** :
  - le désaccord par vignette ;
  - l'accord global entre personas ;
  - l'écart de chaque persona aux contrôles (persona neutre et 5 aléatoires) ;
  - le taux d'hospitalisation par persona (et l'effet de chaque facteur : expérience, spécialité, objectif).
  Les formules exactes restent à fixer avant l'étape 5.

## Points à préciser (ne pas deviner)

- Source exacte des données NHAMCS (fichier, année, variables utilisées, variable de décision réelle).
- Règle d'égalité du vote majoritaire (24 personas : une égalité 12–12 est possible).
- Formules exactes des métriques de variabilité (par ex. désaccord = proportion de personas hors majorité, ou entropie).
- Consignes exactes du cours sur le format du rapport, la vidéo et l'usage d'outils d'IA.
