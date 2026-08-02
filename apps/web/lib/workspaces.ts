import { documentAudiencesForCategory } from "./workspace-options";

export type WorkspaceRow = Record<string, unknown>;
export type WorkspaceFieldType =
  | "text"
  | "email"
  | "url"
  | "date"
  | "time"
  | "datetime-local"
  | "textarea"
  | "richtext"
  | "select"
  | "number"
  | "checkbox"
  | "json"
  | "list"
  | "multiselect"
  | "media";

export type WorkspaceStructuredField = {
  key: string;
  label: string;
  placeholder?: string;
  type?: "text" | "email" | "url" | "date" | "time" | "textarea";
};

export type WorkspaceField = {
  key: string;
  label: string;
  type?: WorkspaceFieldType;
  required?: boolean;
  checkboxLabel?: string;
  permission?: string;
  options?: string[];
  optionsFor?: (permissions: string[]) => string[];
  optionsForValues?: (values: WorkspaceRow) => string[];
  optionSource?: {
    endpoint: string;
    queryKey: string;
    searchParam?: string;
    value: (row: WorkspaceRow) => string;
    label: (row: WorkspaceRow) => string;
    filter?: (row: WorkspaceRow) => boolean;
    emptyLabel?: string;
  };
  placeholder?: string;
  help?: string;
  prominent?: boolean;
  media?: {
    accept: "image" | "document" | "any";
    multiple?: boolean;
    isPrivate?: boolean;
    aspect?: "portrait" | "landscape" | "square";
    /** When true, each selected image can toggle public download permission. */
    downloadControl?: boolean;
  };
  defaultValue?: string | number | boolean | string[];
  createOnly?: boolean;
  editOnly?: boolean;
  emptyValue?: unknown;
  valueFromRow?: (row: WorkspaceRow) => unknown;
  structuredFields?: WorkspaceStructuredField[];
  structuredItemFields?: WorkspaceStructuredField[];
  addItemLabel?: string;
  /** Include in the save payload without rendering a visible control. */
  hidden?: boolean;
};

export type WorkspaceMutation = {
  label: string;
  submitLabel?: string;
  permission: string;
  endpoint: string | ((row: WorkspaceRow) => string);
  method?: "POST" | "PUT" | "PATCH" | "DELETE";
  fields?: WorkspaceField[];
  successMessage: string;
  confirm?: string;
  danger?: boolean;
  excludeSelf?: boolean;
  open?: boolean;
  href?: (row: WorkspaceRow) => string;
  when?: (row: WorkspaceRow, permissions: string[]) => boolean;
  prepare?: (payload: WorkspaceRow, row?: WorkspaceRow) => WorkspaceRow;
  headers?: (row: WorkspaceRow) => HeadersInit;
};

export type WorkspaceConfig = {
  title: string;
  description: string;
  endpoint: string;
  queryKey: string;
  columns: { key: string; label: string }[];
  exportUrl?: string;
  exportPermission?: string;
  filters?: { key: string; label: string; options: string[] }[];
  serverPagination?: {
    searchParam?: string;
    filterParams?: Record<string, string>;
  };
  create?: WorkspaceMutation;
  update?: WorkspaceMutation;
  archive?: WorkspaceMutation;
  actions?: WorkspaceMutation[];
};

export function workspaceDetailFields(config: WorkspaceConfig) {
  const fields = [
    ...(config.create?.fields ?? []),
    ...(config.update?.fields ?? []),
    ...(config.actions ?? []).flatMap((action) => action.fields ?? []),
  ];

  return new Map(fields.map((field) => [field.key, field]));
}

export function workspaceRowFromMutationResult(result: unknown) {
  return result && typeof result === "object" && !Array.isArray(result)
    ? (result as WorkspaceRow)
    : null;
}

export function workspaceFilterMatches(value: unknown, expected: string) {
  const normalized = expected.toLowerCase();
  return Array.isArray(value)
    ? value.some((item) => String(item).toLowerCase() === normalized)
    : String(value).toLowerCase() === normalized;
}

const memberFields: WorkspaceField[] = [
  {
    key: "email",
    label: "Email",
    type: "email",
    required: true,
    createOnly: true,
  },
  { key: "staff_id", label: "Staff ID" },
  {
    key: "title",
    label: "Title",
    type: "select",
    options: [
      "Prof.",
      "Prof. (Mrs.)",
      "Dr.",
      "Dr. (Mrs.)",
      "Dr. (Miss)",
      "Dr. (Alhaji)",
      "Mr.",
      "Mrs.",
      "Miss",
      "Ms.",
      "Mx.",
      "Rev.",
      "Hon.",
      "Eng.",
      "Sir",
      "Dame",
    ],
  },
  { key: "other_name", label: "Other names", required: true },
  { key: "surname", label: "Surname", required: true },
  {
    key: "gender",
    label: "Gender",
    type: "select",
    options: ["Male", "Female"],
  },
  {
    key: "academic_rank",
    label: "Academic rank",
    type: "select",
    options: [
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
    ],
  },
  { key: "phone_number", label: "Phone number" },
  {
    key: "college_id",
    label: "College",
    type: "select",
    optionSource: {
      endpoint: "/api/v1/organization/units?unit_type=college",
      queryKey: "organization-colleges",
      value: (row) => String(row.id),
      label: (row) => String(row.name),
    },
  },
  {
    key: "school_id",
    label: "School",
    type: "select",
    optionSource: {
      endpoint: "/api/v1/organization/units?unit_type=school",
      queryKey: "organization-schools",
      value: (row) => String(row.id),
      label: (row) => String(row.name),
    },
  },
  {
    key: "department_id",
    label: "Department",
    type: "select",
    optionSource: {
      endpoint: "/api/v1/organization/units?unit_type=department",
      queryKey: "organization-departments",
      value: (row) => String(row.id),
      label: (row) => String(row.name),
    },
  },
  {
    key: "profile_media_id",
    label: "Profile photo",
    type: "media",
    media: {
      accept: "image",
      isPrivate: false,
      aspect: "portrait",
    },
    optionSource: {
      endpoint: "/api/v1/media?status=ready&page_size=100",
      queryKey: "ready-profile-images",
      searchParam: "q",
      value: (row) => String(row.id),
      label: (row) => String(row.original_filename),
      filter: (row) =>
        row.is_private === false &&
        String(row.content_type).startsWith("image/"),
      emptyLabel: "No ready public profile images",
    },
    help: "Optional for members. Upload here or reuse a ready public portrait.",
  },
  {
    key: "roles",
    label: "Roles",
    type: "multiselect",
    permission: "members.roles",
    options: [
      "member",
      "executive",
      "editor",
      "publisher",
      "secretary",
      "administrator",
    ],
    defaultValue: "member",
    help: "Choose every role this account should hold.",
  },
  {
    key: "send_invitation",
    label: "Account access",
    type: "checkbox",
    checkboxLabel: "Email an access invitation",
    defaultValue: true,
    createOnly: true,
    help: "The member account is created immediately. When enabled, an activation link is emailed to the member.",
  },
];

const executiveFields: WorkspaceField[] = [
  {
    key: "user_id",
    label: "Member",
    type: "select",
    required: true,
    optionSource: {
      endpoint: "/api/v1/members?status=active&page_size=100",
      queryKey: "active-members",
      searchParam: "q",
      value: (row) => String(row.id),
      label: (row) => `${String(row.full_name)} · ${String(row.email)}`,
      emptyLabel: "No active members available",
    },
  },
  {
    key: "profile_media_id",
    label: "Public profile photo",
    type: "media",
    required: true,
    media: {
      accept: "image",
      isPrivate: false,
      aspect: "portrait",
    },
    optionSource: {
      endpoint: "/api/v1/media?status=ready&page_size=100",
      queryKey: "ready-profile-images",
      searchParam: "q",
      value: (row) => String(row.id),
      label: (row) => String(row.original_filename),
      filter: (row) =>
        row.is_private === false &&
        String(row.content_type).startsWith("image/"),
      emptyLabel: "No ready public profile images",
    },
    help: "Required for public leadership cards and the executive detail modal.",
  },
  {
    key: "position",
    label: "Position",
    type: "select",
    required: true,
    options: [
      "President",
      "Vice President",
      "Secretary",
      "Assistant Secretary",
      "Treasurer",
      "Assistant Treasurer",
      "Organiser",
      "Women's Executive Officer",
      "Past President",
      "National President",
      "CBAS Rep",
      "CHS Rep",
      "COE Rep",
      "COH Rep",
      "College of Humanities Rep",
      "College of Health Rep",
      "College of Education Rep",
      "Executive Member",
      "Local Executive Council Member",
    ],
  },
  { key: "portfolio", label: "Portfolio" },
  { key: "summary", label: "Public summary", type: "textarea" },
  {
    key: "biography_html",
    label: "Biography",
    type: "richtext",
    emptyValue: "",
  },
  {
    key: "social_links",
    label: "Social links",
    type: "json",
    defaultValue: "{}",
    structuredFields: [
      {
        key: "linkedin",
        label: "LinkedIn profile",
        type: "url",
        placeholder: "https://www.linkedin.com/in/…",
      },
      {
        key: "x",
        label: "X / Twitter profile",
        type: "url",
        placeholder: "https://x.com/…",
      },
      {
        key: "website",
        label: "Personal website",
        type: "url",
        placeholder: "https://…",
      },
    ],
  },
  { key: "appointed_on", label: "Appointed on", type: "date" },
  { key: "ended_on", label: "Ended on", type: "date" },
  { key: "term_number", label: "Term number", type: "number", defaultValue: 1 },
  { key: "is_acting", label: "Acting appointment", type: "checkbox" },
  {
    key: "is_active",
    label: "Current appointment",
    type: "checkbox",
    defaultValue: true,
  },
  {
    key: "is_public",
    label: "Show publicly",
    type: "checkbox",
    defaultValue: true,
  },
  {
    key: "show_email",
    label: "Show member email on the public profile",
    type: "checkbox",
    defaultValue: false,
    help: "Enable only after the office-holder has consented to publishing their email address.",
  },
  {
    key: "show_phone",
    label: "Show member phone on the public profile",
    type: "checkbox",
    defaultValue: false,
    help: "Enable only after the office-holder has consented to publishing their phone number.",
  },
];

const editorialFields: WorkspaceField[] = [
  {
    key: "title",
    label: "Title",
    required: true,
    prominent: true,
    placeholder: "Enter the article headline",
  },
  { key: "excerpt", label: "Excerpt", type: "textarea", emptyValue: "" },
  {
    key: "content_html",
    label: "Article body",
    type: "richtext",
    emptyValue: "",
  },
  {
    key: "featured_media_id",
    label: "Featured image",
    type: "media",
    media: {
      accept: "image",
      isPrivate: false,
      aspect: "landscape",
    },
    optionSource: {
      endpoint: "/api/v1/media?status=ready&page_size=100",
      queryKey: "ready-public-images",
      searchParam: "q",
      value: (row) => String(row.id),
      label: (row) => String(row.original_filename),
      filter: (row) =>
        row.is_private === false &&
        String(row.content_type).startsWith("image/"),
      emptyLabel: "No ready public images",
    },
  },
  { key: "is_featured", label: "Feature this article", type: "checkbox" },
  { key: "tags", label: "Tags", type: "list", emptyValue: [] },
  {
    key: "citations",
    label: "Citations",
    type: "json",
    defaultValue: "[]",
    addItemLabel: "Add citation",
    structuredItemFields: [
      {
        key: "source_name",
        label: "Source name",
        placeholder: "Publication or organization",
      },
      {
        key: "url",
        label: "Source URL",
        type: "url",
        placeholder: "https://…",
      },
      {
        key: "description",
        label: "Description",
        type: "textarea",
        placeholder: "What this source supports",
      },
    ],
  },
  {
    key: "attachment_media_ids",
    label: "Attached documents",
    type: "media",
    media: {
      accept: "document",
      multiple: true,
      isPrivate: false,
    },
    optionSource: {
      endpoint: "/api/v1/media?status=ready&page_size=100",
      queryKey: "ready-public-article-attachments",
      searchParam: "q",
      value: (row) => String(row.id),
      label: (row) =>
        `${String(row.original_filename)} · ${String(row.content_type)}`,
      filter: (row) =>
        row.is_private === false &&
        !String(row.content_type).startsWith("image/"),
      emptyLabel: "No ready public documents",
    },
    valueFromRow: (row) =>
      Array.isArray(row.attachments)
        ? row.attachments.map((item) =>
            String((item as WorkspaceRow).media_asset_id),
          )
        : [],
    help: "Public, security-scanned supporting files shown with the article.",
  },
  {
    key: "status",
    label: "Workflow status",
    type: "select",
    defaultValue: "draft",
    optionsFor: (permissions) =>
      permissions.includes("content.publish")
        ? ["draft", "review", "scheduled", "published"]
        : ["draft", "review"],
  },
  { key: "published_at", label: "Publish at", type: "datetime-local" },
];

const announcementFields: WorkspaceField[] = [
  {
    key: "title",
    label: "Title",
    required: true,
    prominent: true,
    placeholder: "Enter the announcement title",
  },
  { key: "content_html", label: "Message", type: "richtext", required: true },
  {
    key: "priority",
    label: "Priority",
    type: "select",
    defaultValue: "normal",
    options: ["low", "normal", "high", "urgent"],
  },
  {
    key: "audiences",
    label: "Audience",
    type: "multiselect",
    options: [
      "general_public",
      "all_members",
      "member",
      "executive",
      "editor",
      "publisher",
      "secretary",
      "administrator",
    ],
    defaultValue: ["everyone"],
    valueFromRow: (row) =>
      Array.isArray(row.audiences)
        ? row.audiences.flatMap((rule) => {
            if (!rule || typeof rule !== "object") return [];
            const item = rule as WorkspaceRow;
            return item.type === "everyone" || item.type === "all_members"
              ? ["everyone"]
              : item.type === "role" && item.value
                ? [String(item.value)]
                : [];
          })
        : [],
    help: "Publishing sends one inbox notification to every active member in the selected audience. Everyone overrides role selections.",
  },
  {
    key: "status",
    label: "Workflow status",
    type: "select",
    defaultValue: "draft",
    optionsFor: (permissions) =>
      permissions.includes("content.publish")
        ? ["draft", "review", "scheduled", "published"]
        : ["draft", "review"],
  },
  { key: "published_at", label: "Publish at", type: "datetime-local" },
  { key: "expires_at", label: "Expires at", type: "datetime-local" },
];

const eventFields: WorkspaceField[] = [
  {
    key: "title",
    label: "Event title",
    required: true,
    prominent: true,
    placeholder: "Enter the event title",
  },
  {
    key: "short_description",
    label: "Short description",
    type: "textarea",
    emptyValue: "",
  },
  {
    key: "description_html",
    label: "Full description",
    type: "richtext",
    emptyValue: "",
  },
  {
    key: "featured_media_id",
    label: "Featured image",
    type: "media",
    media: {
      accept: "image",
      isPrivate: false,
      aspect: "landscape",
    },
    optionSource: {
      endpoint: "/api/v1/media?status=ready&page_size=100",
      queryKey: "ready-public-images",
      searchParam: "q",
      value: (row) => String(row.id),
      label: (row) => String(row.original_filename),
      filter: (row) =>
        row.is_private === false &&
        String(row.content_type).startsWith("image/"),
      emptyLabel: "No ready public images",
    },
  },
  { key: "start_date", label: "Start date", type: "date", required: true },
  { key: "end_date", label: "End date", type: "date" },
  { key: "start_time", label: "Start time", type: "time" },
  { key: "end_time", label: "End time", type: "time" },
  {
    key: "timezone",
    label: "Timezone",
    defaultValue: "Africa/Accra",
    required: true,
  },
  {
    key: "event_type",
    label: "Type",
    type: "select",
    defaultValue: "meeting",
    options: [
      "meeting",
      "conference",
      "workshop",
      "seminar",
      "lecture",
      "forum",
      "social",
      "online",
      "other",
    ],
  },
  {
    key: "status",
    label: "Event status",
    type: "select",
    defaultValue: "upcoming",
    options: ["upcoming", "ongoing", "completed", "cancelled", "postponed"],
  },
  {
    key: "publication_status",
    label: "Publication",
    type: "select",
    defaultValue: "draft",
    options: ["draft", "review", "scheduled", "published"],
  },
  { key: "published_at", label: "Publish at", type: "datetime-local" },
  { key: "venue", label: "Venue" },
  { key: "address", label: "Address", type: "textarea" },
  { key: "location_url", label: "Map URL" },
  { key: "photos_url", label: "Event photos link", type: "url" },
  { key: "is_online", label: "Online event", type: "checkbox" },
  { key: "online_platform", label: "Online platform" },
  { key: "online_link", label: "Protected online link" },
  { key: "access_code", label: "Protected access code" },
  {
    key: "registration_required",
    label: "Registration required",
    type: "checkbox",
  },
  {
    key: "registration_url",
    label: "External registration link",
    type: "url",
    help: "Public visitors register through this external page instead of signing in.",
  },
  {
    key: "registration_deadline",
    label: "Registration deadline",
    type: "datetime-local",
  },
  { key: "max_participants", label: "Maximum participants", type: "number" },
  {
    key: "expected_participants",
    label: "Expected participants",
    type: "number",
  },
  { key: "cpd_credits", label: "CPD credits", type: "number", defaultValue: 0 },
  {
    key: "organizer",
    label: "Organizer details",
    type: "json",
    defaultValue: "{}",
    structuredFields: [
      {
        key: "name",
        label: "Organizer name",
        placeholder: "Unit or contact person",
      },
      { key: "email", label: "Organizer email", type: "email" },
      { key: "phone", label: "Organizer phone" },
    ],
  },
  {
    key: "speakers",
    label: "Speakers",
    type: "json",
    defaultValue: "[]",
    addItemLabel: "Add speaker",
    structuredItemFields: [
      { key: "name", label: "Speaker name" },
      { key: "title", label: "Title or role" },
      {
        key: "bio",
        label: "Short biography",
        type: "textarea",
        placeholder: "Add a concise speaker biography",
      },
      { key: "presentation_title", label: "Presentation title" },
    ],
  },
  {
    key: "schedule",
    label: "Schedule",
    type: "json",
    defaultValue: "[]",
    addItemLabel: "Add schedule item",
    structuredItemFields: [
      { key: "date", label: "Date", type: "date" },
      { key: "start_time", label: "Start time", type: "time" },
      { key: "end_time", label: "End time", type: "time" },
      { key: "title", label: "Session title" },
      { key: "location", label: "Location" },
      {
        key: "description",
        label: "Description",
        type: "textarea",
        placeholder: "Add session details",
      },
    ],
  },
  {
    key: "supplementary_media_ids",
    label: "Supporting images and documents",
    type: "media",
    media: {
      accept: "any",
      multiple: true,
      isPrivate: false,
    },
    optionSource: {
      endpoint: "/api/v1/media?status=ready&page_size=100",
      queryKey: "ready-public-event-attachments",
      searchParam: "q",
      value: (row) => String(row.id),
      label: (row) =>
        `${String(row.original_filename)} · ${String(row.content_type)}`,
      filter: (row) => row.is_private === false,
      emptyLabel: "No ready public files",
    },
    valueFromRow: (row) =>
      Array.isArray(row.attachments)
        ? row.attachments.map((item) =>
            String((item as WorkspaceRow).media_asset_id),
          )
        : [],
    help: "Add every public image or document that belongs with this event.",
  },
];

const documentAudienceOptions = [
  "general_public",
  "all_members",
  "member",
  "executive",
  "editor",
  "publisher",
  "secretary",
  "administrator",
];

const documentFields: WorkspaceField[] = [
  {
    key: "title",
    label: "Document title",
    required: true,
    prominent: true,
    placeholder: "Enter the document title",
  },
  {
    key: "category",
    label: "Category",
    type: "select",
    defaultValue: "internal",
    options: ["internal", "external"],
  },
  { key: "sender", label: "Sender" },
  { key: "receiver", label: "Receiver" },
  {
    key: "description_html",
    label: "Description",
    type: "richtext",
    emptyValue: "",
  },
  { key: "document_date", label: "Document date", type: "date" },
  {
    key: "audiences",
    label: "Visible to",
    type: "multiselect",
    options: documentAudienceOptions,
    optionsForValues: (values) =>
      values.category === "external"
        ? documentAudienceOptions
        : documentAudienceOptions.filter(
            (option) => option !== "general_public",
          ),
    defaultValue: "member",
    valueFromRow: (row) =>
      Array.isArray(row.audiences)
        ? row.audiences.flatMap((rule) => {
            if (!rule || typeof rule !== "object") return [];
            const item = rule as WorkspaceRow;
            return item.type === "general_public"
              ? ["general_public"]
              : item.type === "everyone" || item.type === "all_members"
                ? ["all_members"]
                : item.type === "role" && item.value
                  ? [String(item.value)]
                  : [];
          })
        : [],
    help: "General Public publishes the approved document on the website. All Members and role choices remain protected behind member login.",
  },
  { key: "retention_class", label: "Retention class" },
  { key: "legal_hold", label: "Legal hold", type: "checkbox" },
  {
    key: "media_asset_ids",
    label: "Uploaded files",
    type: "media",
    required: true,
    createOnly: true,
    media: {
      accept: "any",
      multiple: true,
      isPrivate: true,
    },
    optionSource: {
      endpoint: "/api/v1/media?status=ready&page_size=100",
      queryKey: "ready-files",
      searchParam: "q",
      value: (row) => String(row.id),
      label: (row) =>
        `${String(row.original_filename)} · ${String(row.content_type)}`,
      emptyLabel: "No ready files",
    },
    help: "Choose one or more files that have completed security scanning.",
  },
  { key: "change_note", label: "Initial version note", createOnly: true },
  {
    key: "status",
    label: "Workflow status",
    type: "select",
    defaultValue: "draft",
    options: ["draft", "review", "published"],
  },
];

const campaignFields: WorkspaceField[] = [
  {
    key: "slot_id",
    label: "Placement",
    type: "select",
    required: true,
    optionSource: {
      endpoint: "/api/v1/adverts/slots",
      queryKey: "advert-slots",
      value: (row) => String(row.id),
      label: (row) =>
        `${String(row.name)} · ${String(row.width)}×${String(row.height)}`,
      filter: (row) => row.is_active === true,
      emptyLabel: "No active placements available",
    },
    help: "Key must match a public-site mount. Creative should match the placement size.",
  },
  {
    key: "title",
    label: "Campaign title",
    required: true,
    prominent: true,
    placeholder: "Enter the campaign title",
  },
  {
    key: "media_asset_id",
    label: "Creative",
    type: "media",
    media: {
      accept: "image",
      isPrivate: false,
      aspect: "landscape",
    },
    optionSource: {
      endpoint: "/api/v1/media?status=ready&page_size=100",
      queryKey: "ready-public-media",
      searchParam: "q",
      value: (row) => String(row.id),
      label: (row) => String(row.original_filename),
      filter: (row) =>
        row.is_private === false &&
        String(row.content_type).startsWith("image/"),
      emptyLabel: "No ready public images",
    },
    help: "Required before a campaign can be scheduled or activated.",
  },
  { key: "target_url", label: "Destination URL", type: "url" },
  {
    key: "is_house_ad",
    label: "House ad (UG UTAG own promotion)",
    type: "checkbox",
    defaultValue: false,
    help: "House ads can go live without an advertiser order. Paid inventory must stay unchecked and be linked from Orders.",
  },
  {
    key: "status",
    label: "Status",
    type: "select",
    defaultValue: "draft",
    options: ["draft", "scheduled", "active", "paused", "completed"],
    help: "Paid campaigns need a paid, approved/active order before scheduled or active.",
  },
  { key: "priority", label: "Priority", type: "number", defaultValue: 0 },
  { key: "starts_at", label: "Starts at", type: "datetime-local" },
  { key: "ends_at", label: "Ends at", type: "datetime-local" },
];

const articlePrepare = (payload: WorkspaceRow) => ({
  ...payload,
  content_json: {},
  excerpt: payload.excerpt ?? "",
  content_html: payload.content_html ?? "",
  tags: payload.tags ?? [],
  citations: payload.citations ?? [],
  is_featured: payload.is_featured ?? false,
});

const announcementPrepare = (payload: WorkspaceRow) => ({
  ...payload,
  content_json: {},
  content_html: payload.content_html ?? "",
  audiences: Array.isArray(payload.audiences)
    ? payload.audiences.map((audience) =>
        audience === "everyone"
          ? { type: "everyone", value: "all" }
          : { type: "role", value: audience },
      )
    : [],
});

const eventPrepare = (payload: WorkspaceRow) => ({
  ...payload,
  description_json: {},
  short_description: payload.short_description ?? "",
  description_html: payload.description_html ?? "",
  organizer: payload.organizer ?? {},
  speakers: payload.speakers ?? [],
  schedule: payload.schedule ?? [],
});

const documentPrepare = (payload: WorkspaceRow) => {
  const category = String(payload.category ?? "internal");
  const selectedAudiences = documentAudiencesForCategory(
    category,
    Array.isArray(payload.audiences) ? payload.audiences.map(String) : [],
  );
  return {
    ...payload,
    category,
    audiences: selectedAudiences.map((audience) =>
      audience === "general_public"
        ? { type: "general_public", value: "all" }
        : audience === "all_members"
          ? { type: "all_members", value: "all" }
          : { type: "role", value: audience },
    ),
  };
};

export const workspaces: Record<string, WorkspaceConfig> = {
  members: {
    title: "All members",
    description:
      "One account directory for members and administrators. Roles provide standard access; selected accounts can also receive audited extra permissions.",
    endpoint: "/api/v1/members?page_size=100",
    queryKey: "members",
    serverPagination: {
      searchParam: "q",
      filterParams: { status: "status", roles: "role" },
    },
    exportUrl: "/api/v1/members/exports/csv",
    exportPermission: "members.export",
    filters: [
      {
        key: "status",
        label: "Status",
        options: ["invited", "active", "suspended", "archived"],
      },
      {
        key: "roles",
        label: "Role",
        options: [
          "member",
          "executive",
          "editor",
          "publisher",
          "secretary",
          "administrator",
        ],
      },
    ],
    columns: [
      { key: "full_name", label: "Member" },
      { key: "email", label: "Email" },
      { key: "academic_rank", label: "Rank" },
      { key: "status", label: "Status" },
      { key: "roles", label: "Roles" },
    ],
    create: {
      label: "Create member",
      permission: "members.create",
      endpoint: "/api/v1/members",
      fields: memberFields,
      successMessage: "Member account created",
      prepare: (payload) => ({
        ...payload,
        roles:
          Array.isArray(payload.roles) && payload.roles.length
            ? payload.roles
            : ["member"],
        send_invitation: payload.send_invitation ?? true,
      }),
    },
    update: {
      label: "Edit member",
      permission: "members.update",
      endpoint: (row) => `/api/v1/members/${row.id}`,
      method: "PATCH",
      fields: memberFields,
      successMessage: "Member updated",
      when: (row, permissions) =>
        !Array.isArray(row.roles) ||
        !row.roles.includes("administrator") ||
        permissions.includes("members.roles"),
    },
    archive: {
      label: "Archive member",
      permission: "members.lifecycle",
      endpoint: (row) => `/api/v1/members/${row.id}`,
      method: "DELETE",
      successMessage: "Member archived",
      confirm:
        "Archive this member and revoke their active sessions? The record will be retained.",
      danger: true,
      excludeSelf: true,
      when: (row, permissions) =>
        row.status !== "archived" &&
        (!Array.isArray(row.roles) ||
          !row.roles.includes("administrator") ||
          permissions.includes("members.roles")),
    },
    actions: [
      {
        label: "Manage extra access",
        submitLabel: "Save extra access",
        permission: "members.permissions",
        endpoint: (row) => `/api/v1/members/${row.id}/permissions`,
        method: "PUT",
        fields: [
          {
            key: "extra_permissions",
            label: "Extra permissions",
            type: "multiselect",
            optionSource: {
              endpoint: "/api/v1/members/permission-options",
              queryKey: "member-permission-options",
              value: (row) => String(row.key),
              label: (row) => `${String(row.description)} · ${String(row.key)}`,
              emptyLabel: "No permissions are available",
            },
            help: "These are added to the permissions supplied by the member’s roles. Clearing this list does not remove role-based access.",
          },
        ],
        prepare: (payload) => ({
          permissions: Array.isArray(payload.extra_permissions)
            ? payload.extra_permissions
            : [],
        }),
        successMessage: "Extra permissions updated",
        when: (row) =>
          !Array.isArray(row.roles) || !row.roles.includes("administrator"),
      },
      {
        label: "Send access link",
        permission: "members.credentials",
        endpoint: (row) => `/api/v1/members/${row.id}/access-link`,
        successMessage: "Secure access email queued",
        confirm: "Send a new account access link to this member?",
        excludeSelf: true,
        when: (row, permissions) =>
          row.status !== "suspended" &&
          row.status !== "archived" &&
          (!Array.isArray(row.roles) ||
            !row.roles.includes("administrator") ||
            permissions.includes("members.roles")),
      },
      {
        label: "Reset password",
        permission: "members.credentials",
        endpoint: (row) => `/api/v1/members/${row.id}/password-reset`,
        successMessage: "Password reset link sent and active sessions revoked",
        confirm:
          "Require this member to choose a new password? Their current password and active sessions will stop working immediately.",
        danger: true,
        excludeSelf: true,
        when: (row, permissions) =>
          row.status === "active" &&
          row.email_verified === true &&
          (!Array.isArray(row.roles) ||
            !row.roles.includes("administrator") ||
            permissions.includes("members.roles")),
      },
      {
        label: "Sign out all devices",
        permission: "members.credentials",
        endpoint: (row) => `/api/v1/members/${row.id}/sessions/revoke`,
        successMessage: "Member signed out of all devices",
        confirm: "Revoke every active session for this member?",
        excludeSelf: true,
        when: (row, permissions) =>
          row.status !== "archived" &&
          (!Array.isArray(row.roles) ||
            !row.roles.includes("administrator") ||
            permissions.includes("members.roles")),
      },
      {
        label: "Deactivate member",
        submitLabel: "Deactivate member",
        permission: "members.lifecycle",
        endpoint: (row) => `/api/v1/members/${row.id}/deactivate`,
        fields: [
          {
            key: "reason",
            label: "Reason for deactivation",
            type: "textarea",
            required: true,
            placeholder: "Record why this account is being deactivated",
          },
        ],
        successMessage: "Member deactivated and signed out",
        danger: true,
        excludeSelf: true,
        when: (row, permissions) =>
          ["active", "invited"].includes(String(row.status)) &&
          (!Array.isArray(row.roles) ||
            !row.roles.includes("administrator") ||
            permissions.includes("members.roles")),
      },
      {
        label: "Reactivate member",
        permission: "members.lifecycle",
        endpoint: (row) => `/api/v1/members/${row.id}/reactivate`,
        successMessage: "Member reactivated",
        confirm: "Reactivate this member account?",
        excludeSelf: true,
        when: (row, permissions) =>
          ["suspended", "archived"].includes(String(row.status)) &&
          (!Array.isArray(row.roles) ||
            !row.roles.includes("administrator") ||
            permissions.includes("members.roles")),
      },
    ],
  },
  executives: {
    title: "Executive appointments",
    description:
      "Current and past leadership terms, public biographies, portfolios and social profiles.",
    endpoint: "/api/v1/executives",
    queryKey: "executives",
    exportUrl: "/api/v1/executives/exports/csv",
    exportPermission: "members.export",
    filters: [
      { key: "is_active", label: "Appointment", options: ["true", "false"] },
    ],
    columns: [
      { key: "full_name", label: "Executive" },
      { key: "position", label: "Position" },
      { key: "portfolio", label: "Portfolio" },
      { key: "term_number", label: "Term" },
      { key: "is_active", label: "Current" },
    ],
    create: {
      label: "Add appointment",
      permission: "executives.manage",
      endpoint: "/api/v1/executives",
      fields: executiveFields,
      successMessage: "Executive appointment created",
    },
    update: {
      label: "Edit appointment",
      permission: "executives.manage",
      endpoint: (row) => `/api/v1/executives/${row.id}`,
      method: "PATCH",
      fields: executiveFields,
      successMessage: "Executive appointment updated",
    },
    archive: {
      label: "End appointment",
      permission: "executives.manage",
      endpoint: (row) => `/api/v1/executives/${row.id}`,
      method: "DELETE",
      successMessage: "Executive appointment ended",
      confirm: "End this appointment while retaining its term history?",
      danger: true,
      when: (row) => row.is_active === true,
    },
  },
  organization: {
    title: "Organization",
    description:
      "Schools, colleges, departments and committees represented in the association.",
    endpoint: "/api/v1/organization/units?include_inactive=true",
    queryKey: "organization",
    filters: [
      {
        key: "unit_type",
        label: "Type",
        options: ["school", "college", "department", "committee"],
      },
    ],
    columns: [
      { key: "name", label: "Unit" },
      { key: "unit_type", label: "Type" },
      { key: "parent_name", label: "Parent" },
      { key: "is_active", label: "Active" },
    ],
    create: {
      label: "Add unit",
      permission: "organization.manage",
      endpoint: "/api/v1/organization/units",
      fields: [
        {
          key: "unit_type",
          label: "Type",
          type: "select",
          required: true,
          createOnly: true,
          options: ["school", "college", "department", "committee"],
        },
        { key: "name", label: "Unit name", required: true },
        {
          key: "parent_id",
          label: "Parent unit",
          type: "select",
          optionSource: {
            endpoint: "/api/v1/organization/units",
            queryKey: "organization-units",
            value: (row) => String(row.id),
            label: (row) => `${String(row.name)} · ${String(row.unit_type)}`,
          },
          help: "Schools belong to colleges; departments belong to schools.",
        },
        {
          key: "is_active",
          label: "Active",
          type: "checkbox",
          defaultValue: true,
        },
      ],
      successMessage: "Organization unit created",
    },
    update: {
      label: "Edit unit",
      permission: "organization.manage",
      endpoint: (row) => `/api/v1/organization/units/${row.id}`,
      method: "PATCH",
      fields: [
        { key: "name", label: "Unit name", required: true },
        {
          key: "parent_id",
          label: "Parent unit",
          type: "select",
          optionSource: {
            endpoint: "/api/v1/organization/units",
            queryKey: "organization-units",
            value: (row) => String(row.id),
            label: (row) => `${String(row.name)} · ${String(row.unit_type)}`,
          },
        },
        { key: "is_active", label: "Active", type: "checkbox" },
      ],
      successMessage: "Organization unit updated",
    },
    archive: {
      label: "Deactivate unit",
      permission: "organization.manage",
      endpoint: (row) => `/api/v1/organization/units/${row.id}`,
      method: "DELETE",
      successMessage: "Organization unit deactivated",
      confirm:
        "Deactivate this unit? Existing member links and history will be retained.",
      danger: true,
      when: (row) => row.is_active === true,
    },
  },
  news: {
    title: "News & statements",
    description:
      "Draft, review, schedule and publish the news that appears on the public website.",
    endpoint: "/api/v1/content/articles?page_size=100",
    queryKey: "content",
    serverPagination: {
      searchParam: "q",
      filterParams: { status: "status" },
    },
    filters: [
      {
        key: "status",
        label: "Status",
        options: [
          "draft",
          "review",
          "scheduled",
          "published",
          "archived",
          "withdrawn",
        ],
      },
    ],
    columns: [
      { key: "title", label: "Article" },
      { key: "status", label: "Status" },
      { key: "published_at", label: "Published" },
      { key: "updated_at", label: "Updated" },
      { key: "version", label: "Version" },
    ],
    create: {
      label: "New article",
      permission: "content.edit",
      endpoint: "/api/v1/content/articles",
      fields: editorialFields,
      successMessage: "Article created",
      prepare: articlePrepare,
    },
    update: {
      label: "Edit article",
      permission: "content.edit",
      endpoint: (row) => `/api/v1/content/articles/${row.id}`,
      method: "PATCH",
      fields: editorialFields,
      successMessage: "Article updated",
      prepare: articlePrepare,
      headers: (row) => ({ "If-Match": `"${row.version}"` }),
    },
    archive: {
      label: "Archive article",
      permission: "content.publish",
      endpoint: (row) => `/api/v1/content/articles/${row.id}`,
      method: "DELETE",
      successMessage: "Article archived",
      confirm:
        "Archive this article? Its history will be retained and it will leave the public site.",
      danger: true,
      when: (row) => row.status !== "archived",
    },
    actions: [
      {
        label: "Preview",
        permission: "content.view",
        endpoint: (row) => `/api/v1/content/articles/${row.id}`,
        href: (row) => `/dashboard/preview/news/${row.id}`,
        successMessage: "Preview opened",
        open: true,
      },
    ],
  },
  announcements: {
    title: "Announcements",
    description:
      "Create official association broadcasts. Publishing delivers the notice once to each targeted member's notification inbox.",
    endpoint: "/api/v1/content/announcements?page_size=100",
    queryKey: "announcements",
    serverPagination: {
      searchParam: "q",
      filterParams: { priority: "priority", status: "status" },
    },
    filters: [
      {
        key: "priority",
        label: "Priority",
        options: ["low", "normal", "high", "urgent"],
      },
      {
        key: "status",
        label: "Status",
        options: ["draft", "review", "scheduled", "published", "archived"],
      },
    ],
    columns: [
      { key: "title", label: "Announcement" },
      { key: "priority", label: "Priority" },
      { key: "status", label: "Status" },
      { key: "published_at", label: "Published" },
      { key: "expires_at", label: "Expires" },
    ],
    create: {
      label: "New announcement",
      permission: "content.edit",
      endpoint: "/api/v1/content/announcements",
      fields: announcementFields,
      successMessage: "Announcement created",
      prepare: announcementPrepare,
    },
    update: {
      label: "Edit announcement",
      permission: "content.edit",
      endpoint: (row) => `/api/v1/content/announcements/${row.id}`,
      method: "PATCH",
      fields: announcementFields,
      successMessage: "Announcement updated",
      prepare: announcementPrepare,
      headers: (row) => ({ "If-Match": `"${row.version}"` }),
    },
    archive: {
      label: "Archive announcement",
      permission: "content.publish",
      endpoint: (row) => `/api/v1/content/announcements/${row.id}`,
      method: "DELETE",
      successMessage: "Announcement archived",
      confirm:
        "Archive this announcement? Existing inbox deliveries stay in members' notification history.",
      danger: true,
      when: (row) => row.status !== "archived",
    },
  },
  events: {
    title: "Events",
    description:
      "Planning, schedules, registration, CPD details and protected online access.",
    endpoint: "/api/v1/events?page_size=100",
    queryKey: "events",
    serverPagination: {
      searchParam: "q",
      filterParams: {
        status: "status",
        publication_status: "publication_status",
      },
    },
    filters: [
      {
        key: "status",
        label: "Status",
        options: ["upcoming", "ongoing", "completed", "cancelled", "postponed"],
      },
      {
        key: "publication_status",
        label: "Publication",
        options: ["draft", "review", "scheduled", "published", "archived"],
      },
    ],
    columns: [
      { key: "title", label: "Event" },
      { key: "start_date", label: "Date" },
      { key: "event_type", label: "Type" },
      { key: "status", label: "Status" },
      { key: "registrations", label: "Registrations" },
    ],
    create: {
      label: "New event",
      permission: "events.manage",
      endpoint: "/api/v1/events",
      fields: eventFields,
      successMessage: "Event created",
      prepare: eventPrepare,
    },
    update: {
      label: "Edit event",
      permission: "events.manage",
      endpoint: (row) => `/api/v1/events/${row.id}`,
      method: "PUT",
      fields: eventFields,
      successMessage: "Event updated",
      prepare: eventPrepare,
      headers: (row) => ({ "If-Match": `"${row.version}"` }),
    },
    archive: {
      label: "Archive event",
      permission: "events.manage",
      endpoint: (row) => `/api/v1/events/${row.id}`,
      method: "DELETE",
      successMessage: "Event archived",
      confirm:
        "Archive this event? Registrations and activity history will be retained.",
      danger: true,
      when: (row) => row.publication_status !== "archived",
    },
    actions: [
      {
        label: "Register",
        permission: "dashboard.view",
        endpoint: (row) => `/api/v1/events/${row.id}/registration`,
        successMessage: "Registration confirmed",
        when: (row) =>
          row.registration_required === true &&
          row.registered !== true &&
          row.publication_status === "published",
      },
      {
        label: "Cancel registration",
        permission: "dashboard.view",
        endpoint: (row) => `/api/v1/events/${row.id}/registration`,
        method: "DELETE",
        successMessage: "Registration cancelled",
        confirm: "Cancel your registration for this event?",
        danger: true,
        when: (row) => row.registered === true,
      },
    ],
  },
  documents: {
    title: "Documents",
    description:
      "Audience-controlled records, immutable file versions, retention and legal-hold metadata.",
    endpoint: "/api/v1/documents?page_size=100",
    queryKey: "documents",
    serverPagination: {
      searchParam: "q",
      filterParams: { category: "category", status: "status" },
    },
    filters: [
      { key: "category", label: "Category", options: ["internal", "external"] },
      {
        key: "status",
        label: "Status",
        options: ["draft", "review", "published", "archived"],
      },
    ],
    columns: [
      { key: "public_id", label: "Reference" },
      { key: "title", label: "Document" },
      { key: "category", label: "Category" },
      { key: "status", label: "Status" },
      { key: "document_date", label: "Date" },
      { key: "version", label: "Version" },
    ],
    create: {
      label: "New document",
      permission: "documents.manage",
      endpoint: "/api/v1/documents",
      fields: documentFields,
      successMessage: "Document created",
      prepare: documentPrepare,
    },
    update: {
      label: "Edit document",
      permission: "documents.manage",
      endpoint: (row) => `/api/v1/documents/${row.id}`,
      method: "PATCH",
      fields: documentFields,
      successMessage: "Document updated",
      prepare: documentPrepare,
      headers: (row) => ({ "If-Match": `"${row.version}"` }),
    },
    archive: {
      label: "Archive document",
      permission: "documents.manage",
      endpoint: (row) => `/api/v1/documents/${row.id}`,
      method: "DELETE",
      successMessage: "Document archived",
      confirm:
        "Archive this document? Files and every version will be retained.",
      danger: true,
    },
    actions: [
      {
        label: "Preview",
        permission: "documents.view",
        endpoint: (row) => `/api/v1/documents/${row.id}`,
        href: (row) => `/dashboard/documents/${row.id}/preview`,
        successMessage: "Preview opened",
        open: true,
      },
      {
        label: "Add file version",
        permission: "documents.manage",
        endpoint: (row) => `/api/v1/documents/${row.id}/versions`,
        fields: [
          {
            key: "asset_ids",
            label: "Files in this version",
            type: "media",
            required: true,
            media: {
              accept: "any",
              multiple: true,
              isPrivate: true,
            },
            optionSource: {
              endpoint: "/api/v1/media?status=ready&page_size=100",
              queryKey: "ready-files",
              searchParam: "q",
              value: (row) => String(row.id),
              label: (row) =>
                `${String(row.original_filename)} · ${String(row.content_type)}`,
              emptyLabel: "No ready files",
            },
            help: "Upload replacement files here or reuse files already in the secure library.",
          },
          {
            key: "change_note",
            label: "Version note",
            type: "textarea",
          },
        ],
        successMessage: "New document version added",
      },
      {
        label: "Open latest file",
        permission: "documents.view",
        endpoint: (row) => `/api/v1/media/${row.latest_media_asset_id}/content`,
        successMessage: "Document opened",
        open: true,
        when: (row) => Boolean(row.latest_media_asset_id),
      },
    ],
  },
  media: {
    title: "Media library",
    description:
      "Secure uploads, malware scanning, private delivery and reusable visual assets.",
    endpoint: "/api/v1/media?page_size=100",
    queryKey: "media",
    serverPagination: {
      searchParam: "q",
      filterParams: { status: "status" },
    },
    filters: [
      {
        key: "status",
        label: "Status",
        options: ["quarantined", "scanning", "ready", "rejected"],
      },
    ],
    columns: [
      { key: "original_filename", label: "Asset" },
      { key: "content_type", label: "Type" },
      { key: "byte_size", label: "Size" },
      { key: "status", label: "Status" },
      { key: "created_at", label: "Uploaded" },
    ],
    update: {
      label: "Edit media details",
      permission: "media.manage",
      endpoint: (row) => `/api/v1/media/${row.id}`,
      method: "PATCH",
      fields: [
        { key: "alt_text", label: "Alternative text", type: "textarea" },
        { key: "caption", label: "Caption", type: "textarea" },
        { key: "credit", label: "Credit" },
        { key: "is_private", label: "Private asset", type: "checkbox" },
      ],
      successMessage: "Media details updated",
    },
    archive: {
      label: "Archive media",
      permission: "media.manage",
      endpoint: (row) => `/api/v1/media/${row.id}`,
      method: "DELETE",
      successMessage: "Media asset archived",
      confirm:
        "Archive this media asset? Stored bytes and audit history will be retained.",
      danger: true,
      when: (row) => row.status !== "archived",
    },
    actions: [
      {
        label: "Open file",
        permission: "media.manage",
        endpoint: (row) => `/api/v1/media/${row.id}/content`,
        successMessage: "File opened",
        open: true,
        when: (row) => row.status === "ready",
      },
    ],
  },
  galleries: {
    title: "Galleries",
    description:
      "Curated visual stories for the public site and association record.",
    endpoint: "/api/v1/galleries",
    queryKey: "galleries",
    filters: [
      {
        key: "status",
        label: "Status",
        options: ["draft", "review", "published", "archived"],
      },
    ],
    columns: [
      { key: "title", label: "Gallery" },
      { key: "status", label: "Status" },
      { key: "published_at", label: "Published" },
      { key: "items", label: "Images" },
    ],
    create: {
      label: "New gallery",
      permission: "content.edit",
      endpoint: "/api/v1/galleries",
      fields: [
        {
          key: "title",
          label: "Title",
          required: true,
          prominent: true,
          placeholder: "Enter the gallery title",
        },
        {
          key: "description",
          label: "Description",
          type: "richtext",
          placeholder: "Write the gallery introduction…",
          emptyValue: "",
        },
        {
          key: "status",
          label: "Status",
          type: "select",
          defaultValue: "draft",
          optionsFor: (permissions) =>
            permissions.includes("content.publish")
              ? ["draft", "review", "published"]
              : ["draft", "review"],
        },
        {
          key: "media_asset_ids",
          label: "Gallery images",
          type: "media",
          media: {
            accept: "image",
            multiple: true,
            isPrivate: false,
            aspect: "square",
            downloadControl: true,
          },
          optionSource: {
            endpoint: "/api/v1/media?status=ready&page_size=100",
            queryKey: "ready-public-images",
            searchParam: "q",
            value: (row) => String(row.id),
            label: (row) => String(row.original_filename),
            filter: (row) =>
              row.is_private === false &&
              String(row.content_type).startsWith("image/"),
            emptyLabel: "No ready public images",
          },
          help: "Upload images here or reuse ready images from the Media library. Use Allow download on each image to control the public gallery download button. For Google Drive or OneDrive albums, use the external album link below instead of (or in addition to) uploading.",
        },
        {
          key: "blocked_download_media_ids",
          label: "Images without public download",
          type: "multiselect",
          hidden: true,
          defaultValue: [],
          emptyValue: [],
        },
        {
          key: "external_album_url",
          label: "External album link",
          type: "url",
          help: "Optional shared Google Drive, OneDrive or similar album. Visitors can open it from the public gallery page.",
        },
      ],
      successMessage: "Gallery created",
    },
    update: {
      label: "Edit gallery",
      permission: "content.edit",
      endpoint: (row) => `/api/v1/galleries/${row.id}`,
      method: "PUT",
      fields: [
        {
          key: "title",
          label: "Title",
          required: true,
          prominent: true,
          placeholder: "Enter the gallery title",
        },
        {
          key: "description",
          label: "Description",
          type: "richtext",
          placeholder: "Write the gallery introduction…",
          emptyValue: "",
        },
        {
          key: "status",
          label: "Status",
          type: "select",
          optionsFor: (permissions) =>
            permissions.includes("content.publish")
              ? ["draft", "review", "published", "archived"]
              : ["draft", "review"],
        },
        {
          key: "media_asset_ids",
          label: "Gallery images",
          type: "media",
          media: {
            accept: "image",
            multiple: true,
            isPrivate: false,
            aspect: "square",
            downloadControl: true,
          },
          optionSource: {
            endpoint: "/api/v1/media?status=ready&page_size=100",
            queryKey: "ready-public-images",
            searchParam: "q",
            value: (row) => String(row.id),
            label: (row) => String(row.original_filename),
            filter: (row) =>
              row.is_private === false &&
              String(row.content_type).startsWith("image/"),
            emptyLabel: "No ready public images",
          },
          help: "Upload images here or reuse ready images from the Media library. Toggle Allow download per image for the public gallery.",
        },
        {
          key: "blocked_download_media_ids",
          label: "Images without public download",
          type: "multiselect",
          hidden: true,
          defaultValue: [],
          emptyValue: [],
          valueFromRow: (row) =>
            ((row.items as WorkspaceRow[] | undefined) ?? [])
              .filter((item) => item.allow_download === false)
              .map((item) => String(item.media_asset_id)),
        },
        {
          key: "external_album_url",
          label: "External album link",
          type: "url",
          help: "Optional shared Google Drive, OneDrive or similar album.",
        },
      ],
      successMessage: "Gallery updated",
      headers: (row) => ({ "If-Match": `"${row.version}"` }),
      prepare: (payload, row) => {
        const mediaIds =
          (payload.media_asset_ids as string[] | undefined) ??
          (row?.items as WorkspaceRow[] | undefined)?.map((item) =>
            String(item.media_asset_id),
          ) ??
          [];
        const blocked = new Set(
          (
            (payload.blocked_download_media_ids as string[] | undefined) ?? []
          ).map(String),
        );
        return {
          ...payload,
          media_asset_ids: mediaIds,
          blocked_download_media_ids: mediaIds.filter((id) =>
            blocked.has(String(id)),
          ),
        };
      },
    },
    archive: {
      label: "Archive gallery",
      permission: "content.publish",
      endpoint: (row) => `/api/v1/galleries/${row.id}`,
      method: "DELETE",
      successMessage: "Gallery archived",
      confirm: "Archive this gallery while retaining all images and history?",
      danger: true,
      when: (row) => row.status !== "archived",
    },
  },
  carousel: {
    title: "Homepage carousel",
    description:
      "Ordered, accessible homepage hero slides using scanned public media assets.",
    endpoint: "/api/v1/admin/carousel",
    queryKey: "settings",
    filters: [
      { key: "is_published", label: "Published", options: ["true", "false"] },
    ],
    columns: [
      { key: "title", label: "Slide" },
      { key: "order", label: "Order" },
      { key: "is_published", label: "Published" },
      { key: "media_name", label: "Image" },
    ],
    create: {
      label: "New slide",
      permission: "settings.manage",
      endpoint: "/api/v1/admin/carousel",
      fields: [
        {
          key: "title",
          label: "Title",
          required: true,
          prominent: true,
          placeholder: "Enter the homepage headline",
        },
        {
          key: "description",
          label: "Description",
          type: "richtext",
          placeholder: "Write the supporting homepage message…",
          emptyValue: "",
        },
        {
          key: "media_asset_id",
          label: "Homepage image",
          type: "media",
          required: true,
          media: {
            accept: "image",
            isPrivate: false,
            aspect: "landscape",
          },
          optionSource: {
            endpoint: "/api/v1/media?status=ready&page_size=100",
            queryKey: "ready-public-images",
            searchParam: "q",
            value: (row) => String(row.id),
            label: (row) =>
              `${String(row.original_filename)} · ${String(row.content_type)}`,
            filter: (row) =>
              row.is_private === false &&
              String(row.content_type).startsWith("image/"),
            emptyLabel: "No ready public images",
          },
          help: "Upload a homepage image here or reuse a ready public image.",
        },
        { key: "link_url", label: "Optional link URL" },
        {
          key: "order",
          label: "Display order",
          type: "number",
          defaultValue: 0,
        },
        { key: "is_published", label: "Published", type: "checkbox" },
      ],
      successMessage: "Homepage slide created",
    },
    update: {
      label: "Edit slide",
      permission: "settings.manage",
      endpoint: (row) => `/api/v1/admin/carousel/${row.id}`,
      method: "PATCH",
      fields: [
        {
          key: "title",
          label: "Title",
          required: true,
          prominent: true,
          placeholder: "Enter the homepage headline",
        },
        {
          key: "description",
          label: "Description",
          type: "richtext",
          placeholder: "Write the supporting homepage message…",
          emptyValue: "",
        },
        {
          key: "media_asset_id",
          label: "Homepage image",
          type: "media",
          required: true,
          media: {
            accept: "image",
            isPrivate: false,
            aspect: "landscape",
          },
          optionSource: {
            endpoint: "/api/v1/media?status=ready&page_size=100",
            queryKey: "ready-public-images",
            searchParam: "q",
            value: (row) => String(row.id),
            label: (row) =>
              `${String(row.original_filename)} · ${String(row.content_type)}`,
            filter: (row) =>
              row.is_private === false &&
              String(row.content_type).startsWith("image/"),
            emptyLabel: "No ready public images",
          },
          help: "Upload a homepage image here or reuse a ready public image.",
        },
        { key: "link_url", label: "Optional link URL" },
        { key: "order", label: "Display order", type: "number" },
        { key: "is_published", label: "Published", type: "checkbox" },
      ],
      successMessage: "Homepage slide updated",
    },
    archive: {
      label: "Archive slide",
      permission: "settings.manage",
      endpoint: (row) => `/api/v1/admin/carousel/${row.id}`,
      method: "DELETE",
      successMessage: "Homepage slide archived",
      confirm:
        "Archive this slide? Its audit history and media asset will be retained.",
      danger: true,
      when: (row) => row.archived !== true,
    },
  },
  adverts: {
    title: "Advertising campaigns",
    description:
      "Creatives that run on the public site. Paid campaigns must be linked to a paid order; house ads are for UG UTAG’s own promotions only.",
    endpoint: "/api/v1/adverts/campaigns",
    queryKey: "adverts",
    filters: [
      {
        key: "status",
        label: "Status",
        options: ["draft", "scheduled", "active", "paused", "completed"],
      },
    ],
    columns: [
      { key: "title", label: "Campaign" },
      { key: "placement_name", label: "Placement" },
      { key: "fulfilment", label: "Fulfilment" },
      { key: "advertiser_name", label: "Advertiser" },
      { key: "status", label: "Status" },
      { key: "starts_at", label: "Starts" },
      { key: "impressions", label: "Impressions" },
      { key: "clicks", label: "Clicks" },
    ],
    create: {
      label: "New campaign",
      permission: "adverts.manage",
      endpoint: "/api/v1/adverts/campaigns",
      fields: campaignFields,
      successMessage: "Campaign created",
    },
    update: {
      label: "Edit campaign",
      permission: "adverts.manage",
      endpoint: (row) => `/api/v1/adverts/campaigns/${row.id}`,
      method: "PATCH",
      fields: campaignFields,
      successMessage: "Campaign updated",
    },
    archive: {
      label: "Complete campaign",
      permission: "adverts.manage",
      endpoint: (row) => `/api/v1/adverts/campaigns/${row.id}`,
      method: "DELETE",
      successMessage: "Campaign completed",
      confirm: "Complete this campaign? Performance records will be retained.",
      danger: true,
      when: (row) => row.status !== "completed",
    },
  },
  "advert-slots": {
    title: "Advertising placements",
    description:
      "Public-site mounts, required creative dimensions, and where each placement appears.",
    endpoint: "/api/v1/adverts/slots",
    queryKey: "adverts",
    columns: [
      { key: "name", label: "Placement" },
      { key: "key", label: "Key" },
      { key: "location", label: "Site location" },
      { key: "size", label: "Size" },
      { key: "is_active", label: "Active" },
    ],
    create: {
      label: "New placement",
      permission: "adverts.manage",
      endpoint: "/api/v1/adverts/slots",
      fields: [
        {
          key: "key",
          label: "Key",
          required: true,
          help: "Must match a public-site mount key (for example home-after-hero).",
        },
        { key: "name", label: "Name", required: true },
        {
          key: "location",
          label: "Site location",
          required: true,
          placeholder: "Home · after hero",
          help: "Short description of where this placement appears on the public site.",
        },
        { key: "width", label: "Width (px)", type: "number", required: true },
        { key: "height", label: "Height (px)", type: "number", required: true },
        {
          key: "description",
          label: "Description",
          type: "textarea",
          emptyValue: "",
        },
        {
          key: "is_active",
          label: "Active",
          type: "checkbox",
          defaultValue: true,
        },
      ],
      successMessage: "Advertising placement created",
    },
    update: {
      label: "Edit placement",
      permission: "adverts.manage",
      endpoint: (row) => `/api/v1/adverts/slots/${row.id}`,
      method: "PUT",
      fields: [
        {
          key: "key",
          label: "Key",
          required: true,
          help: "Must match a public-site mount key.",
        },
        { key: "name", label: "Name", required: true },
        {
          key: "location",
          label: "Site location",
          required: true,
          placeholder: "Home · after hero",
        },
        { key: "width", label: "Width (px)", type: "number", required: true },
        { key: "height", label: "Height (px)", type: "number", required: true },
        {
          key: "description",
          label: "Description",
          type: "textarea",
          emptyValue: "",
        },
        { key: "is_active", label: "Active", type: "checkbox" },
      ],
      successMessage: "Advertising placement updated",
    },
  },
  "advert-plans": {
    title: "Advertising plans",
    description:
      "Rate-card plans priced per placement, with duration and availability.",
    endpoint: "/api/v1/adverts/plans",
    queryKey: "adverts",
    columns: [
      { key: "name", label: "Plan" },
      { key: "placement_name", label: "Placement" },
      { key: "price", label: "Price (GHS)" },
      { key: "duration_days", label: "Days" },
      { key: "is_active", label: "Active" },
    ],
    create: {
      label: "New plan",
      permission: "adverts.manage",
      endpoint: "/api/v1/adverts/plans",
      fields: [
        {
          key: "slot_id",
          label: "Placement",
          type: "select",
          required: true,
          optionSource: {
            endpoint: "/api/v1/adverts/slots",
            queryKey: "advert-slots",
            value: (row) => String(row.id),
            label: (row) =>
              `${String(row.name)} · ${String(row.width)}×${String(row.height)}`,
            filter: (row) => row.is_active === true,
            emptyLabel: "No active placements available",
          },
        },
        { key: "name", label: "Name", required: true },
        {
          key: "description",
          label: "Description",
          type: "textarea",
          emptyValue: "",
        },
        { key: "price", label: "Price (GHS)", type: "number", defaultValue: 0 },
        {
          key: "duration_days",
          label: "Duration in days",
          type: "number",
          defaultValue: 30,
        },
        {
          key: "is_active",
          label: "Active",
          type: "checkbox",
          defaultValue: true,
        },
      ],
      successMessage: "Advertising plan created",
    },
    update: {
      label: "Edit plan",
      permission: "adverts.manage",
      endpoint: (row) => `/api/v1/adverts/plans/${row.id}`,
      method: "PATCH",
      fields: [
        {
          key: "slot_id",
          label: "Placement",
          type: "select",
          required: true,
          optionSource: {
            endpoint: "/api/v1/adverts/slots",
            queryKey: "advert-slots",
            value: (row) => String(row.id),
            label: (row) =>
              `${String(row.name)} · ${String(row.width)}×${String(row.height)}`,
            filter: (row) => row.is_active === true,
            emptyLabel: "No active placements available",
          },
        },
        { key: "name", label: "Name", required: true },
        {
          key: "description",
          label: "Description",
          type: "textarea",
          emptyValue: "",
        },
        { key: "price", label: "Price (GHS)", type: "number" },
        { key: "duration_days", label: "Duration in days", type: "number" },
        { key: "is_active", label: "Active", type: "checkbox" },
      ],
      successMessage: "Advertising plan updated",
    },
    archive: {
      label: "Deactivate plan",
      permission: "adverts.manage",
      endpoint: (row) => `/api/v1/adverts/plans/${row.id}`,
      method: "DELETE",
      successMessage: "Advertising plan deactivated",
      confirm: "Deactivate this plan? Existing orders will be retained.",
      danger: true,
      when: (row) => row.is_active === true,
    },
  },
  "advert-orders": {
    title: "Advertising orders",
    description:
      "Bookings from external clients or companies. Creating an order auto-creates a draft campaign on the plan’s placement. Mark paid and approved/active before activating the campaign.",
    endpoint: "/api/v1/adverts/orders",
    queryKey: "adverts",
    filters: [
      {
        key: "status",
        label: "Status",
        options: ["pending", "approved", "active", "completed", "cancelled"],
      },
      {
        key: "payment_status",
        label: "Payment",
        options: ["unpaid", "pending", "paid", "refunded"],
      },
    ],
    columns: [
      { key: "advertiser_name", label: "Client" },
      { key: "plan_name", label: "Plan" },
      { key: "campaign_name", label: "Campaign" },
      { key: "status", label: "Status" },
      { key: "payment_status", label: "Payment" },
      { key: "starts_on", label: "Starts" },
    ],
    create: {
      label: "New order",
      permission: "adverts.manage",
      endpoint: "/api/v1/adverts/orders",
      fields: [
        {
          key: "advertiser_id",
          label: "Client / company",
          type: "select",
          required: true,
          optionSource: {
            endpoint: "/api/v1/adverts/advertisers",
            queryKey: "advert-advertisers",
            value: (row) => String(row.id),
            label: (row) =>
              `${String(row.organization_name)} · ${String(row.email)}`,
            filter: (row) => row.is_active === true,
            emptyLabel: "No active advertisers — add one under Clients first",
          },
          help: "External companies and other non-member clients. Add them under the Clients tab.",
        },
        {
          key: "plan_id",
          label: "Plan",
          type: "select",
          required: true,
          optionSource: {
            endpoint: "/api/v1/adverts/plans",
            queryKey: "advert-plans",
            value: (row) => String(row.id),
            label: (row) =>
              `${String(row.name)} · ${String(row.placement_name ?? "Placement")} · GHS ${String(row.price)} · ${String(row.duration_days)} days`,
            filter: (row) => row.is_active === true,
            emptyLabel: "No active advertising plans available",
          },
        },
        {
          key: "campaign_id",
          label: "Existing campaign (optional)",
          type: "select",
          optionSource: {
            endpoint: "/api/v1/adverts/campaigns",
            queryKey: "advert-campaigns",
            value: (row) => String(row.id),
            label: (row) =>
              `${String(row.title)} · ${String(row.placement_name ?? "Placement")} · ${String(row.status)}`,
            filter: (row) => row.is_house_ad !== true,
            emptyLabel: "No campaigns available",
          },
          help: "Leave empty to auto-create a draft campaign for this order. One campaign can only belong to one order.",
        },
        {
          key: "status",
          label: "Status",
          type: "select",
          defaultValue: "pending",
          options: ["pending", "approved", "active", "completed", "cancelled"],
          help: "Active requires a linked campaign and paid payment status.",
        },
        {
          key: "payment_status",
          label: "Payment",
          type: "select",
          defaultValue: "unpaid",
          options: ["unpaid", "pending", "paid", "refunded"],
        },
        { key: "starts_on", label: "Starts on", type: "date" },
        { key: "ends_on", label: "Ends on", type: "date" },
        { key: "notes", label: "Notes", type: "textarea", emptyValue: "" },
      ],
      successMessage: "Advertising order created",
    },
    update: {
      label: "Edit order",
      permission: "adverts.manage",
      endpoint: (row) => `/api/v1/adverts/orders/${row.id}`,
      method: "PATCH",
      fields: [
        {
          key: "advertiser_id",
          label: "Client / company",
          type: "select",
          optionSource: {
            endpoint: "/api/v1/adverts/advertisers",
            queryKey: "advert-advertisers",
            value: (row) => String(row.id),
            label: (row) =>
              `${String(row.organization_name)} · ${String(row.email)}`,
            filter: (row) => row.is_active === true,
            emptyLabel: "No active advertisers available",
          },
        },
        {
          key: "campaign_id",
          label: "Campaign",
          type: "select",
          optionSource: {
            endpoint: "/api/v1/adverts/campaigns",
            queryKey: "advert-campaigns",
            value: (row) => String(row.id),
            label: (row) =>
              `${String(row.title)} · ${String(row.placement_name ?? "Placement")} · ${String(row.status)}`,
            filter: (row) => row.is_house_ad !== true,
            emptyLabel: "No campaigns available",
          },
          help: "Campaign placement must match the order plan. Active orders require a campaign and paid status.",
        },
        {
          key: "status",
          label: "Status",
          type: "select",
          options: ["pending", "approved", "active", "completed", "cancelled"],
        },
        {
          key: "payment_status",
          label: "Payment",
          type: "select",
          options: ["unpaid", "pending", "paid", "refunded"],
        },
        { key: "starts_on", label: "Starts on", type: "date" },
        { key: "ends_on", label: "Ends on", type: "date" },
        { key: "notes", label: "Notes", type: "textarea", emptyValue: "" },
      ],
      successMessage: "Advertising order updated",
    },
    archive: {
      label: "Cancel order",
      permission: "adverts.manage",
      endpoint: (row) => `/api/v1/adverts/orders/${row.id}`,
      method: "DELETE",
      successMessage: "Advertising order cancelled",
      confirm:
        "Cancel this order? Its linked campaign will be paused if it was live.",
      danger: true,
      when: (row) => row.status !== "cancelled",
    },
  },
  "advert-advertisers": {
    title: "Advertiser clients",
    description:
      "External companies and individuals buying ad inventory. They do not need a portal membership.",
    endpoint: "/api/v1/adverts/advertisers",
    queryKey: "adverts",
    columns: [
      { key: "organization_name", label: "Organization" },
      { key: "contact_name", label: "Contact" },
      { key: "email", label: "Email" },
      { key: "phone", label: "Phone" },
      { key: "is_active", label: "Active" },
    ],
    create: {
      label: "New client",
      permission: "adverts.manage",
      endpoint: "/api/v1/adverts/advertisers",
      fields: [
        {
          key: "organization_name",
          label: "Organization / company",
          required: true,
        },
        { key: "contact_name", label: "Contact name", emptyValue: "" },
        { key: "email", label: "Email", type: "email", required: true },
        { key: "phone", label: "Phone", emptyValue: "" },
        { key: "website", label: "Website", type: "url", emptyValue: null },
        { key: "notes", label: "Notes", type: "textarea", emptyValue: "" },
        {
          key: "is_active",
          label: "Active",
          type: "checkbox",
          defaultValue: true,
        },
      ],
      successMessage: "Advertiser client created",
    },
    update: {
      label: "Edit client",
      permission: "adverts.manage",
      endpoint: (row) => `/api/v1/adverts/advertisers/${row.id}`,
      method: "PATCH",
      fields: [
        {
          key: "organization_name",
          label: "Organization / company",
          required: true,
        },
        { key: "contact_name", label: "Contact name", emptyValue: "" },
        { key: "email", label: "Email", type: "email", required: true },
        { key: "phone", label: "Phone", emptyValue: "" },
        { key: "website", label: "Website", type: "url", emptyValue: null },
        { key: "notes", label: "Notes", type: "textarea", emptyValue: "" },
        { key: "is_active", label: "Active", type: "checkbox" },
      ],
      successMessage: "Advertiser client updated",
    },
    archive: {
      label: "Deactivate client",
      permission: "adverts.manage",
      endpoint: (row) => `/api/v1/adverts/advertisers/${row.id}`,
      method: "DELETE",
      successMessage: "Advertiser client deactivated",
      confirm:
        "Deactivate this client? Existing orders stay on record; new orders will require an active client.",
      danger: true,
      when: (row) => row.is_active === true,
    },
  },
  analytics: {
    title: "Analytics",
    description:
      "A current, privacy-aware view of membership, publishing and event participation.",
    endpoint: "/api/v1/dashboard/analytics",
    queryKey: "analytics",
    columns: [],
  },
  audit: {
    title: "Audit ledger",
    description:
      "Immutable evidence of sensitive reads, writes, decisions and security events.",
    endpoint: "/api/v1/admin/audit?page_size=100",
    queryKey: "audit",
    serverPagination: { searchParam: "q" },
    columns: [
      { key: "actor_name", label: "Actor" },
      { key: "action", label: "Action" },
      { key: "resource_type", label: "Resource" },
      { key: "outcome", label: "Outcome" },
      { key: "created_at", label: "Time" },
    ],
  },
  settings: {
    title: "Portal settings",
    description:
      "Runtime-managed public identity, contact details and homepage controls.",
    endpoint: "/api/v1/admin/settings",
    queryKey: "settings",
    columns: [
      { key: "key", label: "Setting" },
      { key: "value", label: "Value" },
      { key: "is_public", label: "Public" },
    ],
    update: {
      label: "Edit setting",
      permission: "settings.manage",
      endpoint: (row) =>
        `/api/v1/admin/settings/${encodeURIComponent(String(row.key))}`,
      method: "PUT",
      fields: [
        {
          key: "value",
          label: "Structured value",
          type: "json",
          required: true,
        },
        {
          key: "is_public",
          label: "Expose through the public settings API",
          type: "checkbox",
        },
      ],
      successMessage: "Portal setting updated",
      when: (row) => row.key !== "site.carousel",
    },
  },
  "feature-flags": {
    title: "Feature flags",
    description: "Controlled rollout switches for portal capabilities.",
    endpoint: "/api/v1/admin/feature-flags",
    queryKey: "settings",
    columns: [
      { key: "key", label: "Feature" },
      { key: "description", label: "Description" },
      { key: "enabled", label: "Enabled" },
      { key: "rules", label: "Rules" },
    ],
    update: {
      label: "Edit feature",
      permission: "settings.manage",
      endpoint: (row) =>
        `/api/v1/admin/feature-flags/${encodeURIComponent(String(row.key))}`,
      method: "PUT",
      fields: [
        {
          key: "description",
          label: "Description",
          type: "textarea",
          emptyValue: "",
        },
        { key: "enabled", label: "Enabled", type: "checkbox" },
        { key: "rules", label: "Rules", type: "json", defaultValue: "{}" },
      ],
      successMessage: "Feature flag updated",
    },
  },
  jobs: {
    title: "Background jobs",
    description:
      "Imports, exports, contact requests and long-running processing with progress.",
    endpoint: "/api/v1/admin/jobs?page_size=100",
    queryKey: "jobs",
    serverPagination: {
      searchParam: "q",
      filterParams: { status: "status" },
    },
    filters: [
      {
        key: "status",
        label: "Status",
        options: ["queued", "running", "completed", "failed"],
      },
    ],
    columns: [
      { key: "kind", label: "Job" },
      { key: "status", label: "Status" },
      { key: "progress", label: "Progress" },
      { key: "created_at", label: "Created" },
      { key: "error_message", label: "Issue" },
    ],
  },
};

workspaces.content = workspaces.news;
