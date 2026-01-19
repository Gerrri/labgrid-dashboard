interface ConnectionStatusProps {
  isConnected: boolean;
  isReconnecting?: boolean;
}

/**
 * WebSocket connection status indicator
 */
export function ConnectionStatus({
  isConnected,
  isReconnecting = false,
}: ConnectionStatusProps) {
  const getStatusClass = () => {
    if (isReconnecting) return 'reconnecting';
    return isConnected ? 'connected' : 'disconnected';
  };

  const getStatusText = () => {
    if (isReconnecting) return 'Reconnecting...';
    return isConnected ? 'Connected' : 'Disconnected';
  };

  const getStatusIcon = () => {
    if (isReconnecting) return '◐';
    return isConnected ? '●' : '○';
  };

  return (
    <div className={`connection-status ${getStatusClass()}`}>
      <span
        className="status-indicator"
        aria-hidden="true"
        title={getStatusText()}
      >
        {getStatusIcon()}
      </span>
      <span className="status-text">{getStatusText()}</span>
    </div>
  );
}

export default ConnectionStatus;
