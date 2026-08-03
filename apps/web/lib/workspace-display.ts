import { humanize } from "./utils";

const HUMANIZED_KEYS = new Set([
  "action",
  "category",
  "kind",
  "key",
  "outcome",
  "payment_status",
  "priority",
  "resource_type",
  "role",
  "roles",
  "status",
  "unit_type",
]);

export function shouldHumanize(key: string) {
  return (
    HUMANIZED_KEYS.has(key) ||
    key === "permissions" ||
    key.endsWith("_permissions") ||
    key.endsWith("_status") ||
    key.endsWith("_type")
  );
}

export function displayChoice(value: unknown, key = "") {
  const text = String(value);
  if (
    (key === "permissions" || key.endsWith("_permissions")) &&
    text.includes(".")
  ) {
    const [resource, capability] = text.split(".", 2);
    const subject =
      resource === "members" ? "member" : humanize(resource).toLowerCase();
    const permissionNames: Record<string, string> = {
      credentials: `Manage ${subject} credentials`,
      lifecycle: `Activate or deactivate ${subject}`,
      permissions: `Grant ${subject} permissions`,
      roles: `Assign ${subject} roles`,
    };
    return (
      permissionNames[capability] ??
      `${humanize(capability)} ${humanize(resource)}`
    );
  }
  return shouldHumanize(key) ? humanize(text) : text;
}

function formatBytes(bytes: number) {
  if (bytes === 0) return "0 bytes";
  const units = ["bytes", "KB", "MB", "GB", "TB"];
  const unit = Math.min(
    Math.floor(Math.log(Math.abs(bytes)) / Math.log(1024)),
    units.length - 1,
  );
  const amount = bytes / 1024 ** unit;
  return `${new Intl.NumberFormat("en-GH", {
    maximumFractionDigits: unit === 0 ? 0 : 1,
  }).format(amount)} ${units[unit]}`;
}

function contentTypeLabel(contentType: string) {
  const known: Record<string, string> = {
    "application/pdf": "PDF document",
    "application/msword": "Word document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
      "Word document",
    "application/vnd.ms-excel": "Excel workbook",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
      "Excel workbook",
    "application/vnd.ms-powerpoint": "PowerPoint presentation",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation":
      "PowerPoint presentation",
    "text/csv": "CSV file",
    "text/plain": "Text file",
  };
  if (known[contentType]) return known[contentType];
  if (contentType.startsWith("image/")) {
    return `${humanize(contentType.slice("image/".length))} image`;
  }
  return humanize(contentType.replace("/", " "));
}

export function display(value: unknown, key = ""): string {
  if (value == null || value === "") return "Not provided";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) {
    if (value.length === 0) return "Not provided";
    return value.length && typeof value[0] === "object"
      ? `${value.length} ${value.length === 1 ? "item" : "items"}`
      : value
          .map((item) => displayChoice(item, key))
          .join(", ");
  }
  if (typeof value === "object") {
    if (Object.keys(value).length === 0) return "Not provided";
    return Object.entries(value as Record<string, unknown>)
      .map(
        ([itemKey, item]) => `${humanize(itemKey)}: ${display(item, itemKey)}`,
      )
      .join(" · ");
  }
  if (typeof value === "string" && ["[]", "{}"].includes(value.trim())) {
    return "Not provided";
  }
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}(T|$)/.test(value)) {
    const parsed = new Date(value);
    if (!Number.isNaN(parsed.valueOf())) {
      return parsed.toLocaleString("en-GH", {
        dateStyle: "medium",
        ...(value.includes("T") ? { timeStyle: "short" } : {}),
      });
    }
  }
  if (
    (key.endsWith("_time") || key === "time") &&
    typeof value === "string" &&
    /^\d{1,2}:\d{2}(:\d{2})?$/.test(value)
  ) {
    const [hoursRaw, minutes] = value.split(":");
    const hours = Number(hoursRaw);
    const period = hours >= 12 ? "PM" : "AM";
    const hour12 = hours % 12 || 12;
    return `${hour12}:${minutes} ${period}`;
  }
  if (key === "byte_size" && typeof value === "number") {
    return formatBytes(value);
  }
  if (key === "price") {
    return new Intl.NumberFormat("en-GH", {
      style: "currency",
      currency: "GHS",
    }).format(Number(value));
  }
  if (key === "content_type" && typeof value === "string") {
    return contentTypeLabel(value);
  }
  if (typeof value === "number" && Math.abs(value) >= 1_000) {
    return new Intl.NumberFormat("en-GH").format(value);
  }
  if (
    typeof value === "string" &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      value,
    )
  ) {
    return "Internal reference";
  }
  return displayChoice(value, key);
}
