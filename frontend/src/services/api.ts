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

// Runtime environment configuration (injected by entrypoint.sh in production)
// In production with nginx proxy, use relative URL "/api"
declare global {
  interface Window {
    ENV?: {
      API_URL: string;
      WS_URL: string;
    };
  }
}

const API_BASE = window.ENV?.API_URL || import.meta.env.VITE_API_URL || "http://localhost:8000";

/**
 * Axios instance with base configuration
 */
const axiosInstance = axios.create({
  baseURL: API_BASE,
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
  getTargets: () => axiosInstance.get<TargetsResponse>("/api/targets"),

  /**
   * Get a single target by name
   */
  getTarget: (name: string) =>
    axiosInstance.get<Target>(`/api/targets/${encodeURIComponent(name)}`),

  /**
   * Get available commands for a target
   */
  getCommands: (name: string, config?: AxiosRequestConfig) =>
    axiosInstance.get<Command[]>(
      `/api/targets/${encodeURIComponent(name)}/commands`,
      config,
    ),

  /**
   * Execute a command on a target
   */
  executeCommand: (targetName: string, commandName: string) =>
    axiosInstance.post<CommandOutput>(
      `/api/targets/${encodeURIComponent(targetName)}/command`,
      { command_name: commandName },
    ),

  /**
   * Check backend health status
   */
  getHealth: () => axiosInstance.get<HealthResponse>("/api/health"),

  /**
   * Get scheduled commands configuration
   */
  getScheduledCommands: () =>
    axiosInstance.get<ScheduledCommandsResponse>(
      "/api/targets/scheduled-commands",
    ),

  /**
   * Get all available presets
   */
  getPresets: (config?: AxiosRequestConfig) =>
    axiosInstance.get<PresetsResponse>("/api/presets", config),

  /**
   * Get detailed information about a preset including its commands
   */
  getPresetDetail: (presetId: string, config?: AxiosRequestConfig) =>
    axiosInstance.get<PresetDetail>(
      `/api/presets/${encodeURIComponent(presetId)}`,
      config,
    ),

  /**
   * Get the current preset for a target
   */
  getTargetPreset: (targetName: string, config?: AxiosRequestConfig) =>
    axiosInstance.get<TargetPresetResponse>(
      `/api/targets/${encodeURIComponent(targetName)}/preset`,
      config,
    ),

  /**
   * Set the preset for a target
   */
  setTargetPreset: (targetName: string, presetId: string) =>
    axiosInstance.put<TargetPresetResponse>(
      `/api/targets/${encodeURIComponent(targetName)}/preset`,
      { preset_id: presetId },
    ),
};

export default api;
