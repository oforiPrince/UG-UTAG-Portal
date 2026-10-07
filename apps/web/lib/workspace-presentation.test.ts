import { describe, expect, it } from "vitest";

import {
  collectionLabel,
  routedWorkspace,
  wizardStepIndexForField,
  workspacePresentationFor,
  workspacePresentations,
} from "@/lib/workspace-presentation";
import { workspaces } from "@/lib/workspaces";

const fullPageWorkspaces = [
  "members",
  "executives",
  "news",
  "announcements",
  "events",
  "documents",
  "media",
  "galleries",
  "carousel",
  "adverts",
  "advert-orders",
] as const;

describe("workspace presentation registry", () => {
  it("assigns an intentional presentation to every dashboard workspace", () => {
    for (const [key, config] of Object.entries(workspaces)) {
      if (key === "content") continue;
      expect(
        workspacePresentationFor(config),
        `${key} missing presentation`,
      ).toBe(workspacePresentations[key]);
    }
  });

  it.each(fullPageWorkspaces)(
    "routes substantial %s records to pages with guided forms",
    (key) => {
      const presentation = workspacePresentations[key];

      expect(presentation.fullPage).toBe(true);
      expect(presentation.detailEndpoint).toBeTypeOf("function");
      expect(presentation.detailHref).toBeTypeOf("function");
      expect(presentation.editHref).toBeTypeOf("function");
      expect(presentation.createHref).toMatch(/^\/dashboard\//);
      expect(presentation.createSteps?.at(-1)?.id).toBe("review");
      expect(presentation.editSteps?.at(-1)?.id).toBe("review");
    },
  );

  it("keeps small operational records in focused dialogs", () => {
    for (const key of [
      "organization",
      "advert-slots",
      "advert-plans",
      "advert-advertisers",
      "settings",
      "feature-flags",
    ]) {
      expect(workspacePresentations[key]?.fullPage).not.toBe(true);
      expect(
        workspacePresentations[key]?.detailSections.length,
      ).toBeGreaterThan(0);
    }
  });

  it("opens documents in the document preview without replacing their record route", () => {
    const document = { id: "document-id" };

    expect(workspacePresentations.documents.viewHref?.(document)).toBe(
      "/dashboard/documents/document-id/preview",
    );
    expect(workspacePresentations.documents.detailHref?.(document)).toBe(
      "/dashboard/documents/document-id",
    );
    expect(workspacePresentations.documents.listViewReplacesActionLabel).toBe(
      "Preview",
    );
  });

  it("does not expose database implementation fields in semantic detail sections", () => {
    const technical = new Set([
      "id",
      "slug",
      "storage_key",
      "sha256",
      "metadata_json",
      "input_json",
      "result_json",
      "payload",
      "rules",
    ]);

    for (const presentation of Object.values(workspacePresentations)) {
      for (const section of presentation.detailSections) {
        expect(section.fieldKeys.filter((key) => technical.has(key))).toEqual(
          [],
        );
      }
    }
  });

  it("maps the content alias and rejects compact workspaces as routed pages", () => {
    expect(routedWorkspace("content")?.configKey).toBe("news");
    expect(routedWorkspace("galleries")?.configKey).toBe("galleries");
    expect(routedWorkspace("settings")).toBeNull();
  });

  it("presents members and executives as dense people tables", () => {
    expect(workspacePresentations.members.listVariant).toBe("table");
    expect(workspacePresentations.executives.listVariant).toBe("table");
    expect(workspaces.members.columns.map((column) => column.key)).toEqual([
      "full_name",
      "email",
      "academic_rank",
      "roles",
      "status",
    ]);
    expect(workspaces.executives.columns.map((column) => column.key)).toEqual([
      "full_name",
      "position",
      "is_active",
    ]);
  });

  it("keeps operational tables scannable without duplicate columns", () => {
    expect(
      workspaces.adverts.columns.map((column) => ({
        key: column.key,
        label: column.label,
        subtitleKey: column.subtitleKey,
        metricKeys: column.metricKeys,
      })),
    ).toEqual([
      {
        key: "title",
        label: "Campaign",
        subtitleKey: "advertiser_name",
        metricKeys: undefined,
      },
      {
        key: "status",
        label: "Status",
        subtitleKey: "fulfilment",
        metricKeys: undefined,
      },
      {
        key: "starts_at",
        label: "Schedule",
        subtitleKey: undefined,
        metricKeys: undefined,
      },
      {
        key: "impressions",
        label: "Delivery",
        subtitleKey: undefined,
        metricKeys: ["clicks"],
      },
    ]);
    expect(workspaces.documents.columns.map((column) => column.key)).toEqual([
      "title",
      "category",
      "status",
      "document_date",
    ]);
    expect(workspaces.documents.columns[0]?.subtitleKey).toBe("public_id");
    expect(
      workspaces["advert-orders"].columns.map((column) => column.key),
    ).toEqual(["advertiser_name", "campaign_name", "status", "starts_on"]);

    for (const [key, config] of Object.entries(workspaces)) {
      if (key === "content") continue;
      const visible = new Set(config.columns.map((column) => column.key));
      for (const column of config.columns) {
        if (column.subtitleKey) {
          expect(
            visible.has(column.subtitleKey),
            `${key}.${column.key} duplicates ${column.subtitleKey}`,
          ).toBe(false);
        }
        for (const metricKey of column.metricKeys ?? []) {
          expect(
            visible.has(metricKey),
            `${key}.${column.key} duplicates metric ${metricKey}`,
          ).toBe(false);
        }
      }
    }
  });

  it("presents analytics as a snapshot dashboard and audit as a dense log", () => {
    expect(workspacePresentations.analytics.listVariant).toBe("analytics");
    expect(workspacePresentations.audit.listVariant).toBe("table");
    expect(workspaces.audit.columns.map((column) => column.label)).toEqual([
      "Actor",
      "Action",
      "Time",
      "Outcome",
    ]);
    expect(workspaces.audit.columns.map((column) => column.key)).toEqual([
      "actor_name",
      "action",
      "created_at",
      "outcome",
    ]);
    expect(workspaces.audit.columns[1]?.subtitleKey).toBe("resource_type");
  });

  it("uses human collection labels and can jump a wizard field back to its step", () => {
    expect(collectionLabel("Gallery")).toBe("galleries");
    expect(collectionLabel("Member")).toBe("members");
    expect(collectionLabel()).toBe("items");
    expect(
      wizardStepIndexForField(
        workspacePresentations.news.createSteps ?? [],
        "content_html",
      ),
    ).toBe(1);
    expect(
      wizardStepIndexForField(
        workspacePresentations.members.createSteps ?? [],
        "roles",
      ),
    ).toBe(2);
  });
});
