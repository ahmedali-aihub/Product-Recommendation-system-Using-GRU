const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
const CART_ID_STORAGE_KEY = "cart_id";

// A cart is identified by a client-generated id, not a login -- created
// once per browser and reused on every visit (see backend's src/serving/
// routers/cart.py for why: no accounts in v1, and this keeps the cart
// tied to "this session" rather than a user profile, matching how the
// recommender itself will eventually work).
export function getCartId() {
  let cartId = localStorage.getItem(CART_ID_STORAGE_KEY);
  if (!cartId) {
    cartId = crypto.randomUUID();
    localStorage.setItem(CART_ID_STORAGE_KEY, cartId);
  }
  return cartId;
}

async function request(path, { method = "GET", body, cartScoped = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (cartScoped) {
    headers["X-Cart-Id"] = getCartId();
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? `Request failed: ${response.status}`);
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

export const api = {
  getCategories: () => request("/api/categories"),
  getProducts: ({ category, search, page = 1, pageSize = 24 } = {}) => {
    const params = new URLSearchParams({ page, page_size: pageSize });
    if (category) params.set("category", category);
    if (search) params.set("search", search);
    return request(`/api/products?${params.toString()}`);
  },
  getProduct: (productId) => request(`/api/products/${productId}`),
  getCart: () => request("/api/cart", { cartScoped: true }),
  addCartItem: (productId, quantity = 1) =>
    request("/api/cart/items", {
      method: "POST",
      body: { product_id: productId, quantity },
      cartScoped: true,
    }),
  updateCartItem: (productId, quantity) =>
    request(`/api/cart/items/${productId}`, {
      method: "PATCH",
      body: { quantity },
      cartScoped: true,
    }),
  removeCartItem: (productId) =>
    request(`/api/cart/items/${productId}`, { method: "DELETE", cartScoped: true }),
  predict: (productIds, topK = 8) =>
    request("/api/predict", { method: "POST", body: { product_ids: productIds, top_k: topK } }),
};
