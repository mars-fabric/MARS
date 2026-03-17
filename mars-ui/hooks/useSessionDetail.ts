import { useState, useEffect, useCallback } from "react";
import { SessionDetail, SessionRun } from "@/types/sessions";

export function useSessionDetail(sessionId: string | null) {
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [runs, setRuns] = useState<SessionRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    if (!sessionId) {
      setDetail(null);
      setRuns([]);
      setSelectedRunId(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const [detailRes, runsRes] = await Promise.all([
        fetch(`/api/sessions/${sessionId}`),
        fetch(`/api/sessions/${sessionId}/runs`),
      ]);

      if (!detailRes.ok) {
        throw new Error("Failed to fetch session detail");
      }

      const detailData = await detailRes.json();
      setDetail(detailData);

      if (runsRes.ok) {
        const runsData = await runsRes.json();
        const runsList = runsData.runs || [];
        setRuns(runsList);
        if (runsList.length > 0) {
          setSelectedRunId(runsList[0].id);
        } else {
          setSelectedRunId(null);
        }
      } else {
        setRuns([]);
        setSelectedRunId(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return {
    detail,
    runs,
    selectedRunId,
    setSelectedRunId,
    loading,
    error,
    refetch: fetchAll,
  };
}
