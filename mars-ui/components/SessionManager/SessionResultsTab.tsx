"use client";

import { useEffect, useMemo, useState } from "react";
import { FileText, Loader2, AlertCircle, Download } from "lucide-react";
import { getApiUrl } from "@/lib/config";

interface SessionResultsTabProps {
    runId: string;
}

interface RunFile {
    id: string;
    file_path: string;
    file_name: string;
    created_at: string | null;
}

export function SessionResultsTab({ runId }: SessionResultsTabProps) {
    const [files, setFiles] = useState<RunFile[]>([]);
    const [selectedFile, setSelectedFile] = useState<RunFile | null>(null);
    const [content, setContent] = useState<string>("");
    const [loadingFiles, setLoadingFiles] = useState(true);
    const [loadingContent, setLoadingContent] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchSelectedContent = async (): Promise<string | null> => {
        if (!selectedFile?.file_path) return null;
        const response = await fetch(
            getApiUrl(`/api/files/content?path=${encodeURIComponent(selectedFile.file_path)}`)
        );
        if (!response.ok) return null;
        const data = await response.json();
        return data.content || null;
    };

    const downloadMarkdown = async () => {
        if (!selectedFile) return;

        const reportContent = content || (await fetchSelectedContent());
        if (!reportContent) return;

        const blob = new Blob([reportContent], { type: "text/markdown" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = selectedFile.file_name || "session-result.md";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    };

    const downloadPdf = async () => {
        if (!selectedFile) return;

        const reportContent = content || (await fetchSelectedContent());
        if (!reportContent) return;

        try {
            const html2pdf = (await import("html2pdf.js")).default;

            const htmlContent = reportContent
                .replace(/^### (.*$)/gm, '<h3 style="color:#1a1a2e;margin-top:18px;margin-bottom:8px;">$1</h3>')
                .replace(/^## (.*$)/gm, '<h2 style="color:#16213e;margin-top:24px;margin-bottom:10px;">$1</h2>')
                .replace(/^# (.*$)/gm, '<h1 style="color:#0f3460;margin-top:30px;margin-bottom:12px;">$1</h1>')
                .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
                .replace(/\*(.*?)\*/g, "<em>$1</em>")
                .replace(/^- (.*$)/gm, '<li style="margin-left:20px;">$1</li>')
                .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" style="color:#2563eb;">$1</a>')
                .replace(/\n{2,}/g, "<br/><br/>")
                .replace(/\n/g, "<br/>");

            const wrapper = document.createElement("div");
            wrapper.innerHTML = `<div style="font-family:Arial,sans-serif;font-size:11px;line-height:1.6;color:#222;padding:20px;">${htmlContent}</div>`;

            const fileName = (selectedFile.file_name || "session-result.md").replace(/\.md$/i, ".pdf");
            const opt = {
                margin: [10, 10, 10, 10] as [number, number, number, number],
                filename: fileName,
                image: { type: "jpeg" as const, quality: 0.98 },
                html2canvas: { scale: 2 },
                jsPDF: { unit: "mm" as const, format: "a4" as const, orientation: "portrait" as const },
            };

            await html2pdf().set(opt).from(wrapper).save();
        } catch {
            // Keep UI silent on optional PDF conversion failure to avoid noisy UX.
        }
    };

    useEffect(() => {
        let ignore = false;

        const loadFiles = async () => {
            setLoadingFiles(true);
            setError(null);

            try {
                const response = await fetch(getApiUrl(`/api/runs/${runId}/files`));
                if (!response.ok) {
                    throw new Error(`Failed to fetch result files (${response.status})`);
                }

                const data = await response.json();
                const runFiles: RunFile[] = data.files || [];

                if (ignore) return;
                setFiles(runFiles);
            } catch (err) {
                if (ignore) return;
                setError(err instanceof Error ? err.message : "Failed to load result files");
            } finally {
                if (!ignore) setLoadingFiles(false);
            }
        };

        loadFiles();

        return () => {
            ignore = true;
        };
    }, [runId]);

    const candidateFiles = useMemo(() => {
        const withScore = files
            .filter((f) => /\.(md|txt|json)$/i.test(f.file_name || ""))
            .map((f) => {
                const name = (f.file_name || "").toLowerCase();
                let score = 0;
                if (name.includes("report")) score += 5;
                if (name.includes("weekly")) score += 4;
                if (name.includes("result")) score += 3;
                if (name.endsWith(".md")) score += 2;
                return { file: f, score };
            });

        return withScore
            .sort((a, b) => {
                if (b.score !== a.score) return b.score - a.score;
                const tA = a.file.created_at ? Date.parse(a.file.created_at) : 0;
                const tB = b.file.created_at ? Date.parse(b.file.created_at) : 0;
                return tB - tA;
            })
            .map((x) => x.file);
    }, [files]);

    useEffect(() => {
        if (!selectedFile && candidateFiles.length > 0) {
            setSelectedFile(candidateFiles[0]);
        }
    }, [candidateFiles, selectedFile]);

    useEffect(() => {
        let ignore = false;

        const loadContent = async () => {
            if (!selectedFile?.file_path) {
                setContent("");
                return;
            }

            setLoadingContent(true);
            try {
                const response = await fetch(
                    getApiUrl(`/api/files/content?path=${encodeURIComponent(selectedFile.file_path)}`)
                );
                if (!response.ok) {
                    throw new Error(`Failed to fetch file content (${response.status})`);
                }
                const data = await response.json();

                if (ignore) return;

                if (data.content) {
                    setContent(data.content);
                } else if (data.type === "binary") {
                    setContent("This result file is binary and cannot be previewed as text.");
                } else {
                    setContent("No preview available for this file.");
                }
            } catch (err) {
                if (!ignore) {
                    setContent(err instanceof Error ? err.message : "Failed to load result content");
                }
            } finally {
                if (!ignore) setLoadingContent(false);
            }
        };

        loadContent();

        return () => {
            ignore = true;
        };
    }, [selectedFile]);

    if (loadingFiles) {
        return (
            <div className="h-full flex items-center justify-center text-gray-400">
                <Loader2 className="w-6 h-6 animate-spin mr-2" />
                <span className="text-sm">Loading results...</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className="h-full flex items-center justify-center text-red-400">
                <div className="text-center">
                    <AlertCircle className="w-8 h-8 mx-auto mb-2" />
                    <p className="text-sm">{error}</p>
                </div>
            </div>
        );
    }

    if (candidateFiles.length === 0) {
        return (
            <div className="h-full flex items-center justify-center text-gray-400">
                <div className="text-center">
                    <FileText className="w-8 h-8 mx-auto mb-2 text-gray-500" />
                    <p className="text-sm">No result files found for this run.</p>
                    <p className="text-xs text-gray-500 mt-1">Expected: report/result markdown or text files.</p>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full grid grid-cols-[260px_1fr]">
            <div className="border-r border-gray-700 overflow-y-auto">
                {candidateFiles.map((file) => (
                    <button
                        key={file.id}
                        onClick={() => setSelectedFile(file)}
                        className={`w-full text-left px-3 py-2 text-xs border-b border-gray-800 hover:bg-gray-800 transition-colors ${selectedFile?.id === file.id ? "bg-gray-800" : ""
                            }`}
                    >
                        <div className="text-gray-200 truncate">{file.file_name}</div>
                        {file.created_at && (
                            <div className="text-gray-500 mt-0.5">{new Date(file.created_at).toLocaleString()}</div>
                        )}
                    </button>
                ))}
            </div>

            <div className="h-full overflow-auto p-3 bg-gray-900">
                <div className="flex items-center justify-between mb-3">
                    <div>
                        <h3 className="text-white text-sm font-semibold">Generated Report</h3>
                        {selectedFile?.file_path && (
                            <p className="text-gray-500 text-xs mt-0.5 truncate max-w-[680px]" title={selectedFile.file_path}>
                                {selectedFile.file_path}
                            </p>
                        )}
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={downloadMarkdown}
                            className="flex items-center gap-1 px-2.5 py-1.5 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 rounded text-xs transition-colors"
                            disabled={!selectedFile}
                        >
                            <Download className="w-3 h-3" />
                            Download MD
                        </button>
                        <button
                            onClick={downloadPdf}
                            className="flex items-center gap-1 px-2.5 py-1.5 bg-purple-500/20 hover:bg-purple-500/30 text-purple-400 rounded text-xs transition-colors"
                            disabled={!selectedFile}
                        >
                            <Download className="w-3 h-3" />
                            Download PDF
                        </button>
                    </div>
                </div>

                {loadingContent ? (
                    <div className="h-[calc(100%-38px)] flex items-center justify-center text-gray-400">
                        <Loader2 className="w-5 h-5 animate-spin mr-2" />
                        <span className="text-sm">Loading preview...</span>
                    </div>
                ) : (
                    <pre className="text-xs text-gray-300 whitespace-pre-wrap break-words font-mono leading-relaxed border border-gray-800 rounded p-3">
                        {content || "No content available."}
                    </pre>
                )}
            </div>
        </div>
    );
}
