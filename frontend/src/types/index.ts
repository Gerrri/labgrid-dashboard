/**
 * Resource attached to a target
 */
export interface Resource {
  type: string;
  params: Record<string, unknown>;
}

/**
 * Output from a command execution
 */
export interface CommandOutput {
  command: string;
  output: string;
  timestamp: string;
  exit_code: number;
}

/**
 * Target/DUT status
 */
export type TargetStatus = 'available' | 'acquired' | 'offline';

/**
 * Target/DUT representation
 */
export interface Target {
  name: string;
  status: TargetStatus;
  acquired_by: string | null;
  ip_address: string | null;
  web_url: string | null;
  resources: Resource[];
  last_command_outputs: CommandOutput[];
}

/**
 * Predefined command definition
 */
export interface Command {
  name: string;
  command: string;
  description: string;
}

/**
 * API response for targets list
 */
export interface TargetsResponse {
  targets: Target[];
  total: number;
}

/**
 * API response for health check
 */
export interface HealthResponse {
  status: string;
  coordinator_connected: boolean;
  mock_mode: boolean;
}

/**
 * WebSocket message types
 */
export type WSMessageType =
  | 'target_update'
  | 'command_output'
  | 'targets_list'
  | 'subscribe'
  | 'execute_command';

/**
 * WebSocket message structure
 */
export interface WSMessage {
  type: WSMessageType;
  data?: unknown;
}

/**
 * WebSocket target update message
 */
export interface WSTargetUpdateMessage extends WSMessage {
  type: 'target_update';
  data: Target;
}

/**
 * WebSocket command output message
 */
export interface WSCommandOutputMessage extends WSMessage {
  type: 'command_output';
  data: {
    target_name: string;
    output: CommandOutput;
  };
}

/**
 * WebSocket targets list message
 */
export interface WSTargetsListMessage extends WSMessage {
  type: 'targets_list';
  data: Target[];
}
