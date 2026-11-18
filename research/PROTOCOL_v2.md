# HemoSense v2: analysis protocol (written 2026-11-16, before any v2 result was computed)

v1 results are final and stay in the paper as the baseline (`research/results/metrics.json`).
This protocol fixes, in advance, what v2 changes, how it is compared and when it is deployed.

## Motivation (from v1, not from v2 results)
- Labels depend on sex (WHO: women < 12 g/dL, men < 13 g/dL) but no v1 model sees sex.
- Colour features shift with camera and light; v1 has no colour reference. Within-region AUC
  differs strongly (India 0.65, Italy 0.87), consistent with acquisition differences.
- v1 ANFIS settings (gradient training on, 3 terms) were fixed by design; v1 ablations
  suggested alternatives, which must not be picked post hoc. v2 picks them inside training folds.

## Changes (H1-H3), each tested alone and all together
- **H1 sex-aware calibration.** Platt layer gets a sex term: p = sigmoid(a*z + b + c*male).
  For fairness every baseline (LogReg, RF, Mamdani via its calibration, CNN is not re-run) gets
  sex too (LogReg/RF: extra binary feature; Mamdani: same calibration layer as ANFIS).
- **H2 sclera white balance.** Search a region above the user's box for bright, low-saturation
  sclera pixels; scale R, G, B so the sclera mean becomes neutral grey (von Kries); then compute
  features. If no sclera is found, fall back to no correction (flag recorded).
- **H3 nested model selection.** Inside each outer training fold, inner 5-fold CV chooses ANFIS
  {gradient training on/off} x {2, 3 terms per input} by inner AUC.

## Fixed evaluation
- Same 215 participants, same outer folds (`research/results/folds.csv`, seed 42), same
  live-path simulation boxes (seed 42).
- Primary endpoint: live-pipeline ANFIS AUC, v2 (H1+H2+H3) vs v1, paired bootstrap (2,000) CI of
  the difference. Secondary: each H alone; sensitivity/specificity at p >= 0.5; within-region AUC;
  all baselines under the same v2 inputs.

## Deployment rule (decided now)
Deploy v2 only if all hold: (1) v2 ANFIS AUC > v1 ANFIS AUC (0.879); (2) lower bound of the
paired 95 % CI of (v2 - v1) > -0.02; (3) at p >= 0.5, specificity >= 0.78 and sensitivity >= 0.72;
(4) all tests pass and the live endpoint smoke test passes. Otherwise v1 stays deployed and v2 is
reported as a negative or inconclusive result.

## Reporting
Every v2 number is reported, including changes that did not help. v1 remains in the paper.
