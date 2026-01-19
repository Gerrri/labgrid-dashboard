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
 * Output from a scheduled command for a specific target
 */
export interface ScheduledCommandOutput {
  command_name: string;
  output: string;
  timestamp: string;
  exit_code: number;
}

/**
 * Scheduled command definition (from config)
 */
export interface ScheduledCommand {
  name: string;
  command: string;
  interval_seconds: number;
  description: string;
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
  scheduled_outputs: Record<string, ScheduledCommandOutput>;
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
 * API response for scheduled commands
 */
export interface ScheduledCommandsResponse {
  commands: ScheduledCommand[];
}

/**
 * API response for health check
 */
export interface HealthResponse {
  status: string;
  coordinator_connected: boolean;
}

/**
 * WebSocket message types
 */
export type WSMessageType =
  | 'target_update'
  | 'command_output'
  | 'scheduled_output'
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
 * WebSocket scheduled output message
 */
export interface WSScheduledOutputMessage extends WSMessage {
  type: 'scheduled_output';
  data: {
    command_name: string;
    target: string;
    output: ScheduledCommandOutput;
  };
}

/**
 * WebSocket targets list message
 */
export interface WSTargetsListMessage extends WSMessage {
  type: 'targets_list';
  data: Target[];
}
