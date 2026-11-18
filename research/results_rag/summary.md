# RAG vs no-RAG: Dietary Intelligence

Index: `models\rag_index.json`, top-k = 5. Profiles: 20. Same model and prompt in both arms.

| Metric | No RAG | RAG |
|---|---|---|
| Guideline checklist coverage (mean ± SD) | 0.95 ± 0.09 | 0.98 ± 0.05 |
| Answers citing a guideline source | 0% | 95% |
| Citations per answer (mean) | 0.0 | 1.9 |
| Invalid citations (total) | 0 | 0 |
| Disclaimer present | 100% | 100% |
| Model(s) | bedrock:deepseek.v3-v1:0 | bedrock:deepseek.v3-v1:0 |

Paired coverage difference (RAG − no RAG): mean +0.030; RAG better on 5, worse on 2, tied on 13 profiles.

Coverage = share of the applicable checklist items mentioned (keyword match; see CHECKLIST in research/rag_eval.py). Spot-check outputs.jsonl before reporting.

## Limitations (read before reporting)
- The corpus is a single 7-page article (Khurana et al., Indian Pediatrics 2024, on the WHO 2024 Hb
  cut-offs). It covers diagnosis thresholds, not diet, so retrieval can ground severity/referral
  statements but not food advice.
- "Invalid citations = 0" only means every [S#] pointed to a retrieved excerpt. A manual spot-check found
  citations attached to diet claims the excerpt does not support (e.g. a vitamin C pairing tip cited to
  an excerpt about iron fortification). Citation faithfulness was not measured and should not be claimed.
- Coverage gain (+0.03) is small, near the ceiling (0.95 without RAG), and not tested for significance
  with 20 profiles. Report it as "no meaningful difference" in checklist coverage.
- Valid next step: add diet-focused Indian sources (ICMR-NIN Dietary Guidelines 2024, Anemia Mukt Bharat)
  and score citation support per claim.
