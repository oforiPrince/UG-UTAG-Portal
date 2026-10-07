import { PollDetailClient } from "../poll-detail-client";

export default async function PollDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <PollDetailClient pollId={id} />;
}
