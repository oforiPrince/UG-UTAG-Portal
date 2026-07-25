export function WorkspaceRichTextValue({ html }: { html: string }) {
  if (!html.trim()) {
    return <span className="text-muted">Not provided</span>;
  }

  return (
    <div
      className="rich-text-content text-xs leading-6 text-ink"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
