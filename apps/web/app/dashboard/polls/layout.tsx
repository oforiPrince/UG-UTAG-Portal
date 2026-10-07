import type { ReactNode } from "react";

export default function PollsLayout({ children }: { children: ReactNode }) {
  return <div className="poll-workspace min-w-0">{children}</div>;
}
