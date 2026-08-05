import { Search, ShoppingBag } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCart } from "@/context/CartContext.jsx";

import ThemeToggle from "./ThemeToggle.jsx";

export default function Navbar() {
  const [categories, setCategories] = useState([]);
  const { itemCount, openCart } = useCart();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("q") ?? "");

  useEffect(() => {
    api.getCategories().then(setCategories).catch(() => setCategories([]));
  }, []);

  // Keep the box in sync if the URL's ?q= changes from elsewhere (e.g. back/forward nav).
  useEffect(() => {
    setQuery(searchParams.get("q") ?? "");
  }, [searchParams]);

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (trimmed) navigate(`/search?q=${encodeURIComponent(trimmed)}`);
  };

  return (
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-16 items-center gap-4">
        <Link to="/" className="text-lg font-semibold tracking-tight">
          Storefront
        </Link>

        <form onSubmit={handleSubmit} className="relative hidden w-56 flex-shrink-0 sm:block">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search products..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="h-9 pl-8"
          />
        </form>

        <nav className="flex flex-1 items-center gap-2 overflow-x-auto py-2">
          {categories.map((c) => (
            <Link key={c.category} to={`/category/${c.category}`}>
              <Badge variant="secondary" className="whitespace-nowrap font-normal">
                {c.category}
              </Badge>
            </Link>
          ))}
        </nav>

        <ThemeToggle />

        <Button variant="ghost" size="icon" className="relative" onClick={openCart} aria-label="Open cart">
          <ShoppingBag className="h-5 w-5" />
          {itemCount > 0 && (
            <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[10px] font-medium text-destructive-foreground">
              {itemCount}
            </span>
          )}
        </Button>
      </div>
    </header>
  );
}
