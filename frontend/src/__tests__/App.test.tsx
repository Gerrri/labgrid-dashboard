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
        mock_mode: true,
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
            resources: [],
            last_command_outputs: [],
          },
        ],
        total: 1,
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

  it('shows mock mode badge when in mock mode', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Mock Mode')).toBeInTheDocument();
    });
  });

  it('shows target count in footer', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/1 target found/)).toBeInTheDocument();
    });
  });
});
