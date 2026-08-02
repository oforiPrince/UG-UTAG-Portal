import { AdSlotBanner } from "./ad-slot-banner";
import { PublicFooter } from "./public-footer";
import { PublicHeader } from "./public-header";
import { getPublicSite } from "@/lib/public-site";

export async function PublicShell({ children }: { children: React.ReactNode }) {
  const site = await getPublicSite();
  return (
    <div className="public-site">
      <PublicHeader contact={site.contact} features={site.features} />
      {site.unavailable ? (
        <div
          role="status"
          className="bg-amber-50 px-5 py-2 text-center text-xs font-semibold text-amber-900"
        >
          Some live portal content is temporarily unavailable. Please try again
          shortly.
        </div>
      ) : null}
      <main id="main-content">{children}</main>
      <AdSlotBanner
        slotKey="footer"
        context="footer"
      />
      <PublicFooter
        contact={site.contact}
        features={site.features}
        settings={site.footer}
      />
    </div>
  );
}
