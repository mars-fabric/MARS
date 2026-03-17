"use client";

import { useState, useEffect, useRef } from "react";
import { Terminal, Download, Copy, Check, AlertCircle, Loader2 } from "lucide-react";

interface SessionConsoleTabProps {
  runId: string;
}

export function SessionConsoleTab({ runId }: SessionConsoleTabProps) {
  const [content, setContent] = useState<string>("");
  const [totalLines, setTotalLines] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const scrollRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    fetch(`/api/runs/${runId}/console-log`)
      .then((r) => {
        if (!r.ok) {
          if (r.status === 404) throw new Error("No console log available for this run");
          throw new Error(`Failed to fetch console log (${r.status})`);
        }
        return r.json();
      })
      .then((data) => {
        setContent(data.content || "");
        setTotalLines(data.total_lines || 0);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [runId]);

  const handleCopy = () => {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `console_${runId}.log`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        <Loader2 className="h-6 w-6 animate-spin mr-2" />
        <span>Loading console log...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        <div className="text-center">
          <AlertCircle className="w-10 h-10 mx-auto mb-3 text-gray-500" />
          <p className="text-sm">{error}</p>
          <p className="text-xs text-gray-500 mt-1">
            Check the Conversation tab for agent messages instead.
          </p>
        </div>
      </div>
    );
  }

  if (!content) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        <div className="text-center">
          <Terminal className="w-10 h-10 mx-auto mb-3 text-gray-500" />
          <p className="text-sm">Console log is empty</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700 flex-shrink-0">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Terminal className="w-4 h-4" />
          <span>{totalLines} lines</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleCopy}
            className="p-1.5 text-gray-400 hover:text-white transition-colors rounded"
            title="Copy to clipboard"
          >
            {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
          </button>
          <button
            onClick={handleDownload}
            className="p-1.5 text-gray-400 hover:text-white transition-colors rounded"
            title="Download log"
          >
            <Download className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Content */}
      <pre
        ref={scrollRef}
        className="flex-1 overflow-auto p-3 text-xs font-mono text-gray-300 whitespace-pre-wrap break-words"
      >
        {content}
      </pre>
    </div>
  );
}
