"""
model.py
Step 3.1 — Baseline CNN design via transfer learning.
Supports MobileNetV2 or EfficientNet-Lite (B0) backbone.
Configured with Huber loss for robust regression across diverse demographic/lighting conditions.
"""

import tensorflow as tf
from tensorflow.keras import layers, models

import config


def _get_backbone(name, input_shape):
    if name == "mobilenetv2":
        base = tf.keras.applications.MobileNetV2(
            input_shape=input_shape, include_top=False, weights="imagenet"
        )
        preprocess = tf.keras.applications.mobilenet_v2.preprocess_input
    elif name == "efficientnet_lite":
        base = tf.keras.applications.EfficientNetB0(
            input_shape=input_shape, include_top=False, weights="imagenet"
        )
        preprocess = tf.keras.applications.efficientnet.preprocess_input
    else:
        raise ValueError(f"Unknown backbone: {name}")
    return base, preprocess


def build_model(
    backbone=config.BACKBONE,
    input_shape=config.IMG_SIZE + (config.CHANNELS,),
    head=config.DEFAULT_HEAD,
    dropout=0.3,
    dense_units=128,
    freeze_backbone=True,
    lr=config.DEFAULT_LR,
):
    base, preprocess = _get_backbone(backbone, input_shape)
    base.trainable = not freeze_backbone

    inputs = layers.Input(shape=input_shape)
    # Undo [0,1] normalization and apply the backbone's canonical preprocessing
    x = layers.Rescaling(255.0)(inputs)
    x = preprocess(x)
    x = base(x, training=False if freeze_backbone else None)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(dropout)(x)
    x = layers.Dense(dense_units, activation="relu")(x)
    x = layers.Dropout(dropout / 2)(x)

    if head == "regression":
        outputs = layers.Dense(1, activation="linear", name="hb_g_dl", bias_initializer=tf.keras.initializers.Constant(12.5))(x)
        # Huber loss treats small errors quadratically and large errors linearly,
        # preventing extreme lighting variations from destabilizing weights
        if getattr(config, "LOSS_FUNCTION", "mse") == "huber":
            loss = tf.keras.losses.Huber(delta=1.0)
        else:
            loss = "mse"
        metrics = [
            tf.keras.metrics.MeanAbsoluteError(name="mae"),
            tf.keras.metrics.RootMeanSquaredError(name="rmse")
        ]
    elif head == "classification":
        n_classes = len(config.ANEMIA_BUCKETS)
        outputs = layers.Dense(n_classes, activation="softmax", name="anemia_class")(x)
        loss = "sparse_categorical_crossentropy"
        metrics = ["accuracy"]
    else:
        raise ValueError(f"Unknown head type: {head}")

    model = models.Model(inputs, outputs, name=f"hb_{backbone}_{head}")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
        loss=loss,
        metrics=metrics,
    )
    return model


def unfreeze_top_layers(model, n_layers=20, lr=1e-5):
    """
    Fine-tuning step: unfreeze the top n_layers of the backbone and
    recompile with a low learning rate. Automatically detects MobileNet or EfficientNet.
    """
    backbone = None
    for layer in model.layers:
        if "mobilenet" in layer.name.lower() or "efficientnet" in layer.name.lower():
            backbone = layer
            break
    if backbone is None:
        raise ValueError("Could not locate backbone layer to unfreeze.")

    backbone.trainable = True
    for layer in backbone.layers[:-n_layers]:
        layer.trainable = False

    # Fresh metrics to prevent Keras 3 state reuse issues
    if "regression" in model.name:
        fresh_metrics = [
            tf.keras.metrics.MeanAbsoluteError(name="mae"),
            tf.keras.metrics.RootMeanSquaredError(name="rmse")
        ]
    else:
        fresh_metrics = ["accuracy"]

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
        loss=model.loss,
        metrics=fresh_metrics,
    )
    return model


if __name__ == "__main__":
    m = build_model()
    m.summary()