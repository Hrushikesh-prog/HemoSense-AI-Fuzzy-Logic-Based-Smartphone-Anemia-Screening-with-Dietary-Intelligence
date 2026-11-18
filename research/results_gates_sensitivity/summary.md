# Results summary (2026-11-16)

Source files: `metrics.json`, `cnn_metrics.json`, `live_sim_summary.json` in this folder.
Protocol: 215 participants, one sample each, patient-level StratifiedKFold(5, seed 42).

| Model | AUC expert mask | AUC live pipeline |
| --- | --- | --- |
| ANFIS (45 params) | 0.862 [0.805-0.913] | 0.879 [0.829-0.922] |
| Mamdani | 0.864 [0.812-0.911] | 0.888 [0.840-0.932] |
| Logistic regression | 0.885 [0.837-0.928] | 0.897 [0.852-0.937] |
| Random forest | 0.872 [0.820-0.919] | 0.879 [0.830-0.924] |
| CNN EfficientNet-B0 | 0.876 [0.831-0.919] | - |

- App rule (calibrated p >= 0.5), live ANFIS: sensitivity 0.767 [0.67-0.84], specificity 0.816 [0.74-0.87].
- DeLong vs ANFIS (live): LogReg p = 0.079, Mamdani p = 0.403, RF p = 0.98; CNN vs ANFIS (expert) p = 0.618.
- Moderate-or-severe ANFIS AUC 0.896; three-grade accuracy 0.688.
- Live segmentation Dice vs expert union mask: median 0.82 (IQR 0.75-0.87), 0/215 rejected.
- Within-region ANFIS (live): India 0.649, Italy 0.870. Cross-region: India->Italy 0.909, Italy->India 0.687.
- Protocol revision disclosed: univariate top-3 feature selection 0.828 -> greedy forward 0.879.

Full tables: `paper/WRITING_KIT.md`.
