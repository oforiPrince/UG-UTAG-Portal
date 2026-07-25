import { AdSlotBanner } from "./ad-slot-banner";
import { PublicFooter } from "./public-footer";
import { PublicHeader } from "./public-header";

export function PublicShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="public-site">
      <PublicHeader />
      <AdSlotBanner slotKey="top" />
      <main id="main-content">{children}</main>
      <AdSlotBanner slotKey="footer" />
      <PublicFooter />
    </div>
  );
}
