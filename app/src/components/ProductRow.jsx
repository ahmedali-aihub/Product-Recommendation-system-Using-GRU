import { Link } from "react-router-dom";

import ProductCard from "@/components/ProductCard.jsx";
import { Skeleton } from "@/components/ui/skeleton";

// Presentational only -- title + horizontal-scrolling row of ProductCards,
// with skeleton placeholders while `items` is still loading (undefined/null).
export default function ProductRow({ title, subtitle, items, viewAllHref, className = "mt-12" }) {
  return (
    <section className={className}>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
          {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
        </div>
        {viewAllHref && (
          <Link to={viewAllHref} className="text-sm text-muted-foreground hover:text-foreground">
            See all &rarr;
          </Link>
        )}
      </div>
      <div className="flex gap-4 overflow-x-auto pb-2">
        {(items ?? Array.from({ length: 4 })).map((item, i) => (
          <div key={item?.product_id ?? i} className="w-40 flex-shrink-0 sm:w-48">
            {item ? <ProductCard product={item} /> : <Skeleton className="aspect-square w-full rounded-xl" />}
          </div>
        ))}
      </div>
    </section>
  );
}
