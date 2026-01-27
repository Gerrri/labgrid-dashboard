import { useState, useEffect, useCallback } from 'react';

interface RefreshControlProps {
  onRefresh: () => void;
  autoRefreshInterval?: number; // in seconds, 0 to disable
  isRefreshing?: boolean;
}

/**
 * Refresh control with auto-refresh toggle
 */
export function RefreshControl({
  onRefresh,
  autoRefreshInterval = 30,
  isRefreshing = false,
}: RefreshControlProps) {
  const [autoRefresh, setAutoRefresh] = useState(autoRefreshInterval > 0);
  const [countdown, setCountdown] = useState(autoRefreshInterval);

  // Trigger refresh when countdown reaches 0
  useEffect(() => {
    if (countdown === 0 && autoRefresh && autoRefreshInterval > 0) {
      onRefresh();
      setCountdown(autoRefreshInterval);
    }
  }, [countdown, autoRefresh, autoRefreshInterval, onRefresh]);

  // Handle auto-refresh countdown (pure state update, no side effects)
  useEffect(() => {
    if (!autoRefresh || autoRefreshInterval <= 0) {
      return;
    }

    const intervalId = setInterval(() => {
      setCountdown((prev) => (prev <= 1 ? 0 : prev - 1));
    }, 1000);

    return () => clearInterval(intervalId);
  }, [autoRefresh, autoRefreshInterval]);

  // Reset countdown when manual refresh occurs
  useEffect(() => {
    if (isRefreshing && autoRefresh) {
      setCountdown(autoRefreshInterval);
    }
  }, [isRefreshing, autoRefresh, autoRefreshInterval]);

  // Pause auto-refresh when tab is not visible
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        // Tab is hidden, auto-refresh will be paused naturally
        // since interval runs but we don't want to spam refreshes
      } else if (autoRefresh) {
        // Tab is visible again, trigger refresh
        onRefresh();
        setCountdown(autoRefreshInterval);
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [autoRefresh, autoRefreshInterval, onRefresh]);

  const handleToggleAutoRefresh = useCallback(() => {
    setAutoRefresh((prev) => !prev);
    setCountdown(autoRefreshInterval);
  }, [autoRefreshInterval]);

  const handleManualRefresh = useCallback(() => {
    onRefresh();
    setCountdown(autoRefreshInterval);
  }, [onRefresh, autoRefreshInterval]);

  return (
    <div className="refresh-control">
      <div className="refresh-actions">
        <label className="auto-refresh-toggle" title="Toggle auto-refresh">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={handleToggleAutoRefresh}
            disabled={autoRefreshInterval <= 0}
          />
          <span className="toggle-label">Auto refresh</span>
        </label>

        <button
          className={`btn-refresh ${isRefreshing ? 'refreshing' : ''}`}
          onClick={handleManualRefresh}
          disabled={isRefreshing}
          title="Refresh now"
        >
          {isRefreshing ? (
            <span className="refresh-icon spinning">⟳</span>
          ) : (
            <span className="refresh-icon">↻</span>
          )}
          <span className="btn-text">Refresh</span>
        </button>
      </div>
    </div>
  );
}

export default RefreshControl;
