"""Pydantic request/response models for the storefront API."""

from pydantic import BaseModel, Field


class ProductOut(BaseModel):
    product_id: int
    display_name: str
    brand: str | None = None
    category_top: str | None = None
    category_leaf: str | None = None
    category_code: str | None = None
    price: float | None = None
    image_ref: str


class ProductListOut(BaseModel):
    items: list[ProductOut]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class CategoryOut(BaseModel):
    category: str
    product_count: int


class CartItemOut(BaseModel):
    product_id: int
    display_name: str
    brand: str | None = None
    price: float | None = None
    image_ref: str
    quantity: int
    line_total: float


class CartOut(BaseModel):
    cart_id: str
    items: list[CartItemOut]
    total_items: int
    total_price: float


class AddCartItemIn(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1)


class UpdateCartItemIn(BaseModel):
    quantity: int


class PredictIn(BaseModel):
    # The current session's viewed/cart product_ids, ordered oldest to most
    # recent -- the GRU reads order, not just membership.
    product_ids: list[int]
    top_k: int = Field(default=10, ge=1, le=50)


class PredictOut(BaseModel):
    items: list[ProductOut]
