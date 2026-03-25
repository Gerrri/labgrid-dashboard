# Serial-Preferred Command Execution Plan

## Goal

Extend the dashboard so command execution prefers a serial shell and falls back to SSH only when serial execution is not available for the target.

The feature must apply to:

- manual commands
- scheduled commands
- REST and WebSocket execution paths

It must also expose per-target command capability so the frontend can hide command buttons and show a device-specific message when no supported execution transport is available.

## Current Constraints

- Command execution is currently hardcoded to `labgrid-client ssh` in `backend/app/services/labgrid_client.py`.
- Both REST and WebSocket command paths use the same backend execution method, so transport selection can be centralized there.
- The API currently exposes resources and status, but not command capability or chosen execution transport.
- The frontend therefore cannot distinguish between:
  - command-capable targets
  - targets that only support SSH
  - targets that only support serial
  - targets that support neither
- LXATAC targets can be partially available even when some optional USB-related resources are offline, so transport selection must rely on actual execution capabilities instead of whole-target availability alone.

## Required Feature Behavior

### Execution Order

The execution transport order must be:

1. serial
2. ssh
3. unsupported

### Preset-Level Configuration

Each preset must be able to define how command execution should work.

The minimum planned configuration is:

- ordered transport preference per preset
- serial login automation settings per preset
- optional shell readiness settings per preset

Planned `commands.yaml` extension:

```yaml
default_preset: TAC

presets:
  TAC:
    name: "TAC"
    description: "TAC devices"

    command_execution:
      transport_order:
        - serial
        - ssh
      serial:
        login:
          enabled: true
          username: "root"
          password: "labgrid"
        prompt:
          pattern: "root@.*[#>] "
        login_timeout_seconds: 30
        command_timeout_seconds: 60

    commands:
      - name: "OS Release"
        command: "cat /etc/os-release"
        description: "Show OS release information"
```

This schema is intentionally explicit so the backend does not have to guess how to log in over serial.

## Proposed Backend Design

### 1. Add Execution Capability Detection

Determine execution capability per target from matched resources and preset configuration.

Planned backend concepts:

- `serial` capability:
  - target has an available serial-capable resource
  - preset permits serial execution
  - serial login/shell settings are available if required
- `ssh` capability:
  - target has an available SSH-capable resource
  - preset permits SSH execution
- `none` capability:
  - neither serial nor SSH can be used safely

Planned output per target:

- `execution_transport`: `serial` | `ssh` | `none`
- `command_capable`: `true` | `false`
- `command_capability_error`: nullable string with a user-facing explanation

### 2. Refactor Command Execution Into Transport Selectors

Refactor the current backend method into:

- transport selection
- transport-specific execution
- shared acquire/release handling

Planned structure inside `LabgridClient`:

- `_select_execution_transport(place_name, preset_execution_config)`
- `_execute_via_ssh(place_name, command)`
- `_execute_via_serial(place_name, command, serial_config)`
- shared `execute_command(...)` wrapper that:
  - acquires target
  - selects transport
  - runs command
  - releases target

### 3. Keep HTTP and WebSocket Behavior Unified

REST and WebSocket paths should continue using the same backend execution API.

That keeps:

- identical transport behavior
- identical error handling
- identical state updates

### 4. Add Target Capability Information To API Models

The frontend needs capability data from the backend instead of inferring it from resource names.

Planned API model additions:

- `command_capable`
- `execution_transport`
- `command_capability_error`

These fields should be present in:

- `GET /api/targets`
- `GET /api/targets/{name}`
- WebSocket target updates
- WebSocket full target list payloads

## Serial Execution Strategy

### Preferred Implementation Direction

Use a dedicated backend serial execution path, not a frontend workaround.

The current SSH implementation works by shelling out to `labgrid-client ssh`.
For serial, there are two possible approaches:

1. CLI-driven approach
   - use `labgrid-client console`
   - automate login and command execution via a PTY session

2. Python/labgrid driver approach
   - use labgrid driver APIs directly
   - activate a shell-capable serial driver
   - run commands through the driver

The recommended implementation path is:

- first validate whether the production runtime can reliably automate `labgrid-client console`
- if that proves too fragile, switch to direct Python/labgrid integration for serial

### Why Serial Needs More Than `NetworkSerialPort`

`NetworkSerialPort` alone does not guarantee command execution.

Robust serial command execution also needs:

- login prompt detection
- username/password automation
- shell prompt detection
- command completion handling
- timeout handling
- reconnect behavior when the line is noisy or the DUT reboots

## Frontend Changes

### Target Table

Update the target row rendering so command controls depend on backend-provided capability instead of only target status.

Planned behavior:

- if `command_capable` is `true`:
  - show normal command UI
- if `command_capable` is `false`:
  - hide command buttons
  - show target-specific explanation from `command_capability_error`

### Optional UI Enhancement

Optionally show the selected execution transport in the UI:

- `Serial`
- `SSH`
- `Unavailable`

This is not required for the first implementation, but it would simplify debugging.

## Tests To Add Or Update

### Backend Unit Tests

Add tests for:

- transport selection prefers serial over SSH
- serial fallback to SSH when serial is unavailable
- `none` transport returns a clear error
- target capability fields are populated correctly
- per-preset transport configuration is respected
- serial login automation configuration validation

### API Tests

Add tests for:

- `GET /api/targets` includes capability fields
- `GET /api/targets/{name}` includes capability fields
- unsupported targets return the expected error on command execution

### Integration Tests

Extend staging or add a focused integration test path that validates:

- serial-preferred transport selection
- scheduled commands use the same transport order

## Files Expected To Change

Backend:

- `backend/app/services/labgrid_client.py`
- `backend/app/services/command_service.py`
- `backend/app/models/target.py`
- `backend/app/api/routes/targets.py`
- `backend/app/api/websocket.py`
- `backend/app/config.py` if new runtime settings are required

Frontend:

- `frontend/src/types/index.ts`
- `frontend/src/hooks/usePresetsWithTargets.ts`
- `frontend/src/components/TargetTable/TargetRow.tsx`
- `frontend/src/components/CommandPanel/*` if command capability display is needed

Tests:

- `backend/tests/test_labgrid_client.py`
- `backend/tests/test_targets.py`
- `backend/tests/test_acquire_release.py`
- frontend tests for command visibility

Planning/Documentation:

- `plans/serial-command-execution-plan.md`

## Implementation Order

1. Extend preset configuration model for transport order and serial login settings
2. Add capability detection and target capability fields
3. Refactor SSH execution into a dedicated transport executor
4. Implement serial executor
5. Update REST and WebSocket payloads
6. Update frontend to hide commands and show per-device capability errors
7. Add tests
8. Validate with staging and production image

## Open Questions

The following items must be confirmed before the implementation is finalized:

1. What exact `commands.yaml` schema should be used for per-preset execution config?
2. Should serial login credentials be stored in `commands.yaml`, in environment variables, or in a separate secret-backed config source?
3. What prompt patterns must be supported for serial login and shell readiness?
4. Should scheduled commands use the same transport selection logic without exception?
5. Should unsupported targets suppress the entire command panel or show a reduced read-only panel with the explanation?
6. Is `labgrid-client console` automation acceptable as the first implementation, or must serial execution use the Python labgrid driver API from the start?

## Success Criteria

The feature is complete when:

- LXATAC targets prefer serial command execution
- SSH is used only when serial execution is unavailable for the target and preset
- unsupported targets hide command actions and show a clear reason
- scheduled commands use the same transport order
- the backend and frontend expose the selected transport clearly enough for debugging
- the behavior is covered by tests and passes local verification
