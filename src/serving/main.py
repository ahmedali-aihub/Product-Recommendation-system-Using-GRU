"""FastAPI app for the storefront: product browsing, cart, and
session-based recommendations (/predict).

Run as: python -m uvicorn src.serving.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import FRONTEND_DEV_ORIGIN
from src.serving.routers import cart, categories, predict, products

app = FastAPI(title="Product Recommender Storefront")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_DEV_ORIGIN],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(cart.router, prefix="/api")
app.include_router(predict.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
