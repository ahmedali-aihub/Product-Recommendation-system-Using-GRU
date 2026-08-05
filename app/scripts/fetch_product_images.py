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
CATEGORY_QUERIES = {
    "electronics": "modern smartphone flat lay minimal",
    "appliances": "modern kitchen appliance minimal white",
    "apparel": "fashion clothing editorial minimal",
    "computers": "laptop computer minimal desk",
    "furniture": "minimalist furniture interior design",
    "construction": "construction tools flat lay minimal",
    "kids": "kids toys minimal flat lay",
    "accessories": "fashion accessories flat lay minimal",
    "sport": "sports equipment minimal flat lay",
    "auto": "car detail minimal automotive",
    "stationery": "stationery flat lay minimal aesthetic",
    "country_yard": "garden tools minimal outdoor",
    "medicine": "pharmacy medicine minimal flat lay",
    "generic": "minimalist product photography studio",
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


def fetch_all():
    api_key = load_pexels_api_key()
    counts = {}

    for category, query in CATEGORY_QUERIES.items():
        category_dir = IMAGES_DIR / category
        category_dir.mkdir(parents=True, exist_ok=True)

        print(f"Fetching '{query}' for category '{category}'...")
        try:
            result = search_photos(query, api_key)
        except urllib.error.HTTPError as e:
            print(f"  HTTP error {e.code} for '{category}': {e.reason}")
            counts[category] = 0
            continue

        photos = result.get("photos", [])
        saved = 0
        for i, photo in enumerate(photos, start=1):
            image_url = photo["src"]["large"]
            dest_path = category_dir / f"{i}.jpg"
            try:
                download(image_url, dest_path)
                saved += 1
            except urllib.error.URLError as e:
                print(f"  Failed to download image {i} for '{category}': {e}")

        counts[category] = saved
        print(f"  Saved {saved} photos.")
        time.sleep(0.5)  # stay well under Pexels' rate limit

    return counts


if __name__ == "__main__":
    counts = fetch_all()

    print("\nFinal counts per category:")
    for category, count in counts.items():
        print(f"  {category}: {count}")

    print("\nNow update CATEGORY_IMAGE_COUNTS in src/lib/productImage.js with these counts.")
