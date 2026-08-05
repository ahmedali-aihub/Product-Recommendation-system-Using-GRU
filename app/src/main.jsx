import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App.jsx";
import { ThemeProvider } from "./components/ThemeProvider.jsx";
import { Toaster } from "./components/ui/sonner.jsx";
import { CartProvider } from "./context/CartContext.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeProvider>
      <BrowserRouter>
        <CartProvider>
          <App />
          {/* top-center, not the bottom-right default -- the cart drawer's
              total/footer also lives bottom-right and would visually collide */}
          <Toaster position="top-center" />
        </CartProvider>
      </BrowserRouter>
    </ThemeProvider>
  </React.StrictMode>
);
