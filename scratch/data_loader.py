"""
data_loader.py
Loads the three split manifests dataset_preparation.py produced.
Enhanced with:
  1. Cross-machine automatic path resolution (works on any teammate's machine).
  2. Optional conjunctival ROI filtering (prioritizes palpebral and forniceal crops).
  3. Region-Stratified Balancing (equalizes Anemic vs Normal 1:1 independently for India
     and Italy, preventing the model from associating Indian demographic tone with anemia).
  4. Robust multi-sensor color & lighting augmentations.
"""

import os
import numpy as np
import pandas as pd
import tensorflow as tf

import config


def _resolve_path(raw_path, variant="A"):
    """
    If the path in the CSV belongs to another machine (e.g. C:\\Users\\MCS.DESKTOP-744KNRC\\...),
    dynamically remaps it to the local config.DATASET_ROOT or config.FUZZY_ROOT.
    """
    if os.path.exists(raw_path):
        return raw_path

    clean = raw_path.replace("\\", "/")
    target_root = config.FUZZY_ROOT if variant == "B" else config.DATASET_ROOT
    folder_name = os.path.basename(target_root)

    if folder_name in clean:
        parts = clean.split(folder_name + "/")
        if len(parts) > 1:
            remapped = os.path.join(target_root, parts[1].replace("/", os.sep))
            if os.path.exists(remapped):
                return remapped

    for reg in ["India", "Italy"]:
        if f"/{reg}/" in clean:
            rel = clean.split(f"/{reg}/")[1]
            remapped = os.path.join(target_root, reg, rel.replace("/", os.sep))
            if os.path.exists(remapped):
                return remapped

    return raw_path


def load_split(split, variant="A"):
    """
    split: "train" | "val" | "test"
    variant: "A" -> raw images, "B" -> fuzzy-corrected images
    Returns (dataframe, path_column_name)
    """
    csv_path = config.SPLIT_CSVS_FUZZY[split] if variant == "B" else config.SPLIT_CSVS[split]
    if not os.path.exists(csv_path):
        hint = "Run build_fuzzy_dataset.py first." if variant == "B" else \
               "Run dataset_preparation.py first (or check config.DATASET_ROOT)."
        raise FileNotFoundError(f"{csv_path} not found. {hint}")

    df = pd.read_csv(csv_path)
    path_col = "fuzzy_path" if variant == "B" else "image_path"

    if path_col not in df.columns:
        raise KeyError(f"'{path_col}' column not found in {csv_path}. "
                        f"Available columns: {list(df.columns)}")

    df = df[df[path_col].notna() & (df[path_col] != "")].copy()

    # Dynamically resolve paths across different machines
    df[path_col] = df[path_col].apply(lambda p: _resolve_path(p, variant=variant))

    # Optional: Filter to conjunctival ROIs only (_forniceal and _palpebral)
    # This prevents the CNN from learning skin melanin / facial background
    if getattr(config, "FILTER_CONJUNCTIVA_ROIS", False):
        roi_mask = df[path_col].str.lower().apply(
            lambda x: ("forniceal" in x or "palpebral" in x)
        )
        if roi_mask.sum() > 0:
            orig_n = len(df)
            df = df[roi_mask].reset_index(drop=True)
            print(f"[data_loader] Filtered {split} ({variant}) to {len(df)}/{orig_n} conjunctiva ROIs.")

    exists_mask = df[path_col].apply(os.path.exists)
    n_missing = int((~exists_mask).sum())
    if n_missing:
        print(f"[data_loader] WARNING: {n_missing}/{len(df)} images in {os.path.basename(csv_path)} "
              f"not found on disk; dropping them from this run.")
    df = df[exists_mask].reset_index(drop=True)

    if df.empty:
        raise RuntimeError(f"No usable rows left for split='{split}', variant='{variant}' "
                            f"after checking {path_col} on disk. Check config.DATASET_ROOT / FUZZY_ROOT.")
    return df, path_col


def _decode_and_resize(path, label):
    img = tf.io.read_file(path)
    img = tf.image.decode_image(img, channels=config.CHANNELS, expand_animations=False)
    img.set_shape([None, None, config.CHANNELS])
    img = tf.image.resize(img, config.IMG_SIZE)
    img = tf.cast(img, tf.float32) / 255.0
    return img, label


def _augment(img, label, strength=1.0):
    """
    Robust color and geometric augmentations to enforce invariance to
    smartphone sensor differences and ambient illumination shifts.
    """
    img = tf.image.random_flip_left_right(img)
    img = tf.image.random_flip_up_down(img)

    # Ambient brightness variations
    img = tf.image.random_brightness(img, max_delta=0.15 * strength)

    # Dynamic contrast range
    lo = max(0.1, 1.0 - 0.25 * strength)
    hi = 1.0 + 0.25 * strength
    img = tf.image.random_contrast(img, lower=lo, upper=hi)

    # Smartphone white balance & sensor color shift invariance
    img = tf.image.random_saturation(img, lower=lo, upper=hi)
    img = tf.image.random_hue(img, max_delta=0.03 * strength)

    img = tf.clip_by_value(img, 0.0, 1.0)
    return img, label


def _hgb_to_class_index(hgb_value):
    """Convert a hemoglobin float to an integer class index (0-3)."""
    if hgb_value <= 7.0:
        return 0  # Severe
    elif hgb_value <= 10.0:
        return 1  # Moderate
    elif hgb_value <= 12.0:
        return 2  # Mild
    else:
        return 3  # Normal


def balance_dataset_by_region(df, label_col=config.LABEL_COL, region_col=config.REGION_COL):
    """
    Region-Stratified Balancing:
    Balances Anemic (Hb <= 12.0) vs Normal (Hb > 12.0) independently WITHIN each region.
    Prevents the CNN from associating Indian skin tone or ambient lighting with Anemia.
    """
    balanced_subsets = []
    print("\n[data_loader] --- Applying Region-Stratified Balancing ---")

    for region in sorted(df[region_col].unique()):
        rdf = df[df[region_col] == region]
        anemic = rdf[rdf[label_col] <= 12.0]
        normal = rdf[rdf[label_col] > 12.0]

        n_anemic = len(anemic)
        n_normal = len(normal)

        target_size = max(n_anemic, n_normal)

        if n_anemic < target_size and n_anemic > 0:
            upsampled_anemic = anemic.sample(target_size, replace=True, random_state=config.SEED)
        else:
            upsampled_anemic = anemic

        if n_normal < target_size and n_normal > 0:
            upsampled_normal = normal.sample(target_size, replace=True, random_state=config.SEED)
        else:
            upsampled_normal = normal

        reg_balanced = pd.concat([upsampled_anemic, upsampled_normal], ignore_index=True)
        balanced_subsets.append(reg_balanced)

        print(f"  [{region}] Prior: Anemic={n_anemic}, Normal={n_normal} -> Balanced: {len(reg_balanced)} (50% Anemic, 50% Normal)")

    balanced_df = pd.concat(balanced_subsets, ignore_index=True)
    balanced_df = balanced_df.sample(frac=1.0, random_state=config.SEED).reset_index(drop=True)
    print(f" -> Total balanced train size: {len(balanced_df)} images (Prior probability P(Anemic|Region) = 0.5)\n")
    return balanced_df


def make_dataset(df, path_col, training=False, aug_strength=1.0, batch_size=config.BATCH_SIZE,
                  label_col=config.LABEL_COL, head="regression"):
    paths = df[path_col].values.astype(str)

    if head == "classification":
        labels = np.array(
            [_hgb_to_class_index(v) for v in df[label_col].values],
            dtype=np.int32
        )
    else:
        labels = df[label_col].values.astype(np.float32)

    ds = tf.data.Dataset.from_tensor_slices((paths, labels))
    ds = ds.map(_decode_and_resize, num_parallel_calls=tf.data.AUTOTUNE)

    if training:
        ds = ds.shuffle(buffer_size=min(len(df), 2000), seed=config.SEED)
        ds = ds.map(lambda x, y: _augment(x, y, aug_strength), num_parallel_calls=tf.data.AUTOTUNE)

    ds = ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)
    return ds


def get_datasets(variant="A", aug_strength=1.0, batch_size=config.BATCH_SIZE, head="regression"):
    """
    Returns train_ds, val_ds, test_ds, test_df.
    """
    train_df, path_col = load_split("train", variant)
    val_df, _ = load_split("val", variant)
    test_df, _ = load_split("test", variant)

    # Apply Region-Stratified Balancing during training
    if getattr(config, "REGION_STRATIFIED_BALANCE", True):
        train_df = balance_dataset_by_region(train_df)

    train_ds = make_dataset(train_df, path_col, training=True, aug_strength=aug_strength, batch_size=batch_size, head=head)
    val_ds   = make_dataset(val_df,   path_col, training=False, batch_size=batch_size, head=head)
    test_ds  = make_dataset(test_df,  path_col, training=False, batch_size=batch_size, head=head)

    return train_ds, val_ds, test_ds, test_df


if __name__ == "__main__":
    train_ds, val_ds, test_ds, test_df = get_datasets(variant="A")
    for x, y in train_ds.take(1):
        print("batch image shape:", x.shape, "batch label shape:", y.shape)
    print("\nTest set severity_class breakdown:")
    print(test_df[config.SEVERITY_COL].value_counts())