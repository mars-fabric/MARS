"use client";

import { useEffect, useMemo, useState } from "react";
import { FileText, Loader2 } from "lucide-react";

interface SessionPlanTabProps {
    runId: string;
}

interface PlanNode {
    id: string;
    name?: string;
    goal?: string;
    status?: string;
    order_index?: number;
}

export function SessionPlanTab({ runId }: SessionPlanTabProps) {
    const [nodes, setNodes] = useState<PlanNode[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        setLoading(true);
        setError(null);

        fetch(`/api/runs/${runId}/dag`)
            .then((r) => {
                if (!r.ok) {
                    if (r.status === 404) throw new Error("No plan data for this run");
                    throw new Error(`Failed to fetch plan (${r.status})`);
                }
                return r.json();
            })
            .then((data) => {
                setNodes(Array.isArray(data.nodes) ? data.nodes : []);
            })
            .catch((err) => setError(err.message))
            .finally(() => setLoading(false));
    }, [runId]);

    const orderedNodes = useMemo(() => {
        return [...nodes].sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0));
    }, [nodes]);

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center text-gray-400">
                <Loader2 className="h-6 w-6 animate-spin mr-2" />
                <span>Loading plan...</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className="h-full flex items-center justify-center text-gray-400">
                <div className="text-center">
                    <FileText className="w-10 h-10 mx-auto mb-3 text-gray-500" />
                    <p className="text-sm">{error}</p>
                </div>
            </div>
        );
    }

    if (orderedNodes.length === 0) {
        return (
            <div className="h-full flex items-center justify-center text-gray-400">
                <div className="text-center">
                    <FileText className="w-10 h-10 mx-auto mb-3 text-gray-500" />
                    <p className="text-sm">No plan steps available</p>
                </div>
            </div>
        );
    }

    const getStatusClass = (status?: string) => {
        if (status === "completed") return "bg-green-500/10 border-green-500/30";
        if (status === "executing" || status === "running") return "bg-blue-500/10 border-blue-500/30";
        if (status === "failed" || status === "error") return "bg-red-500/10 border-red-500/30";
        return "bg-white/5 border-white/10";
    };

    return (
        <div className="h-full overflow-auto p-4 bg-gray-900">
            <div className="space-y-2">
                {orderedNodes.map((node, index) => (
                    <div key={node.id} className={`p-3 rounded-lg border ${getStatusClass(node.status)}`}>
                        <div className="flex items-center gap-2">
                            <span className="text-gray-400 text-xs">Step {index + 1}</span>
                            <span className="text-white text-sm font-medium">{node.name || node.id}</span>
                            {node.status && <span className="ml-auto text-xs text-gray-400">{node.status}</span>}
                        </div>
                        {node.goal && <p className="text-gray-400 text-xs mt-1">{node.goal}</p>}
                    </div>
                ))}
            </div>
        </div>
    );
}
