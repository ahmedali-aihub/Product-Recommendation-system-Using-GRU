// Real per-SKU photos don't exist for this dataset (REES46 has none) --
// so photos are curated PER SUB-CATEGORY (via scripts/fetch_product_images.py,
// a one-time Pexels fetch) and each product deterministically picks one from
// its own category_leaf's pool (e.g. a smartphone always draws from the
// "smartphone" pool, never the "clocks" pool it shares a category_top with).
// Same product always shows the same photo; the pool rotates across every
// product with that same leaf.
//
// A leaf not covered here (long-tail sub-categories, not worth a dedicated
// Pexels query each) falls back to its category_top's blended pool, then to
// "generic" if that doesn't exist either.
export const CATEGORY_LEAF_IMAGE_COUNTS = {
  electronics: { clocks: 6, headphone: 6, smartphone: 6, tv: 6 },
  appliances: { refrigerators: 6, hood: 6, oven: 6, vacuum: 6 },
  apparel: { shoes: 6, keds: 6, underwear: 6, sandals: 6 },
  computers: { notebook: 6, desktop: 6, mouse: 6, monitor: 6 },
  furniture: { chair: 6, bed: 6, cabinet: 6, table: 6 },
  construction: { drill: 6, faucet: 6, pump: 6, saw: 6 },
  kids: { toys: 6, carriage: 6, dolls: 6, skates: 6 },
  accessories: { bag: 6, wallet: 6 },
  sport: { bicycle: 6, tennis: 6, ski: 6, snowboard: 6 },
  auto: { player: 6, videoregister: 6, alarm: 6 },
  country_yard: { lawn_mower: 6, cultivator: 6 },
};

// The blended, category_top-level fallback pool (still real, curated
// photography -- just mixes several sub-categories together, used only when
// a product's specific leaf isn't in CATEGORY_LEAF_IMAGE_COUNTS above).
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
  const { category_top: category, category_leaf: leaf, product_id: id } = product;

  const leafCount = category && leaf ? CATEGORY_LEAF_IMAGE_COUNTS[category]?.[leaf] : undefined;
  if (leafCount) {
    const index = (id % leafCount) + 1;
    return `/images/${category}/leaf-${leaf}/${index}.jpg`;
  }

  const categoryCount = category ? CATEGORY_IMAGE_COUNTS[category] : 0;
  if (categoryCount) {
    const index = (id % categoryCount) + 1;
    return `/images/${category}/${index}.jpg`;
  }

  const genericCount = CATEGORY_IMAGE_COUNTS.generic;
  if (!genericCount) return "/icons/generic.svg"; // photos not fetched yet -- icon fallback
  const index = (id % genericCount) + 1;
  return `/images/generic/${index}.jpg`;
}

// Cover art for a category tile (no specific product to key off of, so no
// leaf either) -- just use the first image in that category's blended pool.
export function getCategoryImageUrl(categoryTop) {
  const count = categoryTop ? CATEGORY_IMAGE_COUNTS[categoryTop] : 0;
  if (!count) {
    const genericCount = CATEGORY_IMAGE_COUNTS.generic;
    return genericCount ? "/images/generic/1.jpg" : "/icons/generic.svg";
  }
  return `/images/${categoryTop}/1.jpg`;
}
