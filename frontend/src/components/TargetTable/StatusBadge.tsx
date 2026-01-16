import type { TargetStatus } from '../../types';

interface StatusBadgeProps {
  status: TargetStatus;
}

const STATUS_CONFIG: Record<
  TargetStatus,
  { label: string; className: string }
> = {
  available: {
    label: 'Available',
    className: 'status-badge status-available',
  },
  acquired: {
    label: 'Acquired',
    className: 'status-badge status-acquired',
  },
  offline: {
    label: 'Offline',
    className: 'status-badge status-offline',
  },
};

/**
 * Status indicator badge with color coding
 * - Available: Green
 * - Acquired: Yellow
 * - Offline: Red
 */
export function StatusBadge({ status }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status];

  return <span className={config.className}>{config.label}</span>;
}

export default StatusBadge;
