import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import CategoryFilterBar from "@/components/CategoryFilterBar.jsx";
import CategoryProductRow from "@/components/CategoryProductRow.jsx";
import CategoryShowcase from "@/components/CategoryShowcase.jsx";
import Pagination from "@/components/Pagination.jsx";
import ProductCard from "@/components/ProductCard.jsx";
import RecommendationsSection from "@/components/RecommendationsSection.jsx";
import { Skeleton } from "@/components/ui/skeleton";
import { getViewedProducts } from "@/lib/sessionHistory";
import { useSlowLoad } from "@/lib/useSlowLoad";

const gridVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04 } },
};

const cardVariants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0 },
};

const formatCategoryLabel = (category) =>
  category.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());

export default function ProductListPage() {
  const { category } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Number(searchParams.get("page") ?? 1);
  const search = searchParams.get("q") ?? undefined;

  const [categories, setCategories] = useState([]);
  const [listing, setListing] = useState(null);
  const [loading, setLoading] = useState(true);
  const isSlow = useSlowLoad(loading);

  useEffect(() => {
    api.getCategories().then(setCategories).catch(() => setCategories([]));
  }, []);

  useEffect(() => {
    setLoading(true);
    api
      .getProducts({ category, search, page })
      .then(setListing)
      .finally(() => setLoading(false));
  }, [category, search, page]);

  const goToPage = (newPage) => {
    const next = { page: newPage };
    if (search) next.q = search;
    setSearchParams(next);
  };

  // Only on the plain landing page (no category/search filter active) --
  // once someone's narrowed down to a category or a search, they've
  // already stated intent, and homepage-style "recommended for you" would
  // just be clutter competing with what they actually asked for.
  const showHomeRecommendations = !category && !search;

  return (
    <div>
      {showHomeRecommendations ? (
        <>
          <div className="mb-10 rounded-xl border bg-card p-4 text-sm text-muted-foreground">
            This store recommends products using a neural network trained on real shopping
            sessions -- not your account or purchase history. Click into a few products below,
            then come back here: <span className="text-foreground">Recommended for you</span> will
            update live based on what you just viewed.
          </div>
          <CategoryShowcase categories={categories} />
          <RecommendationsSection
            productIds={getViewedProducts()}
            title="Recommended for you"
            subtitle="Based on the products you've viewed this session"
          />
          {categories.slice(0, 2).map((c) => (
            <CategoryProductRow
              key={c.category}
              category={c.category}
              title={`Top in ${formatCategoryLabel(c.category)}`}
            />
          ))}
          <h2 className="mb-4 mt-12 text-lg font-semibold tracking-tight">All Products</h2>
        </>
      ) : search ? (
        <h1 className="mb-4 text-lg font-medium">
          Search results for <span className="font-semibold">&ldquo;{search}&rdquo;</span>
        </h1>
      ) : (
        <CategoryFilterBar categories={categories} activeCategory={category} />
      )}

      {loading && (
        <>
          {isSlow && (
            <div className="mb-4 rounded-lg border bg-card p-3 text-sm text-muted-foreground">
              Waking up the server -- this backend runs on a free tier that sleeps when idle, so
              the first load can take up to a minute. It'll be fast from here on.
            </div>
          )}
          <div className="mt-6 grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="space-y-2">
                <Skeleton className="aspect-square w-full rounded-xl" />
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-1/3" />
              </div>
            ))}
          </div>
        </>
      )}

      {!loading && listing && listing.items.length === 0 && (
        <div className="py-24 text-center text-muted-foreground">No products found.</div>
      )}

      {!loading && listing && listing.items.length > 0 && (
        <>
          <motion.div
            variants={gridVariants}
            initial="hidden"
            animate="show"
            className="mt-6 grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4"
          >
            {listing.items.map((product) => (
              <motion.div key={product.product_id} variants={cardVariants}>
                <ProductCard product={product} />
              </motion.div>
            ))}
          </motion.div>
          <Pagination page={listing.page} totalPages={listing.total_pages} onPageChange={goToPage} />
        </>
      )}
    </div>
  );
}
