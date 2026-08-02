import { Suspense } from "react";

import { AdvertsClient } from "./adverts-client";

export default function AdvertsPage() {
  return (
    <Suspense
      fallback={
        <div className="grid gap-5">
          <div className="h-24 animate-pulse rounded-2xl bg-ink/5" />
          <div className="h-10 w-full max-w-xl animate-pulse rounded-full bg-ink/5" />
          <div className="h-96 animate-pulse rounded-2xl bg-ink/5" />
        </div>
      }
    >
      <AdvertsClient />
    </Suspense>
  );
}
