// Real per-SKU photos don't exist for this dataset (REES46 has none) --
// so photos are curated PER CATEGORY (via scripts/fetch_product_images.py,
// a one-time Pexels fetch) and each product deterministically picks one
// from its category's pool. Same product always shows the same photo;
// the pool rotates across every product in that category.
//
// Counts are filled in as photo sets land in public/images/{category}/ --
// a category not in this map (or count 0) falls back to "generic".
export const CATEGORY_IMAGE_COUNTS = {
  electronics: 8,
  appliances: 8,
  apparel: 8,
  computers: 8,
  furniture: 8,
  construction: 8,
  kids: 8,
  accessories: 8,
  sport: 8,
  auto: 8,
  stationery: 8,
  country_yard: 8,
  medicine: 8,
  generic: 8,
};

export function getProductImageUrl(product) {
  const category = product.category_top;
  const count = category ? CATEGORY_IMAGE_COUNTS[category] : 0;

  if (!count) {
    const genericCount = CATEGORY_IMAGE_COUNTS.generic;
    if (!genericCount) return "/icons/generic.svg"; // photos not fetched yet -- icon fallback
    const index = (product.product_id % genericCount) + 1;
    return `/images/generic/${index}.jpg`;
  }

  const index = (product.product_id % count) + 1;
  return `/images/${category}/${index}.jpg`;
}

// Cover art for a category tile (no specific product to key off of) --
// just use the first image in that category's pool.
export function getCategoryImageUrl(categoryTop) {
  const count = categoryTop ? CATEGORY_IMAGE_COUNTS[categoryTop] : 0;
  if (!count) {
    const genericCount = CATEGORY_IMAGE_COUNTS.generic;
    return genericCount ? "/images/generic/1.jpg" : "/icons/generic.svg";
  }
  return `/images/${categoryTop}/1.jpg`;
}
