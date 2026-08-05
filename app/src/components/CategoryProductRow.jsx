import { useEffect, useState } from "react";

import { api } from "@/api/client";
import ProductRow from "@/components/ProductRow.jsx";

// Homepage-only: a popularity-sorted sample of one category, e.g. "Top in
// electronics". Products already come back ORDER BY event_count DESC from
// the API, so no extra sorting/params needed here.
export default function CategoryProductRow({ category, title }) {
  const [listing, setListing] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getProducts({ category, page: 1, pageSize: 8 })
      .then((result) => {
        if (!cancelled) setListing(result);
      })
      .catch(() => {
        if (!cancelled) setListing({ items: [] });
      });
    return () => {
      cancelled = true;
    };
  }, [category]);

  if (listing && listing.items.length === 0) return null;

  return <ProductRow title={title} items={listing?.items} viewAllHref={`/category/${category}`} />;
}
