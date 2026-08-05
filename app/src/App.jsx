import { Route, Routes } from "react-router-dom";

import CartDrawer from "./components/CartDrawer.jsx";
import Footer from "./components/Footer.jsx";
import Navbar from "./components/Navbar.jsx";
import ProductDetailPage from "./pages/ProductDetailPage.jsx";
import ProductListPage from "./pages/ProductListPage.jsx";

export default function App() {
  return (
    <>
      <Navbar />
      <CartDrawer />
      <main className="container py-8">
        <Routes>
          <Route path="/" element={<ProductListPage />} />
          <Route path="/category/:category" element={<ProductListPage />} />
          <Route path="/search" element={<ProductListPage />} />
          <Route path="/products/:productId" element={<ProductDetailPage />} />
        </Routes>
      </main>
      <Footer />
    </>
  );
}
