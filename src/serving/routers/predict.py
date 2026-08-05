"""POST /api/predict -- session-based next-item recommendation.

Takes the current session's product_ids (viewed/in-cart, oldest to most
recent) and returns the model's top-N predicted next items. This is the
piece the README always described as coming later, once GRU4Rec is
trained -- everything else in the storefront (browsing, cart) was built
and shipped without waiting on it (see README Section 11).

The model + vocab load once at import time (module load), not per
request -- the same "load once, serve many" principle export.py etc.
already follow for other expensive resources. A fresh training run's
weights only take effect after the backend process restarts; there's no
live file-watching hot-reload here yet (a documented simplification, not
the target design described in README Section 4).
"""

import numpy as np
from fastapi import APIRouter
from tensorflow.keras.utils import pad_sequences

from src.config import EMBED_DIM, GRU_UNITS, MAX_SEQ_LEN, MODEL_PATH, OTHER_TOKEN, PAD_TOKEN, VOCAB_PATH
from src.data.db import get_connection
from src.data.vocab import load_vocab
from src.model.gru4rec import load_model
from src.serving.routers.products import PRODUCT_COLUMNS, row_to_product
from src.serving.schemas import PredictIn, PredictOut

router = APIRouter()

_vocab = load_vocab(VOCAB_PATH)
_product_to_id = _vocab["product_to_id"]
_id_to_product = {token_id: product_id for product_id, token_id in _product_to_id.items()}
_vocab_size = _vocab["vocab_size"] + _vocab["num_special_tokens"]

_model = load_model(
    vocab_size=_vocab_size, embed_dim=EMBED_DIM, gru_units=GRU_UNITS,
    max_seq_len=MAX_SEQ_LEN, weights_path=MODEL_PATH,
)


@router.post("/predict", response_model=PredictOut)
def predict(body: PredictIn):
    if not body.product_ids:
        return PredictOut(items=[])

    encoded = [_product_to_id.get(pid, OTHER_TOKEN) for pid in body.product_ids]
    padded = pad_sequences([encoded], maxlen=MAX_SEQ_LEN, padding="pre", truncating="pre", value=PAD_TOKEN)
    context = _model(padded, training=False)
    logits = _model.full_logits(context)[0].numpy()

    # Over-fetch candidates -- some decoded tokens are PAD/UNK/<OTHER> or
    # products already in the session, both get filtered below.
    candidate_count = min(body.top_k * 4, len(logits))
    top_indices = np.argpartition(-logits, kth=candidate_count - 1)[:candidate_count]
    top_indices = top_indices[np.argsort(-logits[top_indices])]

    already_seen = set(body.product_ids)
    recommended_ids = []
    for idx in top_indices:
        product_id = _id_to_product.get(int(idx))
        if product_id is not None and product_id not in already_seen:
            recommended_ids.append(product_id)
        if len(recommended_ids) >= body.top_k:
            break

    if not recommended_ids:
        return PredictOut(items=[])

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        placeholders = ",".join(["%s"] * len(recommended_ids))
        cursor.execute(
            f"SELECT {PRODUCT_COLUMNS} FROM products WHERE product_id IN ({placeholders})",
            recommended_ids,
        )
        rows_by_id = {row["product_id"]: row for row in cursor.fetchall()}
    finally:
        cursor.close()
        conn.close()

    # Preserve the model's ranking order -- SQL's IN() doesn't guarantee row order.
    ordered_rows = [rows_by_id[pid] for pid in recommended_ids if pid in rows_by_id]
    return PredictOut(items=[row_to_product(row) for row in ordered_rows])
