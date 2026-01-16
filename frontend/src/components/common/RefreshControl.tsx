import { useState, useEffect, useCallback } from 'react';

interface RefreshControlProps {
  onRefresh: () => void;
  lastUpdated: Date | null;
  autoRefreshInterval?: number; // in seconds, 0 to disable
  isRefreshing?: boolean;
}

/**
 * Refresh control with auto-refresh toggle and last-updated timestamp
 */
export function RefreshControl({
  onRefresh,
  lastUpdated,
  autoRefreshInterval = 30,
  isRefreshing = false,
}: RefreshControlProps) {
  const [autoRefresh, setAutoRefresh] = useState(autoRefreshInterval > 0);
  const [countdown, setCountdown] = useState(autoRefreshInterval);

  // Format last updated time
  const formatLastUpdated = (date: Date | null): string => {
    if (!date) return 'Never';
    const now = new Date();
    const diffSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diffSeconds < 60) {
      return diffSeconds === 0 ? 'Just now' : `${diffSeconds}s ago`;
    } else if (diffSeconds < 3600) {
      const minutes = Math.floor(diffSeconds / 60);
      return `${minutes}m ago`;
    } else {
      return date.toLocaleTimeString();
    }
  };

  // Handle auto-refresh
  useEffect(() => {
    if (!autoRefresh || autoRefreshInterval <= 0) {
      return;
    }

    const intervalId = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          onRefresh();
          return autoRefreshInterval;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(intervalId);
  }, [autoRefresh, autoRefreshInterval, onRefresh]);

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
      <div className="refresh-info">
        <span className="last-updated" title={lastUpdated?.toLocaleString()}>
          Updated: {formatLastUpdated(lastUpdated)}
        </span>
        {autoRefresh && autoRefreshInterval > 0 && (
          <span className="auto-refresh-countdown" title="Next auto-refresh">
            ({countdown}s)
          </span>
        )}
      </div>

      <div className="refresh-actions">
        <label className="auto-refresh-toggle" title="Toggle auto-refresh">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={handleToggleAutoRefresh}
            disabled={autoRefreshInterval <= 0}
          />
          <span className="toggle-label">Auto</span>
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
