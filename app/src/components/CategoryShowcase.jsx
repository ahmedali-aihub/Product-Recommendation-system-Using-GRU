import { motion } from "framer-motion";
import { Link } from "react-router-dom";

import { Skeleton } from "@/components/ui/skeleton";
import { getCategoryImageUrl } from "@/lib/productImage";

export default function CategoryShowcase({ categories }) {
  return (
    <section>
      <h2 className="mb-4 text-lg font-semibold tracking-tight">Shop by Category</h2>
      {/* A horizontal scroll strip instead of a multi-row grid -- keeps all
          categories reachable without the homepage opening on two screens'
          worth of tiles before any actual products show up. */}
      <div className="flex gap-4 overflow-x-auto pb-2">
        {(categories.length === 0 ? Array.from({ length: 6 }) : categories).map((c, i) => (
          <div key={c?.category ?? i} className="w-32 flex-shrink-0 sm:w-36">
            {!c ? (
              <div className="space-y-2">
                <Skeleton className="aspect-square w-full rounded-xl" />
                <Skeleton className="h-4 w-2/3" />
              </div>
            ) : (
              <Link to={`/category/${c.category}`}>
                <motion.div
                  whileHover={{ y: -4 }}
                  transition={{ type: "spring", stiffness: 300, damping: 20 }}
                  className="overflow-hidden rounded-xl border bg-card shadow-sm transition-shadow hover:shadow-md"
                >
                  <div className="aspect-square overflow-hidden bg-muted">
                    <img
                      src={getCategoryImageUrl(c.category)}
                      alt={c.category}
                      className="h-full w-full object-cover"
                      onError={(e) => {
                        e.currentTarget.onerror = null;
                        e.currentTarget.src = "/icons/generic.svg";
                      }}
                    />
                  </div>
                  <div className="space-y-0.5 p-3">
                    <p className="text-sm font-medium capitalize">{c.category.replace("_", " ")}</p>
                    <p className="text-xs text-muted-foreground">{c.product_count.toLocaleString()} products</p>
                  </div>
                </motion.div>
              </Link>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
