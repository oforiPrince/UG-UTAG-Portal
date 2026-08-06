"use client";

import { format } from "date-fns";
import {
  ArrowLeft,
  ArrowUpRight,
  Download,
  Eye,
  FileImage,
  FileSpreadsheet,
  FileText,
  LoaderCircle,
  Presentation,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import type {
  PDFDocumentLoadingTask,
  PDFDocumentProxy,
  RenderTask,
} from "pdfjs-dist";

import { Button } from "@/components/ui/button";
import {
  type DocumentPreviewData,
  type DocumentPreviewFile,
  documentPreviewKind,
  fileSize,
} from "@/lib/documents";
import { humanize } from "@/lib/utils";

function FileIcon({ contentType }: { contentType: string }) {
  const kind = documentPreviewKind(contentType);
  if (kind === "image") return <FileImage className="size-5" />;
  if (contentType.includes("spreadsheet")) {
    return <FileSpreadsheet className="size-5" />;
  }
  if (contentType.includes("presentation")) {
    return <Presentation className="size-5" />;
  }
  return <FileText className="size-5" />;
}

function PdfPage({
  document,
  pageNumber,
}: {
  document: PDFDocumentProxy;
  pageNumber: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let renderTask: RenderTask | undefined;
    let disposed = false;
    void document
      .getPage(pageNumber)
      .then((page) => {
        if (disposed || !canvasRef.current || !containerRef.current) return;
        const unscaled = page.getViewport({ scale: 1 });
        const availableWidth = Math.max(
          240,
          Math.min(1100, containerRef.current.clientWidth - 24),
        );
        const viewport = page.getViewport({
          scale: availableWidth / unscaled.width,
        });
        const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
        const canvas = canvasRef.current;
        canvas.width = Math.floor(viewport.width * pixelRatio);
        canvas.height = Math.floor(viewport.height * pixelRatio);
        canvas.style.width = `${viewport.width}px`;
        canvas.style.height = `${viewport.height}px`;
        renderTask = page.render({
          canvas,
          viewport,
          transform:
            pixelRatio === 1 ? undefined : [pixelRatio, 0, 0, pixelRatio, 0, 0],
        });
        return renderTask.promise;
      })
      .catch((reason: unknown) => {
        if (disposed || reason instanceof DOMException) return;
        setError(
          reason instanceof Error
            ? reason.message
            : "This page could not be rendered",
        );
      });
    return () => {
      disposed = true;
      renderTask?.cancel();
    };
  }, [document, pageNumber]);

  return (
    <section
      ref={containerRef}
      aria-label={`Page ${pageNumber} of ${document.numPages}`}
      className="relative grid min-h-56 place-items-center overflow-hidden sm:min-h-80"
    >
      {error ? (
        <p className="max-w-prose p-6 text-center text-sm font-bold break-words text-red-700 sm:p-8">
          {error}
        </p>
      ) : (
        <canvas
          ref={canvasRef}
          className="h-auto max-w-full bg-white shadow-[0_8px_30px_rgb(23_43_69_/_18%)]"
        />
      )}
      <span className="absolute right-3 bottom-3 rounded-full bg-[#172f4d] px-3 py-1 text-[.62rem] font-bold text-white shadow-sm sm:right-4 sm:bottom-4">
        {pageNumber} / {document.numPages}
      </span>
    </section>
  );
}

function PdfViewer({ data, filename }: { data: Uint8Array; filename: string }) {
  const [document, setDocument] = useState<PDFDocumentProxy>();
  const [error, setError] = useState("");

  useEffect(() => {
    let loadingTask: PDFDocumentLoadingTask | undefined;
    let disposed = false;
    void import("@/lib/pdfjs")
      .then((pdfjs) => {
        if (disposed) return;
        loadingTask = pdfjs.getDocument({ data });
        return loadingTask.promise;
      })
      .then((nextDocument) => {
        if (!nextDocument || disposed) return;
        setDocument(nextDocument);
      })
      .catch((reason: unknown) => {
        if (disposed) return;
        setError(
          reason instanceof Error
            ? reason.message
            : "The PDF could not be opened",
        );
      });
    return () => {
      disposed = true;
      void loadingTask?.destroy();
    };
  }, [data]);

  if (error) {
    return (
      <div className="grid min-h-[34rem] place-items-center px-6 text-center">
        <div>
          <FileText className="mx-auto size-10 text-muted" />
          <p className="mt-4 text-sm font-bold text-ink">{error}</p>
        </div>
      </div>
    );
  }
  if (!document) {
    return (
      <div className="grid min-h-[34rem] place-items-center">
        <LoaderCircle
          className="size-7 animate-spin text-coral"
          aria-label={`Rendering ${filename}`}
        />
      </div>
    );
  }

  return (
    <div className="grid gap-4 bg-[#dfe5eb] p-3 sm:gap-5 sm:p-6">
      {Array.from({ length: document.numPages }, (_, index) => (
        <PdfPage
          key={`${document.fingerprints[0]}-${index + 1}`}
          document={document}
          pageNumber={index + 1}
        />
      ))}
    </div>
  );
}

function FileViewer({ file }: { file: DocumentPreviewFile }) {
  const kind = documentPreviewKind(file.contentType);
  const [pdfData, setPdfData] = useState<Uint8Array>();
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(kind === "pdf" || kind === "text");

  useEffect(() => {
    if (kind !== "pdf" && kind !== "text") return;

    const controller = new AbortController();
    void fetch(file.contentUrl, {
      credentials: "include",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("The file could not be loaded");
        const blob = await response.blob();
        if (controller.signal.aborted) return;
        if (kind === "text") {
          const content = await blob.text();
          if (!controller.signal.aborted) setText(content);
        } else {
          setPdfData(new Uint8Array(await blob.arrayBuffer()));
        }
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          reason instanceof Error
            ? reason.message
            : "The file could not be loaded",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [file.contentUrl, kind]);

  if (loading) {
    return (
      <div className="grid min-h-[34rem] place-items-center bg-[#f4f7fa]">
        <div className="text-center text-sm font-semibold text-muted">
          <LoaderCircle
            className="mx-auto mb-3 size-7 animate-spin text-coral"
            aria-hidden="true"
          />
          Preparing the full preview…
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="grid min-h-[34rem] place-items-center bg-[#f4f7fa] px-6 text-center">
        <div>
          <FileText className="mx-auto size-10 text-muted" />
          <p className="mt-4 text-sm font-bold text-ink">{error}</p>
          <p className="mt-2 text-xs leading-5 text-muted">
            Open the original file to view its complete contents.
          </p>
        </div>
      </div>
    );
  }

  if (kind === "image") {
    return (
      <div className="relative min-h-[34rem] bg-[#eef2f6]">
        <Image
          fill
          unoptimized
          src={file.contentUrl}
          alt={`Full preview of ${file.filename}`}
          className="object-contain p-3"
          sizes="(max-width: 1024px) 100vw, 70vw"
        />
      </div>
    );
  }

  if (kind === "pdf" && pdfData) {
    return <PdfViewer data={pdfData} filename={file.filename} />;
  }

  if (kind === "text") {
    return (
      <pre className="min-h-[34rem] overflow-auto bg-white p-6 text-xs leading-6 whitespace-pre-wrap text-ink sm:p-8">
        {text}
      </pre>
    );
  }

  return (
    <div className="grid min-h-[34rem] place-items-center bg-[#f4f7fa] px-6 text-center">
      <div className="max-w-md">
        <FileIcon contentType={file.contentType} />
        <h3 className="mt-4 text-xl font-black text-[#172f4d]">
          Preview this file in a compatible viewer
        </h3>
        <p className="mt-3 text-sm leading-6 text-muted">
          This document format opens in your browser or installed office
          application so every page, sheet, or slide remains available.
        </p>
        <Button asChild className="mt-6 rounded-md">
          <a href={file.contentUrl} target="_blank" rel="noreferrer">
            <ArrowUpRight className="size-4" /> Open full document
          </a>
        </Button>
      </div>
    </div>
  );
}

export function DocumentPreview({
  document,
  backHref,
  backLabel,
  privateView = false,
  embedded = false,
  onBack,
}: {
  document: DocumentPreviewData;
  backHref?: string;
  backLabel?: string;
  privateView?: boolean;
  /** Compact chrome for the workspace details drawer. */
  embedded?: boolean;
  onBack?: () => void;
}) {
  const [selectedId, setSelectedId] = useState(document.files[0]?.id ?? "");
  const selectedFile = useMemo(
    () =>
      document.files.find((file) => file.id === selectedId) ??
      document.files[0],
    [document.files, selectedId],
  );
  const metadata = [
    ...(privateView
      ? [{ label: "Reference", value: document.reference }]
      : []),
    ...(document.documentDate
      ? [
          {
            label: "Document date",
            value: format(new Date(document.documentDate), "d MMMM yyyy"),
          },
        ]
      : []),
    ...(document.sender ? [{ label: "Sender", value: document.sender }] : []),
    ...(document.receiver
      ? [{ label: "Receiver", value: document.receiver }]
      : []),
    ...document.details,
  ];

  const backControl = onBack ? (
    <Button
      size="sm"
      variant="outline"
      className="shrink-0 border-white/25 bg-transparent text-white hover:bg-white/10 hover:text-white"
      onClick={onBack}
    >
      <ArrowLeft className="size-4" /> {backLabel ?? "Back"}
    </Button>
  ) : backHref ? (
    <Button
      asChild
      size="sm"
      variant="outline"
      className="shrink-0 border-white/25 bg-transparent text-white hover:bg-white/10 hover:text-white"
    >
      <Link href={backHref}>
        <ArrowLeft className="size-4" /> {backLabel ?? "Back"}
      </Link>
    </Button>
  ) : null;

  return (
    <article
      className={`min-w-0 overflow-hidden rounded-md border border-line bg-white ${
        embedded
          ? "shadow-none"
          : "shadow-[0_18px_55px_rgb(23_43_69_/_10%)]"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 bg-[#172f4d] px-4 py-4 text-white sm:px-7">
        <div className="min-w-0">
          <p className="text-[.63rem] font-black tracking-[.14em] text-gold uppercase">
            {privateView
              ? "Protected member preview"
              : "Read online"}
          </p>
          <p className="mt-1 text-xs text-white/65">
            {document.files.length} file{document.files.length === 1 ? "" : "s"}{" "}
            · {privateView ? "Full content" : "No download required"}
          </p>
        </div>
        {backControl}
      </div>

      <header
        className={`border-b border-line px-4 sm:px-9 ${
          embedded ? "py-5 sm:py-6" : "py-6 sm:py-10"
        }`}
      >
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 max-w-4xl">
            {privateView ? (
              <p className="text-[.65rem] font-black tracking-[.12em] break-all text-coral uppercase">
                {document.reference}
              </p>
            ) : null}
            <h1
              className={`display-type leading-tight break-words text-[#172f4d] ${
                embedded
                  ? "text-2xl sm:text-3xl"
                  : "text-[1.85rem] sm:text-5xl"
              } ${privateView ? "mt-3" : ""}`}
            >
              {document.title}
            </h1>
          </div>
          {selectedFile ? (
            <div className="flex w-full min-w-0 flex-wrap gap-2 sm:w-auto sm:justify-end">
              <Button
                asChild
                size="sm"
                variant="outline"
                className="min-w-0 flex-1 rounded-md sm:flex-none"
              >
                <a
                  href={selectedFile.contentUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  <ArrowUpRight className="size-4 shrink-0" /> Open
                </a>
              </Button>
              <Button
                asChild
                size="sm"
                className="min-w-0 flex-1 rounded-md sm:flex-none"
              >
                <a
                  href={selectedFile.contentUrl}
                  download={selectedFile.filename}
                >
                  <Download className="size-4 shrink-0" /> Download
                </a>
              </Button>
            </div>
          ) : null}
        </div>
        {document.descriptionHtml ? (
          <div
            className="prose mt-5 max-w-4xl text-sm leading-7 break-words text-muted sm:mt-6 prose-headings:text-[#172f4d] prose-a:text-coral"
            dangerouslySetInnerHTML={{ __html: document.descriptionHtml }}
          />
        ) : null}
      </header>

      <div className="grid min-w-0 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
        <aside className="min-w-0 border-b border-line bg-[#f8fafc] p-4 sm:p-7 lg:border-r lg:border-b-0">
          <section aria-labelledby={`document-${document.id}-files`}>
            <h2
              id={`document-${document.id}-files`}
              className="text-[.65rem] font-black tracking-[.12em] text-muted uppercase"
            >
              Document files
            </h2>
            <div className="mt-4 grid min-w-0 gap-2">
              {document.files.map((file, index) => {
                const selected = file.id === selectedFile?.id;
                return (
                  <button
                    key={file.id}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => setSelectedId(file.id)}
                    className={`flex min-h-16 w-full min-w-0 items-start gap-3 overflow-hidden rounded-md border px-3 py-2.5 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-coral ${
                      selected
                        ? "border-coral bg-white text-[#172f4d] shadow-sm"
                        : "border-line bg-transparent text-muted hover:border-coral/40 hover:bg-white"
                    }`}
                  >
                    <span
                      className={`mt-0.5 grid size-9 shrink-0 place-items-center rounded-full ${
                        selected ? "bg-coral/10 text-coral" : "bg-[#e9eef4]"
                      }`}
                    >
                      <FileIcon contentType={file.contentType} />
                    </span>
                    <span className="min-w-0 flex-1 overflow-hidden">
                      <span className="block text-xs font-black leading-snug break-all [overflow-wrap:anywhere]">
                        {index + 1}. {file.filename}
                      </span>
                      <span className="mt-1 block text-[.62rem] font-semibold">
                        {humanize(file.contentType.split("/").at(-1) ?? "file")}{" "}
                        · {fileSize(file.byteSize)}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </section>

          <section
            className="mt-8 border-t border-line pt-6"
            aria-label="Document details"
          >
            <h2 className="text-[.65rem] font-black tracking-[.12em] text-muted uppercase">
              Document details
            </h2>
            <dl className="mt-4 grid min-w-0 gap-4">
              {metadata.map((item) => (
                <div key={item.label} className="min-w-0">
                  <dt className="text-[.6rem] font-bold tracking-wide text-muted uppercase">
                    {item.label}
                  </dt>
                  <dd className="mt-1 break-words text-xs font-bold leading-5 text-[#172f4d] [overflow-wrap:anywhere]">
                    {item.value}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        </aside>

        <section aria-label="Selected file preview" className="min-w-0">
          {selectedFile ? (
            <>
              <div className="border-b border-line px-4 py-3 sm:px-6">
                <div className="min-w-0">
                  <p className="flex min-w-0 items-start gap-2 text-xs font-black text-[#172f4d]">
                    <Eye className="mt-0.5 size-4 shrink-0 text-coral" />
                    <span className="min-w-0 break-all [overflow-wrap:anywhere]">
                      {selectedFile.filename}
                    </span>
                  </p>
                  <p className="mt-1 text-[.62rem] font-semibold text-muted">
                    Scroll inside the preview to read the complete file.
                  </p>
                </div>
              </div>
              <div className="min-w-0 overflow-x-auto">
                <FileViewer
                  key={`${selectedFile.id}-${selectedFile.contentUrl}`}
                  file={selectedFile}
                />
              </div>
            </>
          ) : (
            <div className="grid min-h-[24rem] place-items-center bg-[#f4f7fa] px-6 text-center sm:min-h-[34rem]">
              <div>
                <FileText className="mx-auto size-10 text-muted" />
                <p className="mt-4 text-sm font-bold">
                  No preview file is attached.
                </p>
              </div>
            </div>
          )}
        </section>
      </div>
    </article>
  );
}
