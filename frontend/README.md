# Labgrid Dashboard Frontend

React-based frontend for the Labgrid Dashboard, built with TypeScript and Vite.

## Technology Stack

- **React 19** - UI Framework
- **TypeScript** - Type safety
- **Vite 7** - Build tool and dev server
- **Vitest** - Testing framework

## Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Run linting
npm run lint

# Run tests
npm test
npm run test:ui       # With Vitest UI
npm run test:coverage # With coverage report
```

## Project Structure

```
src/
├── components/
│   ├── CommandPanel/      # Command execution UI
│   │   ├── CommandButton.tsx
│   │   ├── CommandPanel.tsx
│   │   ├── OutputViewer.tsx
│   │   └── CommandPanel.css
│   ├── TargetTable/       # Target list display
│   │   ├── TargetTable.tsx    # Main table component
│   │   ├── TargetRow.tsx      # Individual target row
│   │   ├── StatusBadge.tsx    # Status indicator
│   │   └── TargetTable.css
│   ├── TargetSettings/    # Preset configuration UI
│   │   ├── TargetSettings.tsx
│   │   └── TargetSettings.css
│   └── common/            # Shared components
│       ├── ConnectionStatus.tsx
│       ├── ErrorMessage.tsx
│       ├── LoadingSpinner.tsx
│       └── RefreshControl.tsx
├── hooks/
│   ├── useTargets.ts           # Target data fetching
│   ├── usePresetsWithTargets.ts # Grouped preset/target data
│   └── useWebSocket.ts         # Real-time updates
├── services/
│   └── api.ts             # API client for backend communication
├── types/
│   └── index.ts           # TypeScript type definitions
├── __tests__/             # Test files
├── App.tsx                # Main application component
└── main.tsx               # Application entry point
```

## Key Features

### Hardware Presets
Targets are grouped by their assigned preset in the UI:
- Each preset group has its own table section
- Preset-specific scheduled commands shown as columns
- Empty preset groups are automatically hidden

### Settings Panel
Click the ⚙️ icon in an expanded target to:
- View available presets
- See commands included in each preset
- Change the target's preset assignment

### Real-time Updates
WebSocket connection provides live status updates without manual refresh.

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | Backend API URL | `http://localhost:8000` |
| `VITE_WS_URL` | Backend WebSocket URL | `ws://localhost:8000/api/ws` |

## API Integration

The frontend communicates with the backend via:

- **REST API** - Target data, commands, presets
- **WebSocket** - Real-time status updates

Key API methods in `services/api.ts`:
- `getTargets()` - Fetch all targets
- `getPresets()` - List available presets
- `getPresetDetail(id)` - Get preset commands
- `getTargetPreset(name)` - Get target's current preset
- `setTargetPreset(name, presetId)` - Assign preset to target
- `executeCommand(name, command)` - Run command on target

## Testing

```bash
# Run all tests
npm test

# Run with UI
npm run test:ui

# Generate coverage report
npm run test:coverage
```

Tests are located in `src/__tests__/` and use Vitest with React Testing Library.
