import type { Target, CommandOutput, ScheduledCommand } from '../../types';
import { StatusBadge } from './StatusBadge';
import { CommandPanel } from '../CommandPanel';

interface TargetRowProps {
  target: Target;
  expanded: boolean;
  onToggleExpand: (targetName: string) => void;
  onCommandComplete?: (targetName: string, output: CommandOutput) => void;
  commandOutputs?: CommandOutput[];
  onCommandOutputsChange?: (targetName: string, outputs: CommandOutput[]) => void;
  scheduledCommands?: ScheduledCommand[];
  totalColumns?: number;
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
}: TargetRowProps) {
  const toggleExpand = () => {
    onToggleExpand(target.name);
  };

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
        className={`scheduled-output ${isError ? 'error' : ''}`}
        title={`Last updated: ${new Date(output.timestamp).toLocaleString()}`}
      >
        {output.output}
      </span>
    );
  };

  const canExecuteCommands = target.status !== 'offline';

  return (
    <>
      <tr className={`target-row ${expanded ? 'expanded' : ''}`}>
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
            aria-label={expanded ? 'Collapse details' : 'Expand details'}
          >
            {expanded ? '▼' : '▶'}
          </button>
        </td>
      </tr>
      {expanded && (
        <tr className="target-details-row">
          <td colSpan={totalColumns}>
            <div className="target-details">
              {/* Resources Section */}
              <div className="details-section">
                <h4>Resources ({target.resources.length})</h4>
                {target.resources.length > 0 ? (
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
                ) : (
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
                  />
                ) : (
                  <div className="commands-offline">
                    <p className="text-muted">
                      Commands unavailable - target is offline
                    </p>
                  </div>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default TargetRow;
