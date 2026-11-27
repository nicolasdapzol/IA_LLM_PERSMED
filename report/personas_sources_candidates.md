# Étape 2 — Sources candidates pour les personas (à vérifier par le groupe)

Liste proposée par Claude le 27 nov 2026. **Rien n'est encore inscrit dans `config/personas.yaml`.**
Pour chaque référence : la colonne « Vérifié par Claude » indique ce qui a été contrôlé sur une page source (PMC, ACL Anthology, arXiv, medRxiv ou notice Europe PMC). Les citations sont recopiées de ces pages. **Chaque référence doit être relue par un membre du groupe** (case « Vérifié par » à remplir) avant d'entrer dans le fichier.

## A. Expérience (junior / senior)

| id | Référence | Ce qu'elle appuie | Vérifié par Claude | Vérifié par |
|---|---|---|---|---|
| `mcdonald2024` | McDonald N, Antkowiak PS, Burke R, et al. *Emergency physician resource utilization varies by years of experience.* J Am Coll Emerg Physicians Open. 2024;5:e13162. doi:10.1002/emp2.13162 | Les urgentistes juniors admettent davantage : « More junior EPs tend to order more advanced imaging studies and have a higher propensity to admit patients. » | Notice et résumé (Europe PMC) | |
| `lawton2019` | Lawton R, Robinson O, Harrison R, et al. *Are more experienced clinicians better able to tolerate uncertainty and manage risks? A vignette study of doctors in three NHS emergency departments in England.* BMJ Qual Saf. 2019;28(5):382–388. doi:10.1136/bmjqs-2018-008390 | Étude sur vignettes (90 médecins) : « more experienced clinicians made less risk-averse decisions » ; la tolérance à l'incertitude explique environ un quart de l'effet. | Article complet (PMC6560462) | |

## B. Spécialité (urgentiste / généraliste / santé publique)

| id | Référence | Ce qu'elle appuie | Vérifié par Claude | Vérifié par |
|---|---|---|---|---|
| `pines2010` | Pines JM, Isserman JA, Szyld D, et al. *The effect of physician risk tolerance and the presence of an observation unit on decision making for ED patients with chest pain.* Am J Emerg Med. 2010;28:771–779. doi:10.1016/j.ajem.2009.03.019 | Urgentiste : la tolérance au risque est liée à la décision d'admettre. | Notice et conclusion du résumé (Europe PMC) | |
| `smulowitz2024` | Smulowitz PB, Burke RC, Ostrovsky D, et al. *Clinician Risk Tolerance and Rates of Admission From the Emergency Department.* JAMA Netw Open. 2024;7(2):e2356189. doi:10.1001/jamanetworkopen.2023.56189 | Urgentiste : 691 cliniciens ; effet faible de la tolérance au risque sur l'admission (« a small but statistically significant tendency to admit less than the projected admission rate »). | Article complet (PMC10873771) | |
| `fiscella2000` | Fiscella K, Franks P, Zwanziger J, et al. *Risk aversion and costs: a comparison of family physicians and general internists.* J Fam Pract. 2000;49:12–17. | Généraliste : médecins de famille moins averses au risque que les internistes, coûts plus bas. | **Notice seulement** (Europe PMC, pas de résumé). Contenu non vérifié sur le texte. | |
| `alam2017` | Alam R, Cheraghi-Sohi S, Panagioti M, et al. *Managing diagnostic uncertainty in primary care: a systematic critical review.* BMC Fam Pract. 2017;18:79. doi:10.1186/s12875-017-0650-0 | Généraliste : gestion de l'incertitude en soins primaires ; « There is little empirical evidence on how uncertainty is managed in general practice. » | Article complet (PMC5545872). Attention : l'affirmation « les généralistes répondent à l'incertitude par plus d'adressages » y renvoie à une communication de congrès (Tsiga & Panagopoulou, 2014), pas à un article. | |
| `decamp2018` | DeCamp M, Pomerantz D, Cotts K, et al. *Ethical Issues in the Design and Implementation of Population Health Programs.* J Gen Intern Med. 2018;33(3):370–375. doi:10.1007/s11606-017-4234-4 | Santé publique : opposition entre éthique de santé publique (population) et éthique clinique (patient individuel), tableau 1. Analyse éthique, pas étude empirique. | Article complet (PMC5834965) | |

**Lacunes** : aucune étude trouvée qui compare directement urgentistes et généralistes sur la décision d'hospitaliser, ni qui décrit la décision d'un médecin de santé publique face à un patient individuel. Le bloc « santé publique » reposerait donc sur un cadre conceptuel (`decamp2018`), et pas sur une mesure de comportement. À dire dans le rapport, ou à compléter par le groupe.

## C. Objectif (sécurité / coûts / neutre)

| id | Référence | Ce qu'elle appuie | Vérifié par Claude | Vérifié par |
|---|---|---|---|---|
| `katz2005` | Katz DA, Williams GC, Brown RL, et al. *Emergency Physicians' Fear of Malpractice in Evaluating Patients With Possible Acute Cardiac Ischemia.* Ann Emerg Med. 2005;46(6):525–533. doi:10.1016/j.annemergmed.2005.04.016 | Sécurité / médecine défensive : la peur des poursuites diminue les sorties de patients à faible risque (OR ajusté 0,34) ; « Malpractice fear accounts for significant variability in ED decisionmaking ». | Article complet (PMC7539660) | |
| `sabbatini2014` | Sabbatini AK, Tilburt JC, Campbell EG, et al. *Controlling Health Costs: Physician Responses to Patient Expectations for Medical Care.* J Gen Intern Med. 2014;29(9):1234–1241. doi:10.1007/s11606-014-2898-6 | Coûts : étude qualitative (62 médecins) ; « Physicians often make nuanced trade-offs in clinical practice aimed at efficient resource use ». | Article complet (PMC4139526) | |
| `hurst2007` | Hurst SA, Forde R, Reiter-Theil S, et al. *Physicians' views on resource availability and equity in four European health care systems.* BMC Health Serv Res. 2007;7:137. doi:10.1186/1472-6963-7-137 | Coûts : enquête auprès de 656 généralistes et internistes ; « Physicians are willing to participate in cost-containment decisions ». | Article complet (PMC1995213) | |

Objectif « neutre » : pas de source nécessaire si le bloc est simplement absent ou neutre (voir question 2 ci-dessous).

## D. Personas dans les LLM (introduction du rapport et contrôles)

| id | Référence | Ce qu'elle appuie | Vérifié par Claude | Vérifié par |
|---|---|---|---|---|
| `zheng2024` | Zheng M, Pei J, Logeswaran L, et al. *When "A Helpful Assistant" Is Not Really Helpful: Personas in System Prompts Do Not Improve Performances of Large Language Models.* Findings of EMNLP 2024, pp. 15126–15154. doi:10.18653/v1/2024.findings-emnlp.888 | 162 rôles, dont des rôles non professionnels ; l'effet d'une persona est largement aléatoire. Justifie les **5 personas non médicales** et le contrôle **sans persona**. | Page ACL Anthology (résumé) | |
| `klang2026` | Klang E, Gorenstein A, Omar M, et al. *Personas Shift Clinical Action Thresholds in Large Language Models.* medRxiv, 2026. doi:10.64898/2026.01.01.26343302 | Préprint, non relu par les pairs : 9 personas médicales, 20 LLM, vignettes d'urgence ; comparaison à une référence sans persona ; « Decision-style system prompts reliably change clinical action thresholds in LLMs under fixed evidence ». Travail le plus proche du nôtre. | Page medRxiv (résumé) | |
| `abdullahi2026` | Abdullahi T, Ghosh S, Fraser HS, et al. *The Persona Paradox: Medical Personas as Behavioral Priors in Clinical Language Models.* arXiv:2601.05376, 2026. | Préprint : les personas médicales améliorent le triage en soins critiques mais dégradent les soins primaires ; comparaison avec des personas non médicales. | Page arXiv (résumé) | |

## Écartées ou non vérifiées

- *Seniority of Emergency Physician, Patient Disposition and Outcome Following Disposition* (PMID 27238920, 2016) : page inaccessible, non vérifiée.
- Tsiga & Panagopoulou (2014) : communication de congrès seulement, pas d'article trouvé.

## Questions pour le groupe

1. Valider, retirer ou remplacer chaque référence (case « Vérifié par »).
2. Objectif « neutre » : pas de phrase d'objectif du tout (recommandé : seul le facteur objectif change), ou une phrase neutre explicite (par exemple « You weigh all considerations equally ») ?
3. Bloc « santé publique » : accepter qu'il repose sur un cadre conceptuel (`decamp2018`), ou chercher d'autres sources ?
4. 5 identités non médicales : lesquelles ? Je propose de les tirer de la liste des rôles non professionnels de `zheng2024` (à vérifier dans leur dépôt de données), pour que le choix soit sourcé lui aussi.

Une fois les sources validées : rédaction des 8 blocs en anglais (une phrase chacun), puis `config/personas.yaml` et `src/personas.py` selon le plan de l'étape 2.
