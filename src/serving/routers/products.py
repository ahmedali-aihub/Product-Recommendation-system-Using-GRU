"""GET /api/products (paginated, category filter, search), GET /api/products/{id}."""

from fastapi import APIRouter, HTTPException, Query

from src.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from src.data.db import get_connection
from src.serving.schemas import ProductListOut, ProductOut

router = APIRouter()

PRODUCT_COLUMNS = """
    product_id, display_name, brand, category_top, category_leaf,
    category_code, price, image_ref
"""


def row_to_product(row: dict) -> ProductOut:
    return ProductOut(
        product_id=row["product_id"],
        display_name=row["display_name"],
        brand=row["brand"],
        category_top=row["category_top"],
        category_leaf=row["category_leaf"],
        category_code=row["category_code"],
        price=float(row["price"]) if row["price"] is not None else None,
        image_ref=row["image_ref"],
    )


@router.get("/products", response_model=ProductListOut)
def list_products(
    category: str | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
):
    conditions = []
    params = []
    if category:
        conditions.append("category_top = %s")
        params.append(category)
    if search:
        # No FULLTEXT index -- a LIKE scan over 141K rows is fine at this
        # scale; revisit with a FULLTEXT index only if this gets slow.
        conditions.append("(display_name LIKE %s OR brand LIKE %s)")
        like_term = f"%{search}%"
        params.extend([like_term, like_term])
    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(f"SELECT COUNT(*) AS total FROM products {where_sql}", params)
        total_items = cursor.fetchone()["total"]

        offset = (page - 1) * page_size
        cursor.execute(
            f"""
            SELECT {PRODUCT_COLUMNS}
            FROM products
            {where_sql}
            ORDER BY event_count DESC, product_id ASC
            LIMIT %s OFFSET %s
            """,
            [*params, page_size, offset],
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    total_pages = (total_items + page_size - 1) // page_size if total_items else 0
    return ProductListOut(
        items=[row_to_product(r) for r in rows],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(f"SELECT {PRODUCT_COLUMNS} FROM products WHERE product_id = %s", (product_id,))
        row = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return row_to_product(row)
