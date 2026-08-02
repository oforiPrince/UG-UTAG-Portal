"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Point = { at: string; engagement: number; events: number; publications: number };

export function PulseChart({ data }: { data: Point[] }) {
  return <div className="h-64 w-full"><ResponsiveContainer width="100%" height="100%"><AreaChart data={data} margin={{ top: 12, right: 4, left: -28, bottom: 0 }}><defs><linearGradient id="engagement" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#dd6b4d" stopOpacity={0.35} /><stop offset="1" stopColor="#dd6b4d" stopOpacity={0} /></linearGradient><linearGradient id="events" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#5a8fb8" stopOpacity={0.25} /><stop offset="1" stopColor="#5a8fb8" stopOpacity={0} /></linearGradient></defs><CartesianGrid stroke="currentColor" strokeOpacity={0.08} vertical={false} /><XAxis dataKey="at" tickFormatter={(value: string) => new Date(value).toLocaleDateString("en-GH", { weekday: "short" })} axisLine={false} tickLine={false} fontSize={10} tickMargin={10} /><YAxis axisLine={false} tickLine={false} fontSize={10} allowDecimals={false} /><Tooltip contentStyle={{ borderRadius: 14, border: "1px solid var(--line)", background: "var(--panel)", fontSize: 12 }} labelFormatter={(value) => new Date(String(value)).toLocaleDateString("en-GH", { dateStyle: "medium" })} /><Area type="monotone" dataKey="engagement" stroke="#dd6b4d" strokeWidth={2.5} fill="url(#engagement)" /><Area type="monotone" dataKey="events" stroke="#5a8fb8" strokeWidth={2} fill="url(#events)" /></AreaChart></ResponsiveContainer></div>;
}
