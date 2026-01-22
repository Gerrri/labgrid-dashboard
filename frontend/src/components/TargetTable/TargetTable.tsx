import { useState, useCallback, useMemo } from "react";
import type {
  Target,
  CommandOutput,
  ScheduledCommand,
  PresetDetail,
} from "../../types";
import { TargetRow } from "./TargetRow";
import "./TargetTable.css";

interface TargetTableProps {
  targets: Target[];
  loading?: boolean;
  onCommandComplete?: (targetName: string, output: CommandOutput) => void;
  commandOutputs?: Map<string, CommandOutput[]>;
  onCommandOutputsChange?: (
    targetName: string,
    outputs: CommandOutput[],
  ) => void;
  scheduledCommands?: ScheduledCommand[];
  onPresetChange?: (targetName: string, presetId: string) => void;
  /** Optional preset info for grouped display */
  preset?: PresetDetail;
  /** Whether to show the preset header (default: false for backward compatibility) */
  showPresetHeader?: boolean;
}

/**
 * Main table component displaying targets
 * Can display all targets or a subset grouped by preset
 * Manages expandedTargets state to preserve UI state across refreshes
 */
export function TargetTable({
  targets,
  loading = false,
  onCommandComplete,
  commandOutputs,
  onCommandOutputsChange,
  scheduledCommands = [],
  onPresetChange,
  preset,
  showPresetHeader = false,
}: TargetTableProps) {
  // Manage expanded state at table level to preserve across refreshes
  const [expandedTargets, setExpandedTargets] = useState<Set<string>>(
    new Set(),
  );

  // Sort targets alphabetically by name for consistent display
  const sortedTargets = useMemo(() => {
    return [...targets].sort((a, b) => a.name.localeCompare(b.name));
  }, [targets]);

  const handleToggleExpand = useCallback((targetName: string) => {
    setExpandedTargets((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(targetName)) {
        newSet.delete(targetName);
      } else {
        newSet.add(targetName);
      }
      return newSet;
    });
  }, []);

  // Use preset's scheduled commands if available, otherwise fall back to props
  const effectiveScheduledCommands = useMemo(() => {
    if (preset && preset.scheduled_commands.length > 0) {
      return preset.scheduled_commands;
    }
    return scheduledCommands;
  }, [preset, scheduledCommands]);

  // Calculate total columns for expanded row colspan
  const totalColumns = 5 + effectiveScheduledCommands.length;

  // Format target count text
  const targetCountText = useMemo(() => {
    const count = sortedTargets.length;
    return `${count} Target${count !== 1 ? "s" : ""}`;
  }, [sortedTargets.length]);

  // Show empty state only when not loading and no targets
  if (!loading && sortedTargets.length === 0) {
    return (
      <div className="target-table-empty">
        <p>No targets found</p>
      </div>
    );
  }

  return (
    <div className="target-table-container">
      {/* Preset header when displaying grouped tables */}
      {showPresetHeader && preset && (
        <div className="preset-table-header">
          <h2 className="preset-name">
            {preset.name}{" "}
            <span className="preset-target-count">({targetCountText})</span>
          </h2>
          {preset.description && (
            <p className="preset-description">{preset.description}</p>
          )}
        </div>
      )}
      {/* Show loading overlay instead of replacing the entire table */}
      {loading && sortedTargets.length === 0 && (
        <div className="target-table-loading">
          <div className="spinner" />
          <p>Loading targets...</p>
        </div>
      )}
      {sortedTargets.length > 0 && (
        <>
          {loading && (
            <div className="target-table-refreshing">
              <span className="refresh-indicator">Refreshing...</span>
            </div>
          )}
          <table className="target-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Acquired By</th>
                <th>IP Address</th>
                {effectiveScheduledCommands.map((cmd) => (
                  <th
                    key={cmd.name}
                    className="scheduled-column"
                    title={cmd.description}
                  >
                    {cmd.name}
                  </th>
                ))}
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sortedTargets.map((target) => (
                <TargetRow
                  key={target.name}
                  target={target}
                  expanded={expandedTargets.has(target.name)}
                  onToggleExpand={handleToggleExpand}
                  onCommandComplete={onCommandComplete}
                  commandOutputs={commandOutputs?.get(target.name)}
                  onCommandOutputsChange={onCommandOutputsChange}
                  scheduledCommands={effectiveScheduledCommands}
                  totalColumns={totalColumns}
                  onPresetChange={onPresetChange}
                />
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

export default TargetTable;
