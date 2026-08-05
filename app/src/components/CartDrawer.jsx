import { AnimatePresence, motion } from "framer-motion";
import { Minus, Plus, ShoppingBag, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { api } from "@/api/client";
import RecommendationsSection from "@/components/RecommendationsSection.jsx";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useCart } from "@/context/CartContext.jsx";
import { getProductImageUrl } from "@/lib/productImage";

export default function CartDrawer() {
  const { isOpen, setIsOpen, refreshCart } = useCart();
  const [cart, setCart] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      setCart(await api.getCart());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const handleQuantityChange = async (productId, quantity) => {
    await api.updateCartItem(productId, quantity);
    await load();
    await refreshCart();
  };

  const handleRemove = async (productId, name) => {
    await api.removeCartItem(productId);
    await load();
    await refreshCart();
    toast(`Removed ${name}`);
  };

  return (
    <Sheet open={isOpen} onOpenChange={setIsOpen}>
      <SheetContent className="flex w-full flex-col sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <ShoppingBag className="h-5 w-5" />
            Your Bag
          </SheetTitle>
        </SheetHeader>

        {loading && <p className="mt-8 text-center text-sm text-muted-foreground">Loading...</p>}

        {!loading && cart && cart.items.length === 0 && (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
            <ShoppingBag className="h-10 w-10 opacity-30" />
            <p>Your bag is empty.</p>
          </div>
        )}

        {!loading && cart && cart.items.length > 0 && (
          <div className="mt-4 flex flex-1 flex-col overflow-hidden">
            <div className="flex-1 overflow-y-auto pr-1">
              <AnimatePresence initial={false}>
                {cart.items.map((item) => (
                  <motion.div
                    key={item.product_id}
                    layout
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.2 }}
                    className="flex gap-3 py-4"
                  >
                    <img
                      src={getProductImageUrl(item)}
                      alt={item.display_name}
                      className="h-16 w-16 flex-shrink-0 rounded-md border object-cover"
                      onError={(e) => {
                        e.currentTarget.onerror = null;
                        e.currentTarget.src = "/icons/generic.svg";
                      }}
                    />
                    <div className="flex flex-1 flex-col gap-1">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm font-medium leading-tight">{item.display_name}</p>
                        <button
                          onClick={() => handleRemove(item.product_id, item.display_name)}
                          className="text-muted-foreground hover:text-destructive"
                          aria-label="Remove item"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                      {item.brand && <p className="text-xs text-muted-foreground">{item.brand}</p>}
                      <div className="mt-1 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <button
                            className="flex h-6 w-6 items-center justify-center rounded border hover:bg-accent"
                            onClick={() => handleQuantityChange(item.product_id, item.quantity - 1)}
                          >
                            <Minus className="h-3 w-3" />
                          </button>
                          <span className="w-4 text-center text-sm">{item.quantity}</span>
                          <button
                            className="flex h-6 w-6 items-center justify-center rounded border hover:bg-accent"
                            onClick={() => handleQuantityChange(item.product_id, item.quantity + 1)}
                          >
                            <Plus className="h-3 w-3" />
                          </button>
                        </div>
                        <span className="text-sm font-semibold">${item.line_total.toFixed(2)}</span>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>

              <RecommendationsSection productIds={cart.items.map((item) => item.product_id)} />
            </div>

            <Separator />
            <div className="flex items-center justify-between py-4 text-base font-semibold">
              <span>Total</span>
              <span>${cart.total_price.toFixed(2)}</span>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
