"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  LoaderCircle,
  LockKeyhole,
  Save,
  ShieldCheck,
  UserRoundCog,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import Image from "next/image";
import { useState } from "react";
import { toast } from "sonner";

import { RichTextEditor } from "@/components/dashboard/rich-text-editor";
import { WorkspaceMediaField } from "@/components/dashboard/workspace-media-field";
import { WorkspaceSelect } from "@/components/dashboard/workspace-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { initials } from "@/lib/utils";
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
  biography_html: string;
  social_links: Record<string, string>;
};
type ExecutiveProfileForm = Pick<
  ExecutiveProfile,
  "biography_html" | "social_links"
>;

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
  "min-h-12 rounded-xl border border-line bg-panel px-4 text-sm font-normal outline-none transition focus:border-ink/25";

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
        emptyLabel: `No active ${type}s`,
      },
    },
  ]),
) as Record<"school" | "college" | "department", WorkspaceField>;

const profilePhotoField: WorkspaceField = {
  key: "profile_media_id",
  label: "Public profile photo",
  type: "media",
  required: true,
  media: {
    accept: "image",
    isPrivate: false,
    aspect: "portrait",
  },
  help: "Required for public leadership cards. Upload a clear portrait photo.",
};

export function ProfileClient() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const search = useSearchParams();
  const user = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => api<User>("/api/v1/auth/me"),
  });
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
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingExecutive, setSavingExecutive] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);

  const profile = profileDraft ?? profileFromUser(user.data);
  const publicExecutiveProfile = executiveDraft ?? executiveProfile.data;
  const mustCompleteExecutiveProfile = Boolean(
    user.data?.must_complete_executive_profile,
  );
  const executiveRequired =
    search.get("executive") === "required" || mustCompleteExecutiveProfile;

  function updateProfile(changes: Partial<ProfileForm>) {
    setProfileDraft({ ...profile, ...changes });
  }

  async function saveProfilePhoto(profileMediaId: string | string[]) {
    const nextId = Array.isArray(profileMediaId)
      ? (profileMediaId[0] ?? null)
      : profileMediaId || null;
    try {
      const updated = await api<User>("/api/v1/auth/profile", {
        method: "PATCH",
        body: { profile_media_id: nextId },
      });
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
        error instanceof Error ? error.message : "Could not update profile photo",
      );
    }
  }

  async function saveProfile(event: React.FormEvent) {
    event.preventDefault();
    setSavingProfile(true);
    try {
      await api("/api/v1/auth/profile", {
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
      await api("/api/v1/auth/executive-profile", {
        method: "PATCH",
        body: {
          biography_html: publicExecutiveProfile.biography_html,
          social_links: publicExecutiveProfile.social_links,
        },
      });
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
      toast.success("Public executive profile updated");
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
    setExecutiveDraft({
      biography_html: publicExecutiveProfile.biography_html,
      social_links: publicExecutiveProfile.social_links,
      ...changes,
    });
  }

  return (
    <div className="grid gap-5">
      <header>
        <p className="eyebrow text-coral">Account & security</p>
        <h2 className="display-type mt-3 text-4xl sm:text-5xl">Your profile</h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">
          Keep your association identity, contact details and sign-in security
          current.
        </p>
      </header>

      {user.data?.must_change_password ? (
        <div
          className="flex items-start gap-4 rounded-2xl border border-gold/40 bg-gold/10 p-5"
          role="alert"
        >
          <AlertTriangle className="mt-0.5 size-5 shrink-0 text-amber-700" />
          <div>
            <b className="text-sm">
              Replace your temporary password before continuing
            </b>
            <p className="mt-1 text-xs leading-5 text-muted">
              This account was issued with a temporary credential. Use the
              password form below to choose a private password that only you
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
              Your portrait and biography appear on the public UG UTAG website.
              Add a clear profile photo and a public biography to unlock the
              rest of the dashboard.
            </p>
          </div>
        </div>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-[.72fr_1.28fr]">
        <Card>
          <CardContent className="p-7">
            <span className="relative grid size-20 place-items-center overflow-hidden rounded-2xl bg-ink text-xl font-black text-paper">
              {user.data?.profile_media_id ? (
                <Image
                  fill
                  unoptimized
                  alt={`Profile photo for ${user.data.full_name}`}
                  className="object-cover"
                  sizes="80px"
                  src={`/api/v1/media/${user.data.profile_media_id}/content`}
                />
              ) : (
                initials(user.data?.full_name ?? "UG")
              )}
            </span>
            <h3 className="mt-6 text-xl font-black">
              {user.data?.full_name ?? "Loading profile…"}
            </h3>
            <p className="mt-1 text-sm text-muted">{user.data?.email}</p>
            {user.data?.staff_id ? (
              <p className="mt-1 text-xs text-muted">
                Staff ID: {user.data.staff_id}
              </p>
            ) : null}
            <div className="mt-6 flex flex-wrap gap-2">
              {user.data?.roles.map((role) => (
                <span
                  key={role}
                  className="rounded-full bg-gold/15 px-3 py-1 text-[.62rem] font-bold"
                >
                  {role}
                </span>
              ))}
            </div>
            <div className="mt-8 flex items-center gap-3 border-t border-line pt-6">
              <ShieldCheck className="size-5 text-emerald-600" />
              <p className="text-xs">
                <b className="block">Protected account</b>
                <span className="text-muted">
                  Secure sessions and role-based access
                </span>
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-7">
            <div className="flex items-center gap-3">
              <UserRoundCog className="size-5 text-coral" />
              <div>
                <p className="eyebrow text-coral">Member details</p>
                <h3 className="mt-2 text-xl font-black">Update your profile</h3>
              </div>
            </div>
            <form
              className="mt-7 grid gap-5 sm:grid-cols-2"
              onSubmit={saveProfile}
            >
              <label className="grid gap-2 text-xs font-bold">
                Title
                <select
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
              </label>
              <label className="grid gap-2 text-xs font-bold">
                Gender
                <select
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
              </label>
              <label className="grid gap-2 text-xs font-bold">
                Other names
                <input
                  className={inputClass}
                  required
                  value={profile.other_name}
                  onChange={(event) =>
                    updateProfile({ other_name: event.target.value })
                  }
                />
              </label>
              <label className="grid gap-2 text-xs font-bold">
                Surname
                <input
                  className={inputClass}
                  required
                  value={profile.surname}
                  onChange={(event) =>
                    updateProfile({ surname: event.target.value })
                  }
                />
              </label>
              <label className="grid gap-2 text-xs font-bold">
                Academic rank
                <input
                  className={inputClass}
                  value={profile.academic_rank}
                  onChange={(event) =>
                    updateProfile({ academic_rank: event.target.value })
                  }
                />
              </label>
              <label className="grid gap-2 text-xs font-bold">
                Phone number
                <input
                  className={inputClass}
                  type="tel"
                  value={profile.phone_number}
                  onChange={(event) =>
                    updateProfile({ phone_number: event.target.value })
                  }
                />
              </label>
              <>
                {(["school", "college", "department"] as const).map((type) => {
                  const key = `${type}_id` as
                    "school_id" | "college_id" | "department_id";
                  const labelId = `profile-${type}-label`;
                  return (
                    <div key={type} className="grid gap-2 text-xs font-bold">
                      <label id={labelId} htmlFor={`profile-${type}`}>
                        {profileUnitFields[type].label}
                      </label>
                      <WorkspaceSelect
                        id={`profile-${type}`}
                        labelledBy={labelId}
                        field={profileUnitFields[type]}
                        value={profile[key]}
                        autoFocus={false}
                        onChange={(value) => updateProfile({ [key]: value })}
                      />
                    </div>
                  );
                })}
              </>
              <div className="flex justify-end sm:col-span-2">
                <Button disabled={savingProfile}>
                  {savingProfile ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <Save className="size-4" />
                  )}
                  Save profile
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>

      {publicExecutiveProfile ? (
        <Card>
          <CardContent className="p-7">
            <p className="eyebrow text-coral">Public leadership profile</p>
            <h3 className="mt-3 text-xl font-black">
              Update your {executiveProfile.data?.position ?? "executive"}{" "}
              profile
            </h3>
            <p className="mt-2 max-w-3xl text-xs leading-5 text-muted">
              This portrait, biography, and these links appear in your public
              leadership details. Formatting is preserved after security checks.
            </p>
            <form className="mt-7 grid gap-5" onSubmit={saveExecutiveProfile}>
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
              <div className="grid gap-4 sm:grid-cols-2">
                {[
                  ["linkedin", "LinkedIn profile"],
                  ["facebook", "Facebook profile"],
                  ["twitter", "X / Twitter profile"],
                  ["website", "Website"],
                ].map(([key, label]) => (
                  <label key={key} className="grid gap-2 text-xs font-bold">
                    {label}
                    <input
                      type="url"
                      value={publicExecutiveProfile.social_links[key] ?? ""}
                      placeholder="https://"
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
                  </label>
                ))}
              </div>
              <div className="flex justify-end">
                <Button disabled={savingExecutive}>
                  {savingExecutive ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <Save className="size-4" />
                  )}
                  Save public profile
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardContent className="p-7">
          <p className="eyebrow text-coral">Password</p>
          <h3 className="mt-3 text-xl font-black">Update your password</h3>
          <form
            className="mt-7 grid max-w-2xl gap-5 sm:grid-cols-2"
            onSubmit={savePassword}
          >
            <label className="grid gap-2 text-xs font-bold sm:col-span-2">
              Current password
              <input
                type="password"
                autoComplete="current-password"
                required
                value={current}
                onChange={(event) => setCurrent(event.target.value)}
                className={inputClass}
              />
            </label>
            <label className="grid gap-2 text-xs font-bold">
              New password
              <input
                type="password"
                autoComplete="new-password"
                minLength={8}
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className={inputClass}
              />
              <span className="font-normal leading-5 text-muted">
                At least 8 characters with upper and lowercase letters and a
                number.
              </span>
            </label>
            <label className="grid gap-2 text-xs font-bold">
              Confirm new password
              <input
                type="password"
                autoComplete="new-password"
                minLength={8}
                required
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
                className={inputClass}
              />
            </label>
            <div className="sm:col-span-2">
              <Button disabled={savingPassword}>
                {savingPassword ? (
                  <LoaderCircle className="size-4 animate-spin" />
                ) : (
                  <LockKeyhole className="size-4" />
                )}
                Update password
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
