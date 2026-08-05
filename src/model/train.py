"""Train GRU4Rec end-to-end: export -> sessions -> vocab -> split -> train -> evaluate -> save.

Implements the two halves of the hybrid retrain strategy from README
Section 4:

  - Full retrain (default): builds a fresh vocab from the given data window
    and trains from random initialization. Run periodically on a fixed-size
    sliding window (pass --start-date/--end-date), not ever-growing history.
  - Warm-start fine-tune (--warm-start): loads the existing saved vocab and
    model weights, continues training only on the given window at a lower
    learning rate. Run frequently on just newly accumulated data.

Early stopping watches validation Recall@10, not training loss -- loss can
keep dropping (overfitting) after ranking quality on held-out data plateaus.

Run as:
  python -m src.model.train                                   # full retrain, full export
  python -m src.model.train --start-date 2019-10-01 --end-date 2019-10-02  # small slice
  python -m src.model.train --warm-start --start-date 2019-10-29           # fine-tune on new data
"""

import argparse
from pathlib import Path
import time

import numpy as np
import tensorflow as tf
from tensorflow.keras.utils import pad_sequences

from src.config import (
    BATCH_SIZE,
    EARLY_STOPPING_PATIENCE,
    EMBED_DIM,
    EPOCHS,
    EXPORT_PARQUET_PATH,
    GRU_UNITS,
    LEARNING_RATE,
    MAX_SEQ_LEN,
    MODEL_PATH,
    NUM_SAMPLED_NEGATIVES,
    NUM_SPECIAL_TOKENS,
    OTHER_TOKEN,
    PAD_TOKEN,
    SESSIONS_PARQUET_PATH,
    TEST_DAYS,
    VAL_DAYS,
    VOCAB_PATH,
    WARM_START_LEARNING_RATE,
)
from src.data.sessions import load_and_build
from src.data.split import time_based_split
from src.data.vocab import build_vocab, encode_sequence, load_vocab, save_vocab
from src.model.evaluate import evaluate_model, evaluate_popularity_baseline
from src.model.gru4rec import load_model

BEST_WEIGHTS_PATH = MODEL_PATH.with_name(MODEL_PATH.stem + ".best.weights.h5")


def make_training_pairs(sessions_df, product_to_id):
    """Session [A, B, C, D] -> pairs ([A]->B), ([A,B]->C), ([A,B,C]->D)."""
    inputs, targets = [], []
    for seq in sessions_df["product_seq"]:
        encoded = encode_sequence(seq, product_to_id, default_token=OTHER_TOKEN)
        for i in range(1, len(encoded)):
            inputs.append(encoded[:i])
            targets.append(encoded[i])
    return inputs, targets


def build_dataset(sessions_df, product_to_id, batch_size=BATCH_SIZE, seed=42):
    inputs, targets = make_training_pairs(sessions_df, product_to_id)
    padded = pad_sequences(inputs, maxlen=MAX_SEQ_LEN, padding="pre", truncating="pre", value=PAD_TOKEN)
    targets = np.array(targets, dtype=np.int64)
    ds = (
        tf.data.Dataset.from_tensor_slices((padded, targets))
        .shuffle(buffer_size=len(inputs), seed=seed)
        .batch(batch_size)
        .prefetch(tf.data.AUTOTUNE)
    )
    return ds, len(inputs)


def make_train_step(model, optimizer, num_sampled):
    @tf.function
    def train_step(batch_x, batch_y):
        with tf.GradientTape() as tape:
            context = model(batch_x, training=True)
            labels = tf.expand_dims(batch_y, axis=1)
            losses = tf.nn.sampled_softmax_loss(
                weights=model.output_weights,
                biases=model.output_bias,
                labels=labels,
                inputs=context,
                num_sampled=num_sampled,
                num_classes=model.vocab_size,
            )
            loss = tf.reduce_mean(losses)
        grads = tape.gradient(loss, model.trainable_variables)
        optimizer.apply_gradients(zip(grads, model.trainable_variables))
        return loss

    return train_step


def train(
    start_date=None,
    end_date=None,
    epochs=EPOCHS,
    warm_start=False,
    patience=EARLY_STOPPING_PATIENCE,
    test_days=TEST_DAYS,
    val_days=VAL_DAYS,
    skip_export=False,
    events_parquet_path=EXPORT_PARQUET_PATH,
    limit=None,
):
    """skip_export=True reuses an existing events Parquet file instead of
    querying MySQL -- needed to run this same script on a machine with no
    MySQL access (e.g. Colab: export locally once, upload the Parquet file,
    train there on GPU).

    limit caps how many rows get exported (e.g. limit=1_000_000) -- the
    prototyping-scale workflow: fast enough to retrain from scratch every
    couple of days on this machine, no warm-start complexity needed at this
    size. Remember to pass proportionally smaller --test-days/--val-days
    too (e.g. 0.1) -- 1M rows spans well under a day, not the 3-day default
    window sized for the full export."""
    if skip_export:
        print(f"Skipping MySQL export, using existing Parquet at {events_parquet_path}")
    else:
        # Imported lazily so a machine with no MySQL access (e.g. Colab,
        # skip_export=True) never needs mysql-connector-python installed --
        # a top-level import here would pull it in even when unused.
        from src.data.export import export_events

        print(f"Exporting events from MySQL (start={start_date}, end={end_date}, limit={limit})...")
        export_events(start_date=start_date, end_date=end_date, limit=limit, output_path=events_parquet_path)

    print("Building sessions...")
    sessions_df = load_and_build(input_path=events_parquet_path, output_path=SESSIONS_PARQUET_PATH)

    if warm_start:
        print(f"Warm-start: loading existing vocab from {VOCAB_PATH}")
        vocab = load_vocab(VOCAB_PATH)
        product_to_id = vocab["product_to_id"]
        vocab_size = vocab["vocab_size"] + vocab["num_special_tokens"]
        learning_rate = WARM_START_LEARNING_RATE
    else:
        print("Building vocabulary...")
        product_to_id = build_vocab(sessions_df)
        save_vocab(product_to_id, VOCAB_PATH)
        vocab_size = len(product_to_id) + NUM_SPECIAL_TOKENS
        learning_rate = LEARNING_RATE

    train_df, val_df, test_df = time_based_split(sessions_df, test_days=test_days, val_days=val_days)
    print(f"train={len(train_df):,}  val={len(val_df):,}  test={len(test_df):,} sessions")

    train_ds, num_pairs = build_dataset(train_df, product_to_id)
    print(f"{num_pairs:,} training pairs, ~{num_pairs // BATCH_SIZE + 1} batches/epoch")

    weights_to_load = MODEL_PATH if warm_start else None
    if warm_start:
        print(f"Loading previous weights from {MODEL_PATH}")
    model = load_model(
        vocab_size=vocab_size, embed_dim=EMBED_DIM, gru_units=GRU_UNITS,
        max_seq_len=MAX_SEQ_LEN, weights_path=weights_to_load,
    )

    optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate)
    train_step = make_train_step(model, optimizer, NUM_SAMPLED_NEGATIVES)

    best_recall = -1.0
    epochs_without_improvement = 0

    for epoch in range(epochs):
        start = time.time()
        batch_losses = []
        for batch_x, batch_y in train_ds:
            loss = train_step(batch_x, batch_y)
            batch_losses.append(float(loss))
        elapsed = time.time() - start

        recall_10, ndcg_10 = evaluate_model(model, val_df, product_to_id)
        print(
            f"epoch {epoch + 1}/{epochs}  loss={np.mean(batch_losses):.4f}  "
            f"val_recall@10={recall_10:.4f}  val_ndcg@10={ndcg_10:.4f}  time={elapsed:.1f}s"
        )

        if recall_10 > best_recall:
            best_recall = recall_10
            epochs_without_improvement = 0
            model.save_weights(BEST_WEIGHTS_PATH)
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= patience:
                print(f"No val_recall@10 improvement for {patience} epochs, stopping early.")
                break

    print(f"Restoring best checkpoint (val_recall@10={best_recall:.4f})")
    model.load_weights(BEST_WEIGHTS_PATH)
    model.save_weights(MODEL_PATH)
    BEST_WEIGHTS_PATH.unlink()  # was just a scratch checkpoint during training

    popularity_recall = evaluate_popularity_baseline(val_df, product_to_id)
    test_recall, test_ndcg = evaluate_model(model, test_df, product_to_id, max_sessions=len(test_df))
    print(
        f"\nFinal test set: Recall@10={test_recall:.4f}  NDCG@10={test_ndcg:.4f}  "
        f"(popularity baseline, val set: Recall@10={popularity_recall:.4f})"
    )

    return model


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start-date", default=None, help="YYYY-MM-DD, inclusive")
    parser.add_argument("--end-date", default=None, help="YYYY-MM-DD, exclusive")
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--warm-start", action="store_true", help="fine-tune existing weights instead of a full retrain")
    parser.add_argument("--patience", type=int, default=EARLY_STOPPING_PATIENCE)
    parser.add_argument(
        "--test-days", type=float, default=TEST_DAYS,
        help="size of the test window in days; shrink for short --start-date/--end-date ranges "
             "(e.g. a 1-day run needs test/val windows well under 1 day, not the 3-day full-scale default)",
    )
    parser.add_argument("--val-days", type=float, default=VAL_DAYS)
    parser.add_argument(
        "--skip-export", action="store_true",
        help="reuse an existing events Parquet file instead of querying MySQL "
             "(for running on a machine with no DB access, e.g. Colab)",
    )
    parser.add_argument("--events-parquet-path", default=str(EXPORT_PARQUET_PATH))
    parser.add_argument(
        "--limit", type=int, default=None,
        help="cap the number of exported rows, e.g. 1000000 for the prototyping-scale "
             "workflow -- pair with small --test-days/--val-days (e.g. 0.1)",
    )
    args = parser.parse_args()

    train(
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
        epochs=args.epochs,
        warm_start=args.warm_start,
        patience=args.patience,
        test_days=args.test_days,
        val_days=args.val_days,
        skip_export=args.skip_export,
        events_parquet_path=Path(args.events_parquet_path),
    )
