import { PollPrintClient } from "../../poll-print-client";

export default async function PollPrintPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <PollPrintClient pollId={id} />;
}
