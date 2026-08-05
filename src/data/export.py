"""Query MySQL for a training window and export it to Parquet.

Training doesn't query MySQL repeatedly -- each run exports its target
window once, and every downstream stage (session building, vocab, split)
reads from this Parquet file instead of the database. MySQL stays the
append-friendly system of record; Parquet is the fast, immutable working
format for a given run.

Run as: python -m src.data.export [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--output-path PATH]
"""

import argparse
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.config import EXPORT_PARQUET_PATH
from src.data.db import get_connection

COLUMNS = [
    "event_time", "event_type", "product_id", "category_id",
    "category_code", "brand", "price", "user_id", "user_session",
]

# Rows are streamed via a server-side cursor and written in chunks rather
# than loaded into one pandas DataFrame -- at 20M+ rows that would hold
# several GB in memory at once for no benefit, since the file is written
# incrementally either way.
CHUNK_SIZE = 200_000


def export_events(start_date=None, end_date=None, limit=None, output_path=EXPORT_PARQUET_PATH):
    """Stream events from MySQL to a Parquet file, optionally windowed by date.

    start_date/end_date: 'YYYY-MM-DD' strings (or datetime), half-open range
    [start_date, end_date). limit: cap on row count, mainly for prototyping
    on a small slice before running the full export.
    """
    query = f"SELECT {', '.join(COLUMNS)} FROM events WHERE 1=1"
    params = []
    if start_date:
        query += " AND event_time >= %s"
        params.append(start_date)
    if end_date:
        query += " AND event_time < %s"
        params.append(end_date)
    query += " ORDER BY event_time"
    if limit:
        query += f" LIMIT {int(limit)}"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)

    writer = None
    total_rows = 0
    try:
        while True:
            rows = cursor.fetchmany(CHUNK_SIZE)
            if not rows:
                break
            df = pd.DataFrame(rows, columns=COLUMNS)
            table = pa.Table.from_pandas(df, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(output_path, table.schema)
            writer.write_table(table)
            total_rows += len(df)
            print(f"  exported {total_rows:,} rows so far...")
    finally:
        if writer is not None:
            writer.close()
        cursor.close()
        conn.close()

    return total_rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start-date", default=None, help="YYYY-MM-DD, inclusive")
    parser.add_argument("--end-date", default=None, help="YYYY-MM-DD, exclusive")
    parser.add_argument("--output-path", default=str(EXPORT_PARQUET_PATH))
    args = parser.parse_args()

    output_path = Path(args.output_path)
    n = export_events(start_date=args.start_date, end_date=args.end_date, output_path=output_path)
    print(f"Exported {n:,} rows to {output_path}")
