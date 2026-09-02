import { AlertTriangle, Home, RotateCcw } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { Button } from "./ui/button";

export function ErrorComponent({ error }: { error: Error }) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center p-8 text-center">
      <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-danger/10">
        <AlertTriangle className="h-8 w-8 text-danger" />
      </div>
      <h1 className="mb-2 text-2xl font-semibold tracking-tight text-foreground">
        Something went wrong
      </h1>
      <p className="mb-8 max-w-md text-muted-foreground">
        {error?.message || "An unexpected error occurred while loading this module."}
      </p>
      
      <div className="flex gap-4">
        <Button onClick={() => window.location.reload()} variant="outline">
          <RotateCcw className="mr-2 h-4 w-4" />
          Try again
        </Button>
        <Link to="/">
          <Button>
            <Home className="mr-2 h-4 w-4" />
            Back to Home
          </Button>
        </Link>
      </div>
    </div>
  );
}
