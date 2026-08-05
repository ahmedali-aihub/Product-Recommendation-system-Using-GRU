"""Build the product catalog for the storefront.

The `events` table has no product names or images -- only product_id,
category_code, brand, and price, and even those are only known per-event:
REES46's source data has genuine per-event nulls (the same product_id can
show up with a NULL category_code on one row and a real one on another),
not per-product ones. This script reduces the 20M+ event rows down to one
row per distinct product_id -- keeping the most recently seen non-null
category_code/brand/price for each -- and generates a human-readable
display_name plus an icon key (image_ref) for the frontend, since no real
product photos exist for this dataset.

Safe to re-run: writes via INSERT ... ON DUPLICATE KEY UPDATE, so after any
fresh `events` load this can just be re-run to refresh `products`.

Run as: python -m src.data.build_product_catalog [--limit N]
"""

import argparse

from src.data.db import get_connection

CHUNK_SIZE = 200_000
WRITE_BATCH_SIZE = 5_000


def humanize_segment(segment):
    return segment.replace("_", " ").replace("-", " ").strip().title()


def parse_category(category_code):
    """'appliances.kitchen.refrigerators' -> ('appliances', 'refrigerators')."""
    if not category_code:
        return None, None
    parts = [p for p in category_code.split(".") if p]
    if not parts:
        return None, None
    return parts[0], parts[-1]


def generate_display_name(category_code, brand, product_id):
    _, leaf = parse_category(category_code)
    leaf_name = humanize_segment(leaf) if leaf else None
    brand_name = humanize_segment(brand) if brand else None
    if brand_name and leaf_name:
        return f"{brand_name} {leaf_name}"
    if brand_name:
        return f"{brand_name} Product"
    if leaf_name:
        return leaf_name
    return f"Unbranded Product #{product_id}"


def generate_image_ref(category_code):
    top, _leaf = parse_category(category_code)
    return top if top else "generic"


def build_catalog(limit=None):
    query = "SELECT product_id, category_code, brand, price, event_time FROM events ORDER BY product_id, event_time"
    if limit:
        query += f" LIMIT {int(limit)}"

    conn = get_connection()
    read_cursor = conn.cursor()
    read_cursor.execute(query)

    # One entry per distinct product_id -- 141,694 of them in the full
    # 20M-row load, trivially small to hold in memory even while streaming
    # through all 20M+ event rows to build it.
    products = {}
    total_rows = 0
    try:
        while True:
            rows = read_cursor.fetchmany(CHUNK_SIZE)
            if not rows:
                break
            for product_id, category_code, brand, price, _event_time in rows:
                entry = products.setdefault(
                    product_id, {"category_code": None, "brand": None, "price": None, "event_count": 0}
                )
                entry["event_count"] += 1
                if category_code is not None:
                    entry["category_code"] = category_code
                if brand is not None:
                    entry["brand"] = brand
                if price is not None:
                    entry["price"] = price
            total_rows += len(rows)
            print(f"  processed {total_rows:,} event rows, {len(products):,} distinct products so far...")
    finally:
        read_cursor.close()

    print(f"Reduced {total_rows:,} event rows to {len(products):,} distinct products. Writing...")

    write_cursor = conn.cursor()
    insert_sql = """
        INSERT INTO products
            (product_id, category_code, category_top, category_leaf, brand, price,
             display_name, image_ref, event_count)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            category_code = VALUES(category_code),
            category_top = VALUES(category_top),
            category_leaf = VALUES(category_leaf),
            brand = VALUES(brand),
            price = VALUES(price),
            display_name = VALUES(display_name),
            image_ref = VALUES(image_ref),
            event_count = VALUES(event_count)
    """

    null_category = null_brand = unbranded = 0
    batch = []
    try:
        for product_id, entry in products.items():
            category_code = entry["category_code"]
            brand = entry["brand"]
            category_top, category_leaf = parse_category(category_code)

            if category_code is None:
                null_category += 1
            if brand is None:
                null_brand += 1
            if category_code is None and brand is None:
                unbranded += 1

            batch.append((
                product_id, category_code, category_top, category_leaf, brand, entry["price"],
                generate_display_name(category_code, brand, product_id),
                generate_image_ref(category_code),
                entry["event_count"],
            ))
            if len(batch) >= WRITE_BATCH_SIZE:
                write_cursor.executemany(insert_sql, batch)
                conn.commit()
                batch = []
        if batch:
            write_cursor.executemany(insert_sql, batch)
            conn.commit()
    finally:
        write_cursor.close()
        conn.close()

    print(f"Wrote {len(products):,} products.")
    print(
        f"  NULL category_code: {null_category:,}  NULL brand: {null_brand:,}  "
        f"both NULL (unbranded fallback): {unbranded:,}"
    )
    return len(products)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None, help="cap on event rows scanned, for a quick prototyping pass")
    args = parser.parse_args()
    build_catalog(limit=args.limit)
