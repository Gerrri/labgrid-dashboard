import { useState, useCallback, useEffect, useMemo } from "react";
import { TargetTable } from "./components/TargetTable";
import { usePresetsWithTargets } from "./hooks/usePresetsWithTargets";
import { useWebSocket } from "./hooks/useWebSocket";
import {
  LoadingSpinner,
  ErrorMessage,
  ConnectionStatus,
  RefreshControl,
} from "./components/common";
import { api } from "./services/api";
import type { Target, CommandOutput, HealthResponse } from "./types";
import "./App.css";

const AUTO_REFRESH_INTERVAL = 30; // seconds

/**
 * Main application component
 */
function App() {
  const { presetGroups, loading, error, refetch } = usePresetsWithTargets();
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [healthInfo, setHealthInfo] = useState<HealthResponse | null>(null);
  const [isReconnecting, setIsReconnecting] = useState(false);

  // Store command outputs at App level to preserve across refreshes
  const [commandOutputs, setCommandOutputs] = useState<
    Map<string, CommandOutput[]>
  >(new Map());

  // Calculate total targets from all preset groups
  const totalTargets = useMemo(() => {
    return presetGroups.reduce((sum, group) => sum + group.targets.length, 0);
  }, [presetGroups]);

  // Fetch health info on mount
  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const response = await api.getHealth();
        setHealthInfo(response.data);
      } catch (err) {
        console.error("Failed to fetch health info:", err);
      }
    };

    fetchHealth();
  }, []);

  // Update lastUpdated when targets are fetched
  useEffect(() => {
    if (!loading && totalTargets > 0) {
      setLastUpdated(new Date());
    }
  }, [loading, totalTargets]);

  const handleTargetUpdate = useCallback(
    (updatedTarget: Target) => {
      console.log("Target updated via WebSocket:", updatedTarget.name);
      // Refetch to get the latest data
      refetch();
      setLastUpdated(new Date());
    },
    [refetch],
  );

  const handleCommandOutput = useCallback(
    (targetName: string, output: CommandOutput) => {
      console.log(`Command output for ${targetName}:`, output);
      refetch();
      setLastUpdated(new Date());
    },
    [refetch],
  );

  const handleTargetsList = useCallback(
    (targetsList: Target[]) => {
      console.log("Received targets list via WebSocket:", targetsList.length);
      refetch();
      setLastUpdated(new Date());
    },
    [refetch],
  );

  const handleConnectionChange = useCallback((connected: boolean) => {
    console.log(
      "WebSocket connection:",
      connected ? "connected" : "disconnected",
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
    [],
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
    [],
  );

  // Handler for preset changes - clear outputs and refetch to reload commands
  const handlePresetChange = useCallback(
    (targetName: string, presetId: string) => {
      console.log(`Preset changed for ${targetName} to ${presetId}`);
      // Clear command outputs for this target since commands might have changed
      setCommandOutputs((prev) => {
        const newMap = new Map(prev);
        newMap.delete(targetName);
        return newMap;
      });
      // Refetch targets to ensure data is up to date
      refetch();
    },
    [refetch],
  );

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-title">
          <h1>Labgrid Dashboard</h1>
        </div>
        <div className="header-status">
          <ConnectionStatus
            isConnected={connected}
            isReconnecting={isReconnecting}
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
        {loading && totalTargets === 0 && (
          <LoadingSpinner size="large" message="Loading targets..." />
        )}

        {error && (
          <ErrorMessage
            error={error}
            onRetry={handleRefresh}
            title="Failed to load targets"
          />
        )}

        {!loading && !error && totalTargets === 0 && (
          <div className="no-targets">
            <p>No targets found</p>
            <button className="btn-primary" onClick={handleRefresh}>
              Refresh
            </button>
          </div>
        )}

        {/* Render a table for each preset group (only presets with targets) */}
        {presetGroups.map((group) => (
          <TargetTable
            key={group.preset.id}
            targets={group.targets}
            loading={loading}
            onCommandComplete={handleCommandComplete}
            commandOutputs={commandOutputs}
            onCommandOutputsChange={handleCommandOutputsChange}
            onPresetChange={handlePresetChange}
            preset={group.preset}
            showPresetHeader={true}
          />
        ))}
      </main>

      <footer className="app-footer">
        <div className="footer-info">
          <span className="target-count">
            {totalTargets} target{totalTargets !== 1 ? "s" : ""} found
          </span>
          {healthInfo && (
            <span className="coordinator-status">
              Coordinator:{" "}
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
