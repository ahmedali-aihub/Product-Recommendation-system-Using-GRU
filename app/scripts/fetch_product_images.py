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
# Queries are weighted toward each category's REAL sub-category (category_leaf)
# composition in the products table -- not guessed from the category_top name
# alone. That guess was wrong twice: "auto" sounds like cars, but 88% of it is
# actually car electronics (player/videoregister/alarm -- car stereos, dash
# cams, alarms), and "sport" sounds like gym equipment, but 68% of it is
# bicycles. A query list repeats its dominant leaf's query to weight the pool
# toward it (e.g. two bicycle queries + one tennis + one ski, roughly matching
# sport's real 68/11/10/7 split), without literally duplicating a query
# string (which would just re-fetch the same top results twice).
CATEGORY_QUERIES = {
    # clocks 51%, headphone 14%, smartphone 9%, tv/subwoofer/acoustic ~14%
    "electronics": ["wall clock minimal", "modern wall clock design", "wireless headphones", "smartphone photography"],
    # no single dominant leaf (28 leaves) -- flat mix of the top kitchen appliances
    "appliances": ["refrigerator kitchen", "kitchen extractor hood", "oven stove kitchen", "vacuum cleaner"],
    # shoes+keds+sandals ~69% (footwear), underwear 14%
    "apparel": ["sneakers shoes editorial", "canvas sneakers shoes", "underwear clothing minimal", "sandals shoes"],
    "computers": ["laptop computer minimal desk", "desktop computer tower", "computer mouse", "computer monitor desk"],
    "furniture": ["modern chair minimal", "bed bedroom furniture", "wooden cabinet furniture", "wooden dining table"],
    "construction": ["power drill tool", "faucet bathroom fixture", "water pump tool", "circular saw tool"],
    # toys 42%, carriage (stroller) 31%, dolls 12%, skates 8%
    "kids": ["colorful kids toys", "baby stroller carriage", "doll toy", "roller skates"],
    # bag 78%, wallet 20%, umbrella 2%
    "accessories": ["leather handbag", "designer handbag fashion", "leather wallet"],
    # bicycle 68%, tennis 11%, ski 10%, snowboard 7%
    "sport": ["bicycle cycling outdoor", "road bike bicycle", "tennis racket", "ski snowboard equipment"],
    # player 42%, videoregister (dash cam) 24%, alarm 11%, compressor/radar/parktronic 21%
    "auto": ["car stereo audio system", "car multimedia player dashboard", "dash cam dashboard camera", "car alarm system"],
    # cartrige (printer ink) 100% -- Pexels has no real cartridge product
    # photography (tried several queries, all returned unrelated results:
    # printing presses, ink-in-water art, laser cutters). Falls back to
    # general stationery/office-supply flat lays -- same honest tradeoff as
    # everywhere else: category-representative, not exact-SKU.
    "stationery": ["notebook pen desk flat lay", "office desk supplies minimal", "art supplies colored pencils flat lay"],
    # lawn_mower 86%, cultivator 10%
    "country_yard": ["lawn mower garden grass", "lawn mower cutting grass", "garden cultivator tool"],
    # tonometer (blood pressure monitor) 100% -- same Pexels gap as
    # stationery (tried "blood pressure monitor/cuff/sphygmomanometer", all
    # returned hospital-bed or blood-donation scenes, not product shots).
    # Falls back to general clean medical-device flat lays.
    "medicine": ["medical equipment flat lay minimal", "stethoscope medical device minimal"],
    "generic": ["minimalist product photography studio", "product photography white background"],
}

# The queries above blend several real sub-categories (category_leaf) into
# ONE shared photo pool per top-level category -- e.g. electronics blends
# clock + headphone + smartphone + tv photos into one pool, and a product's
# photo is picked by `product_id % pool_size`, with no regard for which of
# those it actually is. A "Samsung Smartphone" can end up showing a clock.
#
# This maps the dominant leaves to their OWN single-subject query, so
# products get photos from a pool that actually matches their real type.
# Only the leaves that make up most of a category's volume are covered
# (the ones already identified above); long-tail leaves fall back to the
# blended CATEGORY_QUERIES pool for their top-level category.
PHOTOS_PER_LEAF = 6
LEAF_QUERIES = {
    "electronics": {
        "clocks": ["wall clock minimal", "modern wall clock design"],
        "headphone": "wireless headphones",
        "smartphone": "smartphone photography",
        "tv": "television screen minimal",
    },
    "appliances": {
        "refrigerators": "refrigerator kitchen",
        "hood": "kitchen extractor hood",
        "oven": "oven stove kitchen",
        "vacuum": "vacuum cleaner",
    },
    "apparel": {
        "shoes": "sneakers shoes editorial",
        "keds": "canvas sneakers shoes",
        "underwear": "underwear clothing minimal",
        "sandals": "sandals shoes",
    },
    "computers": {
        "notebook": "laptop computer minimal desk",
        "desktop": "desktop computer tower",
        "mouse": "computer mouse",
        "monitor": "computer monitor desk",
    },
    "furniture": {
        "chair": "modern chair minimal",
        "bed": "bed bedroom furniture",
        "cabinet": "wooden cabinet furniture",
        "table": "wooden dining table",
    },
    "construction": {
        "drill": "power drill tool",
        "faucet": "faucet bathroom fixture",
        "pump": "water pump tool",
        "saw": "circular saw tool",
    },
    "kids": {
        "toys": "colorful kids toys",
        "carriage": "baby stroller carriage",
        "dolls": "doll toy",
        "skates": "roller skates",
    },
    "accessories": {
        "bag": ["leather handbag", "designer handbag fashion"],
        "wallet": "leather wallet",
    },
    "sport": {
        "bicycle": ["bicycle cycling outdoor", "road bike bicycle"],
        "tennis": "tennis racket",
        "ski": "ski equipment snow",
        "snowboard": "snowboard equipment",
    },
    "auto": {
        "player": ["car stereo audio system", "car multimedia player dashboard"],
        "videoregister": "dash cam dashboard camera",
        "alarm": "car alarm system",
    },
    "country_yard": {
        "lawn_mower": ["lawn mower garden grass", "lawn mower cutting grass"],
        "cultivator": "garden cultivator tool",
    },
    # stationery and medicine are each 100% one leaf already -- their
    # top-level CATEGORY_QUERIES pool IS the leaf pool, no split needed.
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


def fetch_pool(dest_dir, label, query, api_key, photos_wanted):
    """query may be a single string or a list of strings (split across them)."""
    dest_dir.mkdir(parents=True, exist_ok=True)

    queries = query if isinstance(query, list) else [query]
    per_query = max(1, -(-photos_wanted // len(queries)))  # ceil division

    saved = 0
    for q in queries:
        print(f"Fetching '{q}' for '{label}'...")
        try:
            result = search_photos(q, api_key, per_page=per_query)
        except urllib.error.HTTPError as e:
            print(f"  HTTP error {e.code} for '{label}' query '{q}': {e.reason}")
            time.sleep(0.5)
            continue

        for photo in result.get("photos", []):
            if saved >= photos_wanted:
                break
            saved += 1
            dest_path = dest_dir / f"{saved}.jpg"
            try:
                download(photo["src"]["large"], dest_path)
            except urllib.error.URLError as e:
                print(f"  Failed to download image {saved} for '{label}': {e}")
                saved -= 1
        time.sleep(0.5)  # stay well under Pexels' rate limit

    print(f"  Saved {saved} photos for '{label}'.")
    return saved


def fetch_all(categories=None):
    """Top-level category pools -- the blended fallback used by any product
    whose leaf isn't individually covered by fetch_all_leaves()."""
    api_key = load_pexels_api_key()
    counts = {}
    targets = {c: CATEGORY_QUERIES[c] for c in categories} if categories else CATEGORY_QUERIES

    for category, query in targets.items():
        counts[category] = fetch_pool(IMAGES_DIR / category, category, query, api_key, PHOTOS_PER_CATEGORY)

    return counts


def fetch_all_leaves(categories=None):
    """Per-leaf pools -- what most products actually resolve to. Saved under
    public/images/{category_top}/leaf-{category_leaf}/{n}.jpg."""
    api_key = load_pexels_api_key()
    counts = {}
    targets = {c: LEAF_QUERIES[c] for c in categories} if categories else LEAF_QUERIES

    for category, leaves in targets.items():
        counts[category] = {}
        for leaf, query in leaves.items():
            label = f"{category}/{leaf}"
            dest_dir = IMAGES_DIR / category / f"leaf-{leaf}"
            counts[category][leaf] = fetch_pool(dest_dir, label, query, api_key, PHOTOS_PER_LEAF)

    return counts


if __name__ == "__main__":
    import sys

    # `python fetch_product_images.py auto sport` -> top-level pools for those
    # `python fetch_product_images.py --leaves auto sport` -> leaf pools for those
    # `python fetch_product_images.py --leaves` -> leaf pools for everything
    args = sys.argv[1:]
    if args and args[0] == "--leaves":
        categories_arg = args[1:] or None
        counts = fetch_all_leaves(categories_arg)
        print("\nFinal leaf counts:")
        for category, leaves in counts.items():
            for leaf, count in leaves.items():
                print(f"  {category}/{leaf}: {count}")
        print("\nNow update CATEGORY_LEAF_IMAGE_COUNTS in src/lib/productImage.js with these counts.")
    else:
        categories_arg = args or None
        counts = fetch_all(categories_arg)
        print("\nFinal counts per category:")
        for category, count in counts.items():
            print(f"  {category}: {count}")
        print("\nNow update CATEGORY_IMAGE_COUNTS in src/lib/productImage.js with these counts.")
