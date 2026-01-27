/**
 * Tests for the useTargets hook.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { useTargets } from '../../hooks/useTargets';

// Mock the API module
vi.mock('../../services/api', () => ({
  api: {
    getTargets: vi.fn(),
  },
}));

import { api } from '../../services/api';

const mockTargets = [
  {
    name: 'test-dut-1',
    status: 'available',
    acquired_by: null,
    ip_address: '192.168.1.100',
    resources: [],
    last_command_outputs: [],
  },
  {
    name: 'test-dut-2',
    status: 'acquired',
    acquired_by: 'tester@host',
    ip_address: '192.168.1.101',
    resources: [],
    last_command_outputs: [],
  },
];

describe('useTargets', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches targets on mount', async () => {
    vi.mocked(api.getTargets).mockResolvedValueOnce({
      data: { targets: mockTargets, total: 2 },
    } as never);

    const { result } = renderHook(() => useTargets());

    // Initially loading
    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.targets).toHaveLength(2);
    expect(result.current.error).toBeNull();
    expect(api.getTargets).toHaveBeenCalledTimes(1);
  });

  it('sets error on fetch failure', async () => {
    const errorMessage = 'Network error';
    vi.mocked(api.getTargets).mockRejectedValueOnce(new Error(errorMessage));

    const { result } = renderHook(() => useTargets());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe(errorMessage);
    expect(result.current.targets).toHaveLength(0);
  });

  it('provides refetch function', async () => {
    vi.mocked(api.getTargets).mockResolvedValue({
      data: { targets: mockTargets, total: 2 },
    } as never);

    const { result } = renderHook(() => useTargets());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Call refetch
    await act(async () => {
      await result.current.refetch();
    });

    // Should have called getTargets twice (initial + refetch)
    expect(api.getTargets).toHaveBeenCalledTimes(2);
  });

  it('updates targets on refetch', async () => {
    vi.mocked(api.getTargets)
      .mockResolvedValueOnce({
        data: { targets: [mockTargets[0]], total: 1 },
      } as never)
      .mockResolvedValueOnce({
        data: { targets: mockTargets, total: 2 },
      } as never);

    const { result } = renderHook(() => useTargets());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.targets).toHaveLength(1);

    // Refetch
    await act(async () => {
      await result.current.refetch();
    });

    await waitFor(() => {
      expect(result.current.targets).toHaveLength(2);
    });
  });
});
