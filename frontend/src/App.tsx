import { useCallback } from 'react';
import { TargetTable } from './components/TargetTable';
import { useTargets } from './hooks/useTargets';
import { useWebSocket } from './hooks/useWebSocket';
import type { Target, CommandOutput } from './types';
import './App.css';

/**
 * Main application component
 */
function App() {
  const { targets, loading, error, refetch } = useTargets();

  const handleTargetUpdate = useCallback(
    (updatedTarget: Target) => {
      console.log('Target updated:', updatedTarget.name);
      // Refetch to get the latest data
      refetch();
    },
    [refetch]
  );

  const handleCommandOutput = useCallback(
    (targetName: string, output: CommandOutput) => {
      console.log(`Command output for ${targetName}:`, output);
      refetch();
    },
    [refetch]
  );

  const handleConnectionChange = useCallback((connected: boolean) => {
    console.log('WebSocket connection:', connected ? 'connected' : 'disconnected');
  }, []);

  const { connected } = useWebSocket({
    onTargetUpdate: handleTargetUpdate,
    onCommandOutput: handleCommandOutput,
    onConnectionChange: handleConnectionChange,
  });

  return (
    <div className="app">
      <header className="app-header">
        <h1>Labgrid Dashboard</h1>
        <div className="header-actions">
          <span
            className={`connection-status ${connected ? 'connected' : 'disconnected'}`}
            title={connected ? 'WebSocket connected' : 'WebSocket disconnected'}
          >
            {connected ? '●' : '○'}
          </span>
          <button className="btn-refresh" onClick={refetch} disabled={loading}>
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </header>

      <main className="app-main">
        {error && (
          <div className="error-banner">
            <span>Error: {error}</span>
            <button onClick={refetch}>Retry</button>
          </div>
        )}

        <TargetTable targets={targets} loading={loading} />
      </main>

      <footer className="app-footer">
        <p>
          {targets.length} target{targets.length !== 1 ? 's' : ''} found
        </p>
      </footer>
    </div>
  );
}

export default App;
