"""Group raw events into per-session sequences.

Filters applied:
- Drop sessions with only one event (nothing to predict from).
- Cap session length at SESSION_LEN_PERCENTILE, keeping the most recent
  items -- a handful of pathological sessions with thousands of events
  would otherwise dominate padding/batch cost.

Run as: python -m src.data.sessions
"""

import pandas as pd

from src.config import (
    EXPORT_PARQUET_PATH,
    MIN_SESSION_LEN,
    SESSION_LEN_PERCENTILE,
    SESSIONS_PARQUET_PATH,
)


def build_sessions(events_df, min_session_len=MIN_SESSION_LEN, length_percentile=SESSION_LEN_PERCENTILE):
    """events_df needs columns: user_session, event_time, product_id.

    Returns one row per session: user_session, start_time, product_seq
    (product_ids in event_time order), session_len.
    """
    df = events_df.sort_values(["user_session", "event_time"])

    grouped = df.groupby("user_session").agg(
        product_seq=("product_id", list),
        start_time=("event_time", "min"),
    ).reset_index()
    grouped["session_len"] = grouped["product_seq"].apply(len)

    grouped = grouped[grouped["session_len"] >= min_session_len]

    cap = int(grouped["session_len"].quantile(length_percentile / 100))
    cap = max(cap, min_session_len)
    grouped["product_seq"] = grouped["product_seq"].apply(
        lambda seq: seq[-cap:] if len(seq) > cap else seq
    )
    grouped["session_len"] = grouped["product_seq"].apply(len)

    return grouped[["user_session", "start_time", "product_seq", "session_len"]].reset_index(drop=True)


def load_and_build(input_path=EXPORT_PARQUET_PATH, output_path=SESSIONS_PARQUET_PATH):
    events_df = pd.read_parquet(input_path, columns=["user_session", "event_time", "product_id"])
    sessions_df = build_sessions(events_df)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sessions_df.to_parquet(output_path, index=False)
    return sessions_df


if __name__ == "__main__":
    sessions_df = load_and_build()
    print(f"Built {len(sessions_df):,} sessions -> {SESSIONS_PARQUET_PATH}")
    print(sessions_df["session_len"].describe())
