"use client";

import { motion, useReducedMotion } from "motion/react";

const points = [18, 26, 22, 39, 31, 47, 44, 61, 52, 69, 63, 78, 71, 86];

export function PulseVisual() {
  const reduced = useReducedMotion();
  const path = points.map((point, index) => `${index ? "L" : "M"}${index * 42},${100 - point}`).join(" ");
  return (
    <div className="relative h-64 overflow-hidden rounded-[1.5rem] border border-white/10 bg-white/[.045] p-5 sm:h-72 sm:p-7">
      <div className="absolute inset-0 hairline-grid opacity-15" />
      <div className="relative flex items-start justify-between">
        <div>
          <p className="eyebrow text-gold">Association pulse</p>
          <p className="mt-2 text-sm text-white/55">A living view of member activity</p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-1 text-[.66rem] font-bold text-emerald-200">
          <span className="size-1.5 animate-pulse rounded-full bg-emerald-300" /> Live
        </span>
      </div>
      <svg className="absolute right-5 bottom-4 left-5 h-36 w-[calc(100%-2.5rem)] overflow-visible" viewBox="0 0 546 110" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <linearGradient id="pulse-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#d5a82a" stopOpacity=".35" />
            <stop offset="1" stopColor="#d5a82a" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={`${path} L546,110 L0,110 Z`} fill="url(#pulse-fill)" />
        <motion.path
          d={path}
          fill="none"
          stroke="#e4bf58"
          strokeWidth="3"
          strokeLinecap="round"
          initial={reduced ? undefined : { pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={{ duration: 1.5, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute right-7 bottom-6 flex items-end gap-5 text-right">
        <div><span className="block text-2xl font-black text-white">1,240</span><span className="text-[.65rem] text-white/45">engagements</span></div>
        <div><span className="block text-2xl font-black text-white">+18%</span><span className="text-[.65rem] text-white/45">this month</span></div>
      </div>
    </div>
  );
}
