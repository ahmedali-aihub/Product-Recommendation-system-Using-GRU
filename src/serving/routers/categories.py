"""GET /api/categories -- top-level categories with product counts, used
for the storefront's category nav/filter."""

from fastapi import APIRouter

from src.data.db import get_connection
from src.serving.schemas import CategoryOut

router = APIRouter()


@router.get("/categories", response_model=list[CategoryOut])
def list_categories():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT category_top AS category, COUNT(*) AS product_count
            FROM products
            WHERE category_top IS NOT NULL
            GROUP BY category_top
            ORDER BY product_count DESC
            """
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return [CategoryOut(**row) for row in rows]
