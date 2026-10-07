import type { WorkspaceConfig, WorkspaceRow } from "./workspaces";

export type WorkspaceWizardStep = {
  id: string;
  title: string;
  description: string;
  fieldKeys: string[];
};

export type WorkspaceDetailSection = {
  id: string;
  title: string;
  description?: string;
  fieldKeys: string[];
};

export type WorkspaceListVariant =
  | "table"
  | "cards"
  | "directory"
  | "media"
  | "timeline"
  | "settings"
  | "analytics";

export type WorkspacePresentation = {
  listVariant: WorkspaceListVariant;
  listHref: string;
  detailEndpoint?: (id: string) => string;
  viewHref?: (row: WorkspaceRow) => string;
  listViewReplacesActionLabel?: string;
  detailHref?: (row: WorkspaceRow) => string;
  editHref?: (row: WorkspaceRow) => string;
  createHref?: string;
  fullPage?: boolean;
  detailSections: WorkspaceDetailSection[];
  createSteps?: WorkspaceWizardStep[];
  editSteps?: WorkspaceWizardStep[];
  recoverableFields?: string[];
};

const reviewStep = (label = "Review and save"): WorkspaceWizardStep => ({
  id: "review",
  title: label,
  description: "Check the information and confirm the final details.",
  fieldKeys: [],
});

const memberSteps: WorkspaceWizardStep[] = [
  {
    id: "identity",
    title: "Identity",
    description: "Add the member’s name, contact details, and portrait.",
    fieldKeys: [
      "title",
      "other_name",
      "surname",
      "gender",
      "academic_rank",
      "email",
      "phone_number",
      "profile_media_id",
    ],
  },
  {
    id: "organization",
    title: "Organization",
    description:
      "Place the member in the correct college, school, and department.",
    fieldKeys: ["college_id", "school_id", "department_id"],
  },
  {
    id: "access",
    title: "Account access",
    description:
      "Set the staff reference, portal roles, and invitation preference.",
    fieldKeys: ["staff_id", "roles", "send_invitation"],
  },
  reviewStep(),
];

const executiveSteps: WorkspaceWizardStep[] = [
  {
    id: "office",
    title: "Member and office",
    description: "Choose the member and describe the office they hold.",
    fieldKeys: ["user_id", "position", "portfolio", "profile_media_id"],
  },
  {
    id: "profile",
    title: "Public profile",
    description: "Write the public introduction and leadership biography.",
    fieldKeys: ["summary", "biography_html", "social_links"],
  },
  {
    id: "term",
    title: "Term and visibility",
    description: "Set dates, appointment state, and public contact consent.",
    fieldKeys: [
      "appointed_on",
      "ended_on",
      "term_number",
      "is_acting",
      "is_active",
      "is_public",
      "show_email",
      "show_phone",
    ],
  },
  reviewStep(),
];

const articleSteps: WorkspaceWizardStep[] = [
  {
    id: "story",
    title: "Story",
    description: "Give the article a clear headline and concise introduction.",
    fieldKeys: ["title", "excerpt"],
  },
  {
    id: "body",
    title: "Article body",
    description: "Write and format the full public story.",
    fieldKeys: ["content_html"],
  },
  {
    id: "media",
    title: "Media and sources",
    description: "Add a featured image, supporting files, tags, and citations.",
    fieldKeys: [
      "featured_media_id",
      "attachment_media_ids",
      "tags",
      "citations",
      "is_featured",
    ],
  },
  {
    id: "publishing",
    title: "Publishing",
    description: "Choose the workflow state and publication time.",
    fieldKeys: ["status", "published_at"],
  },
  reviewStep("Review article"),
];

const announcementSteps: WorkspaceWizardStep[] = [
  {
    id: "message",
    title: "Message",
    description: "Write the official announcement members will receive.",
    fieldKeys: ["title", "content_html"],
  },
  {
    id: "audience",
    title: "Audience and priority",
    description: "Choose who should receive the message and how urgent it is.",
    fieldKeys: ["audiences", "priority"],
  },
  {
    id: "timing",
    title: "Timing",
    description: "Set its workflow state, publication time, and expiry.",
    fieldKeys: ["status", "published_at", "expires_at"],
  },
  reviewStep("Review announcement"),
];

const eventSteps: WorkspaceWizardStep[] = [
  {
    id: "basics",
    title: "Event basics",
    description: "Introduce the event and its public presentation.",
    fieldKeys: [
      "title",
      "short_description",
      "description_html",
      "event_type",
      "featured_media_id",
    ],
  },
  {
    id: "schedule",
    title: "Schedule and location",
    description: "Set dates, times, venue, online access, and programme items.",
    fieldKeys: [
      "start_date",
      "end_date",
      "start_time",
      "end_time",
      "timezone",
      "venue",
      "address",
      "location_url",
      "is_online",
      "online_platform",
      "online_link",
      "access_code",
      "schedule",
    ],
  },
  {
    id: "registration",
    title: "Registration",
    description: "Configure attendance, deadlines, capacity, and CPD credit.",
    fieldKeys: [
      "registration_required",
      "registration_url",
      "registration_deadline",
      "max_participants",
      "expected_participants",
      "cpd_credits",
    ],
  },
  {
    id: "people-media",
    title: "People and media",
    description: "Add organizers, speakers, photos, and supporting files.",
    fieldKeys: [
      "organizer",
      "speakers",
      "photos_url",
      "supplementary_media_ids",
    ],
  },
  {
    id: "publishing",
    title: "Publishing",
    description: "Set the event state and public publication status.",
    fieldKeys: ["status", "publication_status", "published_at"],
  },
  reviewStep("Review event"),
];

const documentSteps: WorkspaceWizardStep[] = [
  {
    id: "details",
    title: "Document details",
    description: "Describe and classify the association record.",
    fieldKeys: [
      "title",
      "category",
      "sender",
      "receiver",
      "document_date",
      "description_html",
    ],
  },
  {
    id: "files",
    title: "Files",
    description: "Attach the scanned files that make up the first revision.",
    fieldKeys: ["media_asset_ids", "change_note"],
  },
  {
    id: "access",
    title: "Visibility and retention",
    description: "Choose the audience and records-management controls.",
    fieldKeys: ["audiences", "retention_class", "legal_hold"],
  },
  {
    id: "publishing",
    title: "Publishing",
    description: "Choose the document workflow state.",
    fieldKeys: ["status"],
  },
  reviewStep("Review document"),
];

const mediaCreateSteps: WorkspaceWizardStep[] = [
  {
    id: "upload",
    title: "Upload files",
    description:
      "Choose files and wait for upload and security checks to finish.",
    fieldKeys: ["upload"],
  },
  reviewStep("Finish upload"),
];

const mediaEditSteps: WorkspaceWizardStep[] = [
  {
    id: "accessibility",
    title: "Accessibility and credit",
    description: "Describe the asset and record its source.",
    fieldKeys: ["alt_text", "caption", "credit"],
  },
  {
    id: "privacy",
    title: "Privacy",
    description: "Choose whether the asset can be used publicly.",
    fieldKeys: ["is_private"],
  },
  reviewStep("Review media details"),
];

const gallerySteps: WorkspaceWizardStep[] = [
  {
    id: "story",
    title: "Gallery story",
    description: "Give the collection a title and a short public introduction.",
    fieldKeys: ["title", "description"],
  },
  {
    id: "images",
    title: "Images and downloads",
    description:
      "Choose the photographs and decide which originals visitors may download.",
    fieldKeys: ["media_asset_ids", "blocked_download_media_ids"],
  },
  {
    id: "publishing",
    title: "Publishing",
    description: "Set the workflow state and optional external album.",
    fieldKeys: ["status", "external_album_url"],
  },
  reviewStep("Review gallery"),
];

const carouselSteps: WorkspaceWizardStep[] = [
  {
    id: "copy",
    title: "Slide message",
    description: "Write the homepage headline and supporting text.",
    fieldKeys: ["title", "description"],
  },
  {
    id: "image",
    title: "Image and link",
    description: "Choose the hero image and optional destination.",
    fieldKeys: ["media_asset_id", "link_url"],
  },
  {
    id: "display",
    title: "Display",
    description: "Set the ordering and publication state.",
    fieldKeys: ["order", "is_published"],
  },
  reviewStep("Review homepage slide"),
];

const campaignSteps: WorkspaceWizardStep[] = [
  {
    id: "creative",
    title: "Creative and placement",
    description: "Name the campaign and choose where and how it appears.",
    fieldKeys: ["title", "slot_id", "media_asset_id", "target_url"],
  },
  {
    id: "schedule",
    title: "Schedule and priority",
    description: "Set campaign timing and display priority.",
    fieldKeys: ["starts_at", "ends_at", "priority"],
  },
  {
    id: "status",
    title: "Fulfilment and status",
    description: "Identify house promotions and choose the operating state.",
    fieldKeys: ["is_house_ad", "status"],
  },
  reviewStep("Review campaign"),
];

const orderSteps: WorkspaceWizardStep[] = [
  {
    id: "commercial",
    title: "Client and plan",
    description: "Choose the advertiser and purchased rate-card plan.",
    fieldKeys: ["advertiser_id", "plan_id"],
  },
  {
    id: "campaign",
    title: "Campaign and dates",
    description: "Link the campaign and set the delivery period.",
    fieldKeys: ["campaign_id", "starts_on", "ends_on"],
  },
  {
    id: "payment",
    title: "Payment and status",
    description: "Record fulfilment, payment, and internal notes.",
    fieldKeys: ["status", "payment_status", "notes"],
  },
  reviewStep("Review order"),
];

export const workspacePresentations: Record<string, WorkspacePresentation> = {
  members: {
    listVariant: "table",
    listHref: "/dashboard/members",
    detailEndpoint: (id) => `/api/v1/members/${id}`,
    detailHref: (row) => `/dashboard/members/${row.id}`,
    editHref: (row) => `/dashboard/members/${row.id}/edit`,
    createHref: "/dashboard/members/new",
    fullPage: true,
    createSteps: memberSteps,
    editSteps: memberSteps,
    recoverableFields: [
      "title",
      "other_name",
      "surname",
      "gender",
      "academic_rank",
      "college_id",
      "school_id",
      "department_id",
      "roles",
    ],
    detailSections: [
      { id: "contact", title: "Contact", fieldKeys: ["email", "phone_number"] },
      {
        id: "association",
        title: "Association profile",
        fieldKeys: ["academic_rank", "title", "gender", "staff_id"],
      },
      {
        id: "organization",
        title: "Organization",
        fieldKeys: ["college_name", "school_name", "department_name"],
      },
      {
        id: "access",
        title: "Account access",
        fieldKeys: [
          "status",
          "roles",
          "email_verified",
          "created_at",
          "last_login_at",
        ],
      },
    ],
  },
  executives: {
    listVariant: "table",
    listHref: "/dashboard/executives",
    detailEndpoint: (id) => `/api/v1/executives/${id}`,
    detailHref: (row) => `/dashboard/executives/${row.id}`,
    editHref: (row) => `/dashboard/executives/${row.id}/edit`,
    createHref: "/dashboard/executives/new",
    fullPage: true,
    createSteps: executiveSteps,
    editSteps: executiveSteps,
    recoverableFields: [
      "position",
      "portfolio",
      "summary",
      "biography_html",
      "social_links",
      "appointed_on",
      "ended_on",
      "term_number",
      "is_acting",
      "is_active",
      "is_public",
      "show_email",
      "show_phone",
    ],
    detailSections: [
      {
        id: "office",
        title: "Leadership office",
        fieldKeys: [
          "position",
          "portfolio",
          "term_number",
          "appointed_on",
          "ended_on",
        ],
      },
      {
        id: "profile",
        title: "Public profile",
        fieldKeys: ["summary", "biography_html", "social_links"],
      },
      {
        id: "visibility",
        title: "Visibility",
        fieldKeys: [
          "is_active",
          "is_acting",
          "is_public",
          "show_email",
          "show_phone",
        ],
      },
    ],
  },
  news: {
    listVariant: "cards",
    listHref: "/dashboard/news",
    detailEndpoint: (id) => `/api/v1/content/articles/${id}`,
    detailHref: (row) => `/dashboard/news/${row.id}`,
    editHref: (row) => `/dashboard/news/${row.id}/edit`,
    createHref: "/dashboard/news/new",
    fullPage: true,
    createSteps: articleSteps,
    editSteps: articleSteps,
    recoverableFields: [
      "title",
      "excerpt",
      "content_html",
      "tags",
      "citations",
      "status",
    ],
    detailSections: [
      { id: "story", title: "Story", fieldKeys: ["excerpt", "content_html"] },
      {
        id: "publishing",
        title: "Publishing",
        fieldKeys: [
          "status",
          "published_at",
          "is_featured",
          "tags",
          "updated_at",
        ],
      },
      {
        id: "sources",
        title: "Sources and attachments",
        fieldKeys: ["citations", "attachments"],
      },
    ],
  },
  announcements: {
    listVariant: "cards",
    listHref: "/dashboard/announcements",
    detailEndpoint: (id) => `/api/v1/content/announcements/${id}`,
    detailHref: (row) => `/dashboard/announcements/${row.id}`,
    editHref: (row) => `/dashboard/announcements/${row.id}/edit`,
    createHref: "/dashboard/announcements/new",
    fullPage: true,
    createSteps: announcementSteps,
    editSteps: announcementSteps,
    recoverableFields: [
      "title",
      "content_html",
      "priority",
      "audiences",
      "status",
      "published_at",
      "expires_at",
    ],
    detailSections: [
      { id: "message", title: "Message", fieldKeys: ["content_html"] },
      {
        id: "delivery",
        title: "Delivery",
        fieldKeys: [
          "audiences",
          "priority",
          "status",
          "published_at",
          "expires_at",
        ],
      },
    ],
  },
  events: {
    listVariant: "cards",
    listHref: "/dashboard/events",
    detailEndpoint: (id) => `/api/v1/events/${id}`,
    detailHref: (row) => `/dashboard/events/${row.id}`,
    editHref: (row) => `/dashboard/events/${row.id}/edit`,
    createHref: "/dashboard/events/new",
    fullPage: true,
    createSteps: eventSteps,
    editSteps: eventSteps,
    recoverableFields: [
      "title",
      "short_description",
      "description_html",
      "event_type",
      "start_date",
      "end_date",
      "start_time",
      "end_time",
      "timezone",
      "venue",
      "address",
      "location_url",
      "is_online",
      "registration_required",
      "registration_deadline",
      "max_participants",
      "expected_participants",
      "cpd_credits",
      "organizer",
      "speakers",
      "schedule",
      "status",
      "publication_status",
      "published_at",
    ],
    detailSections: [
      {
        id: "overview",
        title: "About this event",
        fieldKeys: ["short_description", "description_html"],
      },
      {
        id: "schedule",
        title: "Schedule and venue",
        fieldKeys: [
          "when",
          "venue",
          "address",
          "is_online",
          "online_platform",
          "schedule",
        ],
      },
      {
        id: "registration",
        title: "Registration",
        fieldKeys: [
          "registration_required",
          "registered",
          "registrations",
          "registration_deadline",
          "max_participants",
          "expected_participants",
          "cpd_credits",
        ],
      },
      { id: "people", title: "People", fieldKeys: ["organizer", "speakers"] },
      {
        id: "publishing",
        title: "Publishing",
        fieldKeys: [
          "event_type",
          "status",
          "publication_status",
          "published_at",
        ],
      },
    ],
  },
  documents: {
    listVariant: "table",
    listHref: "/dashboard/documents",
    detailEndpoint: (id) => `/api/v1/documents/${id}`,
    viewHref: (row) => `/dashboard/documents/${row.id}/preview`,
    listViewReplacesActionLabel: "Preview",
    detailHref: (row) => `/dashboard/documents/${row.id}`,
    editHref: (row) => `/dashboard/documents/${row.id}/edit`,
    createHref: "/dashboard/documents/new",
    fullPage: true,
    createSteps: documentSteps,
    editSteps: documentSteps,
    recoverableFields: [
      "title",
      "category",
      "sender",
      "receiver",
      "description_html",
      "document_date",
      "audiences",
      "retention_class",
      "legal_hold",
      "status",
      "change_note",
    ],
    detailSections: [
      {
        id: "record",
        title: "Record summary",
        fieldKeys: [
          "public_id",
          "description_html",
          "document_date",
          "sender",
          "receiver",
        ],
      },
      {
        id: "access",
        title: "Access and retention",
        fieldKeys: [
          "category",
          "status",
          "audiences",
          "retention_class",
          "legal_hold",
        ],
      },
      {
        id: "history",
        title: "Files and revisions",
        fieldKeys: ["version", "updated_at"],
      },
    ],
  },
  media: {
    listVariant: "media",
    listHref: "/dashboard/media",
    detailEndpoint: (id) => `/api/v1/media/${id}`,
    detailHref: (row) => `/dashboard/media/${row.id}`,
    editHref: (row) => `/dashboard/media/${row.id}/edit`,
    createHref: "/dashboard/media/new",
    fullPage: true,
    createSteps: mediaCreateSteps,
    editSteps: mediaEditSteps,
    recoverableFields: ["alt_text", "caption", "credit", "is_private"],
    detailSections: [
      {
        id: "description",
        title: "Description and credit",
        fieldKeys: ["alt_text", "caption", "credit"],
      },
      {
        id: "availability",
        title: "Availability",
        fieldKeys: [
          "status",
          "is_private",
          "content_type",
          "byte_size",
          "created_at",
          "scan_status",
          "scan_result",
          "usage_count",
        ],
      },
    ],
  },
  galleries: {
    listVariant: "cards",
    listHref: "/dashboard/galleries",
    detailEndpoint: (id) => `/api/v1/galleries/${id}`,
    detailHref: (row) => `/dashboard/galleries/${row.id}`,
    editHref: (row) => `/dashboard/galleries/${row.id}/edit`,
    createHref: "/dashboard/galleries/new",
    fullPage: true,
    createSteps: gallerySteps,
    editSteps: gallerySteps,
    recoverableFields: ["title", "description", "status", "external_album_url"],
    detailSections: [],
  },
  carousel: {
    listVariant: "cards",
    listHref: "/dashboard/carousel",
    detailEndpoint: (id) => `/api/v1/admin/carousel/${id}`,
    detailHref: (row) => `/dashboard/carousel/${row.id}`,
    editHref: (row) => `/dashboard/carousel/${row.id}/edit`,
    createHref: "/dashboard/carousel/new",
    fullPage: true,
    createSteps: carouselSteps,
    editSteps: carouselSteps,
    recoverableFields: [
      "title",
      "description",
      "link_url",
      "order",
      "is_published",
    ],
    detailSections: [
      { id: "message", title: "Homepage message", fieldKeys: ["description"] },
      {
        id: "destination",
        title: "Destination and display",
        fieldKeys: ["link_url", "order", "is_published"],
      },
    ],
  },
  adverts: {
    listVariant: "table",
    listHref: "/dashboard/adverts",
    detailEndpoint: (id) => `/api/v1/adverts/campaigns/${id}`,
    detailHref: (row) => `/dashboard/adverts/${row.id}`,
    editHref: (row) => `/dashboard/adverts/${row.id}/edit`,
    createHref: "/dashboard/adverts/new",
    fullPage: true,
    createSteps: campaignSteps,
    editSteps: campaignSteps,
    recoverableFields: [
      "title",
      "target_url",
      "is_house_ad",
      "status",
      "priority",
      "starts_at",
      "ends_at",
    ],
    detailSections: [
      {
        id: "delivery",
        title: "Campaign delivery",
        fieldKeys: [
          "placement_name",
          "advertiser_name",
          "fulfilment",
          "status",
          "starts_at",
          "ends_at",
        ],
      },
      {
        id: "performance",
        title: "Performance",
        fieldKeys: ["impressions", "clicks"],
      },
      {
        id: "destination",
        title: "Destination",
        fieldKeys: ["is_house_ad", "target_url"],
      },
    ],
  },
  "advert-orders": {
    listVariant: "table",
    listHref: "/dashboard/adverts?tab=orders",
    detailEndpoint: (id) => `/api/v1/adverts/orders/${id}`,
    detailHref: (row) => `/dashboard/advert-orders/${row.id}`,
    editHref: (row) => `/dashboard/advert-orders/${row.id}/edit`,
    createHref: "/dashboard/advert-orders/new",
    fullPage: true,
    createSteps: orderSteps,
    editSteps: orderSteps,
    recoverableFields: [
      "starts_on",
      "ends_on",
      "status",
      "payment_status",
      "notes",
    ],
    detailSections: [
      {
        id: "commercial",
        title: "Commercial details",
        fieldKeys: ["advertiser_name", "plan_name", "campaign_name"],
      },
      {
        id: "delivery",
        title: "Delivery",
        fieldKeys: ["starts_on", "ends_on", "status", "payment_status"],
      },
      {
        id: "notes",
        title: "Notes",
        fieldKeys: ["notes", "price", "created_at"],
      },
    ],
  },
  organization: {
    listVariant: "table",
    listHref: "/dashboard/organization",
    detailSections: [
      {
        id: "hierarchy",
        title: "Organization hierarchy",
        fieldKeys: [
          "unit_type",
          "parent_name",
          "code",
          "member_count",
          "is_active",
        ],
      },
    ],
  },
  "advert-slots": {
    listVariant: "table",
    listHref: "/dashboard/adverts?tab=placements",
    detailSections: [
      {
        id: "placement",
        title: "Placement",
        fieldKeys: ["location", "size", "description", "is_active"],
      },
    ],
  },
  "advert-plans": {
    listVariant: "table",
    listHref: "/dashboard/adverts?tab=plans",
    detailSections: [
      {
        id: "plan",
        title: "Rate-card plan",
        fieldKeys: [
          "placement_name",
          "price",
          "duration_days",
          "description",
          "is_active",
        ],
      },
    ],
  },
  "advert-advertisers": {
    listVariant: "table",
    listHref: "/dashboard/adverts?tab=clients",
    detailSections: [
      {
        id: "contact",
        title: "Client contact",
        fieldKeys: [
          "contact_name",
          "email",
          "phone",
          "website",
          "notes",
          "is_active",
          "created_at",
        ],
      },
    ],
  },
  analytics: {
    listVariant: "analytics",
    listHref: "/dashboard/analytics",
    detailSections: [],
  },
  audit: {
    listVariant: "table",
    listHref: "/dashboard/audit",
    detailSections: [
      {
        id: "activity",
        title: "Activity",
        fieldKeys: [
          "actor_name",
          "resource_type",
          "outcome",
          "created_at",
          "reason",
          "changes",
        ],
      },
    ],
  },
  settings: {
    listVariant: "settings",
    listHref: "/dashboard/settings",
    detailSections: [
      {
        id: "setting",
        title: "Portal setting",
        fieldKeys: ["description", "is_public"],
      },
    ],
  },
  "feature-flags": {
    listVariant: "settings",
    listHref: "/dashboard/feature-flags",
    detailSections: [
      {
        id: "feature",
        title: "Portal capability",
        fieldKeys: ["description", "enabled"],
      },
    ],
  },
  jobs: {
    listVariant: "timeline",
    listHref: "/dashboard/jobs",
    detailSections: [
      {
        id: "progress",
        title: "Job progress",
        fieldKeys: [
          "status",
          "progress",
          "created_at",
          "updated_at",
          "error_message",
        ],
      },
    ],
  },
};

export function workspacePresentationFor(config: WorkspaceConfig) {
  return config.key ? workspacePresentations[config.key] : undefined;
}

export function routedWorkspace(section: string) {
  const configKey = section === "content" ? "news" : section;
  const presentation = workspacePresentations[configKey];
  if (!presentation?.fullPage) return null;
  return { configKey, presentation };
}

const COLLECTION_LABELS: Record<string, string> = {
  Article: "articles",
  Announcement: "announcements",
  Appointment: "appointments",
  "Audit entry": "audit entries",
  Campaign: "campaigns",
  Client: "clients",
  Document: "documents",
  Event: "events",
  Executive: "executives",
  Feature: "features",
  File: "files",
  Gallery: "galleries",
  Job: "jobs",
  Member: "members",
  Metric: "metrics",
  Order: "orders",
  Placement: "placements",
  Plan: "plans",
  Setting: "settings",
  Slide: "slides",
  Unit: "units",
};

export function collectionLabel(noun?: string) {
  if (!noun) return "items";
  if (COLLECTION_LABELS[noun]) return COLLECTION_LABELS[noun];
  const lower = noun.toLowerCase();
  return lower.endsWith("s") ? lower : `${lower}s`;
}

export function wizardStepIndexForField(
  steps: WorkspaceWizardStep[],
  fieldKey: string,
) {
  return steps.findIndex((step) => step.fieldKeys.includes(fieldKey));
}
