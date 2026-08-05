"""Build the product vocabulary.

Top-N most frequent products become real tokens; everything else maps to
a shared <OTHER> token. A dense softmax over the full catalog (100k+
distinct products here) is memory/compute-heavy for no accuracy benefit
at this project's scale (README Section 6d) -- this truncation, plus
sampled softmax at training time, is what keeps CPU training tractable.

<PAD>/<UNK>/<OTHER> reserve the first three token ids (see src/config.py):
- PAD: padding shorter sequences to MAX_SEQ_LEN.
- OTHER: a real product seen in training data, but outside the top-N by
  frequency -- deliberately merged so the long tail still contributes
  signal instead of being dropped.
- UNK: reserved for a product the model has never seen at all, encountered
  only at inference (e.g. a brand-new listing) -- distinct from OTHER,
  which did appear in training, just not often enough to earn its own id.

Run as: python -m src.data.vocab
"""

import json

import pandas as pd

from src.config import (
    NUM_SPECIAL_TOKENS,
    OTHER_TOKEN,
    PAD_TOKEN,
    SESSIONS_PARQUET_PATH,
    UNK_TOKEN,
    VOCAB_PATH,
    VOCAB_SIZE,
)


def build_vocab(sessions_df, vocab_size=VOCAB_SIZE):
    """Returns product_to_id: raw product_id -> dense token id.

    Token ids for real products start at NUM_SPECIAL_TOKENS. A product
    not present in this dict is long-tail (or unseen) -- callers map it
    to OTHER_TOKEN (training) or UNK_TOKEN (inference) at lookup time.
    """
    counts = pd.Series([p for seq in sessions_df["product_seq"] for p in seq]).value_counts()
    top_products = counts.head(vocab_size).index.tolist()
    return {product_id: NUM_SPECIAL_TOKENS + i for i, product_id in enumerate(top_products)}


def encode_sequence(seq, product_to_id, default_token=OTHER_TOKEN):
    return [product_to_id.get(p, default_token) for p in seq]


def save_vocab(product_to_id, path=VOCAB_PATH):
    payload = {
        "product_to_id": {str(k): v for k, v in product_to_id.items()},
        "pad_token": PAD_TOKEN,
        "unk_token": UNK_TOKEN,
        "other_token": OTHER_TOKEN,
        "num_special_tokens": NUM_SPECIAL_TOKENS,
        "vocab_size": len(product_to_id),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f)


def load_vocab(path=VOCAB_PATH):
    with open(path) as f:
        payload = json.load(f)
    payload["product_to_id"] = {int(k): v for k, v in payload["product_to_id"].items()}
    return payload


if __name__ == "__main__":
    sessions_df = pd.read_parquet(SESSIONS_PARQUET_PATH)
    product_to_id = build_vocab(sessions_df)
    save_vocab(product_to_id)
    print(f"Vocab: {len(product_to_id):,} real products + PAD/UNK/OTHER -> {VOCAB_PATH}")
