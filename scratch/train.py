"""
train.py
Trains Baseline-A (uncorrected images) and Baseline-B (fuzzy-corrected images)
with identical architecture and 2-phase transfer learning fine-tuning.
"""

import argparse
import json
import os
import time

import tensorflow as tf

import config
from data_loader import get_datasets
from model import build_model, unfreeze_top_layers
from evaluate import evaluate_and_save


def train(variant, epochs, lr, aug_strength, dropout, dense_units, head, freeze_backbone=True):
    run_name = f"baseline_{variant}_{head}_{int(time.time())}"
    print(f"[train] Starting run: {run_name}")

    train_ds, val_ds, test_ds, test_df = get_datasets(
        variant=variant, aug_strength=aug_strength, head=head
    )

    model = build_model(
        head=head,
        dropout=dropout,
        dense_units=dense_units,
        freeze_backbone=freeze_backbone,
        lr=lr,
    )

    ckpt_path = os.path.join(config.MODELS_DIR, f"{run_name}_best.keras")
    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            ckpt_path, monitor="val_loss", save_best_only=True, verbose=1
        ),
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=6, restore_best_weights=True
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=3, min_lr=1e-6
        ),
        tf.keras.callbacks.CSVLogger(os.path.join(config.LOGS_DIR, f"{run_name}.csv")),
        tf.keras.callbacks.TensorBoard(log_dir=os.path.join(config.LOGS_DIR, "tb", run_name)),
    ]

    print("\n[train] --- PHASE 1: Training the Head ---")
    history_1 = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=epochs,
        callbacks=callbacks,
    )
    epochs_ran = len(history_1.history["loss"])

    # --- PHASE 2 FINE TUNING ---
    if freeze_backbone:
        print("\n[train] --- PHASE 2: Fine-Tuning the Base Model ---")
        model = unfreeze_top_layers(model, n_layers=20, lr=1e-5)
        
        phase2_callbacks = [
            tf.keras.callbacks.ModelCheckpoint(
                ckpt_path, monitor="val_loss", save_best_only=True, verbose=1
            ),
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=5, restore_best_weights=True
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor="val_loss", factor=0.5, patience=2, min_lr=1e-7
            ),
            tf.keras.callbacks.CSVLogger(os.path.join(config.LOGS_DIR, f"{run_name}_finetune.csv")),
        ]
        
        history_2 = model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=epochs,
            callbacks=phase2_callbacks,
        )
        epochs_ran += len(history_2.history["loss"])

    final_model_path = os.path.join(config.MODELS_DIR, f"{run_name}_final.keras")
    model.save(final_model_path)

    # Evaluate on held-out test set
    metrics = evaluate_and_save(model, test_ds, test_df, run_name, head=head)

    run_meta = {
        "run_name": run_name,
        "variant": variant,
        "epochs_ran": epochs_ran,
        "epochs_requested": epochs,
        "lr": lr,
        "aug_strength": aug_strength,
        "dropout": dropout,
        "dense_units": dense_units,
        "head": head,
        "final_model_path": final_model_path,
        "best_ckpt_path": ckpt_path,
        "test_metrics": metrics,
    }
    with open(os.path.join(config.RESULTS_DIR, f"{run_name}_meta.json"), "w") as f:
        json.dump(run_meta, f, indent=2)

    print(f"[train] Done. Test metrics: {metrics}")
    return run_meta


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=["A", "B"], required=True,
                         help="A = uncorrected images (baseline), B = fuzzy-corrected images (proposed)")
    parser.add_argument("--epochs", type=int, default=config.DEFAULT_EPOCHS)
    parser.add_argument("--lr", type=float, default=config.DEFAULT_LR)
    parser.add_argument("--aug_strength", type=float, default=1.0)
    parser.add_argument("--dropout", type=float, default=0.3)
    parser.add_argument("--dense_units", type=int, default=128)
    parser.add_argument("--head", choices=["regression", "classification"], default=config.DEFAULT_HEAD)
    parser.add_argument("--unfreeze_backbone", action="store_true")
    args = parser.parse_args()

    train(
        variant=args.variant,
        epochs=args.epochs,
        lr=args.lr,
        aug_strength=args.aug_strength,
        dropout=args.dropout,
        dense_units=args.dense_units,
        head=args.head,
        freeze_backbone=not args.unfreeze_backbone,
    )