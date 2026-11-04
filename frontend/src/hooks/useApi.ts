import { useCallback, useEffect, useRef, useState } from "react";

import { apiRequest } from "../api/client";
import { errorMessage } from "../lib/format";

interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

/**
 * Minimal data-fetching hook.
 *
 * `path` is the full API path including the query string, so callers own
 * filtering and pagination. `reload()` re-runs the request.
 */
export function useApi<T>(path: string | null): ApiState<T> & { reload: () => void } {
  const [state, setState] = useState<ApiState<T>>({ data: null, loading: Boolean(path), error: null });
  const [nonce, setNonce] = useState(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (!path) {
      setState({ data: null, loading: false, error: null });
      return;
    }
    const controller = new AbortController();
    setState((previous) => ({ ...previous, loading: true, error: null }));

    apiRequest<T>(path, { signal: controller.signal })
      .then((data) => {
        if (mounted.current) setState({ data, loading: false, error: null });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        if (mounted.current) {
          setState((previous) => ({ ...previous, loading: false, error: errorMessage(error) }));
        }
      });

    return () => controller.abort();
  }, [path, nonce]);

  const reload = useCallback(() => setNonce((value) => value + 1), []);

  return { ...state, reload };
}

export function useMutation() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async <T,>(action: () => Promise<T>): Promise<T | null> => {
    setBusy(true);
    setError(null);
    try {
      return await action();
    } catch (cause) {
      setError(errorMessage(cause));
      return null;
    } finally {
      setBusy(false);
    }
  }, []);

  return { run, busy, error, clearError: () => setError(null) };
}
