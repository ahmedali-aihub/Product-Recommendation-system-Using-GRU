import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";

export default function NotFoundPage() {
  return (
    <div className="flex flex-col items-center gap-4 py-24 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">Page not found</h1>
      <p className="text-muted-foreground">There's nothing at this address.</p>
      <Button asChild>
        <Link to="/">Back to Storefront</Link>
      </Button>
    </div>
  );
}
