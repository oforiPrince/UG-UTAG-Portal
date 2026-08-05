import type { Metadata } from "next";

import { ExecutiveCard } from "@/components/public/executive-card";
import { PageHero } from "@/components/public/page-hero";
import { PublicEmptyState } from "@/components/public/public-empty-state";
import { PublicShell } from "@/components/public/public-shell";
import { publicApi } from "@/lib/api";
import {
  isExecutiveOfficerPosition,
  type PublicExecutiveProfile,
  sortLeadership,
} from "@/lib/leadership";

export const metadata: Metadata = { title: "Leadership" };
export const dynamic = "force-dynamic";

const fallback: PublicExecutiveProfile[] = [];

function LeadershipGrid({
  members,
  emptyTitle,
  emptyDescription,
}: {
  members: PublicExecutiveProfile[];
  emptyTitle: string;
  emptyDescription: string;
}) {
  return (
    <div className="mt-9 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
      {members.length === 0 && (
        <PublicEmptyState title={emptyTitle} description={emptyDescription} />
      )}
      {members.map((leader) => (
        <ExecutiveCard key={leader.id} profile={leader} />
      ))}
    </div>
  );
}

export default async function LeadershipPage() {
  const leaders = await publicApi<PublicExecutiveProfile[]>(
    "/api/v1/public/leadership",
    fallback,
    { revalidate: false },
  );
  const orderedLeaders = sortLeadership(leaders);
  const executiveOfficers = orderedLeaders.filter((leader) =>
    isExecutiveOfficerPosition(leader.position),
  );
  const localCouncilMembers = orderedLeaders.filter(
    (leader) => !isExecutiveOfficerPosition(leader.position),
  );

  return (
    <PublicShell>
      <PageHero
        eyebrow="Leadership"
        title="Leadership serving UG UTAG"
        intro="Meet the Executive Officers and Local Executive Council Members entrusted with representing the University of Ghana Branch of UTAG."
      />
      <section
        id="executive-officers"
        className="mx-auto max-w-[82rem] scroll-mt-36 px-5 py-16 sm:px-6 lg:px-8 lg:py-22"
      >
        <div className="max-w-3xl">
          <p className="text-[.7rem] font-extrabold tracking-[.15em] text-coral uppercase">
            Branch leadership
          </p>
          <h2 className="display-type mt-3 text-3xl text-[#172f4d] sm:text-4xl">
            Executive Officers
          </h2>
          <div className="mt-4 h-1 w-14 bg-gold" />
          <p className="mt-5 text-sm leading-7 text-muted sm:text-base">
            The principal officers responsible for the branch&apos;s strategic
            direction, administration, financial stewardship, and member
            representation.
          </p>
        </div>
        <LeadershipGrid
          members={executiveOfficers}
          emptyTitle="No Executive Officers published"
          emptyDescription="Approved Executive Officer profiles will appear here when published by the secretariat."
        />
      </section>

      <section
        id="local-executive-council-members"
        className="scroll-mt-36 bg-[#f5f8fb] px-5 py-16 sm:px-6 lg:px-8 lg:py-22"
      >
        <div className="mx-auto max-w-[82rem]">
          <div className="max-w-3xl">
            <p className="text-[.7rem] font-extrabold tracking-[.15em] text-coral uppercase">
              Representative council
            </p>
            <h2 className="display-type mt-3 text-3xl text-[#172f4d] sm:text-4xl">
              Local Executive Council Members
            </h2>
            <div className="mt-4 h-1 w-14 bg-gold" />
            <p className="mt-5 text-sm leading-7 text-muted sm:text-base">
              Council representatives who connect colleges and constituencies to
              the work and decisions of the branch.
            </p>
          </div>
          <LeadershipGrid
            members={localCouncilMembers}
            emptyTitle="No Local Executive Council Members published"
            emptyDescription="Approved Local Executive Council Member profiles will appear here when published by the secretariat."
          />
        </div>
      </section>
    </PublicShell>
  );
}
