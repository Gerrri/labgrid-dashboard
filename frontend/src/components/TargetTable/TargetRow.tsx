import { useState, useCallback, useMemo } from "react";
import { createPortal } from "react-dom";
import type { Target, CommandOutput, ScheduledCommand } from "../../types";
import { StatusBadge } from "./StatusBadge";
import { CommandPanel } from "../CommandPanel";
import { TargetSettings } from "../TargetSettings";

/**
 * Debug logger helper - only logs when VITE_DEBUG_SCHEDULED=true
 * Memoized to avoid creating new functions on every render
 */
const DEBUG_ENABLED = import.meta.env.VITE_DEBUG_SCHEDULED === 'true';
const debugLog = DEBUG_ENABLED
  ? (message: string, data?: unknown) => console.log(message, data)
  : () => {};

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
  onCommandStart?: (targetName: string) => void;
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
  onCommandStart,
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

  const handleCommandStart = () => {
    onCommandStart?.(target.name);
  };

  const handleOutputsChange = (outputs: CommandOutput[]) => {
    onCommandOutputsChange?.(target.name, outputs);
  };

  const renderIpAddress = () => {
    if (!target.ip_address) {
      return <span className="text-muted">-</span>;
    }

    // Validate URL to prevent XSS via javascript:/data: protocols
    const safeUrl = (() => {
      if (!target.web_url) return null;
      try {
        const url = new URL(target.web_url, window.location.origin);
        return url.protocol === "http:" || url.protocol === "https:"
          ? url.toString()
          : null;
      } catch {
        return null;
      }
    })();

    if (safeUrl) {
      return (
        <a
          href={safeUrl}
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
   *
   * Cache Strategy:
   * - If no output exists: show "N/A"
   * - If exit_code != 0 (error): show "N/A"
   * - If cache expired (older than 60 minutes): show "N/A"
   * - Otherwise: show the output
   */
  const renderScheduledOutput = (cmdName: string) => {
    const output = target.scheduled_outputs?.[cmdName];
    const CACHE_TIMEOUT_MS = 60 * 60 * 1000; // 60 minutes in milliseconds

    // Debug logging (enable with VITE_DEBUG_SCHEDULED=true)
    debugLog(`[${target.name}] renderScheduledOutput for "${cmdName}":`, {
      hasScheduledOutputs: !!target.scheduled_outputs,
      scheduledOutputsKeys: target.scheduled_outputs ? Object.keys(target.scheduled_outputs) : [],
      output: output,
    });

    // No output available
    if (!output) {
      return <span className="text-muted">N/A</span>;
    }

    // Check if cache is expired (guard against invalid timestamps)
    const outputTimestamp = Date.parse(output.timestamp);
    if (Number.isNaN(outputTimestamp)) {
      return <span className="text-muted">N/A</span>;
    }
    const now = Date.now();
    const isCacheExpired = now - outputTimestamp > CACHE_TIMEOUT_MS;

    // Show N/A if error occurred or cache expired
    const isError = output.exit_code !== 0;

    // Debug logging for cache/error checks (enable with VITE_DEBUG_SCHEDULED=true)
    debugLog(`[${target.name}] "${cmdName}" cache check:`, {
      timestamp_raw: output.timestamp,
      outputTimestamp: outputTimestamp,
      outputTimestamp_isNaN: Number.isNaN(outputTimestamp),
      now: now,
      age_ms: now - outputTimestamp,
      CACHE_TIMEOUT_MS: CACHE_TIMEOUT_MS,
      isCacheExpired: isCacheExpired,
      exit_code: output.exit_code,
      isError: isError,
      willShowNA: isError || isCacheExpired,
    });

    if (isError || isCacheExpired) {
      return <span className="text-muted">N/A</span>;
    }

    const formattedTimestamp = new Date(output.timestamp).toLocaleString();

    return (
      <span
        className="scheduled-output"
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
                      onCommandStart={handleCommandStart}
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
