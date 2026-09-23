"""
config.py
Central configuration for Phase 3 (CNN Hemoglobin Estimation).
Wired directly to your teammates' Phase 1/2 output:
  - dataset_preparation.py already produced train_split.csv / val_split.csv / test_split.csv
    with columns: image_path, hemoglobin_level, region, severity_class
  - anemia_pipeline.py has apply_fuzzy_correction(roi_bgr) — Phase 2's fuzzy color correction.
    build_fuzzy_dataset.py (this folder) imports it directly and applies it to every image
    referenced in the three split CSVs, so Baseline-B trains on real Phase-2 output rather
    than a re-implementation.
Run order:
    1. dataset_preparation.py   (already run by your teammate — produces the 3 split CSVs)
    2. build_fuzzy_dataset.py   (this project — produces *_fuzzy.csv with a fuzzy_path column)
    3. build_lighting_buckets.py (this project — synthetic lighting robustness test set, step 3.6)
    4. train.py / tune.py / quantize.py / cross_validate.py
"""
import os

# ---- Paths ----
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Folder that contains anemia_pipeline.py (Phase 2's fuzzy correction code).
PIPELINE_DIR = PROJECT_ROOT

# Dataset root: auto-detects path across teammates' machines
candidate_paths = [
    os.path.abspath(os.path.join(PROJECT_ROOT, "..", "dataset", "datasetanemia")),
    os.path.abspath(os.path.join(PROJECT_ROOT, "dataset", "datasetanemia")),
    r"C:\Users\ajite\Downloads\project\HemoSense AI Fuzzy Logic-Based Smartphone Anemia Screening with Dietary Intelligence\dataset\datasetanemia",
    r"C:\Users\MCS.DESKTOP-744KNRC\Documents\PROJECTS\HemoSense AI Fuzzy Logic-Based Smartphone Anemia Screening with Dietary Intelligence\dataset\datasetanemia",
]

DATASET_ROOT = None
for p in candidate_paths:
    if os.path.exists(p):
        DATASET_ROOT = p
        break

if DATASET_ROOT is None:
    DATASET_ROOT = candidate_paths[0]  # Fallback to local relative path

# Where fuzzy-corrected copies get written (mirrors DATASET_ROOT's India/<n>/... structure)
FUZZY_ROOT = os.path.join(os.path.dirname(DATASET_ROOT), "datasetanemia_fuzzy")

# Where synthetic lighting-perturbed test images get written (step 3.6)
LIGHTING_BUCKETS_ROOT = os.path.join(os.path.dirname(DATASET_ROOT), "datasetanemia_lighting_buckets")

# The three split manifests dataset_preparation.py already generated
SPLIT_CSVS = {
    "train": os.path.join(DATASET_ROOT, "train_split.csv"),
    "val": os.path.join(DATASET_ROOT, "val_split.csv"),
    "test": os.path.join(DATASET_ROOT, "test_split.csv"),
}

# After build_fuzzy_dataset.py runs, these enriched manifests (with a fuzzy_path column) exist
SPLIT_CSVS_FUZZY = {k: v.replace(".csv", "_fuzzy.csv") for k, v in SPLIT_CSVS.items()}

# After build_lighting_buckets.py runs, this manifest exists (test-only, for step 3.6)
LIGHTING_BUCKETS_CSV = os.path.join(PROJECT_ROOT, "results", "test_lighting_buckets.csv")

# ---- Column names actually produced by dataset_preparation.py ----
LABEL_COL = "hemoglobin_level"
SEVERITY_COL = "severity_class"
REGION_COL = "region"

# Columns evaluate.py will try to break results down by, if present in a given manifest
BREAKDOWN_COLUMNS = [SEVERITY_COL, REGION_COL, "lighting_bucket"]

MODELS_DIR = os.path.join(PROJECT_ROOT, "saved_models")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
for d in (MODELS_DIR, LOGS_DIR, RESULTS_DIR):
    os.makedirs(d, exist_ok=True)

# ---- Image / model ----
IMG_SIZE = (224, 224)          # MobileNetV2 / EfficientNet-Lite default
CHANNELS = 3
BATCH_SIZE = 16                 # small dataset (560 train images) — smaller batch trains more stably
SEED = 42

# ---- Training defaults (overridden by tune.py during 3.4) ----
DEFAULT_LR = 1e-4
DEFAULT_EPOCHS = 40
DEFAULT_HEAD = "regression"    # or "classification" to predict severity_class instead

# ---- Backbone choice ----
BACKBONE = "efficientnet_lite"  # "mobilenetv2" | "efficientnet_lite"

# ---- Loss choice ----
# Huber loss is far more robust to lighting variations/outliers than MSE
LOSS_FUNCTION = "huber"         # "huber" | "mse"

# ---- Domain Adaptation & India Dataset Balancing Strategy ----
# 1. Balance anemic vs normal WITHIN each region so the model doesn't associate "India" with "Anemia"
REGION_STRATIFIED_BALANCE = True

# 2. Filter dataset to true conjunctival ROIs (_forniceal and _palpebral), ignoring full-face/eye JPGs
# where skin melanin confuses the CNN
FILTER_CONJUNCTIVA_ROIS = True

# ---- Anemia severity buckets — must match dataset_preparation.py's pd.cut labels exactly ----
ANEMIA_BUCKETS = {
    "Severe": (0, 7.0),
    "Moderate": (7.0, 10.0),
    "Mild": (10.0, 12.0),
    "Normal": (12.0, 30.0),
}