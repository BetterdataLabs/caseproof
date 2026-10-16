import type { Metadata } from "next";
import { Suspense } from "react";
import { ResearchView } from "@/components/research-view";
import { Skeleton } from "@/components/ui/primitives";

export const metadata: Metadata = { title: "Research" };

export default function ResearchPage() {
  return (
    <Suspense
      fallback={
        <div className="p-8">
          <Skeleton className="h-96" />
        </div>
      }
    >
      <ResearchView />
    </Suspense>
  );
}
