# HemoSense paper: writing kit

This kit gives you the **facts, numbers, structure and figures**. It deliberately contains
no finished paragraphs: write every sentence yourself, in your own voice, section by section.
Every number below is copied from `research/results/metrics.json`,
`research/results/cnn_metrics.json` or `research/results/live_sim_summary.json`; if you
change a number, re-check it there. Figures are in `paper/figures/`.

Suggested format: IEEE two-column conference style, about 6 pages.

---

## Working title options (pick or adapt)
- Explainable smartphone anemia screening from conjunctiva photographs with an adaptive neuro-fuzzy inference system
- HemoSense: interpretable neuro-fuzzy screening for anemia from eyelid photographs

## Abstract: what it must contain (about 200 words, write it last)
1. Problem in one line (anemia screening needs a blood draw; conjunctival pallor is a known sign).
2. What you built: phone app + server; user-guided segmentation; 4 colour features; zero-order Sugeno ANFIS (3 inputs x 3 terms, 27 rules, 45 parameters); diet guidance.
3. Data and protocol: Eyes-defy-anemia, 215 adults (India 94, Italy 121), WHO sex-specific labels, patient-level 5-fold CV.
4. Main numbers: live-pipeline ANFIS AUC 0.879 (95 % CI 0.829-0.922); at the app's rule sens 0.77 / spec 0.82; statistically level with logistic regression (0.897, DeLong p = 0.079) and a CNN (0.876 vs 0.862 on expert masks, p = 0.62).
5. One-line conclusion: interpretable 45-parameter fuzzy model matches black-box baselines; limits = single dataset, small n.

---

## 1. Introduction (points to cover, in your order)
- Anemia is common and under-diagnosed; a lab test is the reference (cite WHO guidance; verify the 2024 cut-off update).
- Clinicians already inspect the palpebral conjunctiva for pallor; photographs can quantify it [Collings 2016; Suner 2021; Zhao 2024 from `docs/literature_review.md`].
- Gap 1: many reported accuracies are inflated by leakage (augmentation before the split: Ramos-Soto 2025 [12], Appiahene palm [18]).
- Gap 2: deep models are hard to explain; pallor is a graded concept that fits fuzzy sets. Among the studies you reviewed, none apply a trained fuzzy system (ANFIS) to conjunctiva photos. Say "among the studies reviewed", not "first".
- Contributions (make this a numbered list in the paper):
  1. A user-guided segmentation + quality gate for live phone use.
  2. A 45-parameter ANFIS with per-decision rule explanations.
  3. A leakage-free, patient-level evaluation with CIs, DeLong tests, ablations and a cross-region test.
  4. A deployed system (Android app + cloud API) with diet guidance.

## 2. Related work
Use `docs/literature_review.md` (23 papers, already tagged by how far you read them). Three paragraphs:
conjunctiva colour features (EI, HHR, CIELAB); deep learning (CP-AnemiC CNN/ViT about 0.84 AUC under 5-fold CV);
leakage and colour-constancy issues. Only cite papers in that file; mark anything unverified.

## 3. Materials and methods

### 3.1 Dataset (facts)
| Item | Value |
| --- | --- |
| Source | Eyes-defy-anemia, IEEE DataPort, DOI 10.21227/t5s2-4j73 |
| Listed / usable | 218 / 215 |
| Excluded | Italy-93 (no Hb), India-7 and Italy-95 (no palpebral mask) |
| India | 94 patients, 67 anemic (71 %), 39 moderate or severe |
| Italy | 121 patients, 23 anemic (19 %), 14 moderate or severe |
| Total | 215, 90 anemic (42 %), 53 moderate or severe |
| Ages | 19-88 years, all adults |
| Labels | WHO 2011: women < 12.0 g/dL, men < 13.0 g/dL; mild >= 11.0; moderate 8.0-10.9; severe < 8.0; pregnancy not recorded |

Data-quality issues found and fixed (worth a short paragraph; reviewers value it):
1. The earlier pipeline split image files, and each patient folder holds a photo plus three derived crops, so the same eye appeared in training and test. Fixed by one sample per patient.
2. The Italy sheet uses decimal commas; 15 patients had been silently dropped by the old parser.
3. Three mask encodings (alpha-transparent 8/16-bit, white background, partially transparent).

### 3.2 Live pipeline (one figure: the architecture diagram from the prep guide, redrawn by you)
- Input: phone photo + user-drawn box (fractions of the EXIF-rotated photo).
- Quality gate on the box: mean brightness < 0.15 -> too dark; > 25 % clipped pixels -> overexposed; Laplacian variance < 12 (at 320 px width) -> blurry.
- Segmentation: GrabCut seeded by the box (crop with 15 % margin, max side 360 px, 4 iterations), then colour refinement: drop V <= 0.15, specular (V > 0.92 and S < 0.15), S <= 0.15; Otsu split of Gaussian-smoothed (sigma 3) CIELAB a* applied only if the class means differ by > 8 a* units; floor a* >= 8; morphological opening 3x3; keep components >= 25 % of the largest. Reject if fewer than max(150 px, 2 % of box).
- Features on segmented pixels (give the formulas as equations):
  - EI = 100 (log10 mean R - log10 mean G)   [Collings 2016]
  - mean CIELAB a*
  - HHR = share of pixels with hue within +/-15 deg of red and S > 0.30   [Zhao 2024]
  - mean HSV saturation
- Live-path validation: boxes simulated around expert masks (random 10-40 % margin, +/-10 % jitter): Dice vs expert conjunctiva mask median 0.82 (IQR 0.75-0.87), precision 0.86, recall 0.83, 0 rejections out of 215, about 1.2 s per photo on a laptop CPU.

- Safety layer added after the main evaluation (report it as such): (1) **half-moon shape prior**: the kept region must have elongation (length^2/area) >= 2.7, solidity <= 0.85 and width/height >= 1.1; thresholds set just outside the range of all 215 dataset masks (elongation >= 2.9, solidity <= 0.80, w/h >= 1.24 there); (2) **eye check**: bright low-saturation sclera pixels must exist just above the region; (3) box shorter side >= 40 px at 900 px working size ("move closer"). Motivation: in early live tests with arm's-length selfies, a box over the shirt or the nose was analysed as if it were an eyelid.
- Sensitivity analysis with the safety layer on (`research/results_gates_sensitivity/`): 2 of 215 dataset photos rejected (0.9 %); live-pipeline ANFIS AUC 0.879 [0.829-0.922], unchanged; at p >= 0.5 sensitivity 0.727, specificity 0.832. Note for the discussion: removing two patients reshuffles the folds, and the expert-mask ANFIS AUC moved from 0.862 to 0.821 with unchanged features, so single 5-fold estimates on ~200 patients vary by several points (also see the 5x5 repeated CV).

### 3.3 ANFIS (write the equations)
- Inputs: 3 features chosen inside each training fold by greedy forward selection (inner 5-fold logistic-regression AUC).
- Membership: Gaussian, 3 terms per input (Low, Medium, High) -> 27 rules.
- Rule firing w_r = product of memberships; normalised wbar_r; output z = sum_r wbar_r theta_r; p = sigmoid(a z + b) (Platt).
- Parameters: 9 centres + 9 widths + 27 consequents = 45.
- Initialisation: Low centre = median of anemic group, High = median of non-anemic group, Medium = midpoint; consequents by ridge least squares on wbar (Jang's hybrid learning idea).
- Training: Adam (lr 0.01) on binary cross-entropy + L2 (0.01) on consequents; early stopping on a 20 % inner split (patience 60, max 800 epochs), then refit on the full training fold for the chosen number of epochs; rules with mean normalised firing < 0.005 pruned (deployed model keeps 21 of 27 rules).
- Gradients are analytic and verified against finite differences (unit test).
- A second ANFIS (same design) separates moderate-or-severe from the rest to give the grade.

### 3.4 Baselines
- Mamdani (expert rules, EI x a* matrix with an HHR shift, min-max inference, centroid defuzzification, data-derived centres).
- Logistic regression (standardised, 4 features), random forest (300 trees, min leaf 3), majority class.
- CNN: EfficientNet-B0 (ImageNet), 224 px masked palpebral crops, frozen backbone then top-20-layer fine-tuning, light augmentation, early stopping on a 15 % split of the training fold, same 5 folds.

### 3.5 Evaluation protocol
- StratifiedKFold(5, shuffle, seed 42) on region x anemia; identical folds for every model (`research/results/folds.csv`).
- Calibration and thresholds from inner 5-fold out-of-fold predictions on the training fold only.
- Thresholds reported: Youden; highest threshold with >= 85 % sensitivity; and the app's fixed rule p >= 0.5.
- Metrics: AUC with 2,000-sample bootstrap 95 % CI; sensitivity/specificity with Wilson CI; Brier score; ECE; DeLong test vs ANFIS.
- Protocol revision (must be disclosed): the first protocol picked the top-3 features by single-feature AUC; it repeatedly chose the redundant trio a*, EI, saturation. Replaced by greedy selection; both are reported (Table 4).

## 4. Results

### Table 1: main comparison (AUC [95 % CI])
| Model | Expert mask | Live pipeline |
| --- | --- | --- |
| ANFIS (45 params) | 0.862 [0.805-0.913] | 0.879 [0.829-0.922] |
| Mamdani (hand rules) | 0.864 [0.812-0.911] | 0.888 [0.840-0.932] |
| Logistic regression | 0.885 [0.837-0.928] | 0.897 [0.852-0.937] |
| Random forest | 0.872 [0.820-0.919] | 0.879 [0.830-0.924] |
| CNN EfficientNet-B0 | 0.876 [0.831-0.919] | not run |
| Majority class | 0.477 | 0.477 |

DeLong vs ANFIS (live): LogReg p = 0.079, Mamdani p = 0.403, RF p = 0.98. Expert: CNN p = 0.618, LogReg p = 0.138.
Repeated 5 x 5-fold CV (live): ANFIS 0.873 +/- 0.010, LogReg 0.894 +/- 0.001, Mamdani 0.888 +/- 0.001, RF 0.870 +/- 0.006.

### Table 2: operating points, ANFIS live pipeline (pooled out-of-fold)
| Rule | Sensitivity [95 % CI] | Specificity [95 % CI] | TP/FN/TN/FP |
| --- | --- | --- | --- |
| Youden | 0.800 [0.71-0.87] | 0.768 [0.69-0.83] | 72/18/96/29 |
| >= 85 % sensitivity target | 0.867 | 0.768 | |
| p >= 0.5 (app) | 0.767 [0.67-0.84] | 0.816 [0.74-0.87] | 69/21/102/23 |
Calibration (live ANFIS): Brier 0.140, ECE 0.057.

### Table 3: severity grade (app rule)
Moderate-or-severe ANFIS: AUC 0.896 [0.843-0.940]. Three-grade accuracy 0.688; 86.8 % of moderate/severe patients are flagged as anemic (Mild or worse).

| True \ Predicted | Normal | Mild | Moderate-to-Severe |
| --- | --- | --- | --- |
| Normal (n = 125) | 102 | 18 | 5 |
| Mild (n = 37) | 14 | 15 | 8 |
| Moderate-to-Severe (n = 53) | 7 | 15 | 31 |

Point to make: errors are mostly between neighbouring grades; Mild is the hardest class.

### Table 4: ablations (ANFIS AUC, live pipeline unless stated)
| Factor | Setting -> AUC |
| --- | --- |
| Region of interest | Haar automatic 0.770; Haar + fuzzy correction 0.784; user box + segmentation 0.879 |
| Fuzzy illumination correction (expert mask) | off 0.862; on 0.861 |
| Mask extent (expert) | palpebral strip 0.862; whole conjunctiva 0.906 |
| Feature selection | single-feature top-3 0.828; greedy 0.879 |
| Training | least-squares consequents only 0.894; + Adam 0.879 |
| Inputs | 2: 0.887; 3: 0.879; 4: 0.876 |
| Terms per input | 2: 0.891; 3: 0.879 |

### Table 5: cross-region (AUC)
| Train -> test | ANFIS | LogReg | Mamdani |
| --- | --- | --- | --- |
| India -> Italy (live) | 0.909 | 0.899 | 0.904 |
| Italy -> India (live) | 0.687 | 0.750 | 0.750 |
| India -> Italy (expert) | 0.775 | 0.922 | 0.918 |
| Italy -> India (expert) | 0.664 | 0.689 | 0.705 |
Within-region ANFIS (live): India AUC 0.649 [0.53-0.76]; Italy 0.870 [0.76-0.96].

### Figures available (`paper/figures/`)
- `roc_live_pipeline.png`, `roc_expert_palpebral.png`: ROC curves of all models.
- `anfis_membership.png`: learned membership functions of the deployed model.
- `calibration_anfis_live.png`: reliability plot.
- `features_by_class.png`: feature distributions, anemic vs not.
- Also take 2-3 app screenshots (result, "Why this result?", diet) on the phone.

## 5. Discussion: questions your text should answer
- Why does a 45-parameter fuzzy model match logistic regression and a CNN? (few, strong colour features; small n)
- What does interpretability buy in practice? (rule shown per result; clinicians can audit it)
- Why does the whole conjunctiva (0.906) beat the palpebral strip (0.862)? (more pixels, less noise; the live segmenter naturally finds the whole region)
- Why did gradient training not improve AUC over the least-squares start? (small data; most gain is in the structure + initialisation; report honestly)
- Why is India much harder (AUC 0.65 within region)? (high prevalence, narrower Hb range, camera/lighting differences); pooled AUC partly reflects cohort differences.
- Compare with literature numbers (Collings validation sens 57 % / spec 83 %; Suner 72.6 % accuracy; Zhao AUC 0.76; CP-AnemiC AUC about 0.84) with care: different data and protocols.

## 6. Limitations (one paragraph or a short list)
Single public dataset, 215 adults; dataset photos rather than independent phone captures; no colour reference; pregnancy unknown; few severe cases; user must draw a box; protocol revised once (disclosed).

## 7. Conclusion and future work
Sclera-based white balance; U-Net segmentation; CP-AnemiC children; prospective phone study with lab Hb; on-device inference.

## Reproducibility statement (facts)
Code: `hemosense/` + `research/` (see `research/README.md`); seed 42; tests in `tests/`; deployed model `models/anfis.json`.
