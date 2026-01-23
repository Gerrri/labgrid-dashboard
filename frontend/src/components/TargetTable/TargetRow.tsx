import { useState, useCallback } from "react";
import { createPortal } from "react-dom";
import type { Target, CommandOutput, ScheduledCommand } from "../../types";
import { StatusBadge } from "./StatusBadge";
import { CommandPanel } from "../CommandPanel";
import { TargetSettings } from "../TargetSettings";

interface TooltipState {
  visible: boolean;
  cmdName: string;
  output: string;
  timestamp: string;
  x: number;
  y: number;
}

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
 * Tooltip component rendered via portal
 */
function ScheduledOutputTooltip({ state }: { state: TooltipState }) {
  return createPortal(
    <div
      className="scheduled-output-tooltip"
      style={{
        display: "block",
        left: state.x,
        top: state.y,
      }}
    >
      <div className="tooltip-command-name">{state.cmdName}</div>
      <div className="tooltip-output">{state.output}</div>
      <div className="tooltip-timestamp">Last updated: {state.timestamp}</div>
    </div>,
    document.body,
  );
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
  const [tooltipState, setTooltipState] = useState<TooltipState | null>(null);

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
   * Handle mouse enter on scheduled output to show tooltip
   */
  const handleScheduledOutputMouseEnter = (
    e: React.MouseEvent<HTMLSpanElement>,
    cmdName: string,
    outputText: string,
    timestamp: string,
  ) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const tooltipWidth = 300;
    const tooltipHeight = 150;

    // Calculate position - prefer below, but flip if not enough space
    let x = rect.left + rect.width / 2 - tooltipWidth / 2;
    let y = rect.bottom + 8;

    // Adjust horizontal position if it goes off-screen
    if (x < 10) x = 10;
    if (x + tooltipWidth > window.innerWidth - 10) {
      x = window.innerWidth - tooltipWidth - 10;
    }

    // Flip to top if not enough space below
    if (y + tooltipHeight > window.innerHeight - 10) {
      y = rect.top - tooltipHeight - 8;
    }

    setTooltipState({
      visible: true,
      cmdName,
      output: outputText,
      timestamp,
      x,
      y,
    });
  };

  /**
   * Handle mouse leave on scheduled output to hide tooltip
   */
  const handleScheduledOutputMouseLeave = () => {
    setTooltipState(null);
  };

  /**
   * Render the scheduled command output for a given command
   * Includes a tooltip showing command name, full output, and timestamp
   */
  const renderScheduledOutput = (cmdName: string) => {
    const output = target.scheduled_outputs?.[cmdName];
    if (!output) {
      return <span className="text-muted">-</span>;
    }

    const isError = output.exit_code !== 0;
    const formattedTimestamp = new Date(output.timestamp).toLocaleString();

    return (
      <span
        className={`scheduled-output ${isError ? "error" : ""}`}
        onMouseEnter={(e) =>
          handleScheduledOutputMouseEnter(
            e,
            cmdName,
            output.output,
            formattedTimestamp,
          )
        }
        onMouseLeave={handleScheduledOutputMouseLeave}
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
                /* Command Panel Section */
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
              )}
            </div>
          </td>
        </tr>
      )}
      {/* Fixed position tooltip for scheduled outputs - rendered via portal */}
      {tooltipState && <ScheduledOutputTooltip state={tooltipState} />}
    </>
  );
}

export default TargetRow;
