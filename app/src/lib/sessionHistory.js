// A lightweight, client-side "current session" -- the last few products
// viewed, most recent last. This is what gets sent to /predict: it's the
// same idea as the cart_id pattern (no login, no server-side session),
// and it's genuinely what the model was trained to read -- a short recent
// sequence, not a full account history.
const STORAGE_KEY = "viewed_products";
const MAX_HISTORY = 10;

export function recordProductView(productId) {
  const history = getViewedProducts().filter((id) => id !== productId);
  history.push(productId);
  const trimmed = history.slice(-MAX_HISTORY);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
  return trimmed;
}

export function getViewedProducts() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}
