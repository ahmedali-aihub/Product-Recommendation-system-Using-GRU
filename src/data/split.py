"""Time-based train/val/test split.

Sessions are split by start_time, not shuffled randomly -- a random split
would let sessions from the test period leak into training and inflate
Recall@10/NDCG@10 artificially (README Section 6f). The last TEST_DAYS
become the test set, the VAL_DAYS before that the validation set,
everything earlier is training data.

Run as: python -m src.data.split
"""

import pandas as pd

from src.config import SESSIONS_PARQUET_PATH, TEST_DAYS, VAL_DAYS


def time_based_split(sessions_df, test_days=TEST_DAYS, val_days=VAL_DAYS):
    df = sessions_df.sort_values("start_time")
    max_time = df["start_time"].max()

    test_cutoff = max_time - pd.Timedelta(days=test_days)
    val_cutoff = test_cutoff - pd.Timedelta(days=val_days)

    train_df = df[df["start_time"] < val_cutoff]
    val_df = df[(df["start_time"] >= val_cutoff) & (df["start_time"] < test_cutoff)]
    test_df = df[df["start_time"] >= test_cutoff]

    return (
        train_df.reset_index(drop=True),
        val_df.reset_index(drop=True),
        test_df.reset_index(drop=True),
    )


if __name__ == "__main__":
    sessions_df = pd.read_parquet(SESSIONS_PARQUET_PATH)
    train_df, val_df, test_df = time_based_split(sessions_df)
    print(f"train={len(train_df):,}  val={len(val_df):,}  test={len(test_df):,}")
