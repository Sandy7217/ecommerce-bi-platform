"use client";

import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";

import { apiGet } from "@/lib/api";

export function useApiData<T>(path: string | null, initial: T) {
  const [data, setData] = useState<T>(initial);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!path) {
      setData(initial);
      setLoading(false);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setData(await apiGet<T>(path));
    } catch (err) {
      const message = err instanceof Error ? err.message : "API request failed";
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    load();
  }, [load]);

  return { data, loading, error, retry: load };
}
