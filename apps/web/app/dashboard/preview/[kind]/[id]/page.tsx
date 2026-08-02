import { ModerationPreviewClient } from "./preview-client";

export default async function ModerationPreviewPage({
  params,
}: {
  params: Promise<{ kind: string; id: string }>;
}) {
  const { kind, id } = await params;
  return <ModerationPreviewClient kind={kind} id={id} />;
}
