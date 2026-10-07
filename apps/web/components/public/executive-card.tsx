import Image from "next/image";

import { ExecutiveProfileButton } from "@/components/public/executive-profile-button";
import {
  formatExecutivePosition,
  type PublicExecutiveProfile,
} from "@/lib/leadership";
import { publicMediaUrl } from "@/lib/public-media";
import { cn, formatPersonName, formatRankForName, initials } from "@/lib/utils";

export function ExecutiveCard({
  profile,
  compact = false,
}: {
  profile: PublicExecutiveProfile;
  compact?: boolean;
}) {
  return (
    <article
      className={cn(
        "group flex overflow-hidden rounded-md border border-line bg-white text-center text-[#172f4d] shadow-[0_8px_26px_rgb(23_43_69_/_8%)]",
        compact && "shadow-lg",
      )}
    >
      <div className="flex w-full flex-col">
        <div
          className={cn(
            "relative grid place-items-center overflow-hidden bg-[linear-gradient(145deg,#e8eef5,#f8fafc)]",
            compact ? "aspect-[4/3.8]" : "aspect-[4/4.2]",
          )}
        >
          <div className="absolute inset-x-0 top-0 z-10 h-1 bg-gold" />
          {profile.profile_media_id ? (
            <>
              <Image
                fill
                alt={`Portrait of ${profile.full_name}`}
                className="object-cover object-[center_20%] transition duration-500 group-hover:scale-[1.025]"
                sizes={
                  compact
                    ? "(min-width: 1024px) 16vw, (min-width: 640px) 50vw, 100vw"
                    : "(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw"
                }
                src={publicMediaUrl(profile.profile_media_id, "w480")!}
                unoptimized
              />
              <div className="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-[#102a46]/24 to-transparent" />
            </>
          ) : (
            <span
              aria-label={`No profile photo has been added for ${profile.full_name}`}
              className={cn(
                "grid place-items-center rounded-full border-4 border-white bg-[#172f4d] font-black text-gold shadow-lg",
                compact ? "size-24 text-3xl" : "size-28 text-4xl",
              )}
            >
              {initials(profile.full_name)}
            </span>
          )}
        </div>

        <div
          className={cn(
            "flex flex-1 flex-col border-t border-line text-center",
            compact ? "p-5" : "p-6",
          )}
        >
          <p className="text-[.68rem] font-extrabold tracking-wide text-coral uppercase">
            {formatExecutivePosition(profile.position)}
          </p>
          <h3
            className={cn(
              "mt-2 font-extrabold text-[#172f4d]",
              compact ? "text-base" : "text-lg",
            )}
          >
            {formatPersonName(profile.full_name)}
          </h3>
          {profile.academic_rank ? (
            <p className="mt-1 text-xs font-semibold text-muted">
              {formatRankForName(profile.full_name, profile.academic_rank)}
            </p>
          ) : null}
          <div className={cn("mt-auto", compact ? "pt-5" : "pt-6")}>
            <ExecutiveProfileButton className="w-full" profile={profile} />
          </div>
        </div>
      </div>
    </article>
  );
}
