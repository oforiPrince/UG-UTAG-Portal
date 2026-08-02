import { describe, expect, it } from "vitest";

import { workspaces } from "./workspaces";

function fieldType(workspace: string, key: string) {
  const fields = workspaces[workspace]?.create?.fields ?? [];
  return fields.find((field) => field.key === key)?.type;
}

function configuredFields() {
  return Object.entries(workspaces)
    .filter(([workspace]) => workspace !== "content")
    .flatMap(([workspace, config]) =>
      [
        config.create,
        config.update,
        config.archive,
        ...(config.actions ?? []),
      ].flatMap((mutation) =>
        (mutation?.fields ?? []).map((field) => ({ workspace, field })),
      ),
    );
}

describe("workspace content editors", () => {
  it("opens a complete protected preview for every document", () => {
    const preview = workspaces.documents.actions?.find(
      (action) => action.label === "Preview",
    );
    expect(preview).toMatchObject({
      permission: "documents.view",
      open: true,
    });
    expect(preview?.href?.({ id: "document-1" })).toBe(
      "/dashboard/documents/document-1/preview",
    );
  });

  it("offers General Public only for external documents", () => {
    const audience = workspaces.documents.create?.fields?.find(
      (field) => field.key === "audiences",
    );
    expect(audience).toMatchObject({
      options: expect.arrayContaining(["general_public", "all_members"]),
    });
    expect(
      audience?.optionsForValues?.({ category: "internal" }),
    ).not.toContain("general_public");
    expect(audience?.optionsForValues?.({ category: "external" })).toContain(
      "general_public",
    );
    expect(
      workspaces.documents.create?.prepare?.({
        title: "Public policy",
        category: "internal",
        audiences: ["general_public"],
      }),
    ).toMatchObject({
      category: "internal",
      audiences: [{ type: "role", value: "member" }],
    });
    expect(
      workspaces.documents.create?.prepare?.({
        title: "Public policy",
        category: "external",
        audiences: ["general_public"],
      }),
    ).toMatchObject({
      category: "external",
      audiences: [{ type: "general_public", value: "all" }],
    });
  });

  it.each([
    ["executives", "biography_html"],
    ["news", "content_html"],
    ["announcements", "content_html"],
    ["events", "description_html"],
    ["documents", "description_html"],
    ["galleries", "description"],
    ["carousel", "description"],
  ])("uses rich text for %s.%s", (workspace, key) => {
    expect(fieldType(workspace, key)).toBe("richtext");
  });

  it("classifies every long-form and plain multiline field across every workspace", () => {
    const actualRichText = [
      ...new Set(
        configuredFields()
          .filter(({ field }) => field.type === "richtext")
          .map(({ workspace, field }) => `${workspace}.${field.key}`),
      ),
    ].sort();
    const actualPlainText = [
      ...new Set(
        configuredFields()
          .filter(({ field }) => field.type === "textarea")
          .map(({ workspace, field }) => `${workspace}.${field.key}`),
      ),
    ].sort();

    expect(actualRichText).toEqual(
      [
        "announcements.content_html",
        "carousel.description",
        "documents.description_html",
        "events.description_html",
        "executives.biography_html",
        "galleries.description",
        "news.content_html",
      ].sort(),
    );
    expect(actualPlainText).toEqual(
      [
        "advert-advertisers.notes",
        "advert-orders.notes",
        "advert-plans.description",
        "advert-slots.description",
        "documents.change_note",
        "events.address",
        "events.short_description",
        "executives.summary",
        "feature-flags.description",
        "media.alt_text",
        "media.caption",
        "members.reason",
        "news.excerpt",
      ].sort(),
    );
  });

  it("gives repeatable publishing notes proper multiline fields", () => {
    expect(
      workspaces.news.create?.fields
        ?.find((field) => field.key === "citations")
        ?.structuredItemFields?.find((field) => field.key === "description")
        ?.type,
    ).toBe("textarea");
    expect(
      workspaces.events.create?.fields
        ?.find((field) => field.key === "speakers")
        ?.structuredItemFields?.find((field) => field.key === "bio")?.type,
    ).toBe("textarea");
    expect(
      workspaces.events.create?.fields
        ?.find((field) => field.key === "schedule")
        ?.structuredItemFields?.find((field) => field.key === "description")
        ?.type,
    ).toBe("textarea");
  });

  it.each([
    "news",
    "announcements",
    "events",
    "documents",
    "galleries",
    "carousel",
    "adverts",
  ])("makes the %s title a prominent full-width field", (workspace) => {
    for (const mutation of [
      workspaces[workspace]?.create,
      workspaces[workspace]?.update,
    ]) {
      if (!mutation) continue;
      const title = mutation.fields?.find((field) => field.key === "title");
      expect(title?.prominent).toBe(true);
      expect(title?.placeholder).toBeTruthy();
    }
  });

  it("keeps carousel create and update forms aligned", () => {
    for (const workspace of ["carousel", "galleries"]) {
      for (const mutation of [
        workspaces[workspace].create,
        workspaces[workspace].update,
      ]) {
        const description = mutation?.fields?.find(
          (field) => field.key === "description",
        );
        expect(description).toMatchObject({
          label: "Description",
          type: "richtext",
          emptyValue: "",
        });
        expect(description?.placeholder).toBeTruthy();
      }
    }
  });

  it("supports optional inline member portraits and required executive portraits", () => {
    const memberPhoto = workspaces.members.create?.fields?.find(
      (field) => field.key === "profile_media_id",
    );
    const executivePhoto = workspaces.executives.create?.fields?.find(
      (field) => field.key === "profile_media_id",
    );

    expect(memberPhoto?.type).toBe("media");
    expect(memberPhoto?.required).not.toBe(true);
    expect(memberPhoto?.media).toMatchObject({
      accept: "image",
      isPrivate: false,
      aspect: "portrait",
    });
    expect(executivePhoto?.type).toBe("media");
    expect(executivePhoto?.required).toBe(true);
    expect(
      memberPhoto?.optionSource?.filter?.({
        content_type: "image/jpeg",
        is_private: false,
      }),
    ).toBe(true);
    expect(
      memberPhoto?.optionSource?.filter?.({
        content_type: "image/jpeg",
        is_private: true,
      }),
    ).toBe(false);
    expect(
      memberPhoto?.optionSource?.filter?.({
        content_type: "application/pdf",
        is_private: false,
      }),
    ).toBe(false);
  });

  it.each([
    ["news", "featured_media_id", false],
    ["events", "featured_media_id", false],
    ["documents", "media_asset_ids", true],
    ["galleries", "media_asset_ids", true],
    ["carousel", "media_asset_id", false],
    ["adverts", "media_asset_id", false],
  ])("uses inline upload and preview for %s.%s", (workspace, key, multiple) => {
    const field = workspaces[workspace]?.create?.fields?.find(
      (candidate) => candidate.key === key,
    );
    expect(field?.type).toBe("media");
    expect(Boolean(field?.media?.multiple)).toBe(multiple);
  });

  it("ties advert plans to placements and surfaces site location", () => {
    const planSlot = workspaces["advert-plans"].create?.fields?.find(
      (field) => field.key === "slot_id",
    );
    expect(planSlot?.required).toBe(true);
    expect(planSlot?.type).toBe("select");
    expect(
      workspaces["advert-plans"].columns.some(
        (column) => column.key === "placement_name",
      ),
    ).toBe(true);

    const location = workspaces["advert-slots"].create?.fields?.find(
      (field) => field.key === "location",
    );
    expect(location?.required).toBe(true);
    expect(
      workspaces["advert-slots"].columns.some(
        (column) => column.key === "location",
      ),
    ).toBe(true);
    expect(
      workspaces["advert-slots"].columns.some((column) => column.key === "size"),
    ).toBe(true);

    const destination = workspaces.adverts.create?.fields?.find(
      (field) => field.key === "target_url",
    );
    expect(destination?.type).toBe("url");

    const houseAd = workspaces.adverts.create?.fields?.find(
      (field) => field.key === "is_house_ad",
    );
    expect(houseAd?.type).toBe("checkbox");
    expect(
      workspaces.adverts.columns.some((column) => column.key === "fulfilment"),
    ).toBe(true);
  });
});
