import axios from 'axios';
import type {
  Target,
  TargetsResponse,
  Command,
  CommandOutput,
  HealthResponse,
} from '../types';
import { mockApi } from './mockApi';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

/**
 * Axios instance with base configuration
 */
const axiosInstance = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Real API service for interacting with the Labgrid Dashboard backend
 */
const realApi = {
  /**
   * Get all targets with their current status
   */
  getTargets: () =>
    axiosInstance.get<TargetsResponse>('/api/targets'),

  /**
   * Get a single target by name
   */
  getTarget: (name: string) =>
    axiosInstance.get<Target>(`/api/targets/${encodeURIComponent(name)}`),

  /**
   * Get available commands for a target
   */
  getCommands: (name: string) =>
    axiosInstance.get<Command[]>(`/api/targets/${encodeURIComponent(name)}/commands`),

  /**
   * Execute a command on a target
   */
  executeCommand: (targetName: string, commandName: string) =>
    axiosInstance.post<CommandOutput>(
      `/api/targets/${encodeURIComponent(targetName)}/command`,
      { command_name: commandName }
    ),

  /**
   * Check backend health status
   */
  getHealth: () =>
    axiosInstance.get<HealthResponse>('/api/health'),
};

/**
 * Export the appropriate API based on environment
 */
export const api = USE_MOCK ? mockApi : realApi;

export default api;
