import { ArrowLeft, Minus, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { api } from "@/api/client";
import ProductRow from "@/components/ProductRow.jsx";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useCart } from "@/context/CartContext.jsx";
import { getProductImageUrl } from "@/lib/productImage";
import { recordProductView } from "@/lib/sessionHistory";
import { useSlowLoad } from "@/lib/useSlowLoad";

export default function ProductDetailPage() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const { refreshCart, openCart } = useCart();

  const [product, setProduct] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [quantity, setQuantity] = useState(1);
  const [adding, setAdding] = useState(false);
  const [relatedProducts, setRelatedProducts] = useState(null);
  const isSlow = useSlowLoad(!product && !notFound);

  useEffect(() => {
    setNotFound(false);
    setProduct(null);
    setRelatedProducts(null);
    setQuantity(1);
    api
      .getProduct(productId)
      .then((p) => {
        setProduct(p);
        // Record the view -- still drives the homepage's "Recommended for
        // you" (an actual model prediction). This page's own "You might
        // also like" is plain same-category browsing, not a prediction.
        recordProductView(p.product_id);

        if (!p.category_top) {
          setRelatedProducts([]);
          return;
        }
        api
          .getProducts({ category: p.category_top, page: 1, pageSize: 9 })
          .then((result) => {
            setRelatedProducts(result.items.filter((item) => item.product_id !== p.product_id).slice(0, 8));
          })
          .catch(() => setRelatedProducts([]));
      })
      .catch(() => setNotFound(true));
  }, [productId]);

  if (notFound) {
    return <div className="py-24 text-center text-muted-foreground">Product not found.</div>;
  }

  if (!product) {
    return (
      <div>
        {isSlow && (
          <div className="mb-4 rounded-lg border bg-card p-3 text-sm text-muted-foreground">
            Waking up the server -- this backend runs on a free tier that sleeps when idle, so
            the first load can take up to a minute. It'll be fast from here on.
          </div>
        )}
        <div className="flex flex-col gap-8 sm:flex-row">
          <Skeleton className="h-72 w-72 rounded-xl" />
          <div className="flex-1 space-y-3">
            <Skeleton className="h-8 w-1/2" />
            <Skeleton className="h-4 w-1/4" />
            <Skeleton className="h-10 w-32" />
          </div>
        </div>
      </div>
    );
  }

  const handleAddToCart = async () => {
    setAdding(true);
    try {
      await api.addCartItem(product.product_id, quantity);
      await refreshCart();
      toast(`Added ${quantity} × ${product.display_name} to bag`);
      openCart();
    } finally {
      setAdding(false);
    }
  };

  return (
    <div>
      <button
        onClick={() => navigate(-1)}
        className="mb-6 flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> Back
      </button>

      <div className="flex flex-col gap-10 sm:flex-row">
        <img
          src={getProductImageUrl(product)}
          alt={product.display_name}
          className="aspect-square w-full max-w-md rounded-2xl border object-cover"
          onError={(e) => {
            e.currentTarget.onerror = null;
            e.currentTarget.src = "/icons/generic.svg";
          }}
        />

        <div className="flex-1 space-y-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{product.display_name}</h1>
            {product.brand && <p className="mt-1 text-muted-foreground">{product.brand}</p>}
          </div>

          {product.category_code && (
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              {product.category_code.split(".").join(" / ")}
            </p>
          )}

          <p className="text-3xl font-semibold">
            {product.price != null ? `$${product.price.toFixed(2)}` : "Price unavailable"}
          </p>

          <div className="flex items-center gap-4 pt-2">
            <div className="flex items-center rounded-md border">
              <button
                className="flex h-10 w-10 items-center justify-center hover:bg-accent"
                onClick={() => setQuantity((q) => Math.max(1, q - 1))}
              >
                <Minus className="h-4 w-4" />
              </button>
              <span className="w-8 text-center">{quantity}</span>
              <button
                className="flex h-10 w-10 items-center justify-center hover:bg-accent"
                onClick={() => setQuantity((q) => q + 1)}
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>
            <Button size="lg" onClick={handleAddToCart} disabled={adding} className="flex-1 sm:flex-none">
              {adding ? "Adding..." : "Add to Bag"}
            </Button>
          </div>
        </div>
      </div>

      {relatedProducts == null || relatedProducts.length > 0 ? (
        <ProductRow title="You might also like" items={relatedProducts} />
      ) : null}
    </div>
  );
}
