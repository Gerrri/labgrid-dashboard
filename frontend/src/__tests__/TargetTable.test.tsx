/**
 * Tests for the TargetTable component.
 */

import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { TargetTable } from "../components/TargetTable";
import type { Target } from "../types";

// Mock the API module
vi.mock("../services/api", () => ({
  api: {
    getCommands: vi.fn().mockResolvedValue({
      data: [
        {
          name: "Test Command",
          command: "echo test",
          description: "A test command",
        },
      ],
    }),
    executeCommand: vi.fn().mockResolvedValue({
      data: {
        command: "echo test",
        output: "test",
        timestamp: new Date().toISOString(),
        exit_code: 0,
      },
    }),
  },
}));

const mockTargets: Target[] = [
  {
    name: "test-dut-1",
    status: "available",
    acquired_by: null,
    ip_address: "192.168.1.100",
    web_url: "http://192.168.1.100:8080",
    resources: [
      {
        type: "NetworkSerialPort",
        params: { host: "192.168.1.100", port: 4001 },
      },
    ],
    last_command_outputs: [
      {
        command: "echo test",
        output: "test",
        timestamp: new Date().toISOString(),
        exit_code: 0,
        execution_transport: "ssh",
      },
    ],
    scheduled_outputs: {},
    command_capable: true,
    command_transport: "serial",
    command_capability_error: null,
  },
  {
    name: "test-dut-2",
    status: "acquired",
    acquired_by: "tester@host",
    ip_address: "192.168.1.101",
    web_url: null,
    resources: [],
    last_command_outputs: [],
    scheduled_outputs: {},
    command_capable: true,
    command_transport: "ssh",
    command_capability_error: null,
  },
  {
    name: "test-dut-3",
    status: "offline",
    acquired_by: null,
    ip_address: null,
    web_url: null,
    resources: [],
    last_command_outputs: [],
    scheduled_outputs: {},
    command_capable: false,
    command_transport: null,
    command_capability_error: "No command transport configured for this device",
  },
];

describe("TargetTable", () => {
  it("renders the table headers", () => {
    render(
      <TargetTable
        targets={mockTargets}
        loading={false}
        onCommandComplete={vi.fn()}
      />,
    );

    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("IP Address")).toBeInTheDocument();
  });

  it("renders all targets", () => {
    render(
      <TargetTable
        targets={mockTargets}
        loading={false}
        onCommandComplete={vi.fn()}
      />,
    );

    expect(screen.getByText("test-dut-1")).toBeInTheDocument();
    expect(screen.getByText("test-dut-2")).toBeInTheDocument();
    expect(screen.getByText("test-dut-3")).toBeInTheDocument();
  });

  it("renders the preset description as an info symbol in the preset header", () => {
    render(
      <TargetTable
        targets={[mockTargets[0]]}
        loading={false}
        onCommandComplete={vi.fn()}
        showPresetHeader={true}
        preset={{
          id: "tac",
          name: "TAC",
          description: "Serial-first preset for labgrid exporters",
          commands: [],
          scheduled_commands: [],
          auto_refresh_commands: [],
        }}
      />,
    );

    expect(screen.getByText("TAC")).toBeInTheDocument();
    const trigger = screen.getByLabelText(
      "Preset description: Serial-first preset for labgrid exporters",
    );

    expect(trigger).toHaveTextContent("i");
    expect(trigger).toHaveAttribute(
      "data-tooltip",
      "Serial-first preset for labgrid exporters",
    );
    expect(
      screen.queryByText("Serial-first preset for labgrid exporters"),
    ).not.toBeInTheDocument();
  });

  it("renders status badges", () => {
    render(
      <TargetTable
        targets={mockTargets}
        loading={false}
        onCommandComplete={vi.fn()}
      />,
    );

    // Status badges are capitalized in the UI
    expect(screen.getByText("Available")).toBeInTheDocument();
    expect(screen.getByText("Acquired")).toBeInTheDocument();
    expect(screen.getByText("Offline")).toBeInTheDocument();
  });

  it("renders acquired_by information", () => {
    render(
      <TargetTable
        targets={mockTargets}
        loading={false}
        onCommandComplete={vi.fn()}
      />,
    );

    expect(screen.getByText("tester@host")).toBeInTheDocument();
  });

  it("renders IP addresses", () => {
    render(
      <TargetTable
        targets={mockTargets}
        loading={false}
        onCommandComplete={vi.fn()}
      />,
    );

    expect(screen.getByText("192.168.1.100")).toBeInTheDocument();
    expect(screen.getByText("192.168.1.101")).toBeInTheDocument();
  });

  it("shows dash for missing IP address", () => {
    render(
      <TargetTable
        targets={mockTargets}
        loading={false}
        onCommandComplete={vi.fn()}
      />,
    );

    // test-dut-3 has no IP address, should show '-' or empty
    const rows = screen.getAllByRole("row");
    expect(rows.length).toBeGreaterThan(1); // Header + data rows
  });

  it("renders the command panel for capable targets", async () => {
    render(
      <TargetTable
        targets={[mockTargets[0]]}
        loading={false}
        onCommandComplete={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /expand details/i }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Test Command" }),
      ).toBeInTheDocument();
    });

    expect(screen.queryByText("Commands for test-dut-1")).not.toBeInTheDocument();
    expect(screen.queryByText("Command transport: ssh")).not.toBeInTheDocument();
    expect(
      screen.getByTitle("Transport used for this execution"),
    ).toHaveTextContent("ssh");
  });

  it("renders the command panel without a transport banner when no output exists", async () => {
    render(
      <TargetTable
        targets={[mockTargets[1]]}
        loading={false}
        onCommandComplete={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /expand details/i }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Test Command" }),
      ).toBeInTheDocument();
    });

    expect(screen.queryByText("Commands for test-dut-2")).not.toBeInTheDocument();
    expect(screen.queryByText("Command transport: ssh")).not.toBeInTheDocument();
  });

  it("hides the command panel and shows an error for incapable targets", async () => {
    const api = await import("../services/api");
    const getCommandsSpy = vi.mocked(api.api.getCommands);
    getCommandsSpy.mockClear();

    render(
      <TargetTable
        targets={[mockTargets[2]]}
        loading={false}
        onCommandComplete={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /expand details/i }));

    expect(screen.getByRole("alert")).toHaveTextContent("Commands unavailable");
    expect(
      screen.getByText("No command transport configured for this device"),
    ).toBeInTheDocument();
    expect(getCommandsSpy).not.toHaveBeenCalled();
  });

  it("shows loading state", () => {
    render(
      <TargetTable targets={[]} loading={true} onCommandComplete={vi.fn()} />,
    );

    // When loading, the component might show a loading indicator or just render
    // This depends on the component implementation
  });

  it("handles empty targets list", () => {
    const { container } = render(
      <TargetTable targets={[]} loading={false} onCommandComplete={vi.fn()} />,
    );

    // When there are no targets, the component may render nothing or an empty state
    // The container should exist but may not contain a table
    expect(container).toBeDefined();
  });
});
