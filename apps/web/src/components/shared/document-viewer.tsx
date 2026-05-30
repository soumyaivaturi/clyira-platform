"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, AlertTriangle, FileText } from "lucide-react";
import { documentsApi } from "@/lib/api";

interface DocumentViewerProps {
  documentId: string;
  fileType?: string;
  className?: string;
}

export function DocumentViewer({ documentId, fileType, className }: DocumentViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [phase, setPhase] = useState<"loading" | "ready" | "error">("loading");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    const type = (fileType || "").toLowerCase();
    if (type !== "docx" && type !== "doc") {
      setErrorMsg(
        type === "pdf"
          ? "PDF preview is not yet supported here. Download the file to view it."
          : "Document preview is only available for DOCX files."
      );
      setPhase("error");
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        const { renderAsync } = await import("docx-preview");
        const res = await documentsApi.getFileBlob(documentId);
        if (cancelled || !containerRef.current) return;

        await renderAsync(res.data, containerRef.current, undefined, {
          className: "docx-viewer-page",
          inWrapper: true,
          ignoreWidth: false,
          ignoreHeight: false,
          breakPages: true,
          renderHeaders: true,
          renderFooters: true,
          renderChanges: true,
          useBase64URL: true,
        });

        if (!cancelled) setPhase("ready");
      } catch (err: any) {
        if (!cancelled) {
          setErrorMsg(err?.response?.data?.detail ?? err?.message ?? "Failed to render document.");
          setPhase("error");
        }
      }
    })();

    return () => { cancelled = true; };
  }, [documentId, fileType]);

  return (
    <div className={className}>
      {phase === "loading" && (
        <div className="flex flex-col items-center justify-center py-24 gap-3 text-muted-foreground">
          <Loader2 className="w-7 h-7 animate-spin text-primary" />
          <p className="text-sm">Rendering document…</p>
        </div>
      )}

      {phase === "error" && (
        <div className="m-6 flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-amber-800">Preview unavailable</p>
            <p className="text-xs text-amber-700 mt-0.5">{errorMsg}</p>
          </div>
        </div>
      )}

      {/* docx-preview renders into this div */}
      <div
        ref={containerRef}
        className={cn("docx-viewer-container", phase === "loading" ? "invisible h-0 overflow-hidden" : "")}
      />
    </div>
  );
}

function cn(...classes: (string | undefined | false)[]) {
  return classes.filter(Boolean).join(" ");
}
