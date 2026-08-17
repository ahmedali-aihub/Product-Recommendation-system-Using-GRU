"""FastAPI app for the storefront: product browsing, cart, and
session-based recommendations (/predict).

Run as: python -m uvicorn src.serving.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import FRONTEND_ORIGINS
from src.serving.routers import cart, categories, predict, products

app = FastAPI(title="Product Recommender Storefront")

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
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


# Temporary diagnostic route -- narrows down a "Name or service not known"
# DNS failure connecting to Aiven that only reproduces on Render's network,
# not locally. Remove once the root cause is confirmed fixed.
@app.get("/api/debug/db")
def debug_db():
    import os
    import socket

    host = os.environ.get("MYSQL_HOST")
    port = int(os.environ.get("MYSQL_PORT", 3306))
    result = {"host": host, "port": port}

    try:
        result["dns"] = socket.getaddrinfo(host, port)
        result["dns_ok"] = True
    except Exception as e:
        result["dns_ok"] = False
        result["dns_error"] = f"{type(e).__name__}: {e}"
        return result

    try:
        from src.data.db import get_connection

        conn = get_connection()
        conn.close()
        result["connect_ok"] = True
    except Exception as e:
        result["connect_ok"] = False
        result["connect_error"] = f"{type(e).__name__}: {e}"

    return result
