import type { Target, CommandOutput } from '../../types';
import { TargetRow } from './TargetRow';
import './TargetTable.css';

interface TargetTableProps {
  targets: Target[];
  loading?: boolean;
  onCommandComplete?: (targetName: string, output: CommandOutput) => void;
}

/**
 * Main table component displaying all targets
 */
export function TargetTable({
  targets,
  loading = false,
  onCommandComplete,
}: TargetTableProps) {
  if (loading) {
    return (
      <div className="target-table-loading">
        <div className="spinner" />
        <p>Loading targets...</p>
      </div>
    );
  }

  if (targets.length === 0) {
    return (
      <div className="target-table-empty">
        <p>No targets found</p>
      </div>
    );
  }

  return (
    <div className="target-table-container">
      <table className="target-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Status</th>
            <th>Acquired By</th>
            <th>IP Address</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {targets.map((target) => (
            <TargetRow
              key={target.name}
              target={target}
              onCommandComplete={onCommandComplete}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default TargetTable;
