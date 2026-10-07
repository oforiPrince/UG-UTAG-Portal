import { humanize } from "./utils";

export type PublicDocument = {
  id: string;
  public_id?: string;
  title: string;
  sender: string | null;
  receiver: string | null;
  description_html: string;
  document_date: string | null;
  filename: string;
  content_type: string;
  byte_size: number;
  content_url?: string;
  download_url: string;
  files: {
    media_asset_id: string;
    filename: string;
    content_type: string;
    byte_size: number;
    content_url?: string;
    download_url: string;
  }[];
};

export type MemberDocument = {
  id: string;
  public_id: string;
  title: string;
  category: string;
  sender: string | null;
  receiver: string | null;
  description_html: string;
  document_date: string | null;
  status: string;
  audiences: { type: string; value: string }[];
  retention_class: string | null;
  legal_hold: boolean;
  version: number;
  files: {
    media_asset_id: string;
    filename: string;
    content_type: string;
    byte_size: number;
    content_url: string;
  }[];
};

export type DocumentPreviewFile = {
  id: string;
  filename: string;
  contentType: string;
  byteSize: number;
  contentUrl: string;
};

export type DocumentPreviewData = {
  id: string;
  reference: string;
  title: string;
  sender: string | null;
  receiver: string | null;
  descriptionHtml: string;
  documentDate: string | null;
  files: DocumentPreviewFile[];
  details: { label: string; value: string }[];
};

export type DocumentPreviewKind =
  "image" | "pdf" | "text" | "office" | "unknown";

export function documentPreviewKind(contentType: string): DocumentPreviewKind {
  if (contentType.startsWith("image/")) return "image";
  if (contentType === "application/pdf") return "pdf";
  if (contentType.startsWith("text/")) return "text";
  if (contentType.includes("officedocument")) return "office";
  return "unknown";
}

export function fileSize(bytes: number) {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function audienceLabel(audience: { type: string; value: string }) {
  if (audience.type === "general_public") return "General public";
  if (audience.type === "all_members" || audience.type === "everyone") {
    return "All members";
  }
  if (audience.type === "role") return humanize(audience.value);
  return `${humanize(audience.type)} · ${audience.value}`;
}

export function publicDocumentPreview(
  document: PublicDocument,
): DocumentPreviewData {
  return {
    id: document.id,
    reference: document.public_id ?? "",
    title: document.title,
    sender: document.sender,
    receiver: document.receiver,
    descriptionHtml: document.description_html,
    documentDate: document.document_date,
    files: document.files.map((file) => ({
      id: file.media_asset_id,
      filename: file.filename,
      contentType: file.content_type,
      byteSize: file.byte_size,
      contentUrl: file.content_url ?? file.download_url,
    })),
    details: [],
  };
}

export function memberDocumentPreview(
  document: MemberDocument,
): DocumentPreviewData {
  return {
    id: document.id,
    reference: document.public_id,
    title: document.title,
    sender: document.sender,
    receiver: document.receiver,
    descriptionHtml: document.description_html,
    documentDate: document.document_date,
    files: document.files.map((file) => ({
      id: file.media_asset_id,
      filename: file.filename,
      contentType: file.content_type,
      byteSize: file.byte_size,
      contentUrl: file.content_url,
    })),
    details: [
      { label: "Category", value: humanize(document.category) },
      { label: "Workflow", value: humanize(document.status) },
      {
        label: "Visible to",
        value:
          document.audiences.map(audienceLabel).join(", ") || "All members",
      },
      { label: "Version", value: String(document.version) },
      ...(document.retention_class
        ? [{ label: "Retention class", value: document.retention_class }]
        : []),
      ...(document.legal_hold
        ? [{ label: "Legal hold", value: "Enabled" }]
        : []),
    ],
  };
}
