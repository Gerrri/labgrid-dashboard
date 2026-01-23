import { useState, useEffect, useCallback, useRef } from "react";
import type { Command, CommandOutput } from "../../types";
import { api } from "../../services/api";
import { CommandButton } from "./CommandButton";
import { OutputViewer } from "./OutputViewer";
import "./CommandPanel.css";

interface CommandPanelProps {
  targetName: string;
  initialOutputs?: CommandOutput[];
  persistedOutputs?: CommandOutput[];
  onCommandComplete?: (output: CommandOutput) => void;
  onOutputsChange?: (outputs: CommandOutput[]) => void;
  onSettingsClick?: () => void;
}

/**
 * Panel for executing commands and viewing output
 * Uses persistedOutputs to preserve command outputs across refreshes
 */
export function CommandPanel({
  targetName,
  initialOutputs = [],
  persistedOutputs,
  onCommandComplete,
  onOutputsChange,
  onSettingsClick,
}: CommandPanelProps) {
  const [commands, setCommands] = useState<Command[]>([]);
  // Use persisted outputs if available, otherwise fall back to initial outputs
  const [outputs, setOutputs] = useState<CommandOutput[]>(
    persistedOutputs ?? initialOutputs,
  );
  const [loadingCommands, setLoadingCommands] = useState(true);
  const [executingCommand, setExecutingCommand] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Track if this is the first mount to avoid overwriting persisted state
  const isFirstMount = useRef(true);

  // Fetch available commands for the target
  useEffect(() => {
    const fetchCommands = async () => {
      try {
        setLoadingCommands(true);
        setError(null);
        const response = await api.getCommands(targetName);
        setCommands(response.data);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to load commands";
        setError(message);
        console.error("Error fetching commands:", err);
      } finally {
        setLoadingCommands(false);
      }
    };

    fetchCommands();
  }, [targetName]);

  // Only update from initialOutputs on first mount and if no persisted outputs
  useEffect(() => {
    if (isFirstMount.current) {
      isFirstMount.current = false;
      // Only set from initialOutputs if we don't have persisted outputs
      if (!persistedOutputs || persistedOutputs.length === 0) {
        setOutputs(initialOutputs);
        onOutputsChange?.(initialOutputs);
      }
    }
    // Intentionally not including initialOutputs in deps to avoid overwrites
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sync with persisted outputs when they change (e.g., from parent state)
  useEffect(() => {
    if (persistedOutputs !== undefined) {
      setOutputs(persistedOutputs);
    }
  }, [persistedOutputs]);

  const handleExecuteCommand = useCallback(
    async (commandName: string) => {
      try {
        setExecutingCommand(commandName);
        setError(null);
        const response = await api.executeCommand(targetName, commandName);
        const newOutput = response.data;

        const newOutputs = [newOutput, ...outputs];
        setOutputs(newOutputs);
        onOutputsChange?.(newOutputs);
        onCommandComplete?.(newOutput);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Command execution failed";
        setError(message);
        console.error("Error executing command:", err);
      } finally {
        setExecutingCommand(null);
      }
    },
    [targetName, outputs, onCommandComplete, onOutputsChange],
  );

  const handleClearOutput = () => {
    setOutputs([]);
    onOutputsChange?.([]);
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
              disabled={
                executingCommand !== null && executingCommand !== command.name
              }
            />
          ))
        ) : (
          <p className="no-commands">No commands available for this target.</p>
        )}
      </div>

      <div className="command-output-section">
        <OutputViewer outputs={outputs} />
      </div>

      {onSettingsClick && (
        <button
          className="btn-settings"
          onClick={onSettingsClick}
          title="Target Settings"
          aria-label="Open target settings"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>
      )}
    </div>
  );
}

export default CommandPanel;
