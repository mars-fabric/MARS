"use client";

import { useState, useEffect } from "react";
import { Loader2, AlertCircle } from "lucide-react";
import { DAGVisualization } from "@/components/dag";

interface SessionDAGTabProps {
  runId: string;
}

export function SessionDAGTab({ runId }: SessionDAGTabProps) {
  const [dagData, setDagData] = useState<{ nodes: any[]; edges: any[] } | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    fetch(`/api/runs/${runId}/dag`)
      .then((r) => {
        if (!r.ok) {
          if (r.status === 404) throw new Error("No DAG data for this run");
          throw new Error(`Failed to fetch DAG (${r.status})`);
        }
        return r.json();
      })
      .then((data) => {
        if (data.nodes && data.nodes.length > 0) {
          setDagData({ nodes: data.nodes, edges: data.edges || [] });
        } else {
          setDagData(null);
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [runId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        <Loader2 className="h-6 w-6 animate-spin mr-2" />
        <span>Loading DAG...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        <div className="text-center">
          <AlertCircle className="w-10 h-10 mx-auto mb-3 text-gray-500" />
          <p className="text-sm">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-hidden bg-gray-900">
      <DAGVisualization dagData={dagData} runId={runId} />
    </div>
  );
}
