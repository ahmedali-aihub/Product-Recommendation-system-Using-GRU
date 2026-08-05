import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api } from "../api/client";

// Shared state this app needs: the cart item count (navbar badge) and
// whether the cart drawer is open, so "Add to Cart" on any page can pop
// the drawer open. Cart *contents* are still fetched by the drawer itself
// when it opens -- no global store for that, just this small bit of UI state.
const CartContext = createContext(null);

export function CartProvider({ children }) {
  const [itemCount, setItemCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);

  const refreshCart = useCallback(async () => {
    try {
      const cart = await api.getCart();
      setItemCount(cart.total_items);
    } catch {
      setItemCount(0);
    }
  }, []);

  useEffect(() => {
    refreshCart();
  }, [refreshCart]);

  const openCart = useCallback(() => setIsOpen(true), []);
  const closeCart = useCallback(() => setIsOpen(false), []);

  return (
    <CartContext.Provider value={{ itemCount, refreshCart, isOpen, setIsOpen, openCart, closeCart }}>
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  return useContext(CartContext);
}
