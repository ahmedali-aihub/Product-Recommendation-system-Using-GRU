import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";

export default function CategoryFilterBar({ categories, activeCategory }) {
  return (
    <div className="flex flex-wrap gap-2">
      <Link to="/">
        <Badge variant={!activeCategory ? "default" : "outline"} className="cursor-pointer font-normal">
          All
        </Badge>
      </Link>
      {categories.map((c) => (
        <Link key={c.category} to={`/category/${c.category}`}>
          <Badge
            variant={activeCategory === c.category ? "default" : "outline"}
            className="cursor-pointer font-normal"
          >
            {c.category} ({c.product_count})
          </Badge>
        </Link>
      ))}
    </div>
  );
}
