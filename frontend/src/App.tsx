import { useState, useCallback, useEffect } from 'react';
import { TargetTable } from './components/TargetTable';
import { useTargets } from './hooks/useTargets';
import { useWebSocket } from './hooks/useWebSocket';
import {
  LoadingSpinner,
  ErrorMessage,
  ConnectionStatus,
  RefreshControl,
} from './components/common';
import { api } from './services/api';
import type { Target, CommandOutput, HealthResponse, ScheduledCommand } from './types';
import './App.css';

const AUTO_REFRESH_INTERVAL = 30; // seconds

/**
 * Main application component
 */
function App() {
  const { targets, loading, error, refetch } = useTargets();
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [healthInfo, setHealthInfo] = useState<HealthResponse | null>(null);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [scheduledCommands, setScheduledCommands] = useState<ScheduledCommand[]>([]);
  
  // Store command outputs at App level to preserve across refreshes
  const [commandOutputs, setCommandOutputs] = useState<Map<string, CommandOutput[]>>(
    new Map()
  );

  // Fetch health info and scheduled commands on mount
  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const response = await api.getHealth();
        setHealthInfo(response.data);
      } catch (err) {
        console.error('Failed to fetch health info:', err);
      }
    };
    
    const fetchScheduledCommands = async () => {
      try {
        const response = await api.getScheduledCommands();
        setScheduledCommands(response.data.commands);
      } catch (err) {
        console.error('Failed to fetch scheduled commands:', err);
      }
    };
    
    fetchHealth();
    fetchScheduledCommands();
  }, []);

  // Update lastUpdated when targets are fetched
  useEffect(() => {
    if (!loading && targets.length > 0) {
      setLastUpdated(new Date());
    }
  }, [loading, targets]);

  const handleTargetUpdate = useCallback(
    (updatedTarget: Target) => {
      console.log('Target updated via WebSocket:', updatedTarget.name);
      // Refetch to get the latest data
      refetch();
      setLastUpdated(new Date());
    },
    [refetch]
  );

  const handleCommandOutput = useCallback(
    (targetName: string, output: CommandOutput) => {
      console.log(`Command output for ${targetName}:`, output);
      refetch();
      setLastUpdated(new Date());
    },
    [refetch]
  );

  const handleTargetsList = useCallback(
    (targetsList: Target[]) => {
      console.log('Received targets list via WebSocket:', targetsList.length);
      refetch();
      setLastUpdated(new Date());
    },
    [refetch]
  );

  const handleConnectionChange = useCallback((connected: boolean) => {
    console.log(
      'WebSocket connection:',
      connected ? 'connected' : 'disconnected'
    );
    setIsReconnecting(!connected);
  }, []);

  const { connected, subscribe } = useWebSocket({
    onTargetUpdate: handleTargetUpdate,
    onCommandOutput: handleCommandOutput,
    onTargetsList: handleTargetsList,
    onConnectionChange: handleConnectionChange,
  });

  // Subscribe to all targets when connected
  useEffect(() => {
    if (connected) {
      subscribe(); // Subscribe to all targets
      setIsReconnecting(false);
    }
  }, [connected, subscribe]);

  const handleRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  const handleCommandComplete = useCallback(
    (targetName: string, output: CommandOutput) => {
      console.log(`Command completed on ${targetName}:`, output.command);
      // The TargetRow already handles updating its local state
      // We can optionally refetch to sync with server
    },
    []
  );

  // Handler to update command outputs for a specific target
  const handleCommandOutputsChange = useCallback(
    (targetName: string, outputs: CommandOutput[]) => {
      setCommandOutputs((prev) => {
        const newMap = new Map(prev);
        newMap.set(targetName, outputs);
        return newMap;
      });
    },
    []
  );

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-title">
          <h1>Labgrid Dashboard</h1>
          {healthInfo?.mock_mode && (
            <span className="mode-badge mock">Mock Mode</span>
          )}
        </div>
        <div className="header-status">
          <ConnectionStatus
            isConnected={connected}
            isReconnecting={isReconnecting}
            mockMode={healthInfo?.mock_mode}
          />
          <RefreshControl
            onRefresh={handleRefresh}
            lastUpdated={lastUpdated}
            autoRefreshInterval={AUTO_REFRESH_INTERVAL}
            isRefreshing={loading}
          />
        </div>
      </header>

      <main className="app-main">
        {loading && targets.length === 0 && (
          <LoadingSpinner size="large" message="Loading targets..." />
        )}

        {error && (
          <ErrorMessage
            error={error}
            onRetry={handleRefresh}
            title="Failed to load targets"
          />
        )}

        {!loading && !error && targets.length === 0 && (
          <div className="no-targets">
            <p>No targets found</p>
            <button className="btn-primary" onClick={handleRefresh}>
              Refresh
            </button>
          </div>
        )}

        {targets.length > 0 && (
          <TargetTable
            targets={targets}
            loading={loading}
            onCommandComplete={handleCommandComplete}
            commandOutputs={commandOutputs}
            onCommandOutputsChange={handleCommandOutputsChange}
            scheduledCommands={scheduledCommands}
          />
        )}
      </main>

      <footer className="app-footer">
        <div className="footer-info">
          <span className="target-count">
            {targets.length} target{targets.length !== 1 ? 's' : ''} found
          </span>
          {healthInfo && (
            <span className="coordinator-status">
              Coordinator:{' '}
              {healthInfo.coordinator_connected ? (
                <span className="status-ok">Connected</span>
              ) : (
                <span className="status-error">Disconnected</span>
              )}
            </span>
          )}
        </div>
      </footer>
    </div>
  );
}

export default App;
