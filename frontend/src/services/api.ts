import axios, { type AxiosRequestConfig } from "axios";
import type {
  Target,
  TargetsResponse,
  Command,
  CommandOutput,
  HealthResponse,
  ScheduledCommandsResponse,
  PresetsResponse,
  PresetDetail,
  TargetPresetResponse,
} from "../types";
import { buildApiUrl } from "../utils/urlBuilder";

/**
 * Axios instance with base configuration
 */
const axiosInstance = axios.create({
  timeout: 10000,
  headers: {
    "Content-Type": "application/json",
  },
});

/**
 * API service for interacting with the Labgrid Dashboard backend
 */
export const api = {
  /**
   * Get all targets with their current status
   */
  getTargets: (config?: AxiosRequestConfig) =>
    axiosInstance.get<TargetsResponse>(buildApiUrl("/api/targets"), config),

  /**
   * Get a single target by name
   */
  getTarget: (name: string) =>
    axiosInstance.get<Target>(
      buildApiUrl(`/api/targets/${encodeURIComponent(name)}`),
    ),

  /**
   * Get available commands for a target
   */
  getCommands: (name: string, config?: AxiosRequestConfig) =>
    axiosInstance.get<Command[]>(
      buildApiUrl(`/api/targets/${encodeURIComponent(name)}/commands`),
      config,
    ),

  /**
   * Execute a command on a target
   */
  executeCommand: (targetName: string, commandName: string) =>
    axiosInstance.post<CommandOutput>(
      buildApiUrl(`/api/targets/${encodeURIComponent(targetName)}/command`),
      { command_name: commandName },
    ),

  /**
   * Check backend health status
   */
  getHealth: () => axiosInstance.get<HealthResponse>(buildApiUrl("/api/health")),

  /**
   * Get scheduled commands configuration
   */
  getScheduledCommands: () =>
    axiosInstance.get<ScheduledCommandsResponse>(
      buildApiUrl("/api/targets/scheduled-commands"),
    ),

  /**
   * Get all available presets
   */
  getPresets: (config?: AxiosRequestConfig) =>
    axiosInstance.get<PresetsResponse>(buildApiUrl("/api/presets"), config),

  /**
   * Get detailed information about a preset including its commands
   */
  getPresetDetail: (presetId: string, config?: AxiosRequestConfig) =>
    axiosInstance.get<PresetDetail>(
      buildApiUrl(`/api/presets/${encodeURIComponent(presetId)}`),
      config,
    ),

  /**
   * Get the current preset for a target
   */
  getTargetPreset: (targetName: string, config?: AxiosRequestConfig) =>
    axiosInstance.get<TargetPresetResponse>(
      buildApiUrl(`/api/targets/${encodeURIComponent(targetName)}/preset`),
      config,
    ),

  /**
   * Set the preset for a target
   */
  setTargetPreset: (targetName: string, presetId: string) =>
    axiosInstance.put<TargetPresetResponse>(
      buildApiUrl(`/api/targets/${encodeURIComponent(targetName)}/preset`),
      { preset_id: presetId },
    ),
};

export default api;
