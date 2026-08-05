import { useEffect, useState } from "react";

import { api } from "@/api/client";
import ProductRow from "@/components/ProductRow.jsx";

// Session-based, not account-based: `productIds` is whatever short recent
// sequence the caller has on hand (viewed-product history on a product
// page, current cart contents in the drawer) -- not tied to a login.
export default function RecommendationsSection({ productIds, title = "You might also like", className = "mt-12" }) {
  const [items, setItems] = useState(null);
  // Arrays compare by reference -- a fresh literal from the caller (e.g.
  // cart.items.map(...)) would re-trigger this effect on every unrelated
  // re-render. Depend on a stable string key of the actual contents instead.
  const idsKey = (productIds ?? []).join(",");

  useEffect(() => {
    if (!idsKey) {
      setItems([]);
      return;
    }
    let cancelled = false;
    api
      .predict(idsKey.split(",").map(Number))
      .then((result) => {
        if (!cancelled) setItems(result.items);
      })
      .catch(() => {
        if (!cancelled) setItems([]);
      });
    return () => {
      cancelled = true;
    };
  }, [idsKey]);

  if (items && items.length === 0) return null;

  return <ProductRow title={title} items={items} className={className} />;
}
