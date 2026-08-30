"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BriefcaseBusiness,
  Building2,
  Eye,
  EyeOff,
  Globe2,
  IdCard,
  Link2,
  LoaderCircle,
  LockKeyhole,
  Mail,
  Phone,
  RefreshCw,
  Save,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import Image from "next/image";
import { useState } from "react";
import { toast } from "sonner";

import { RichTextEditor } from "@/components/dashboard/rich-text-editor";
import { WorkspaceMediaField } from "@/components/dashboard/workspace-media-field";
import { WorkspaceSelect } from "@/components/dashboard/workspace-client";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import {
  cn,
  formatPersonName,
  formatRankForName,
  humanize,
  initials,
} from "@/lib/utils";
import type { WorkspaceField } from "@/lib/workspaces";

type User = {
  full_name: string;
  email: string;
  profile_media_id: string | null;
  staff_id: string | null;
  title: string;
  other_name: string;
  surname: string;
  gender: string | null;
  academic_rank: string | null;
  phone_number: string | null;
  school_id: string | null;
  college_id: string | null;
  department_id: string | null;
  must_change_password: boolean;
  must_complete_executive_profile: boolean;
  roles: string[];
  permissions: string[];
};

type ProfileForm = {
  title: string;
  other_name: string;
  surname: string;
  gender: string;
  academic_rank: string;
  phone_number: string;
  school_id: string;
  college_id: string;
  department_id: string;
};

type ExecutiveProfile = {
  id: string;
  position: string;
  portfolio: string | null;
  summary: string | null;
  biography_html: string;
  social_links: Record<string, string>;
  term_number: number;
  is_acting: boolean;
  is_public: boolean;
  show_email: boolean;
  show_phone: boolean;
  appointed_on: string | null;
};

type ExecutiveProfileForm = {
  portfolio: string;
  summary: string;
  biography_html: string;
  social_links: Record<string, string>;
  show_email: boolean;
  show_phone: boolean;
};

type ProfileTab = "account" | "leadership" | "security";

const ACADEMIC_RANK_OPTIONS = [
  "Professor",
  "Associate Professor",
  "Senior Lecturer",
  "Lecturer",
  "Assistant Lecturer",
  "Research Fellow",
  "Senior Research Fellow",
  "Principal Research Fellow",
  "Assistant Research Fellow",
  "Research Associate",
  "Senior Librarian",
  "Librarian",
  "Tutor",
  "Dean",
  "Director",
  "Pro-Vice-Chancellor",
  "Visiting Scholar",
] as const;

const SOCIAL_FIELDS = [
  {
    key: "linkedin",
    label: "LinkedIn",
    placeholder: "https://www.linkedin.com/in/your-profile",
    Icon: Link2,
  },
  {
    key: "facebook",
    label: "Facebook",
    placeholder: "https://www.facebook.com/your-profile",
    Icon: Globe2,
  },
  {
    key: "twitter",
    label: "X / Twitter",
    placeholder: "https://x.com/your-handle",
    Icon: Globe2,
  },
  {
    key: "website",
    label: "Personal or office website",
    placeholder: "https://example.edu.gh",
    Icon: Globe2,
  },
] as const;

function executiveFormFromProfile(
  profile?: ExecutiveProfile | null,
): ExecutiveProfileForm | undefined {
  if (!profile) return undefined;
  return {
    portfolio: profile.portfolio ?? "",
    summary: profile.summary ?? "",
    biography_html: profile.biography_html ?? "",
    social_links: profile.social_links ?? {},
    show_email: Boolean(profile.show_email),
    show_phone: Boolean(profile.show_phone),
  };
}

const blankProfile: ProfileForm = {
  title: "",
  other_name: "",
  surname: "",
  gender: "",
  academic_rank: "",
  phone_number: "",
  school_id: "",
  college_id: "",
  department_id: "",
};

function profileFromUser(user?: User): ProfileForm {
  if (!user) return blankProfile;
  return {
    title: user.title ?? "",
    other_name: user.other_name ?? "",
    surname: user.surname ?? "",
    gender: user.gender ?? "",
    academic_rank: user.academic_rank ?? "",
    phone_number: user.phone_number ?? "",
    school_id: user.school_id ?? "",
    college_id: user.college_id ?? "",
    department_id: user.department_id ?? "",
  };
}

const inputClass =
  "min-h-12 w-full rounded-xl border border-line bg-panel px-4 text-sm font-normal outline-none transition placeholder:text-muted/70 focus:border-coral/40 focus:ring-4 focus:ring-coral/10";

const profileUnitFields: Record<
  "school" | "college" | "department",
  WorkspaceField
> = Object.fromEntries(
  (["school", "college", "department"] as const).map((type) => [
    type,
    {
      key: `${type}_id`,
      label: type[0]?.toUpperCase() + type.slice(1),
      type: "select",
      optionSource: {
        endpoint: "/api/v1/organization/units",
        queryKey: "organization-profile-options",
        value: (row) => String(row.id),
        label: (row) => String(row.name),
        filter: (row) => row.unit_type === type && row.is_active !== false,
        filterForValues: (row, values) => {
          if (type === "college") return true;
          if (type === "school") {
            return (
              Boolean(values.college_id) &&
              String(row.parent_id) === String(values.college_id)
            );
          }
          return (
            Boolean(values.school_id) &&
            String(row.parent_id) === String(values.school_id)
          );
        },
        disabledForValues: (values) =>
          (type === "school" && !values.college_id) ||
          (type === "department" && !values.school_id),
        emptyLabelForValues: (values) => {
          if (type === "school" && !values.college_id) {
            return "Select a college first";
          }
          if (type === "department" && !values.school_id) {
            return "Select a school first";
          }
          return `No active ${type}s for this selection`;
        },
      },
    },
  ]),
) as Record<"school" | "college" | "department", WorkspaceField>;

const profilePhotoField: WorkspaceField = {
  key: "profile_media_id",
  label: "Profile photo",
  type: "media",
  required: true,
  media: {
    accept: "image",
    isPrivate: false,
    aspect: "portrait",
  },
  help: "Used on public leadership cards. Prefer a clear head-and-shoulders portrait.",
};

const memberPhotoField: WorkspaceField = {
  ...profilePhotoField,
  required: false,
  help: "Optional for members. Executives need a portrait for public leadership pages.",
};

function PasswordField({
  id,
  value,
  onChange,
  autoComplete,
  required,
  minLength,
  invalid,
  describedBy,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: string;
  required?: boolean;
  minLength?: number;
  invalid?: boolean;
  describedBy?: string;
}) {
  const [visible, setVisible] = useState(false);

  return (
    <span className="relative block">
      <input
        id={id}
        type={visible ? "text" : "password"}
        autoComplete={autoComplete}
        required={required}
        minLength={minLength}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={cn(
          inputClass,
          "pr-12 [&::-ms-reveal]:hidden [&::-webkit-credentials-auto-fill-button]:hidden [&::-webkit-strong-password-auto-fill-button]:hidden",
        )}
      />
      <button
        type="button"
        onClick={() => setVisible((current) => !current)}
        className="absolute top-1/2 right-2 z-10 -translate-y-1/2 rounded-lg p-2 text-muted transition hover:bg-ink/5 hover:text-ink"
        aria-label={visible ? "Hide password" : "Show password"}
      >
        {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </button>
    </span>
  );
}

function FieldLabel({
  htmlFor,
  children,
  hint,
}: {
  htmlFor?: string;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <div className="grid gap-1.5">
      <label
        htmlFor={htmlFor}
        className="text-[.68rem] font-extrabold tracking-[.08em] text-muted uppercase"
      >
        {children}
      </label>
      {hint ? (
        <p className="text-[.7rem] leading-5 text-muted">{hint}</p>
      ) : null}
    </div>
  );
}

function SectionHeading({
  icon: Icon,
  eyebrow,
  title,
  description,
}: {
  icon: typeof UserRound;
  eyebrow: string;
  title: string;
  description?: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-coral/10 text-coral">
        <Icon className="size-5" />
      </span>
      <div>
        <p className="text-[.68rem] font-extrabold tracking-[.08em] text-muted uppercase">
          {eyebrow}
        </p>
        <p className="text-sm font-bold text-ink sm:text-base">{title}</p>
        {description ? (
          <p className="mt-1 text-xs leading-5 text-muted">{description}</p>
        ) : null}
      </div>
    </div>
  );
}

export function ProfileClient() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const search = useSearchParams();
  const user = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => api<User>("/api/v1/auth/me"),
  });
  const isExecutiveRole = Boolean(user.data?.roles?.includes("executive"));
  const executiveProfile = useQuery({
    queryKey: ["auth", "executive-profile"],
    queryFn: () =>
      api<ExecutiveProfile | null>("/api/v1/auth/executive-profile"),
    enabled: Boolean(user.data),
  });
  const [profileDraft, setProfileDraft] = useState<ProfileForm>();
  const [executiveDraft, setExecutiveDraft] = useState<ExecutiveProfileForm>();
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [savingPhoto, setSavingPhoto] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingExecutive, setSavingExecutive] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);
  const [tab, setTab] = useState<ProfileTab | null>(null);

  const profile = profileDraft ?? profileFromUser(user.data);
  const publicExecutiveProfile =
    executiveDraft ?? executiveFormFromProfile(executiveProfile.data);
  const appointmentMeta = executiveProfile.data;
  const hasLeadership = Boolean(appointmentMeta && publicExecutiveProfile);
  const mustCompleteExecutiveProfile = Boolean(
    user.data?.must_complete_executive_profile,
  );
  const executiveRequired =
    search.get("executive") === "required" || mustCompleteExecutiveProfile;
  const displayName = formatPersonName(user.data?.full_name ?? "");
  const displayRank = formatRankForName(
    user.data?.full_name,
    user.data?.academic_rank,
  );

  let defaultTab: ProfileTab = "account";
  if (
    user.data?.must_change_password ||
    search.get("password") === "required"
  ) {
    defaultTab = "security";
  } else if (hasLeadership || executiveRequired || isExecutiveRole) {
    defaultTab = "leadership";
  }

  const activeTab = tab ?? defaultTab;
  const passwordsMatch = !confirm || password === confirm;
  const passwordIsStrong =
    password.length >= 8 &&
    /[A-Z]/.test(password) &&
    /[a-z]/.test(password) &&
    /\d/.test(password);

  function updateProfile(changes: Partial<ProfileForm>) {
    setProfileDraft((currentDraft) => ({
      ...(currentDraft ?? profileFromUser(user.data)),
      ...changes,
    }));
  }

  async function saveProfilePhoto(profileMediaId: string | string[]) {
    const nextId = Array.isArray(profileMediaId)
      ? (profileMediaId[0] ?? null)
      : profileMediaId || null;
    setSavingPhoto(true);
    try {
      const updated = await api<User>("/api/v1/auth/profile", {
        method: "PATCH",
        body: { profile_media_id: nextId },
      });
      queryClient.setQueryData(["auth", "me"], updated);
      await queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      toast.success("Profile photo updated");
      if (
        !updated.must_complete_executive_profile &&
        !updated.must_change_password &&
        executiveRequired
      ) {
        router.replace("/dashboard");
      }
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Could not update profile photo",
      );
    } finally {
      setSavingPhoto(false);
    }
  }

  async function saveProfile(event: React.FormEvent) {
    event.preventDefault();
    setSavingProfile(true);
    try {
      const updated = await api<User>("/api/v1/auth/profile", {
        method: "PATCH",
        body: {
          ...profile,
          gender: profile.gender || null,
          academic_rank: profile.academic_rank || null,
          phone_number: profile.phone_number || null,
          school_id: profile.school_id || null,
          college_id: profile.college_id || null,
          department_id: profile.department_id || null,
        },
      });
      queryClient.setQueryData(["auth", "me"], updated);
      setProfileDraft(undefined);
      await queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      toast.success("Profile updated");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not update profile",
      );
    } finally {
      setSavingProfile(false);
    }
  }

  async function savePassword(event: React.FormEvent) {
    event.preventDefault();
    if (password !== confirm) {
      toast.error("The new passwords do not match");
      return;
    }
    setSavingPassword(true);
    try {
      await api("/api/v1/auth/password", {
        method: "POST",
        body: { current_password: current, new_password: password },
      });
      setCurrent("");
      setPassword("");
      setConfirm("");
      await queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      toast.success("Password updated");
      if (
        search.get("password") === "required" ||
        user.data?.must_change_password
      ) {
        const me = await api<User>("/api/v1/auth/me");
        router.replace(
          me.must_complete_executive_profile
            ? "/dashboard/profile?executive=required"
            : "/dashboard",
        );
      }
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not update password",
      );
    } finally {
      setSavingPassword(false);
    }
  }

  async function saveExecutiveProfile(event: React.FormEvent) {
    event.preventDefault();
    if (!publicExecutiveProfile) return;
    setSavingExecutive(true);
    try {
      const updated = await api<ExecutiveProfile>(
        "/api/v1/auth/executive-profile",
        {
          method: "PATCH",
          body: {
            portfolio: publicExecutiveProfile.portfolio || null,
            summary: publicExecutiveProfile.summary || null,
            biography_html: publicExecutiveProfile.biography_html,
            social_links: publicExecutiveProfile.social_links,
            show_email: publicExecutiveProfile.show_email,
            show_phone: publicExecutiveProfile.show_phone,
          },
        },
      );
      queryClient.setQueryData(["auth", "executive-profile"], updated);
      setExecutiveDraft(undefined);
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["auth", "executive-profile"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["workspace", "executives"],
        }),
        queryClient.invalidateQueries({ queryKey: ["auth", "me"] }),
      ]);
      toast.success("Public leadership profile updated");
      const me = await api<User>("/api/v1/auth/me");
      if (!me.must_complete_executive_profile && !me.must_change_password) {
        if (executiveRequired) router.replace("/dashboard");
      }
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Could not update the executive profile",
      );
    } finally {
      setSavingExecutive(false);
    }
  }

  function updateExecutiveProfile(changes: Partial<ExecutiveProfileForm>) {
    if (!publicExecutiveProfile) return;
    setExecutiveDraft((currentDraft) => ({
      ...(currentDraft ?? publicExecutiveProfile),
      ...changes,
    }));
  }

  const tabs: Array<{ id: ProfileTab; label: string; show: boolean }> = [
    { id: "account", label: "Account", show: true },
    {
      id: "leadership",
      label: "Public leadership",
      show: hasLeadership || isExecutiveRole || executiveRequired,
    },
    { id: "security", label: "Security", show: true },
  ];
  const visibleTabs = tabs.filter((item) => item.show);

  function activateTabAt(index: number) {
    const next = visibleTabs[index];
    if (!next) return;
    setTab(next.id);
    window.requestAnimationFrame(() =>
      document.getElementById(`profile-tab-${next.id}`)?.focus(),
    );
  }

  if (user.isPending || (Boolean(user.data) && executiveProfile.isPending)) {
    return (
      <div className="grid gap-6" aria-busy="true" aria-live="polite">
        <span className="sr-only">Loading your profile</span>
        <div className="h-28 animate-pulse rounded-3xl bg-ink/5" />
        <div className="h-[34rem] animate-pulse rounded-3xl border border-line bg-panel" />
      </div>
    );
  }

  if (user.isError || !user.data) {
    return (
      <div className="grid min-h-80 place-items-center rounded-3xl border border-line bg-panel p-8 text-center">
        <div className="max-w-md">
          <AlertTriangle className="mx-auto size-8 text-coral" />
          <h2 className="mt-4 text-xl font-black text-ink">
            Profile unavailable
          </h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            We could not load your account details. Check your connection and
            try again.
          </p>
          <Button
            type="button"
            variant="outline"
            className="mt-5"
            onClick={() => void user.refetch()}
          >
            <RefreshCw className="size-4" /> Try again
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="grid gap-6">
      <header className="max-w-3xl">
        <p className="eyebrow text-coral">Account</p>
        <h2 className="display-type mt-3 text-4xl sm:text-5xl">Profile</h2>
        <p className="mt-3 text-sm leading-6 text-muted">
          {hasLeadership
            ? "Manage your personal details and the public leadership profile members see on the website."
            : "Keep your association identity, campus affiliation, and sign-in security current."}
        </p>
      </header>

      {user.data?.must_change_password ? (
        <div
          className="flex items-start gap-4 rounded-2xl border border-gold/40 bg-gold/10 p-5"
          role="alert"
        >
          <AlertTriangle className="mt-0.5 size-5 shrink-0 text-amber-700 dark:text-amber-300" />
          <div>
            <b className="text-sm">
              Replace your temporary password before continuing
            </b>
            <p className="mt-1 text-xs leading-5 text-muted">
              Open the Security tab and choose a private password that only you
              know.
            </p>
          </div>
        </div>
      ) : null}

      {mustCompleteExecutiveProfile && !user.data?.must_change_password ? (
        <div
          className="flex items-start gap-4 rounded-2xl border border-coral/35 bg-coral/8 p-5"
          role="alert"
        >
          <AlertTriangle className="mt-0.5 size-5 shrink-0 text-coral" />
          <div>
            <b className="text-sm">
              Complete your public leadership profile before continuing
            </b>
            <p className="mt-1 text-xs leading-5 text-muted">
              Add a portrait, biography, and optional social links so your
              public leadership card is ready.
            </p>
          </div>
        </div>
      ) : null}

      {executiveProfile.isError ? (
        <div
          className="flex items-start justify-between gap-4 rounded-2xl border border-line bg-panel p-5"
          role="alert"
        >
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 size-5 shrink-0 text-coral" />
            <div>
              <b className="text-sm text-ink">Leadership details unavailable</b>
              <p className="mt-1 text-xs leading-5 text-muted">
                Your account and security settings are still available.
              </p>
            </div>
          </div>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => void executiveProfile.refetch()}
          >
            <RefreshCw className="size-3.5" /> Retry
          </Button>
        </div>
      ) : null}

      <section className="overflow-hidden rounded-3xl border border-line bg-panel shadow-[0_16px_48px_rgba(23,43,69,.06)]">
        <div className="relative overflow-hidden bg-[linear-gradient(135deg,#102a46_0%,#1f5f99_55%,#2f7ab8_100%)] px-6 py-8 text-white sm:px-8 sm:py-10">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 opacity-30"
            style={{
              backgroundImage:
                "radial-gradient(circle at 18% 20%, rgba(255,255,255,.28), transparent 34%), radial-gradient(circle at 88% 12%, rgba(240,196,116,.35), transparent 28%)",
            }}
          />
          <div className="relative grid gap-6 lg:grid-cols-[auto_1fr] lg:items-end">
            <div className="relative size-28 shrink-0 overflow-hidden rounded-[1.75rem] border-4 border-white/25 bg-white/10 shadow-2xl sm:size-36">
              {user.data?.profile_media_id ? (
                <Image
                  fill
                  unoptimized
                  alt={`Profile photo for ${displayName || "member"}`}
                  className="object-cover"
                  sizes="144px"
                  src={`/api/v1/media/${user.data.profile_media_id}/content`}
                />
              ) : (
                <span className="grid h-full place-items-center text-3xl font-black text-gold sm:text-4xl">
                  {initials(user.data?.full_name ?? "UG")}
                </span>
              )}
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                {(user.data?.roles ?? []).map((role) => (
                  <span
                    key={role}
                    className="rounded-full bg-white/12 px-3 py-1 text-[.62rem] font-bold tracking-wide text-white/95 backdrop-blur"
                  >
                    {humanize(role)}
                  </span>
                ))}
                {appointmentMeta ? (
                  <span className="rounded-full bg-gold/20 px-3 py-1 text-[.62rem] font-bold tracking-wide text-gold">
                    {appointmentMeta.position}
                    {appointmentMeta.is_acting ? " · Acting" : ""}
                  </span>
                ) : null}
              </div>
              <h3 className="mt-3 text-2xl font-black tracking-tight sm:text-4xl">
                {displayName || "Loading profile…"}
              </h3>
              {displayRank ? (
                <p className="mt-1 text-sm font-semibold text-white/80 sm:text-base">
                  {displayRank}
                </p>
              ) : null}
              <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-sm text-white/80">
                {user.data?.email ? (
                  <span className="inline-flex min-w-0 items-center gap-2 break-all">
                    <Mail className="size-4 shrink-0 opacity-80" />
                    {user.data.email}
                  </span>
                ) : null}
                {user.data?.staff_id ? (
                  <span className="inline-flex items-center gap-2">
                    <IdCard className="size-4 shrink-0 opacity-80" />
                    Staff ID {user.data.staff_id}
                  </span>
                ) : null}
                {user.data?.phone_number ? (
                  <span className="inline-flex items-center gap-2">
                    <Phone className="size-4 shrink-0 opacity-80" />
                    {user.data.phone_number}
                  </span>
                ) : null}
              </div>
            </div>
          </div>
        </div>

        <div
          className="flex flex-wrap gap-2 border-b border-line bg-ink/[.02] px-4 py-3 sm:px-6"
          role="tablist"
          aria-label="Profile sections"
        >
          {visibleTabs.map((item, index) => (
            <button
              id={`profile-tab-${item.id}`}
              key={item.id}
              type="button"
              role="tab"
              aria-selected={activeTab === item.id}
              aria-controls={`profile-panel-${item.id}`}
              tabIndex={activeTab === item.id ? 0 : -1}
              className={cn(
                "rounded-full px-4 py-2 text-xs font-bold outline-none transition focus-visible:ring-2 focus-visible:ring-coral/45 focus-visible:ring-offset-2",
                activeTab === item.id
                  ? "bg-ink text-paper shadow-sm"
                  : "text-muted hover:bg-ink/5 hover:text-ink",
              )}
              onClick={() => setTab(item.id)}
              onKeyDown={(event) => {
                if (event.key === "ArrowRight") {
                  event.preventDefault();
                  activateTabAt((index + 1) % visibleTabs.length);
                } else if (event.key === "ArrowLeft") {
                  event.preventDefault();
                  activateTabAt(
                    (index - 1 + visibleTabs.length) % visibleTabs.length,
                  );
                } else if (event.key === "Home") {
                  event.preventDefault();
                  activateTabAt(0);
                } else if (event.key === "End") {
                  event.preventDefault();
                  activateTabAt(visibleTabs.length - 1);
                }
              }}
            >
              {item.label}
            </button>
          ))}
        </div>

        {activeTab === "account" ? (
          <div
            id="profile-panel-account"
            role="tabpanel"
            aria-labelledby="profile-tab-account"
            className="grid gap-0 lg:grid-cols-[minmax(16rem,0.9fr)_1.1fr]"
          >
            <div className="border-b border-line p-6 sm:p-8 lg:border-r lg:border-b-0">
              <SectionHeading
                icon={UserRound}
                eyebrow="Portrait"
                title="Update your photo"
              />
              <div className="mt-5">
                <WorkspaceMediaField
                  field={hasLeadership ? profilePhotoField : memberPhotoField}
                  value={user.data?.profile_media_id ?? ""}
                  onChange={(value) => {
                    void saveProfilePhoto(value);
                  }}
                />
                <p
                  className="mt-2 min-h-5 text-xs text-muted"
                  aria-live="polite"
                >
                  {savingPhoto ? "Saving your new profile photo…" : ""}
                </p>
              </div>
              <div className="mt-6 flex items-start gap-3 rounded-2xl border border-line bg-ink/[.02] p-4">
                <ShieldCheck className="mt-0.5 size-5 shrink-0 text-emerald-600 dark:text-emerald-300" />
                <p className="text-xs leading-5">
                  <b className="block text-ink">Protected account</b>
                  <span className="text-muted">
                    Secure sessions and role-based access keep your workspace
                    private.
                  </span>
                </p>
              </div>
            </div>

            <form className="grid gap-6 p-6 sm:p-8" onSubmit={saveProfile}>
              <SectionHeading
                icon={IdCard}
                eyebrow="Identity"
                title="Name and contact details"
              />
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-2">
                  <FieldLabel htmlFor="profile-title">Title</FieldLabel>
                  <select
                    id="profile-title"
                    name="honorific-prefix"
                    autoComplete="honorific-prefix"
                    className={inputClass}
                    value={profile.title}
                    onChange={(event) =>
                      updateProfile({ title: event.target.value })
                    }
                  >
                    <option value="">Select</option>
                    {[
                      "Prof.",
                      "Dr.",
                      "Mr.",
                      "Mrs.",
                      "Miss",
                      "Ms.",
                      "Rev.",
                      "Hon.",
                      "Eng.",
                    ].map((title) => (
                      <option key={title} value={title}>
                        {title}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="grid gap-2">
                  <FieldLabel htmlFor="profile-gender">Gender</FieldLabel>
                  <select
                    id="profile-gender"
                    className={inputClass}
                    value={profile.gender}
                    onChange={(event) =>
                      updateProfile({ gender: event.target.value })
                    }
                  >
                    <option value="">Select</option>
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                  </select>
                </div>
                <div className="grid gap-2">
                  <FieldLabel htmlFor="profile-other-name">
                    Other names
                  </FieldLabel>
                  <input
                    id="profile-other-name"
                    name="given-name"
                    autoComplete="given-name"
                    className={inputClass}
                    required
                    value={profile.other_name}
                    onChange={(event) =>
                      updateProfile({ other_name: event.target.value })
                    }
                  />
                </div>
                <div className="grid gap-2">
                  <FieldLabel htmlFor="profile-surname">Surname</FieldLabel>
                  <input
                    id="profile-surname"
                    name="family-name"
                    autoComplete="family-name"
                    className={inputClass}
                    required
                    value={profile.surname}
                    onChange={(event) =>
                      updateProfile({ surname: event.target.value })
                    }
                  />
                </div>
                <div className="grid gap-2">
                  <FieldLabel htmlFor="profile-rank">Academic rank</FieldLabel>
                  <select
                    id="profile-rank"
                    className={inputClass}
                    value={profile.academic_rank}
                    onChange={(event) =>
                      updateProfile({ academic_rank: event.target.value })
                    }
                  >
                    <option value="">Select</option>
                    {profile.academic_rank &&
                    !ACADEMIC_RANK_OPTIONS.includes(
                      profile.academic_rank as (typeof ACADEMIC_RANK_OPTIONS)[number],
                    ) ? (
                      <option value={profile.academic_rank}>
                        {profile.academic_rank}
                      </option>
                    ) : null}
                    {ACADEMIC_RANK_OPTIONS.map((rank) => (
                      <option key={rank} value={rank}>
                        {rank}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="grid gap-2">
                  <FieldLabel htmlFor="profile-phone">Phone number</FieldLabel>
                  <input
                    id="profile-phone"
                    name="tel"
                    autoComplete="tel"
                    className={inputClass}
                    type="tel"
                    value={profile.phone_number}
                    onChange={(event) =>
                      updateProfile({ phone_number: event.target.value })
                    }
                  />
                </div>
              </div>

              <div className="border-t border-line pt-6">
                <SectionHeading
                  icon={Building2}
                  eyebrow="Affiliation"
                  title="College, school, and department"
                  description="Choose the college first, then its school and department. Changing a parent clears the dependent selections."
                />
                <div className="mt-5 grid gap-4 sm:grid-cols-2">
                  {(["college", "school", "department"] as const).map(
                    (type) => {
                      const key = `${type}_id` as
                        "school_id" | "college_id" | "department_id";
                      const labelId = `profile-${type}-label`;
                      return (
                        <div
                          key={type}
                          className={cn(
                            "grid gap-2",
                            type === "department" && "sm:col-span-2",
                          )}
                        >
                          <span
                            id={labelId}
                            className="text-[.68rem] font-extrabold tracking-[.08em] text-muted uppercase"
                          >
                            {profileUnitFields[type].label}
                          </span>
                          <WorkspaceSelect
                            id={`profile-${type}`}
                            labelledBy={labelId}
                            field={profileUnitFields[type]}
                            value={profile[key]}
                            autoFocus={false}
                            formValues={profile}
                            onChange={(value) => {
                              if (type === "college") {
                                updateProfile({
                                  college_id: value,
                                  school_id: "",
                                  department_id: "",
                                });
                                return;
                              }
                              if (type === "school") {
                                updateProfile({
                                  school_id: value,
                                  department_id: "",
                                });
                                return;
                              }
                              updateProfile({ department_id: value });
                            }}
                          />
                        </div>
                      );
                    },
                  )}
                </div>
              </div>

              <div className="flex justify-end border-t border-line pt-5">
                <Button
                  type="submit"
                  disabled={savingProfile || savingPhoto}
                  className="w-full sm:w-auto sm:min-w-40"
                >
                  {savingProfile ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <Save className="size-4" />
                  )}
                  Save account
                </Button>
              </div>
            </form>
          </div>
        ) : null}

        {activeTab === "leadership" ? (
          hasLeadership && publicExecutiveProfile && appointmentMeta ? (
            <form
              id="profile-panel-leadership"
              role="tabpanel"
              aria-labelledby="profile-tab-leadership"
              className="grid gap-0 lg:grid-cols-[1.15fr_.85fr]"
              onSubmit={saveExecutiveProfile}
            >
              <div className="grid gap-8 border-b border-line p-6 sm:p-8 lg:border-r lg:border-b-0">
                <div className="grid gap-3 rounded-2xl border border-line bg-ink/[.02] p-4 sm:grid-cols-3">
                  <div>
                    <p className="text-[.68rem] font-extrabold tracking-[.08em] text-muted uppercase">
                      Position
                    </p>
                    <p className="mt-1 text-sm font-bold text-ink">
                      {appointmentMeta.position}
                      {appointmentMeta.is_acting ? " · Acting" : ""}
                    </p>
                  </div>
                  <div>
                    <p className="text-[.68rem] font-extrabold tracking-[.08em] text-muted uppercase">
                      Term
                    </p>
                    <p className="mt-1 text-sm font-bold text-ink">
                      Term {appointmentMeta.term_number}
                    </p>
                  </div>
                  <div>
                    <p className="text-[.68rem] font-extrabold tracking-[.08em] text-muted uppercase">
                      Appointed
                    </p>
                    <p className="mt-1 text-sm font-bold text-ink">
                      {appointmentMeta.appointed_on
                        ? new Date(
                            `${appointmentMeta.appointed_on}T12:00:00`,
                          ).toLocaleDateString("en-GH", {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                          })
                        : "Not recorded"}
                    </p>
                  </div>
                </div>

                <div className="grid gap-5">
                  <SectionHeading
                    icon={Globe2}
                    eyebrow="Social profiles"
                    title="Public social URLs"
                    description="These links appear on your public leadership card and profile modal."
                  />
                  <div className="grid gap-4">
                    {SOCIAL_FIELDS.map(({ key, label, placeholder, Icon }) => (
                      <div
                        key={key}
                        className="grid gap-2 rounded-2xl border border-line bg-panel p-4"
                      >
                        <div className="flex items-center gap-2">
                          <Icon className="size-4 text-coral" />
                          <FieldLabel htmlFor={`profile-social-${key}`}>
                            {label}
                          </FieldLabel>
                        </div>
                        <input
                          id={`profile-social-${key}`}
                          type="url"
                          value={publicExecutiveProfile.social_links[key] ?? ""}
                          placeholder={placeholder}
                          onChange={(event) =>
                            updateExecutiveProfile({
                              social_links: {
                                ...publicExecutiveProfile.social_links,
                                [key]: event.target.value,
                              },
                            })
                          }
                          className={inputClass}
                        />
                      </div>
                    ))}
                  </div>
                </div>

                <div className="grid gap-5 border-t border-line pt-6">
                  <SectionHeading
                    icon={BriefcaseBusiness}
                    eyebrow="Introduction"
                    title="Portfolio and short summary"
                  />
                  <div className="grid gap-4">
                    <div className="grid gap-2">
                      <FieldLabel htmlFor="profile-executive-portfolio">
                        Portfolio
                      </FieldLabel>
                      <input
                        id="profile-executive-portfolio"
                        className={inputClass}
                        value={publicExecutiveProfile.portfolio}
                        placeholder="e.g. Member welfare and conditions of service"
                        onChange={(event) =>
                          updateExecutiveProfile({
                            portfolio: event.target.value,
                          })
                        }
                      />
                    </div>
                    <div className="grid gap-2">
                      <FieldLabel
                        htmlFor="profile-executive-summary"
                        hint="One or two sentences shown under your name on leadership cards."
                      >
                        Public summary
                      </FieldLabel>
                      <textarea
                        id="profile-executive-summary"
                        aria-describedby="profile-executive-summary-help"
                        rows={3}
                        maxLength={500}
                        className={cn(inputClass, "min-h-24 resize-y py-3")}
                        value={publicExecutiveProfile.summary}
                        placeholder="A concise public introduction for members and visitors…"
                        onChange={(event) =>
                          updateExecutiveProfile({
                            summary: event.target.value,
                          })
                        }
                      />
                      <p
                        id="profile-executive-summary-help"
                        className="text-right text-[.68rem] text-muted"
                      >
                        {publicExecutiveProfile.summary.length}/500
                      </p>
                    </div>
                  </div>
                </div>

                <div className="grid gap-5 border-t border-line pt-6">
                  <SectionHeading
                    icon={UserRound}
                    eyebrow="Biography"
                    title="Full public leadership biography"
                  />
                  <div className="grid gap-2 text-xs font-bold">
                    <span id="profile-executive-photo-label">
                      {profilePhotoField.label}
                    </span>
                    <WorkspaceMediaField
                      field={profilePhotoField}
                      value={user.data?.profile_media_id ?? ""}
                      onChange={(value) => {
                        void saveProfilePhoto(value);
                      }}
                    />
                    <span
                      className="min-h-5 text-xs font-normal text-muted"
                      aria-live="polite"
                    >
                      {savingPhoto ? "Saving your new profile photo…" : ""}
                    </span>
                  </div>
                  <div className="grid gap-2 text-xs font-bold">
                    <label
                      id="profile-executive-biography-label"
                      htmlFor="profile-executive-biography"
                    >
                      Biography
                    </label>
                    <RichTextEditor
                      id="profile-executive-biography"
                      labelledBy="profile-executive-biography-label"
                      value={publicExecutiveProfile.biography_html}
                      placeholder="Write your public executive biography…"
                      onChange={(biography_html) =>
                        updateExecutiveProfile({ biography_html })
                      }
                    />
                  </div>
                </div>

                <div className="grid gap-5 border-t border-line pt-6">
                  <SectionHeading
                    icon={Mail}
                    eyebrow="Public contact"
                    title="Choose what visitors can see"
                  />
                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-line bg-panel p-4 transition hover:border-coral/30">
                      <input
                        type="checkbox"
                        className="mt-1 size-4 accent-[var(--coral)]"
                        checked={publicExecutiveProfile.show_email}
                        onChange={(event) =>
                          updateExecutiveProfile({
                            show_email: event.target.checked,
                          })
                        }
                      />
                      <span>
                        <b className="block text-sm text-ink">
                          Show email publicly
                        </b>
                        <span className="mt-1 block text-xs leading-5 text-muted">
                          Displays {user.data?.email ?? "your email"} on your
                          public leadership profile.
                        </span>
                      </span>
                    </label>
                    <label
                      className={cn(
                        "flex items-start gap-3 rounded-2xl border border-line bg-panel p-4 transition",
                        user.data?.phone_number
                          ? "cursor-pointer hover:border-coral/30"
                          : "cursor-not-allowed opacity-60",
                      )}
                    >
                      <input
                        type="checkbox"
                        className="mt-1 size-4 accent-[var(--coral)]"
                        disabled={!user.data?.phone_number}
                        checked={publicExecutiveProfile.show_phone}
                        onChange={(event) =>
                          updateExecutiveProfile({
                            show_phone: event.target.checked,
                          })
                        }
                      />
                      <span>
                        <b className="block text-sm text-ink">
                          Show phone publicly
                        </b>
                        <span className="mt-1 block text-xs leading-5 text-muted">
                          {user.data?.phone_number
                            ? "Displays your saved phone number on your public leadership profile."
                            : "Add a phone number on the Account tab before making it public."}
                        </span>
                      </span>
                    </label>
                  </div>
                </div>

                <div className="flex justify-end border-t border-line pt-5">
                  <Button
                    type="submit"
                    disabled={savingExecutive || savingPhoto}
                    className="w-full sm:w-auto sm:min-w-52"
                  >
                    {savingExecutive ? (
                      <LoaderCircle className="size-4 animate-spin" />
                    ) : (
                      <Save className="size-4" />
                    )}
                    Save leadership profile
                  </Button>
                </div>
              </div>

              <aside className="bg-[linear-gradient(180deg,rgb(23_43_69_/_0.03),transparent)] p-6 sm:p-8">
                <p className="text-[.68rem] font-extrabold tracking-[.08em] text-muted uppercase">
                  Public preview
                </p>
                <div className="mt-4 overflow-hidden rounded-2xl border border-line bg-paper shadow-sm">
                  <div className="relative aspect-[4/3.4] bg-ink/6">
                    {user.data?.profile_media_id ? (
                      <Image
                        fill
                        unoptimized
                        alt=""
                        className="object-cover object-[center_20%]"
                        sizes="320px"
                        src={`/api/v1/media/${user.data.profile_media_id}/content`}
                      />
                    ) : (
                      <span className="grid h-full place-items-center text-3xl font-black text-ink/20">
                        {initials(user.data?.full_name ?? "UG")}
                      </span>
                    )}
                  </div>
                  <div className="p-5 text-center">
                    <p className="text-[.68rem] font-extrabold tracking-wide text-coral uppercase">
                      {appointmentMeta.position}
                    </p>
                    <h4 className="mt-2 text-base font-extrabold text-ink">
                      {displayName}
                    </h4>
                    {displayRank ? (
                      <p className="mt-1 text-xs font-semibold text-muted">
                        {displayRank}
                      </p>
                    ) : null}
                    {publicExecutiveProfile.portfolio ? (
                      <p className="mt-3 text-xs leading-5 text-muted">
                        {publicExecutiveProfile.portfolio}
                      </p>
                    ) : null}
                    {publicExecutiveProfile.summary ? (
                      <p className="mt-2 text-xs leading-5 text-muted">
                        {publicExecutiveProfile.summary}
                      </p>
                    ) : null}
                    <div className="mt-4 flex flex-wrap justify-center gap-2">
                      {SOCIAL_FIELDS.filter(
                        (field) =>
                          publicExecutiveProfile.social_links[field.key],
                      ).map((field) => (
                        <span
                          key={field.key}
                          className="rounded-full bg-ink/5 px-2.5 py-1 text-[.62rem] font-bold text-ink"
                        >
                          {field.label}
                        </span>
                      ))}
                      {!SOCIAL_FIELDS.some(
                        (field) =>
                          publicExecutiveProfile.social_links[field.key],
                      ) ? (
                        <span className="text-[.62rem] text-muted">
                          No social links yet
                        </span>
                      ) : null}
                    </div>
                  </div>
                </div>
                <p className="mt-4 text-xs leading-5 text-muted">
                  This is how members and visitors will see your leadership card
                  on the public website.
                </p>
              </aside>
            </form>
          ) : (
            <div
              id="profile-panel-leadership"
              role="tabpanel"
              aria-labelledby="profile-tab-leadership"
              className="grid gap-3 p-8"
            >
              <SectionHeading
                icon={BriefcaseBusiness}
                eyebrow="Public leadership"
                title="No active executive appointment is linked yet"
                description="Once an administrator assigns your leadership term, you can edit social URLs, biography, portfolio, and public contact here."
              />
            </div>
          )
        ) : null}

        {activeTab === "security" ? (
          <div
            id="profile-panel-security"
            role="tabpanel"
            aria-labelledby="profile-tab-security"
            className="p-6 sm:p-8"
          >
            <SectionHeading
              icon={LockKeyhole}
              eyebrow="Password"
              title="Update your password"
              description="Choose a password only you know. Temporary staff-ID passwords should be replaced after first sign-in."
            />
            <form
              className="mt-6 grid max-w-2xl grid-cols-1 gap-x-4 gap-y-5 sm:grid-cols-2 sm:items-start"
              onSubmit={savePassword}
            >
              <div className="grid gap-2 sm:col-span-2">
                <FieldLabel htmlFor="profile-current-password">
                  Current password
                </FieldLabel>
                <PasswordField
                  id="profile-current-password"
                  autoComplete="current-password"
                  required
                  value={current}
                  onChange={setCurrent}
                />
              </div>
              <div className="grid gap-2">
                <FieldLabel htmlFor="profile-new-password">
                  New password
                </FieldLabel>
                <PasswordField
                  id="profile-new-password"
                  autoComplete="new-password"
                  minLength={8}
                  required
                  invalid={Boolean(password) && !passwordIsStrong}
                  describedBy="profile-password-guidance"
                  value={password}
                  onChange={setPassword}
                />
              </div>
              <div className="grid gap-2">
                <FieldLabel htmlFor="profile-confirm-password">
                  Confirm new password
                </FieldLabel>
                <PasswordField
                  id="profile-confirm-password"
                  autoComplete="new-password"
                  minLength={8}
                  required
                  invalid={!passwordsMatch}
                  describedBy="profile-password-match"
                  value={confirm}
                  onChange={setConfirm}
                />
                <p
                  id="profile-password-match"
                  className={cn(
                    "min-h-5 text-xs",
                    passwordsMatch
                      ? "text-muted"
                      : "text-red-700 dark:text-red-300",
                  )}
                  role={passwordsMatch ? undefined : "alert"}
                >
                  {confirm && passwordsMatch
                    ? "Passwords match"
                    : !passwordsMatch
                      ? "The new passwords do not match"
                      : ""}
                </p>
              </div>
              <p
                id="profile-password-guidance"
                className={cn(
                  "text-xs leading-5 sm:col-span-2",
                  password && !passwordIsStrong
                    ? "text-red-700 dark:text-red-300"
                    : "text-muted",
                )}
              >
                Use at least 8 characters with upper and lowercase letters and a
                number.
              </p>
              <div className="sm:col-span-2">
                <Button
                  type="submit"
                  disabled={
                    savingPassword ||
                    !current ||
                    !password ||
                    !confirm ||
                    !passwordIsStrong ||
                    !passwordsMatch
                  }
                  className="w-full sm:w-auto sm:min-w-44"
                >
                  {savingPassword ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <LockKeyhole className="size-4" />
                  )}
                  Update password
                </Button>
              </div>
            </form>
          </div>
        ) : null}
      </section>
    </div>
  );
}
