"""One-time fetch: curated product photography per top-level category.

REES46 has no real per-product photos, so this doesn't try to find a
unique photo per SKU (141,694 of them) -- it fetches a small, hand-picked
pool of high-quality photos per CATEGORY from Pexels, saved as static
assets. src/lib/productImage.js then deterministically picks one photo
from a product's category pool (based on product_id), so the same product
always shows the same photo, and the pool rotates across every product in
that category. This is the honest tradeoff stated in the plan: real
photography, category-representative, not one-unique-photo-per-SKU.

Not part of the regular pipeline -- run once, images become checked-in
static assets from then on. Uses only the stdlib (urllib) since this is a
one-off asset-prep script, not worth a new pip dependency for.

Run as: python scripts/fetch_product_images.py
(from the app/ directory; reads PEXELS_API_KEY from the repo root .env)
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
APP_DIR = SCRIPT_DIR.parent
REPO_ROOT = APP_DIR.parent
IMAGES_DIR = APP_DIR / "public" / "images"
PHOTOS_PER_CATEGORY = 8

# Hand-picked queries aimed at a clean, editorial/minimal look (Apple/CK-style),
# not generic clip-art -- this is the part that actually determines whether
# the site looks premium or looks like stock-photo soup.
#
# A category can map to either a single query (fetches PHOTOS_PER_CATEGORY
# from it) or a list of queries (splits PHOTOS_PER_CATEGORY across them).
# The list form exists because a single query often returns one
# photographer's whole shoot -- e.g. "car detail minimal automotive"
# returned 8 close-ups of the same Camaro badge, not 8 different cars.
# Spreading across several specific queries (real brands, real equipment)
# gives an actually-diverse, recognizable pool instead.
CATEGORY_QUERIES = {
    "electronics": ["smartphone photography", "wireless headphones", "smart tv screen", "digital camera minimal"],
    "appliances": ["refrigerator kitchen", "washing machine", "coffee maker minimal", "microwave oven"],
    "apparel": ["denim jeans fashion", "leather jacket fashion", "sneakers shoes editorial", "fashion clothing rack"],
    "computers": ["laptop computer minimal desk", "gaming pc setup", "computer monitor desk", "mechanical keyboard"],
    "furniture": ["modern sofa living room", "wooden dining table", "office chair minimal", "bed bedroom furniture"],
    "construction": ["power tools construction", "hammer nails tools", "toolbox tools minimal", "drill tool"],
    "kids": ["colorful kids toys", "stuffed animal toy", "wooden building blocks toy", "baby stroller"],
    "accessories": ["wrist watch minimal", "sunglasses fashion editorial", "leather handbag", "jewelry accessories minimal"],
    "sport": ["dumbbells gym", "barbell weights gym", "gym bench press equipment", "gym equipment minimal"],
    "auto": ["BMW car exterior", "Mercedes Benz car exterior", "Toyota car exterior", "Audi car exterior"],
    "stationery": ["notebook pen stationery", "office desk supplies", "art supplies colored pencils", "planner notebook minimal"],
    "country_yard": ["garden tools minimal", "lawn mower yard", "watering can garden", "outdoor patio furniture"],
    "medicine": ["pharmacy medicine bottles", "vitamins supplements minimal", "first aid kit", "medical equipment minimal"],
    "generic": ["minimalist product photography studio", "product photography white background"],
}


def load_pexels_api_key():
    env_path = REPO_ROOT / ".env"
    for line in env_path.read_text().splitlines():
        if line.startswith("PEXELS_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(f"PEXELS_API_KEY not found in {env_path}")


def search_photos(query, api_key, per_page=PHOTOS_PER_CATEGORY):
    # Pexels sits behind Cloudflare, which blocks Python's default
    # "Python-urllib/x.y" User-Agent as a bot signature -- a browser-like
    # one is required even though curl (a different default UA) works fine.
    url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(query)}&per_page={per_page}&orientation=square"
    request = urllib.request.Request(
        url,
        headers={"Authorization": api_key, "User-Agent": "Mozilla/5.0 (compatible; product-recommender/1.0)"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def download(url, dest_path):
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (compatible; product-recommender/1.0)"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        dest_path.write_bytes(response.read())


def fetch_category(category, query, api_key):
    """query may be a single string or a list of strings (split across them)."""
    category_dir = IMAGES_DIR / category
    category_dir.mkdir(parents=True, exist_ok=True)

    queries = query if isinstance(query, list) else [query]
    per_query = max(1, -(-PHOTOS_PER_CATEGORY // len(queries)))  # ceil division

    saved = 0
    for q in queries:
        print(f"Fetching '{q}' for category '{category}'...")
        try:
            result = search_photos(q, api_key, per_page=per_query)
        except urllib.error.HTTPError as e:
            print(f"  HTTP error {e.code} for '{category}' query '{q}': {e.reason}")
            time.sleep(0.5)
            continue

        for photo in result.get("photos", []):
            if saved >= PHOTOS_PER_CATEGORY:
                break
            saved += 1
            dest_path = category_dir / f"{saved}.jpg"
            try:
                download(photo["src"]["large"], dest_path)
            except urllib.error.URLError as e:
                print(f"  Failed to download image {saved} for '{category}': {e}")
                saved -= 1
        time.sleep(0.5)  # stay well under Pexels' rate limit

    print(f"  Saved {saved} photos for '{category}'.")
    return saved


def fetch_all(categories=None):
    api_key = load_pexels_api_key()
    counts = {}
    targets = {c: CATEGORY_QUERIES[c] for c in categories} if categories else CATEGORY_QUERIES

    for category, query in targets.items():
        counts[category] = fetch_category(category, query, api_key)

    return counts


if __name__ == "__main__":
    import sys

    categories_arg = sys.argv[1:] or None  # e.g. `python fetch_product_images.py auto sport`
    counts = fetch_all(categories_arg)

    print("\nFinal counts per category:")
    for category, count in counts.items():
        print(f"  {category}: {count}")

    print("\nNow update CATEGORY_IMAGE_COUNTS in src/lib/productImage.js with these counts.")
