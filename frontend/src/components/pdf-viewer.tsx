import { useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import {
  ChevronLeft,
  ChevronRight,
  Loader2,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { Button } from "./ui/button";
import { getToken } from "@/lib/api";

// Configure worker for Vite
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PDFViewerProps {
  url: string;
}

export function PDFViewer({ url }: PDFViewerProps) {
  const [numPages, setNumPages] = useState<number>();
  const [pageNumber, setPageNumber] = useState<number>(1);
  const [scale, setScale] = useState<number>(1.0);

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
    setPageNumber(1);
  }

  const handleZoomIn = () => setScale((prev) => Math.min(prev + 0.2, 3.0));
  const handleZoomOut = () => setScale((prev) => Math.max(prev - 0.2, 0.5));
  const prevPage = () => setPageNumber((prev) => Math.max(prev - 1, 1));
  const nextPage = () =>
    setPageNumber((prev) => Math.min(prev + 1, numPages || 1));

  return (
    <div className="flex h-full flex-col overflow-hidden bg-muted/30">
      <div className="flex items-center justify-between border-b border-border bg-card px-4 py-2 shadow-sm">
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="icon"
            onClick={prevPage}
            disabled={pageNumber <= 1}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-xs text-muted-foreground w-20 text-center font-medium">
            {pageNumber} / {numPages || "?"}
          </span>
          <Button
            variant="outline"
            size="icon"
            onClick={nextPage}
            disabled={pageNumber >= (numPages || 1)}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={handleZoomOut}>
            <ZoomOut className="h-4 w-4" />
          </Button>
          <span className="text-xs text-muted-foreground font-mono w-12 text-center">
            {Math.round(scale * 100)}%
          </span>
          <Button variant="ghost" size="icon" onClick={handleZoomIn}>
            <ZoomIn className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4 flex justify-center">
        <Document
          file={{
            url,
            headers: {
              Authorization: `Bearer ${getToken()}`,
            },
          }}
          onLoadSuccess={onDocumentLoadSuccess}
          loading={
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          }
          error={
            <div className="flex h-64 items-center justify-center text-sm text-danger">
              Failed to load PDF.
            </div>
          }
          className="shadow-xl"
        >
          <Page
            pageNumber={pageNumber}
            scale={scale}
            renderTextLayer={true}
            renderAnnotationLayer={true}
            className="rounded bg-white"
          />
        </Document>
      </div>
    </div>
  );
}
