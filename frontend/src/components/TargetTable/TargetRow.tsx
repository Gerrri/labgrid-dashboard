import { useState } from 'react';
import type { Target, CommandOutput } from '../../types';
import { StatusBadge } from './StatusBadge';
import { CommandPanel } from '../CommandPanel';

interface TargetRowProps {
  target: Target;
  onCommandComplete?: (targetName: string, output: CommandOutput) => void;
}

/**
 * Single row displaying target information
 */
export function TargetRow({ target, onCommandComplete }: TargetRowProps) {
  const [expanded, setExpanded] = useState(false);

  const toggleExpand = () => {
    setExpanded((prev) => !prev);
  };

  const handleCommandComplete = (output: CommandOutput) => {
    onCommandComplete?.(target.name, output);
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
          <td colSpan={5}>
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
                    onCommandComplete={handleCommandComplete}
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
