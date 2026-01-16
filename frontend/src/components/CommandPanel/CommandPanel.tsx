import { useState, useEffect, useCallback } from 'react';
import type { Command, CommandOutput } from '../../types';
import { api } from '../../services/api';
import { CommandButton } from './CommandButton';
import { OutputViewer } from './OutputViewer';
import './CommandPanel.css';

interface CommandPanelProps {
  targetName: string;
  initialOutputs?: CommandOutput[];
  onCommandComplete?: (output: CommandOutput) => void;
}

/**
 * Panel for executing commands and viewing output
 */
export function CommandPanel({
  targetName,
  initialOutputs = [],
  onCommandComplete,
}: CommandPanelProps) {
  const [commands, setCommands] = useState<Command[]>([]);
  const [outputs, setOutputs] = useState<CommandOutput[]>(initialOutputs);
  const [loadingCommands, setLoadingCommands] = useState(true);
  const [executingCommand, setExecutingCommand] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch available commands for the target
  useEffect(() => {
    const fetchCommands = async () => {
      try {
        setLoadingCommands(true);
        setError(null);
        const response = await api.getCommands(targetName);
        setCommands(response.data);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load commands';
        setError(message);
        console.error('Error fetching commands:', err);
      } finally {
        setLoadingCommands(false);
      }
    };

    fetchCommands();
  }, [targetName]);

  // Update outputs when initialOutputs change (e.g., from WebSocket)
  useEffect(() => {
    setOutputs(initialOutputs);
  }, [initialOutputs]);

  const handleExecuteCommand = useCallback(
    async (commandName: string) => {
      try {
        setExecutingCommand(commandName);
        setError(null);
        const response = await api.executeCommand(targetName, commandName);
        const newOutput = response.data;

        setOutputs((prev) => [newOutput, ...prev]);
        onCommandComplete?.(newOutput);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Command execution failed';
        setError(message);
        console.error('Error executing command:', err);
      } finally {
        setExecutingCommand(null);
      }
    },
    [targetName, onCommandComplete]
  );

  const handleClearOutput = () => {
    setOutputs([]);
  };

  if (loadingCommands) {
    return (
      <div className="command-panel loading">
        <div className="loading-spinner">
          <span className="spinner-icon">⟳</span>
          <span>Loading commands...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="command-panel">
      <div className="command-panel-header">
        <h4>Commands for {targetName}</h4>
        {outputs.length > 0 && (
          <button
            className="btn-clear"
            onClick={handleClearOutput}
            title="Clear output"
          >
            Clear
          </button>
        )}
      </div>

      {error && (
        <div className="command-error">
          <span className="error-icon">⚠</span>
          <span>{error}</span>
        </div>
      )}

      <div className="command-buttons">
        {commands.length > 0 ? (
          commands.map((command) => (
            <CommandButton
              key={command.name}
              command={command}
              onExecute={handleExecuteCommand}
              isExecuting={executingCommand === command.name}
              disabled={executingCommand !== null && executingCommand !== command.name}
            />
          ))
        ) : (
          <p className="no-commands">No commands available for this target.</p>
        )}
      </div>

      <div className="command-output-section">
        <OutputViewer outputs={outputs} />
      </div>
    </div>
  );
}

export default CommandPanel;
