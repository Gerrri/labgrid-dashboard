import { useState, useEffect, useCallback } from 'react';
import type { Target } from '../types';
import { api } from '../services/api';

interface UseTargetsResult {
  targets: Target[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

/**
 * Custom hook for fetching and managing targets
 */
export function useTargets(): UseTargetsResult {
  const [targets, setTargets] = useState<Target[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTargets = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.getTargets();
      setTargets(response.data.targets);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to fetch targets';
      setError(errorMessage);
      console.error('Error fetching targets:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTargets();
  }, [fetchTargets]);

  return {
    targets,
    loading,
    error,
    refetch: fetchTargets,
  };
}

export default useTargets;
