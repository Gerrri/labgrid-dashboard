interface ConnectionIndicatorsProps {
  websocketConnected: boolean;
  coordinatorConnected: boolean;
  isReconnecting?: boolean;
}

/**
 * Connection status indicators with pictograms for footer
 */
export function ConnectionIndicators({
  websocketConnected,
  coordinatorConnected,
  isReconnecting = false,
}: ConnectionIndicatorsProps) {
  return (
    <div className="connection-indicators">
      {/* Frontend ↔ Backend WebSocket Connection */}
      <div
        className={`connection-indicator ${websocketConnected && !isReconnecting ? 'connected' : 'disconnected'} ${isReconnecting ? 'reconnecting' : ''}`}
        title={`Frontend ↔ Backend: ${isReconnecting ? 'Reconnecting...' : websocketConnected ? 'Connected' : 'Disconnected'}`}
      >
        <span className="status-dot" />
        <span className="connection-label">Backend</span>
      </div>

      {/* Backend ↔ Coordinator Connection */}
      <div
        className={`connection-indicator ${coordinatorConnected ? 'connected' : 'disconnected'}`}
        title={`Backend ↔ Coordinator: ${coordinatorConnected ? 'Connected' : 'Disconnected'}`}
      >
        <span className="status-dot" />
        <span className="connection-label">Coordinator</span>
      </div>
    </div>
  );
}

export default ConnectionIndicators;
