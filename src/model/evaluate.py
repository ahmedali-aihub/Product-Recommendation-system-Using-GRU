"""Evaluation: Recall@10, NDCG@10, and a popularity baseline.

Plain accuracy is the wrong metric for a ranking problem -- see README
Section 8. The popularity baseline ("always recommend the top-10 most
popular items, ignore the session") is the bar the model actually has to
clear; matching it means the model hasn't learned anything session-specific.

Run as: python -m src.model.evaluate  (evaluates the saved model against
the test split of the current sessions Parquet)
"""

import numpy as np
from tensorflow.keras.utils import pad_sequences

from src.config import MAX_SEQ_LEN, NUM_SPECIAL_TOKENS, OTHER_TOKEN, PAD_TOKEN
from src.data.vocab import encode_sequence


def evaluate_model(model, eval_df, product_to_id, k=10, max_sessions=2000, seed=42, batch_size=512):
    """Returns (recall_at_k, ndcg_at_k) over a sample of eval_df's sessions.

    For each session, everything but the last item is the "prefix" fed to
    the model; the last item is the target it should rank in its top-k.

    Runs the forward pass in batches rather than one session at a time --
    at thousands of eval sessions (and this runs every epoch during
    training), one eager call per session is dominated by per-call
    dispatch overhead rather than actual compute.
    """
    subset = eval_df.sample(n=min(max_sessions, len(eval_df)), random_state=seed)
    prefixes, targets = [], []
    for seq in subset["product_seq"]:
        encoded = encode_sequence(seq, product_to_id, default_token=OTHER_TOKEN)
        if len(encoded) < 2:
            continue
        prefixes.append(encoded[:-1])
        targets.append(encoded[-1])
    if not prefixes:
        return 0.0, 0.0

    padded = pad_sequences(prefixes, maxlen=MAX_SEQ_LEN, padding="pre", truncating="pre", value=PAD_TOKEN)
    targets = np.array(targets)

    hits, ndcgs = [], []
    for start in range(0, len(padded), batch_size):
        batch = padded[start : start + batch_size]
        batch_targets = targets[start : start + batch_size]

        context = model(batch, training=False)
        logits = model.full_logits(context).numpy()

        # argpartition finds the top-k unsorted in O(vocab) instead of
        # O(vocab log vocab) from a full sort -- then sort just those k.
        row_idx = np.arange(logits.shape[0])[:, None]
        top_k_idx = np.argpartition(-logits, kth=k - 1, axis=1)[:, :k]
        top_k_scores = logits[row_idx, top_k_idx]
        order = np.argsort(-top_k_scores, axis=1)
        top_k_sorted = top_k_idx[row_idx, order]

        for row, target in zip(top_k_sorted, batch_targets):
            hit_positions = np.where(row == target)[0]
            if len(hit_positions) > 0:
                hits.append(1)
                ndcgs.append(1 / np.log2(hit_positions[0] + 2))
            else:
                hits.append(0)
                ndcgs.append(0.0)

    return float(np.mean(hits)), float(np.mean(ndcgs))


def evaluate_popularity_baseline(eval_df, product_to_id, k=10, max_sessions=2000, seed=42):
    """Vocab ids are assigned in descending frequency order (src/data/vocab.py),
    so the top-k most popular ids are simply the first k real-item ids."""
    popular_top_k = set(range(NUM_SPECIAL_TOKENS, NUM_SPECIAL_TOKENS + k))
    subset = eval_df.sample(n=min(max_sessions, len(eval_df)), random_state=seed)
    hits = []
    for seq in subset["product_seq"]:
        encoded = encode_sequence(seq, product_to_id, default_token=OTHER_TOKEN)
        if len(encoded) < 2:
            continue
        target = encoded[-1]
        hits.append(1 if target in popular_top_k else 0)
    if not hits:
        return 0.0
    return float(np.mean(hits))


if __name__ == "__main__":
    import pandas as pd

    from src.config import EMBED_DIM, GRU_UNITS, MODEL_PATH, SESSIONS_PARQUET_PATH, VOCAB_PATH
    from src.data.split import time_based_split
    from src.data.vocab import load_vocab
    from src.model.gru4rec import load_model

    vocab = load_vocab(VOCAB_PATH)
    product_to_id = vocab["product_to_id"]
    vocab_size = vocab["vocab_size"] + vocab["num_special_tokens"]

    sessions_df = pd.read_parquet(SESSIONS_PARQUET_PATH)
    _, _, test_df = time_based_split(sessions_df)

    model = load_model(
        vocab_size=vocab_size, embed_dim=EMBED_DIM, gru_units=GRU_UNITS,
        max_seq_len=MAX_SEQ_LEN, weights_path=MODEL_PATH,
    )

    recall_10, ndcg_10 = evaluate_model(model, test_df, product_to_id, max_sessions=len(test_df))
    popularity_recall_10 = evaluate_popularity_baseline(test_df, product_to_id, max_sessions=len(test_df))

    print(f"Test set ({len(test_df):,} sessions):")
    print(f"  GRU4Rec     Recall@10={recall_10:.4f}  NDCG@10={ndcg_10:.4f}")
    print(f"  Popularity  Recall@10={popularity_recall_10:.4f}")
