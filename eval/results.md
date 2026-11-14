# Evaluation results

- Set: test, rules + Gemini (100 samples)
- Precision: 83.5% (137/164 findings match a labelled error)
- Recall: 95.8% (137/143 labelled errors found)
- Citation accuracy: 83.2% (114/137 matched findings cite the labelled source)
- AI answered: 97/100 samples; failures: AI review unavailable (ServerError). Showing rule checks only. (3)
- Clean samples wrongly flagged: 10/25

## Recall by error type
- accessibility: 11/12
- claim: 23/23
- messaging: 11/12
- outdated_fact: 23/26
- terminology: 50/50
- tone: 19/20

Labelled sources most often cited wrongly: G07 (8), G03 (6), G12 (5), G15 (2), F01 (1)
