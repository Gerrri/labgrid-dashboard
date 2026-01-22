import { useState, useCallback, useMemo } from "react";
import type { Target, CommandOutput, ScheduledCommand } from "../../types";
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
}

/**
 * Main table component displaying all targets
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

  // Calculate total columns for expanded row colspan
  const totalColumns = 5 + scheduledCommands.length;

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
                {scheduledCommands.map((cmd) => (
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
                  scheduledCommands={scheduledCommands}
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
