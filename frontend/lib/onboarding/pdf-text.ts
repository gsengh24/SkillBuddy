/**
 * Reads the text of a PDF in the browser with PDF.js (ADR 0023). The file never leaves the
 * device: it is read into memory, its text is returned, and the worker is stopped. PDF.js
 * is loaded only when someone picks a file, so no other page carries it.
 */

/** The size limit shown on screen 6. */
export const PDF_MAX_BYTES = 2 * 1024 * 1024;
/** A resume is a page or two; more pages are not read. */
export const PDF_MAX_PAGES = 5;

export type PdfText = { text: string; pages: number };

export class PdfReadError extends Error {
  constructor(
    readonly reason: "too_big" | "not_pdf" | "unreadable" | "no_text",
    message: string,
  ) {
    super(message);
  }
}

export function checkPdf(file: File): void {
  if (file.size > PDF_MAX_BYTES) {
    throw new PdfReadError("too_big", "That file is over 2 MB. Try a smaller PDF.");
  }
  if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
    throw new PdfReadError("not_pdf", "Choose a PDF file.");
  }
}

export async function readPdfText(
  file: File,
  onPage: (done: number, total: number) => void = () => {},
): Promise<PdfText> {
  checkPdf(file);
  const data = new Uint8Array(await file.arrayBuffer());
  const pdfjs = await import("pdfjs-dist");
  // The worker is this site's own bundled file (CSP worker-src 'self').
  const port = new Worker(new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url), {
    type: "module",
  });
  const worker = pdfjs.PDFWorker.create({ port });
  let task: ReturnType<typeof pdfjs.getDocument> | null = null;
  try {
    task = pdfjs.getDocument({
      data,
      worker,
      // Text only: no fonts, no network, no scripts in the file.
      disableFontFace: true,
      useSystemFonts: false,
      useWorkerFetch: false,
      enableXfa: false,
      isOffscreenCanvasSupported: false,
    });
    const pdf = await task.promise.catch(() => {
      throw new PdfReadError("unreadable", "We couldn't read that PDF. Try pasting the text.");
    });
    const pages = pdf.numPages;
    const total = Math.min(pages, PDF_MAX_PAGES);
    const lines: string[] = [];
    for (let number = 1; number <= total; number++) {
      const page = await pdf.getPage(number);
      const content = await page.getTextContent();
      let line = "";
      for (const item of content.items) {
        if (!("str" in item)) continue;
        line += item.str;
        if (item.hasEOL) {
          lines.push(line);
          line = "";
        } else if (item.str && !item.str.endsWith(" ")) {
          line += " ";
        }
      }
      if (line.trim()) lines.push(line);
      onPage(number, total);
    }
    const text = lines.join("\n").trim();
    if (!text) {
      throw new PdfReadError(
        "no_text",
        "We couldn't find any text in that PDF. If it's a scan, try pasting the text instead.",
      );
    }
    return { text, pages };
  } finally {
    await task?.destroy();
    worker.destroy();
    port.terminate();
  }
}
