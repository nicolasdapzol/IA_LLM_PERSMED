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
- **Répartition des rôles : à décider.** (À remplir : qui fait données/personas, inférence/analyse, démo/rapport/vidéo.)

## État d'avancement

À mettre à jour à chaque session :

- [ ] Chargement NHAMCS et construction des vignettes
- [ ] Définition des 24 personas (avec sources)
- [ ] Inférence MedGemma sur petit échantillon
- [ ] Parsing des décisions + tests
- [ ] Run complet
- [ ] Métriques de variabilité et figures
- [ ] Performance par persona isolée et en vote majoritaire
- [ ] Démo Gradio en ligne
- [ ] Rapport LaTeX
- [ ] Vidéo

## Points à préciser (ne pas deviner)

- Source exacte des données NHAMCS (fichier, année, variables utilisées).
- Définition précise de la « décision » (hospitalisation oui/non, ou plusieurs classes ?).
- Métrique(s) de variabilité retenue(s).
- Référence (« vérité terrain ») pour évaluer la performance, et règle du vote majoritaire (toutes les personas ou un sous-ensemble, gestion des égalités).
- Consignes exactes du cours sur le format du rapport, la vidéo et l'usage d'outils d'IA.
