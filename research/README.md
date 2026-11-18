# Research pipeline (reproduces every number in the paper)

All code shared with the server lives in `hemosense/` (labels, features, segmentation,
ANFIS, Mamdani, metrics). Scripts here only orchestrate it. Seed = 42 everywhere.

Dataset: Eyes-defy-anemia. Set `HEMOSENSE_DATA_ROOT` to the folder that holds
`India/` and `Italy/` (default: the path on the main laptop). Images never leave
`research/data/` (git-ignored).

```
python -m research.extract_features   # features for expert masks, fuzzy-corrected, Haar ROI  (~4 min)
python -m research.cache_photos       # photos at serving resolution + expert masks          (~3 min, once)
python -m research.live_path_sim      # serving segmenter on simulated user boxes              (~5 min)
python -m research.run_experiment     # 5-fold patient-level CV, baselines, ablations, export (~10 min)
python -m research.cnn_cv             # EfficientNet-B0 baseline on the same folds             (~30 min CPU)
python -m research.seg_check 60       # quick segmenter Dice + speed check
python -m pytest tests -q             # unit + API tests
```

Outputs (`research/results/`):

| File | Content |
| --- | --- |
| `features.csv` | one row per participant, features for every pipeline variant |
| `live_sim_features.csv`, `live_sim_summary.json` | live-path simulation: gate outcome, Dice, features |
| `folds.csv` | the patient-level 5-fold assignment used by every model |
| `oof_<setting>_<model>.csv`, `oof_cnn.csv` | out-of-fold calibrated probabilities |
| `metrics.json` | all reported metrics (AUC + CI, sens/spec + CI, DeLong, ablations, cross-region) |
| `cnn_metrics.json` | CNN baseline metrics |
| `figures/*.png` | ROC curves, membership functions, calibration, feature box plots |

The deployed model `models/anfis.json` is written by `run_experiment.py` (ANFIS trained on
all participants with live-path features; Platt calibration and thresholds from inner 5-fold
out-of-fold predictions).
