# Étape 2 — Brouillon des blocs de personas (à relire par le groupe)

Brouillon rédigé par Claude le 27 nov 2026, avant la vérification des sources par le groupe (voir `report/personas_sources_candidates.md`). **Rien n'est encore inscrit dans `config/personas.yaml`.**

Hypothèses retenues en attendant la réponse du groupe (questions 2 à 4 du fichier des sources) :
- objectif « neutre » = **aucune phrase d'objectif** ;
- bloc « santé publique » appuyé sur le cadre conceptuel `decamp2018` ;
- 5 identités non médicales tirées de la liste de rôles de `zheng2024`.

## Principe de rédaction

- **Même structure pour tous les blocs d'un facteur**, pour que deux personas voisines ne diffèrent que par les mots du facteur étudié.
- Phrases courtes et factuelles, sans consigne sur la décision attendue : le bloc décrit la persona, il ne dit pas « hospitalise plus ».
- Persona = `{experience} {specialty} {objective}`, puis une ligne vide, puis la consigne commune.

## A. Expérience

| Bloc | Texte proposé | Sources |
|---|---|---|
| `junior` | You are a junior physician with less than two years of independent clinical practice. | `mcdonald2024` (tranche 0–2 ans), `lawton2019` |
| `senior` | You are a senior physician with more than ten years of independent clinical practice. | `mcdonald2024` (tranche la plus ancienne : plus de 9 ans), `lawton2019` |

## B. Spécialité

| Bloc | Texte proposé | Sources |
|---|---|---|
| `urgentiste` | Your specialty is emergency medicine. | `pines2010`, `smulowitz2024` |
| `generaliste` | Your specialty is family medicine (general practice). | `fiscella2000`, `alam2017` |
| `sante_publique` | Your specialty is public health and preventive medicine, with a focus on the health of the whole population. | `decamp2018` |

Pour `sante_publique`, la fin de la phrase (« with a focus on the health of the whole population ») reprend l'opposition population / patient individuel de `decamp2018`. Sans elle, le bloc ne dit rien de ce qui distingue cette spécialité. Elle rallonge le bloc : c'est au groupe de décider de la garder ou non.

## C. Objectif

| Bloc | Texte proposé | Sources |
|---|---|---|
| `securite` | Your top priority is patient safety: you want to avoid missing a serious condition or sending home a patient who could deteriorate. | `katz2005`, `lawton2019` |
| `couts` | Your top priority is the efficient use of healthcare resources: you want to avoid unnecessary hospital admissions and their costs. | `sabbatini2014`, `hurst2007` |
| `neutre` | *(aucune phrase)* | — |

Variante possible pour `securite`, plus proche de `katz2005` (médecine défensive) : ajouter « and its legal consequences » après « a serious condition ». Je ne l'ai pas retenue, pour que le bloc parle de sécurité du patient et pas de peur des poursuites.

## D. Contrôles

**Sans persona (neutre)** : la consigne commune seule, suivie de la vignette.

**5 identités non médicales.**
- **Liste de départ** : les 58 rôles de la catégorie « other occupations » du fichier `data/role_info.csv` du dépôt de `zheng2024` (github.com/Jiaxin-Pei/Prompting-with-Social-Roles).
- **Rôles retirés** parce qu'ils touchent au soin : `midwife`, `counsellor`, `counselor`, `attendant`. Il reste 54 rôles.
- **Tirage** de 5 rôles avec la graine 42 de `config/experiment.yaml` (`random.Random(42).sample(sorted(pool), 5)`). Le tirage sera refait dans le code, pas écrit à la main.

| id | Rôle tiré | Texte proposé |
|---|---|---|
| R01 | police | You are a police officer. |
| R02 | auctioneer | You are an auctioneer. |
| R03 | accountant | You are an accountant. |
| R04 | scientist | You are a scientist. |
| R05 | collector | You are a collector. |

Points à trancher :
- « police » est passé à « police officer » pour que la phrase soit correcte.
- « collector » est ambigu (collectionneur ou percepteur) : on le garde tel quel, ou on refait le tirage ?
- « scientist » peut être perçu comme proche du raisonnement médical : le garder ou l'exclure ?

## E. Consigne commune (identique pour les 24 conditions)

```text
Below is the record of an emergency department visit. Based only on this record, decide whether the patient should be hospitalized (admitted to this hospital or transferred to another hospital) or not hospitalized.

Answer with a JSON object only, with no other text:
{"decision": "hospitalize"} or {"decision": "do_not_hospitalize"}

Visit record:
{vignette}
```

La définition entre parenthèses reprend notre vérité terrain : admission ou transfert.

## F. Exemples de prompts complets (début seulement)

**F_junior_urgentiste_securite**
```text
You are a junior physician with less than two years of independent clinical practice. Your specialty is emergency medicine. Your top priority is patient safety: you want to avoid missing a serious condition or sending home a patient who could deteriorate.

Below is the record of an emergency department visit. ...
```

**F_senior_sante_publique_neutre**
```text
You are a senior physician with more than ten years of independent clinical practice. Your specialty is public health and preventive medicine, with a focus on the health of the whole population.

Below is the record of an emergency department visit. ...
```

**R03 (accountant)**
```text
You are an accountant.

Below is the record of an emergency department visit. ...
```

**N (sans persona)**
```text
Below is the record of an emergency department visit. ...
```

## G. Longueur des personas

Les personas factorielles font entre environ 20 et 60 mots. Les identités non médicales font 4 ou 5 mots, et la condition sans persona 0. Si l'analyse montre un effet des contrôles, la différence de longueur sera une explication concurrente à mentionner dans le rapport. `src/personas.py` enregistrera la longueur de chaque persona.

## Suite

Une fois le brouillon et les sources validés :
1. Inscrire les blocs, les sources et la règle de tirage dans `config/personas.yaml`, avec l'accord du groupe.
2. Écrire `src/personas.py` et ses tests, selon le plan de l'étape 2.
