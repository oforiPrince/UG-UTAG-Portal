import { PollBuilderClient } from "../../poll-builder-client";

export default async function EditPollPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <PollBuilderClient pollId={id} />;
}
