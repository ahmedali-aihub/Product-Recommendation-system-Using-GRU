"""Paths, hyperparameters, and constants shared across the pipeline."""

from pathlib import Path

# --- Paths ---
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = ROOT_DIR / "data" / "raw"
DATA_INTERIM_DIR = ROOT_DIR / "data" / "interim"
DATA_PROCESSED_DIR = ROOT_DIR / "data" / "processed"
MODELS_DIR = ROOT_DIR / "models"

EXPORT_PARQUET_PATH = DATA_INTERIM_DIR / "events.parquet"
SESSIONS_PARQUET_PATH = DATA_INTERIM_DIR / "sessions.parquet"
VOCAB_PATH = MODELS_DIR / "item_vocab.json"
# Keras 3's Model.save_weights requires the filename end in ".weights.h5"
# for its native checkpoint format -- not just any ".h5" extension.
MODEL_PATH = MODELS_DIR / "gru4rec.weights.h5"

# --- Session building ---
MIN_SESSION_LEN = 2          # sessions with only 1 event are dropped (nothing to predict)
SESSION_LEN_PERCENTILE = 95  # cap session length at this percentile to bound padding cost

# --- Vocabulary ---
VOCAB_SIZE = 40_000  # top-N most frequent products kept as real tokens; rest -> <OTHER>
PAD_TOKEN = 0
UNK_TOKEN = 1
OTHER_TOKEN = 2
NUM_SPECIAL_TOKENS = 3  # PAD, UNK, OTHER occupy ids 0-2; real items start at 3

# --- Sequence encoding ---
MAX_SEQ_LEN = 20  # sessions longer than this are truncated to the most recent N events

# --- Time-based split ---
TEST_DAYS = 3   # last N days of the export window -> test set
VAL_DAYS = 3    # N days before that -> validation set

# --- Model / training ---
EMBED_DIM = 128
GRU_UNITS = 128
NUM_SAMPLED_NEGATIVES = 100  # sampled softmax: score true item + this many negatives, not full vocab
BATCH_SIZE = 256
LEARNING_RATE = 1e-3
EPOCHS = 10
EARLY_STOPPING_PATIENCE = 2  # stop if val Recall@10 doesn't improve for this many epochs

# --- Warm-start fine-tuning (README Section 4 hybrid retrain strategy) ---
# A smaller learning rate than a full retrain -- nudge the existing weights
# toward recent data, don't overwrite what they already learned.
WARM_START_LEARNING_RATE = 1e-4

# --- Serving layer (storefront v1) ---
DEFAULT_PAGE_SIZE = 24
MAX_PAGE_SIZE = 100
FRONTEND_DEV_ORIGIN = "http://localhost:5173"  # Vite's default dev port, used for CORS
