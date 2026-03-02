# Testing Guide

This document describes repeatable verification steps for changes in this repository.

Do not record point-in-time pass/fail results, test counts, or temporary failures here. Update this file only when the testing process changes.

## Required Test Environment

Use staging mode for integration testing:

```bash
docker compose --profile staging up -d --build
```

This is the default environment for validating end-to-end behavior because it exercises the frontend, backend, coordinator, exporters, and scheduled command flow together.

## Baseline Checks

Run the smallest relevant checks for the change you made:

### Frontend Build

```bash
cd frontend
npm run build
```

### Backend Tests

```bash
cd backend
python -m pytest
```

### Production Image Smoke Test

```bash
./scripts/test-production-image.sh
```

## Manual Verification Scenarios

Choose the scenarios that match the change set.

### XSS Protection for `web_url`

1. Open a target that exposes a `web_url`.
2. Verify normal `http://` and `https://` links still render as links.
3. Verify invalid or unsafe values such as `javascript:` and `data:` render as plain text.
4. Confirm no script execution occurs when interacting with the rendered IP address.

### Command Output Ordering

1. Open a target command panel.
2. Trigger multiple commands in quick succession.
3. Confirm every result is shown.
4. Confirm newer results appear first and older results remain visible.

### Preset Loading and Caching

1. Open target settings for a target.
2. Confirm presets and the current assignment load successfully.
3. Close and reopen the dialog.
4. Confirm preset details are still available and there are no duplicate fetch regressions.

### Component Unmount Handling

1. Open target settings or a command panel on a throttled network.
2. Close the UI immediately before requests finish.
3. Confirm the UI closes cleanly.
4. Confirm there are no stale state update warnings or broken loading states.

### Scheduled Output Rendering

1. Verify recent successful scheduled outputs are shown in the table.
2. Verify failed scheduled outputs display `N/A`.
3. Verify invalid timestamps display `N/A`.
4. Verify stale cached values expire as expected.

### WebSocket Connectivity

1. Start the staging stack.
2. Open the dashboard.
3. Confirm the WebSocket connects successfully.
4. Confirm live target updates appear without a page reload.

## Production Deployment Verification

Use this when validating the production image or release process:

```bash
docker build -t labgrid-dashboard:test -f Dockerfile.prod .

docker run -d \
  --name labgrid-test \
  -p 8080:80 \
  -e COORDINATOR_URL=ws://your-coordinator:20408/ws \
  labgrid-dashboard:test
```

Check:

- `http://localhost:8080/health` returns the nginx health response
- `http://localhost:8080/api/health` returns the backend health payload
- `http://localhost:8080/` serves the frontend
- `http://localhost:8080/env-config.js` serves runtime configuration

## Regression Checklist

Before merging a non-trivial change, verify these still work:

- Target expansion and collapse
- Command execution
- Preset assignment changes
- Scheduled command columns
- Target settings dialog
- Real-time updates via WebSocket

## Maintenance Notes

- Keep this document procedural.
- Reference release-specific outcomes in pull requests, CI logs, or release notes instead of here.
- If the test workflow changes, update this file and the release checklist together.
