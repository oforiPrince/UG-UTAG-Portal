"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowDownToLine,
  FileSpreadsheet,
  LoaderCircle,
  Upload,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { formatPersonName, formatRankForName } from "@/lib/utils";

type ImportIssue = { row: number; field: string | null; message: string };
type ImportPreview = {
  row: number;
  email: string;
  staff_id: string | null;
  full_name: string;
  academic_rank: string | null;
  roles: string[];
  chat_groups: string[];
};
type ImportResult = {
  dry_run: boolean;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  imported_rows: number;
  duplicate_rows: number;
  chat_groups_created: number;
  chat_memberships_added: number;
  issues: ImportIssue[];
  preview: ImportPreview[];
  preview_truncated: boolean;
};

type User = { permissions: string[] };

function importRequest(file: File, dryRun: boolean) {
  const form = new FormData();
  form.append("file", file);
  form.append("dry_run", String(dryRun));
  return api<ImportResult>("/api/v1/members/import", {
    method: "POST",
    body: form,
  });
}

function ImportDialog({ close }: { close: () => void }) {
  const queryClient = useQueryClient();
  const picker = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File>();
  const [result, setResult] = useState<ImportResult>();

  const preview = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("Choose a CSV or Excel file");
      return importRequest(file, true);
    },
    onSuccess: setResult,
    onError: (error) =>
      toast.error(
        error instanceof Error
          ? error.message
          : "The member file could not be checked",
      ),
  });
  const commit = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("Choose a CSV or Excel file");
      return importRequest(file, false);
    },
    onSuccess: async (imported) => {
      setResult(imported);
      if (imported.issues.length) {
        toast.error("Fix the reported rows before importing");
        return;
      }
      toast.success(
        `${imported.imported_rows} account(s) created with ${imported.chat_memberships_added} chat membership(s)`,
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["members"] }),
        queryClient.invalidateQueries({ queryKey: ["jobs"] }),
        queryClient.invalidateQueries({ queryKey: ["chat"] }),
      ]);
      close();
    },
    onError: (error) =>
      toast.error(
        error instanceof Error
          ? error.message
          : "The members could not be imported",
      ),
  });
  const busy = preview.isPending || commit.isPending;

  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape" && !busy) close();
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [busy, close]);

  return (
    <div
      className="fixed inset-0 z-[90] flex justify-end bg-black/45 backdrop-blur-sm"
      role="presentation"
      onMouseDown={() => {
        if (!busy) close();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-label="Import members"
        className="h-full w-full max-w-3xl overflow-y-auto bg-paper p-6 shadow-2xl sm:p-8"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-5">
          <div>
            <p className="eyebrow text-coral">Bulk account workflow</p>
            <h2 className="display-type mt-3 text-4xl">Import members</h2>
            <p className="mt-2 max-w-xl text-xs leading-6 text-muted">
              Preview CSV or XLSX rows before creating active accounts and their
              UTAG, school, and department chats.
            </p>
          </div>
          <Button
            size="icon"
            variant="ghost"
            onClick={close}
            disabled={busy}
            aria-label="Close import"
          >
            <X className="size-5" />
          </Button>
        </div>

        <input
          ref={picker}
          className="sr-only"
          type="file"
          accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          onChange={(event) => {
            setFile(event.target.files?.[0]);
            setResult(undefined);
          }}
        />
        <button
          type="button"
          onClick={() => picker.current?.click()}
          className="mt-7 flex min-h-32 w-full items-center justify-center gap-4 rounded-2xl border-2 border-dashed border-line p-6 text-left transition hover:border-sky"
        >
          <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-ink/5">
            <FileSpreadsheet className="size-5 text-coral" />
          </span>
          <span>
            <b className="block text-sm">
              {file?.name ?? "Choose a member spreadsheet"}
            </b>
            <span className="mt-1 block text-[.68rem] leading-5 text-muted">
              CSV or XLSX · maximum 8 MB and 2,000 data rows
            </span>
          </span>
        </button>

        <div className="mt-4 rounded-xl bg-ink/[.035] p-4 text-[.68rem] leading-6 text-muted">
          Required columns:{" "}
          <b className="text-ink">
            staff_id, email, other_name, surname, college, school, department
          </b>
          . Optional: title, gender, academic_rank, phone_number, roles. Role
          values may be separated by commas or semicolons.
          <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1">
            <a
              href="/api/v1/members/import-template.xlsx"
              className="flex w-fit items-center gap-2 font-bold text-coral"
            >
              <ArrowDownToLine className="size-3.5" /> Download Excel template
            </a>
            <a
              href="/api/v1/members/organization-reference.csv"
              className="flex w-fit items-center gap-2 font-bold text-coral"
            >
              <ArrowDownToLine className="size-3.5" /> Organization reference
            </a>
          </div>
        </div>

        <div className="mt-4 rounded-xl border border-gold/35 bg-gold/10 p-4 text-[.68rem] leading-6 text-ink">
          <b>First sign-in:</b> each member uses their university email and
          exact staff ID as the temporary password. The portal requires a new
          private password before any dashboard or chat access.
        </div>

        {result ? (
          <div className="mt-6 grid gap-5">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                ["Rows", result.total_rows],
                ["Ready", result.valid_rows],
                ["Issues", result.invalid_rows],
                ["Duplicates", result.duplicate_rows],
              ].map(([label, value]) => (
                <div
                  key={String(label)}
                  className="rounded-xl border border-line bg-panel p-4"
                >
                  <b className="text-2xl">{value}</b>
                  <span className="mt-1 block text-[.62rem] font-bold text-muted uppercase">
                    {label}
                  </span>
                </div>
              ))}
            </div>

            {result.issues.length ? (
              <div className="rounded-2xl border border-red-500/25 bg-red-500/5 p-5">
                <div className="flex items-center gap-2 text-sm font-black text-red-700 dark:text-red-300">
                  <AlertTriangle className="size-4" /> Fix these rows before
                  importing
                </div>
                <ul className="mt-3 max-h-48 space-y-2 overflow-y-auto text-xs leading-5">
                  {result.issues.slice(0, 100).map((issue, index) => (
                    <li key={`${issue.row}-${issue.field}-${index}`}>
                      <b>Row {issue.row}</b>
                      {issue.field ? ` · ${issue.field}` : ""}: {issue.message}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {result.preview.length ? (
              <div className="overflow-hidden rounded-2xl border border-line">
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[64rem] text-left text-xs">
                    <thead className="bg-ink/[.035] text-[.62rem] font-black uppercase">
                      <tr>
                        <th className="px-4 py-3">Row</th>
                        <th className="px-4 py-3">Member</th>
                        <th className="px-4 py-3">Staff ID</th>
                        <th className="px-4 py-3">Email</th>
                        <th className="px-4 py-3">Rank</th>
                        <th className="px-4 py-3">Roles</th>
                        <th className="px-4 py-3">Chat groups</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {result.preview.map((member) => (
                        <tr key={`${member.row}-${member.email}`}>
                          <td className="px-4 py-3 text-muted">{member.row}</td>
                          <td className="px-4 py-3 font-bold">
                            {formatPersonName(member.full_name)}
                          </td>
                          <td className="px-4 py-3 font-mono">
                            {member.staff_id}
                          </td>
                          <td className="px-4 py-3">{member.email}</td>
                          <td className="px-4 py-3 text-muted">
                            {member.academic_rank
                              ? formatRankForName(
                                  member.full_name,
                                  member.academic_rank,
                                )
                              : "—"}
                          </td>
                          <td className="px-4 py-3">
                            {member.roles.join(", ")}
                          </td>
                          <td className="px-4 py-3 text-muted">
                            {member.chat_groups.join(" · ")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {result.preview_truncated ? (
                  <p className="border-t border-line p-3 text-center text-[.65rem] text-muted">
                    Showing the first 50 valid rows.
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="mt-7 flex flex-wrap justify-end gap-2 border-t border-line pt-5">
          <Button variant="outline" onClick={close} disabled={busy}>
            Cancel
          </Button>
          <Button
            variant="outline"
            disabled={!file || preview.isPending || commit.isPending}
            onClick={() => preview.mutate()}
          >
            {preview.isPending ? (
              <LoaderCircle className="size-4 animate-spin" />
            ) : (
              <FileSpreadsheet className="size-4" />
            )}
            Preview rows
          </Button>
          <Button
            disabled={!result || result.issues.length > 0 || commit.isPending}
            onClick={() => commit.mutate()}
          >
            {commit.isPending ? (
              <LoaderCircle className="size-4 animate-spin" />
            ) : (
              <Upload className="size-4" />
            )}
            Create accounts and chats{" "}
            {result?.valid_rows ? `(${result.valid_rows})` : ""}
          </Button>
        </div>
      </section>
    </div>
  );
}

export function MemberImportButton() {
  const [open, setOpen] = useState(false);
  const user = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => api<User>("/api/v1/auth/me"),
    staleTime: 60_000,
  });
  if (!user.data?.permissions.includes("members.create")) return null;
  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}>
        <FileSpreadsheet className="size-4" /> Import
      </Button>
      {open ? <ImportDialog close={() => setOpen(false)} /> : null}
    </>
  );
}
