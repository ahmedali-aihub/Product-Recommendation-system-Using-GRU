import { Github } from "lucide-react";

export default function Footer() {
  return (
    <footer className="border-t bg-muted/30 text-muted-foreground">
      <div className="container flex flex-col items-center gap-2 py-8 text-sm sm:flex-row sm:justify-between">
        <p>
          <span className="font-medium text-foreground">Storefront</span> &mdash; session-based recommendations
          powered by GRU4Rec
        </p>
        <a
          href="https://github.com/datascientistx7/Product-Recommendation-system-Using-GRU"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1.5 hover:text-foreground"
        >
          <Github className="h-4 w-4" />
          View on GitHub
        </a>
      </div>
    </footer>
  );
}
