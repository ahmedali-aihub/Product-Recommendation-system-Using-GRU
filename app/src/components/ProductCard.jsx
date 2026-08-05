import { motion } from "framer-motion";
import { Plus } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { api } from "@/api/client";
import { useCart } from "@/context/CartContext.jsx";
import { getProductImageUrl } from "@/lib/productImage";

export default function ProductCard({ product }) {
  const { refreshCart } = useCart();

  const handleQuickAdd = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    await api.addCartItem(product.product_id, 1);
    await refreshCart();
    toast(`Added ${product.display_name} to bag`);
  };

  return (
    <motion.div
      whileHover={{ y: -4 }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
      className="group relative overflow-hidden rounded-xl border bg-card shadow-sm transition-shadow hover:shadow-md"
    >
      <Link to={`/products/${product.product_id}`}>
        <div className="relative aspect-square overflow-hidden bg-muted">
          <motion.img
            src={getProductImageUrl(product)}
            alt={product.display_name}
            className="h-full w-full object-cover"
            whileHover={{ scale: 1.05 }}
            transition={{ duration: 0.4 }}
            onError={(e) => {
              e.currentTarget.onerror = null;
              e.currentTarget.src = "/icons/generic.svg";
            }}
          />
          <button
            onClick={handleQuickAdd}
            className="absolute bottom-3 right-3 flex h-9 w-9 items-center justify-center rounded-full bg-background/90 opacity-0 shadow-md backdrop-blur transition-opacity group-hover:opacity-100 hover:bg-background"
            aria-label="Quick add to cart"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>
        <div className="space-y-1 p-3">
          <p className="line-clamp-1 text-sm font-medium">{product.display_name}</p>
          {product.brand && <p className="text-xs text-muted-foreground">{product.brand}</p>}
          <p className="text-sm font-semibold">
            {product.price != null ? `$${product.price.toFixed(2)}` : "—"}
          </p>
        </div>
      </Link>
    </motion.div>
  );
}
