# Labgrid Dashboard

A web-based dashboard for monitoring and interacting with devices (DUTs) managed by a [Labgrid](https://github.com/labgrid-project/labgrid) Coordinator.

## ⚠️ Disclaimer

> **This project is largely developed using AI-assisted "vibe coding".**
> 
> While functional, the code may contain patterns, approaches, or implementations that were generated with significant AI assistance. Use in production environments should be done with appropriate review and testing.

## What is this project?

Labgrid Dashboard provides a real-time web interface to:

- **View all targets** managed by your Labgrid Coordinator in a clean table view
- **Monitor status** - See which devices are available, acquired, or offline
- **Track ownership** - Know who currently has acquired each exporter/target
- **Quick access** - Click on IP addresses to directly access device web interfaces
- **Execute commands** - Run predefined commands on DUTs and view their outputs
- **Real-time updates** - WebSocket-based live status updates without manual refresh

## Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | React + TypeScript |
| Backend | Python + FastAPI |
| Real-time | WebSockets |
| Labgrid Communication | WAMP Protocol (via autobahn) |
| Development | Docker Compose |

## Project Status

🚧 **Under Development** 🚧

See [`plans/architecture-plan.md`](plans/architecture-plan.md) for the full architecture documentation.

## Getting Started

*Documentation will be added as the project develops.*

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## License

*License to be determined.*
