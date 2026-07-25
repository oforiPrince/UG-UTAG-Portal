import { Suspense } from "react";

import { ProfileClient } from "./profile-client";

export default function ProfilePage() {
  return (
    <Suspense fallback={<div className="h-96 animate-pulse rounded-3xl bg-ink/5" />}>
      <ProfileClient />
    </Suspense>
  );
}
