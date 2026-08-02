declare module "pdfjs-dist/webpack.mjs" {
  export * from "pdfjs-dist";
}

declare module "pdfjs-dist/legacy/build/pdf.mjs" {
  export * from "pdfjs-dist";
}

declare module "pdfjs-dist/legacy/build/pdf.worker.min.mjs" {
  const worker: Worker;
  export default worker;
}
