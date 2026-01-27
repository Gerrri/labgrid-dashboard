/**
 * Tests for the main App component.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import App from '../App';

// Mock the API module
vi.mock('../services/api', () => ({
  api: {
    getHealth: vi.fn().mockResolvedValue({
      data: {
        status: 'healthy',
        coordinator_connected: true,
        service: 'labgrid-dashboard-backend',
      },
    }),
    getTargets: vi.fn().mockResolvedValue({
      data: {
        targets: [
          {
            name: 'test-dut-1',
            status: 'available',
            acquired_by: null,
            ip_address: '192.168.1.100',
            web_url: null,
            resources: [],
            last_command_outputs: [],
            scheduled_outputs: {},
          },
        ],
        total: 1,
      },
    }),
    getPresets: vi.fn().mockResolvedValue({
      data: {
        presets: [
          {
            id: 'basic',
            name: 'Basic',
            description: 'Standard commands',
          },
        ],
        default_preset: 'basic',
      },
    }),
    getTargetPreset: vi.fn().mockResolvedValue({
      data: {
        target_name: 'test-dut-1',
        preset_id: 'basic',
        preset: {
          id: 'basic',
          name: 'Basic',
          description: 'Standard commands',
        },
      },
    }),
    getPresetDetail: vi.fn().mockResolvedValue({
      data: {
        id: 'basic',
        name: 'Basic',
        description: 'Standard commands',
        commands: [],
        scheduled_commands: [],
        auto_refresh_commands: [],
      },
    }),
  },
}));

// Mock the WebSocket hook
vi.mock('../hooks/useWebSocket', () => ({
  useWebSocket: () => ({
    connected: true,
    subscribe: vi.fn(),
    sendCommand: vi.fn(),
  }),
}));

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the app header', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Labgrid Dashboard')).toBeInTheDocument();
    });
  });

  it('shows loading spinner initially', () => {
    render(<App />);

    // The loading spinner should be present initially
    expect(screen.getByText('Loading targets...')).toBeInTheDocument();
  });

  it('displays targets after loading', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('test-dut-1')).toBeInTheDocument();
    });
  });

  it('shows connection status when connected', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  it('shows target count in footer', async () => {
    render(<App />);

    await waitFor(() => {
      const footerCount = document.querySelector('.target-count');
      expect(footerCount).not.toBeNull();
      expect(footerCount).toHaveTextContent('1 target found');
    });
  });
});
