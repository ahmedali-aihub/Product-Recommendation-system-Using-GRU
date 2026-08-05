"""GET/POST/PATCH/DELETE /api/cart/... -- a cart is identified by a
client-generated UUID sent as the X-Cart-Id header, not a logged-in user.
No accounts in v1: this keeps the backend fully stateless per request,
matching the "serving is stateless" principle the README already states
for the future /predict endpoint."""

from fastapi import APIRouter, Depends, Header, HTTPException, Response

from src.data.db import get_connection
from src.serving.schemas import AddCartItemIn, CartItemOut, CartOut, UpdateCartItemIn

router = APIRouter()


def get_cart_id(x_cart_id: str = Header(...)) -> str:
    if not x_cart_id or len(x_cart_id) > 36:
        raise HTTPException(status_code=422, detail="X-Cart-Id header is required and must be 1-36 characters")
    return x_cart_id


def _load_cart(cursor, cart_id: str) -> CartOut:
    cursor.execute(
        """
        SELECT ci.product_id, p.display_name, p.brand, p.price, p.image_ref, ci.quantity
        FROM cart_items ci
        JOIN products p ON p.product_id = ci.product_id
        WHERE ci.cart_id = %s
        ORDER BY ci.added_at
        """,
        (cart_id,),
    )
    rows = cursor.fetchall()

    items, total_items, total_price = [], 0, 0.0
    for row in rows:
        price = float(row["price"]) if row["price"] is not None else 0.0
        line_total = round(price * row["quantity"], 2)
        items.append(CartItemOut(
            product_id=row["product_id"], display_name=row["display_name"], brand=row["brand"],
            price=row["price"], image_ref=row["image_ref"], quantity=row["quantity"], line_total=line_total,
        ))
        total_items += row["quantity"]
        total_price += line_total

    return CartOut(cart_id=cart_id, items=items, total_items=total_items, total_price=round(total_price, 2))


@router.get("/cart", response_model=CartOut)
def get_cart(cart_id: str = Depends(get_cart_id)):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        return _load_cart(cursor, cart_id)
    finally:
        cursor.close()
        conn.close()


@router.post("/cart/items", response_model=CartOut)
def add_cart_item(body: AddCartItemIn, cart_id: str = Depends(get_cart_id)):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT 1 FROM products WHERE product_id = %s", (body.product_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Product not found")

        # Cart row is created lazily, on the first successful add -- not on page load.
        cursor.execute(
            "INSERT INTO carts (cart_id) VALUES (%s) ON DUPLICATE KEY UPDATE cart_id = cart_id",
            (cart_id,),
        )
        cursor.execute(
            """
            INSERT INTO cart_items (cart_id, product_id, quantity)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
            """,
            (cart_id, body.product_id, body.quantity),
        )
        conn.commit()
        return _load_cart(cursor, cart_id)
    finally:
        cursor.close()
        conn.close()


@router.patch("/cart/items/{product_id}", response_model=CartOut)
def update_cart_item(product_id: int, body: UpdateCartItemIn, cart_id: str = Depends(get_cart_id)):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT 1 FROM cart_items WHERE cart_id = %s AND product_id = %s", (cart_id, product_id))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Item not in cart")

        if body.quantity <= 0:
            # quantity is never stored as 0 -- delete the row instead.
            cursor.execute("DELETE FROM cart_items WHERE cart_id = %s AND product_id = %s", (cart_id, product_id))
        else:
            cursor.execute(
                "UPDATE cart_items SET quantity = %s WHERE cart_id = %s AND product_id = %s",
                (body.quantity, cart_id, product_id),
            )
        conn.commit()
        return _load_cart(cursor, cart_id)
    finally:
        cursor.close()
        conn.close()


@router.delete("/cart/items/{product_id}", status_code=204)
def delete_cart_item(product_id: int, cart_id: str = Depends(get_cart_id)):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT 1 FROM cart_items WHERE cart_id = %s AND product_id = %s", (cart_id, product_id))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Item not in cart")

        cursor.execute("DELETE FROM cart_items WHERE cart_id = %s AND product_id = %s", (cart_id, product_id))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return Response(status_code=204)
