import { useState, useCallback } from "react";
import type { Target, CommandOutput, ScheduledCommand } from "../../types";
import { StatusBadge } from "./StatusBadge";
import { CommandPanel } from "../CommandPanel";
import { TargetSettings } from "../TargetSettings";

interface TargetRowProps {
  target: Target;
  expanded: boolean;
  onToggleExpand: (targetName: string) => void;
  onCommandComplete?: (targetName: string, output: CommandOutput) => void;
  commandOutputs?: CommandOutput[];
  onCommandOutputsChange?: (
    targetName: string,
    outputs: CommandOutput[],
  ) => void;
  scheduledCommands?: ScheduledCommand[];
  totalColumns?: number;
  onPresetChange?: (targetName: string, presetId: string) => void;
}

/**
 * Single row displaying target information
 * Expanded state is controlled by parent to preserve across refreshes
 */
export function TargetRow({
  target,
  expanded,
  onToggleExpand,
  onCommandComplete,
  commandOutputs,
  onCommandOutputsChange,
  scheduledCommands = [],
  totalColumns = 5,
  onPresetChange,
}: TargetRowProps) {
  const [showSettings, setShowSettings] = useState(false);
  const [resourcesExpanded, setResourcesExpanded] = useState(false);

  const toggleExpand = () => {
    onToggleExpand(target.name);
    // Reset settings view when collapsing
    if (expanded) {
      setShowSettings(false);
    }
  };

  const handleSettingsClick = useCallback(() => {
    setShowSettings(true);
  }, []);

  const handleSettingsClose = useCallback(() => {
    setShowSettings(false);
  }, []);

  const handlePresetChange = useCallback(
    (presetId: string) => {
      onPresetChange?.(target.name, presetId);
      // Reset settings view after preset change
      setShowSettings(false);
    },
    [target.name, onPresetChange],
  );

  const handleCommandComplete = (output: CommandOutput) => {
    onCommandComplete?.(target.name, output);
  };

  const handleOutputsChange = (outputs: CommandOutput[]) => {
    onCommandOutputsChange?.(target.name, outputs);
  };

  const renderIpAddress = () => {
    if (!target.ip_address) {
      return <span className="text-muted">-</span>;
    }

    if (target.web_url) {
      return (
        <a
          href={target.web_url}
          target="_blank"
          rel="noopener noreferrer"
          className="ip-link"
        >
          {target.ip_address}
        </a>
      );
    }

    return <span>{target.ip_address}</span>;
  };

  /**
   * Render the scheduled command output for a given command
   */
  const renderScheduledOutput = (cmdName: string) => {
    const output = target.scheduled_outputs?.[cmdName];
    if (!output) {
      return <span className="text-muted">-</span>;
    }

    const isError = output.exit_code !== 0;
    return (
      <span
        className={`scheduled-output ${isError ? "error" : ""}`}
        title={`Last updated: ${new Date(output.timestamp).toLocaleString()}`}
      >
        {output.output}
      </span>
    );
  };

  const canExecuteCommands = target.status !== "offline";

  return (
    <>
      <tr className={`target-row ${expanded ? "expanded" : ""}`}>
        <td className="target-name">{target.name}</td>
        <td className="target-status">
          <StatusBadge status={target.status} />
        </td>
        <td className="target-acquired-by">
          {target.acquired_by || <span className="text-muted">-</span>}
        </td>
        <td className="target-ip">{renderIpAddress()}</td>
        {scheduledCommands.map((cmd) => (
          <td key={cmd.name} className="target-scheduled-output">
            {renderScheduledOutput(cmd.name)}
          </td>
        ))}
        <td className="target-actions">
          <button
            className="btn-expand"
            onClick={toggleExpand}
            aria-expanded={expanded}
            aria-label={expanded ? "Collapse details" : "Expand details"}
          >
            {expanded ? "▼" : "▶"}
          </button>
        </td>
      </tr>
      {expanded && (
        <tr className="target-details-row">
          <td colSpan={totalColumns}>
            <div className="target-details">
              {showSettings ? (
                /* Full-width Target Settings when open */
                <div className="details-section full-width">
                  <TargetSettings
                    targetName={target.name}
                    onPresetChange={handlePresetChange}
                    onClose={handleSettingsClose}
                  />
                </div>
              ) : (
                <>
                  {/* Resources Section - Collapsible */}
                  <div className="details-section collapsible">
                    <button
                      className="section-toggle"
                      onClick={() => setResourcesExpanded(!resourcesExpanded)}
                      aria-expanded={resourcesExpanded}
                    >
                      <span className="toggle-icon">
                        {resourcesExpanded ? "▼" : "▶"}
                      </span>
                      <h4>
                        Connection Type
                        {target.resources.length > 0 && (
                          <span className="resource-type-hint">
                            {target.resources.map((r) => r.type).join(", ")}
                          </span>
                        )}
                      </h4>
                    </button>
                    {resourcesExpanded && target.resources.length > 0 && (
                      <ul className="resources-list">
                        {target.resources.map((resource, index) => (
                          <li key={index} className="resource-item">
                            <strong>{resource.type}</strong>
                            {Object.keys(resource.params).length > 0 && (
                              <pre className="resource-params">
                                {JSON.stringify(resource.params, null, 2)}
                              </pre>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                    {resourcesExpanded && target.resources.length === 0 && (
                      <p className="text-muted">No resources available</p>
                    )}
                  </div>

                  {/* Command Panel Section */}
                  <div className="details-section">
                    {canExecuteCommands ? (
                      <CommandPanel
                        targetName={target.name}
                        initialOutputs={target.last_command_outputs}
                        persistedOutputs={commandOutputs}
                        onCommandComplete={handleCommandComplete}
                        onOutputsChange={handleOutputsChange}
                        onSettingsClick={handleSettingsClick}
                      />
                    ) : (
                      <div className="commands-offline">
                        <p className="text-muted">
                          Commands unavailable - target is offline
                        </p>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default TargetRow;
