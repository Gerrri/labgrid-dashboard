import axios from "axios";
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

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

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
  getTargets: () => axiosInstance.get<any>("/api/targets"),

  /**
   * Get a single target by name
   */
  getTarget: (name: string) => axiosInstance.get<Target>(`/api/targets/${name}`),

  /**
   * Get available commands for a target
   */
  getCommands: (name: string) =>
    axiosInstance.get<Command[]>(
      `/api/targets/${encodeURIComponent(name)}/commands`,
    ),

  /**
   * Execute a command on a target
   */
  executeCommand: (targetName: string, commandName: string) => {
    console.log("Executing command", targetName, commandName);
    return axiosInstance.post<CommandOutput>(
      `/api/targets/${encodeURIComponent(targetName)}/command`,
      { command_name: commandName },
    );
  },

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
  getPresets: () => axiosInstance.get<PresetsResponse>("/api/presets"),

  /**
   * Get detailed information about a preset including its commands
   */
  getPresetDetail: (presetId: string) =>
    axiosInstance.get<PresetDetail>(
      `/api/presets/${encodeURIComponent(presetId)}`,
    ),

  /**
   * Get the current preset for a target
   */
  getTargetPreset: (targetName: string) =>
    axiosInstance.get<TargetPresetResponse>(
      `/api/targets/${encodeURIComponent(targetName)}/preset`,
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
