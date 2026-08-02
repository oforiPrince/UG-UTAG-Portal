"use client";

/**
 * Legacy PDF.js build includes polyfills for APIs like
 * Map.prototype.getOrInsertComputed that modern builds assume.
 */
import { GlobalWorkerOptions } from "pdfjs-dist/legacy/build/pdf.mjs";

if (typeof window !== "undefined" && "Worker" in window) {
  GlobalWorkerOptions.workerPort = new Worker(
    new URL(
      "pdfjs-dist/legacy/build/pdf.worker.min.mjs",
      import.meta.url,
    ),
    { type: "module" },
  );
}

export * from "pdfjs-dist/legacy/build/pdf.mjs";
