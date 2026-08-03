import { display } from "./workspace-display";

export type WorkspaceDetailRow = Record<string, unknown>;

export type DetailFieldFormat =
  | "date"
  | "time"
  | "datetime"
  | "richtext"
  | "status"
  | "boolean"
  | "json"
  | "file"
  | "text";

export type WorkspaceDetailField = {
  key: string;
  label: string;
  format?: DetailFieldFormat;
  /** Compose multiple row keys into one display value (e.g. start/end when). */
  compose?: string[];
};

export type WorkspaceDetailConfig = {
  noun: string;
  titleKey: string;
  subtitleKeys?: string[];
  hideEmpty?: boolean;
  managePermission?: string;
  staffPermission?: string;
  fields: WorkspaceDetailField[];
  manageFields?: WorkspaceDetailField[];
  staffFields?: WorkspaceDetailField[];
};

export type WorkspacePreviewKind = "document" | "news";

function isEmptyDetailValue(value: unknown) {
  if (value == null || value === "") return true;
  if (typeof value === "boolean") return false;
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === "object") return Object.keys(value).length === 0;
  if (typeof value === "string" && ["[]", "{}", "Not provided"].includes(value.trim())) {
    return true;
  }
  return false;
}

export function formatTimeValue(value: unknown) {
  if (value == null || value === "") return "";
  const text = String(value);
  const match = text.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?/);
  if (!match) return text;
  const hours = Number(match[1]);
  const minutes = match[2];
  const period = hours >= 12 ? "PM" : "AM";
  const hour12 = hours % 12 || 12;
  return `${hour12}:${minutes} ${period}`;
}

export function formatDateValue(value: unknown) {
  if (value == null || value === "") return "";
  const text = String(value);
  const parsed = new Date(
    /^\d{4}-\d{2}-\d{2}$/.test(text) ? `${text}T12:00:00` : text,
  );
  if (Number.isNaN(parsed.valueOf())) return text;
  return parsed.toLocaleDateString("en-GH", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function formatDateTimeValue(value: unknown) {
  if (value == null || value === "") return "";
  const text = String(value);
  const parsed = new Date(text);
  if (Number.isNaN(parsed.valueOf())) return text;
  return parsed.toLocaleString("en-GH", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function composeWhen(row: WorkspaceDetailRow) {
  const startDate = formatDateValue(row.start_date);
  const endDate = formatDateValue(row.end_date);
  const startTime = formatTimeValue(row.start_time);
  const endTime = formatTimeValue(row.end_time);
  const timezone =
    typeof row.timezone === "string" && row.timezone ? row.timezone : "";

  if (!startDate && !startTime) return "";

  let when = startDate;
  if (startTime) when = when ? `${when} · ${startTime}` : startTime;
  const endPart = [
    endDate && endDate !== startDate ? endDate : "",
    endTime,
  ]
    .filter(Boolean)
    .join(" · ");
  if (endPart) when = `${when} – ${endPart}`;
  if (timezone) when = `${when} (${timezone})`;
  return when;
}

export function detailFieldValue(
  row: WorkspaceDetailRow,
  field: WorkspaceDetailField,
): unknown {
  if (field.key === "when" || field.compose?.includes("start_date")) {
    return composeWhen(row);
  }
  if (field.compose?.length) {
    const parts = field.compose
      .map((key) => {
        const value = row[key];
        if (isEmptyDetailValue(value)) return "";
        if (field.format === "time" || key.endsWith("_time")) {
          return formatTimeValue(value);
        }
        if (field.format === "date" || key.endsWith("_date")) {
          return formatDateValue(value);
        }
        if (field.format === "datetime") return formatDateTimeValue(value);
        return display(value, key);
      })
      .filter(Boolean);
    return parts.join(" · ");
  }

  const value = row[field.key];
  if (field.format === "time") return formatTimeValue(value);
  if (field.format === "date") return formatDateValue(value);
  if (field.format === "datetime") return formatDateTimeValue(value);
  if (field.format === "boolean") {
    if (value == null || value === "") return "";
    return value ? "Yes" : "No";
  }
  return value;
}

export function resolveDetailFields(
  detail: WorkspaceDetailConfig,
  permissions: string[],
): WorkspaceDetailField[] {
  const fields = [...detail.fields];
  if (
    detail.managePermission &&
    permissions.includes(detail.managePermission) &&
    detail.manageFields?.length
  ) {
    fields.push(...detail.manageFields);
  }
  if (
    detail.staffPermission &&
    permissions.includes(detail.staffPermission) &&
    detail.staffFields?.length
  ) {
    fields.push(...detail.staffFields);
  }
  return fields;
}

export function visibleDetailEntries(
  row: WorkspaceDetailRow,
  detail: WorkspaceDetailConfig,
  permissions: string[],
) {
  const hideEmpty = detail.hideEmpty !== false;
  const titleKey = detail.titleKey;
  return resolveDetailFields(detail, permissions)
    .filter((field) => field.key !== titleKey)
    .map((field) => {
      const value = detailFieldValue(row, field);
      return { field, value };
    })
    .filter(({ value }) => !hideEmpty || !isEmptyDetailValue(value));
}

export const workspaceDetails: Record<string, WorkspaceDetailConfig> = {
  members: {
    noun: "Member",
    titleKey: "full_name",
    hideEmpty: true,
    managePermission: "members.update",
    staffPermission: "members.roles",
    fields: [
      { key: "email", label: "Email" },
      { key: "phone_number", label: "Phone" },
      { key: "academic_rank", label: "Academic rank", format: "status" },
      { key: "title", label: "Title" },
      { key: "gender", label: "Gender" },
      { key: "status", label: "Status", format: "status" },
      { key: "roles", label: "Roles", format: "status" },
    ],
    manageFields: [
      { key: "staff_id", label: "Staff ID" },
      { key: "college_name", label: "College" },
      { key: "school_name", label: "School" },
      { key: "department_name", label: "Department" },
      { key: "email_verified", label: "Email verified", format: "boolean" },
      { key: "created_at", label: "Joined", format: "datetime" },
      { key: "last_login_at", label: "Last sign-in", format: "datetime" },
      { key: "extra_permissions", label: "Extra permissions" },
    ],
    staffFields: [{ key: "id", label: "Internal reference" }],
  },
  executives: {
    noun: "Executive",
    titleKey: "full_name",
    hideEmpty: true,
    managePermission: "executives.manage",
    fields: [
      { key: "position", label: "Position" },
      { key: "portfolio", label: "Portfolio" },
      { key: "summary", label: "Summary" },
      { key: "biography_html", label: "Biography", format: "richtext" },
      { key: "term_number", label: "Term" },
      { key: "is_active", label: "Current", format: "boolean" },
      { key: "is_acting", label: "Acting", format: "boolean" },
      { key: "is_public", label: "Public", format: "boolean" },
    ],
    manageFields: [
      { key: "appointed_on", label: "Appointed", format: "date" },
      { key: "ended_on", label: "Ended", format: "date" },
      { key: "show_email", label: "Show email publicly", format: "boolean" },
      { key: "show_phone", label: "Show phone publicly", format: "boolean" },
      { key: "social_links", label: "Social links", format: "json" },
      { key: "email", label: "Email" },
      { key: "phone_number", label: "Phone" },
    ],
  },
  organization: {
    noun: "Unit",
    titleKey: "name",
    hideEmpty: true,
    managePermission: "organization.manage",
    fields: [
      { key: "unit_type", label: "Type", format: "status" },
      { key: "parent_name", label: "Parent" },
      { key: "is_active", label: "Active", format: "boolean" },
    ],
    manageFields: [
      { key: "code", label: "Code" },
      { key: "member_count", label: "Members" },
    ],
  },
  news: {
    noun: "Article",
    titleKey: "title",
    hideEmpty: true,
    managePermission: "content.edit",
    fields: [
      { key: "excerpt", label: "Summary" },
      { key: "status", label: "Status", format: "status" },
      { key: "published_at", label: "Published", format: "datetime" },
      { key: "is_featured", label: "Featured", format: "boolean" },
      { key: "tags", label: "Tags" },
    ],
    manageFields: [
      { key: "slug", label: "Slug" },
      { key: "updated_at", label: "Updated", format: "datetime" },
      { key: "version", label: "Version" },
      { key: "citations", label: "Citations", format: "json" },
    ],
  },
  content: {
    noun: "Article",
    titleKey: "title",
    hideEmpty: true,
    managePermission: "content.edit",
    fields: [
      { key: "excerpt", label: "Summary" },
      { key: "status", label: "Status", format: "status" },
      { key: "published_at", label: "Published", format: "datetime" },
      { key: "is_featured", label: "Featured", format: "boolean" },
      { key: "tags", label: "Tags" },
    ],
    manageFields: [
      { key: "slug", label: "Slug" },
      { key: "updated_at", label: "Updated", format: "datetime" },
      { key: "version", label: "Version" },
    ],
  },
  announcements: {
    noun: "Announcement",
    titleKey: "title",
    hideEmpty: true,
    managePermission: "content.edit",
    fields: [
      { key: "content_html", label: "Message", format: "richtext" },
      { key: "priority", label: "Priority", format: "status" },
      { key: "status", label: "Status", format: "status" },
      { key: "published_at", label: "Published", format: "datetime" },
      { key: "expires_at", label: "Expires", format: "datetime" },
    ],
    manageFields: [
      { key: "audiences", label: "Audience" },
      { key: "version", label: "Version" },
    ],
  },
  events: {
    noun: "Event",
    titleKey: "title",
    hideEmpty: true,
    managePermission: "events.manage",
    fields: [
      {
        key: "when",
        label: "When",
        compose: ["start_date", "start_time", "end_date", "end_time", "timezone"],
      },
      { key: "event_type", label: "Type", format: "status" },
      { key: "status", label: "Status", format: "status" },
      { key: "short_description", label: "Summary" },
      { key: "description_html", label: "Description", format: "richtext" },
      { key: "venue", label: "Venue" },
      { key: "address", label: "Address" },
      { key: "is_online", label: "Online", format: "boolean" },
      { key: "registration_required", label: "Registration required", format: "boolean" },
      { key: "registered", label: "You are registered", format: "boolean" },
      { key: "registrations", label: "Registrations" },
    ],
    manageFields: [
      { key: "slug", label: "Slug" },
      { key: "publication_status", label: "Publication", format: "status" },
      { key: "published_at", label: "Publish at", format: "datetime" },
      { key: "online_platform", label: "Platform" },
      { key: "online_link", label: "Online link" },
      { key: "access_code", label: "Access code" },
      { key: "max_participants", label: "Capacity" },
      { key: "expected_participants", label: "Expected" },
      { key: "cpd_credits", label: "CPD credits" },
      { key: "registration_deadline", label: "Registration deadline", format: "datetime" },
      { key: "registration_url", label: "External registration" },
      { key: "organizer", label: "Organizer", format: "json" },
      { key: "speakers", label: "Speakers", format: "json" },
      { key: "schedule", label: "Schedule", format: "json" },
      { key: "version", label: "Version" },
    ],
  },
  documents: {
    noun: "Document",
    titleKey: "title",
    hideEmpty: true,
    managePermission: "documents.manage",
    fields: [
      { key: "public_id", label: "Reference" },
      { key: "category", label: "Category", format: "status" },
      { key: "status", label: "Status", format: "status" },
      { key: "document_date", label: "Document date", format: "date" },
      { key: "sender", label: "Sender" },
      { key: "receiver", label: "Receiver" },
      { key: "description_html", label: "Summary", format: "richtext" },
      { key: "version", label: "Version" },
    ],
    manageFields: [
      { key: "audiences", label: "Audiences" },
      { key: "retention_class", label: "Retention" },
      { key: "legal_hold", label: "Legal hold", format: "boolean" },
      { key: "updated_at", label: "Updated", format: "datetime" },
    ],
  },
  media: {
    noun: "File",
    titleKey: "original_filename",
    hideEmpty: true,
    managePermission: "media.manage",
    staffPermission: "settings.manage",
    fields: [
      { key: "content_type", label: "Type" },
      { key: "byte_size", label: "Size" },
      { key: "status", label: "Status", format: "status" },
      { key: "is_private", label: "Private", format: "boolean" },
      { key: "created_at", label: "Uploaded", format: "datetime" },
    ],
    manageFields: [
      { key: "scan_status", label: "Scan status", format: "status" },
      { key: "scan_result", label: "Scan result" },
      { key: "usage_count", label: "Linked uses" },
    ],
    staffFields: [
      { key: "storage_key", label: "Storage key" },
      { key: "sha256", label: "Checksum" },
    ],
  },
  galleries: {
    noun: "Gallery",
    titleKey: "title",
    hideEmpty: true,
    managePermission: "content.edit",
    fields: [
      { key: "description", label: "Description", format: "richtext" },
      { key: "status", label: "Status", format: "status" },
      { key: "published_at", label: "Published", format: "datetime" },
      { key: "items", label: "Images" },
      { key: "external_album_url", label: "External album" },
    ],
    manageFields: [
      { key: "slug", label: "Slug" },
      { key: "updated_at", label: "Updated", format: "datetime" },
    ],
  },
  carousel: {
    noun: "Slide",
    titleKey: "title",
    hideEmpty: true,
    managePermission: "settings.manage",
    fields: [
      { key: "description", label: "Description", format: "richtext" },
      { key: "link_url", label: "Link" },
      { key: "order", label: "Order" },
      { key: "is_published", label: "Published", format: "boolean" },
      { key: "media_name", label: "Image" },
    ],
    manageFields: [
      { key: "starts_at", label: "Starts", format: "datetime" },
      { key: "ends_at", label: "Ends", format: "datetime" },
    ],
  },
  adverts: {
    noun: "Campaign",
    titleKey: "title",
    hideEmpty: true,
    managePermission: "adverts.manage",
    fields: [
      { key: "placement_name", label: "Placement" },
      { key: "advertiser_name", label: "Advertiser" },
      { key: "fulfilment", label: "Fulfilment", format: "status" },
      { key: "status", label: "Status", format: "status" },
      { key: "starts_at", label: "Starts", format: "datetime" },
      { key: "ends_at", label: "Ends", format: "datetime" },
      { key: "impressions", label: "Impressions" },
      { key: "clicks", label: "Clicks" },
    ],
    manageFields: [
      { key: "is_house_ad", label: "House ad", format: "boolean" },
      { key: "target_url", label: "Target URL" },
      { key: "order_id", label: "Order reference" },
    ],
  },
  "advert-slots": {
    noun: "Placement",
    titleKey: "name",
    hideEmpty: true,
    managePermission: "adverts.manage",
    fields: [
      { key: "key", label: "Key" },
      { key: "location", label: "Site location" },
      { key: "size", label: "Size" },
      { key: "width", label: "Width" },
      { key: "height", label: "Height" },
      { key: "description", label: "Description" },
      { key: "is_active", label: "Active", format: "boolean" },
    ],
  },
  "advert-plans": {
    noun: "Plan",
    titleKey: "name",
    hideEmpty: true,
    managePermission: "adverts.manage",
    fields: [
      { key: "placement_name", label: "Placement" },
      { key: "price", label: "Price" },
      { key: "duration_days", label: "Duration (days)" },
      { key: "description", label: "Description" },
      { key: "is_active", label: "Active", format: "boolean" },
    ],
  },
  "advert-orders": {
    noun: "Order",
    titleKey: "advertiser_name",
    hideEmpty: true,
    managePermission: "adverts.manage",
    fields: [
      { key: "plan_name", label: "Plan" },
      { key: "campaign_title", label: "Campaign" },
      { key: "status", label: "Status", format: "status" },
      { key: "payment_status", label: "Payment", format: "status" },
      { key: "starts_on", label: "Starts", format: "date" },
      { key: "ends_on", label: "Ends", format: "date" },
      { key: "notes", label: "Notes" },
    ],
    manageFields: [
      { key: "price", label: "Price" },
      { key: "created_at", label: "Created", format: "datetime" },
    ],
  },
  "advert-advertisers": {
    noun: "Client",
    titleKey: "organization_name",
    hideEmpty: true,
    managePermission: "adverts.manage",
    fields: [
      { key: "contact_name", label: "Contact" },
      { key: "email", label: "Email" },
      { key: "phone", label: "Phone" },
      { key: "is_active", label: "Active", format: "boolean" },
    ],
    manageFields: [
      { key: "notes", label: "Notes" },
      { key: "created_at", label: "Created", format: "datetime" },
    ],
  },
  analytics: {
    noun: "Metric",
    titleKey: "key",
    hideEmpty: true,
    fields: [
      { key: "group", label: "Group", format: "status" },
      { key: "value", label: "Value" },
      { key: "period", label: "Period" },
      { key: "description", label: "Description" },
    ],
  },
  audit: {
    noun: "Audit entry",
    titleKey: "action",
    hideEmpty: true,
    managePermission: "audit.view",
    staffPermission: "settings.manage",
    fields: [
      { key: "actor_name", label: "Actor" },
      { key: "resource_type", label: "Resource", format: "status" },
      { key: "outcome", label: "Outcome", format: "status" },
      { key: "created_at", label: "Time", format: "datetime" },
    ],
    manageFields: [
      { key: "ip_address", label: "IP address" },
      { key: "user_agent", label: "User agent" },
      { key: "request_id", label: "Request ID" },
    ],
    staffFields: [
      { key: "resource_id", label: "Resource ID" },
      { key: "metadata", label: "Metadata", format: "json" },
    ],
  },
  settings: {
    noun: "Setting",
    titleKey: "key",
    hideEmpty: true,
    managePermission: "settings.manage",
    fields: [
      { key: "value", label: "Value", format: "json" },
      { key: "is_public", label: "Public", format: "boolean" },
      { key: "description", label: "Description" },
    ],
    manageFields: [{ key: "updated_at", label: "Updated", format: "datetime" }],
  },
  "feature-flags": {
    noun: "Feature",
    titleKey: "key",
    hideEmpty: true,
    managePermission: "settings.manage",
    fields: [
      { key: "description", label: "Description" },
      { key: "enabled", label: "Enabled", format: "boolean" },
    ],
    manageFields: [{ key: "rules", label: "Rules", format: "json" }],
  },
  jobs: {
    noun: "Job",
    titleKey: "kind",
    hideEmpty: true,
    managePermission: "jobs.manage",
    staffPermission: "settings.manage",
    fields: [
      { key: "status", label: "Status", format: "status" },
      { key: "progress", label: "Progress" },
      { key: "created_at", label: "Created", format: "datetime" },
      { key: "error_message", label: "Issue" },
    ],
    staffFields: [
      { key: "id", label: "Job ID" },
      { key: "payload", label: "Payload", format: "json" },
    ],
  },
};

export function attachWorkspaceDetails(
  workspaces: Record<string, { detail?: WorkspaceDetailConfig }>,
) {
  for (const [key, detail] of Object.entries(workspaceDetails)) {
    if (workspaces[key]) {
      workspaces[key].detail = detail;
    }
  }
}
