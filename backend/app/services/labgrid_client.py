"""
WAMP client for Labgrid Coordinator communication.

This service handles the connection to the Labgrid Coordinator using the WAMP protocol
via the autobahn library. It provides methods to query places/targets, subscribe
to real-time updates, and execute commands on targets.
"""

import asyncio
import logging
import socket
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.config import get_settings
from app.models.target import CommandOutput, Resource, Target

logger = logging.getLogger(__name__)

# Constants for serial communication
COMMAND_TIMEOUT = 30  # seconds
READ_BUFFER_SIZE = 4096
COMMAND_DELAY = 0.1  # seconds to wait after sending command


class LabgridClient:
    """Async WAMP client for Labgrid Coordinator communication."""

    def __init__(
        self,
        url: str = "ws://coordinator:20408/ws",
        realm: str = "realm1",
        timeout: int = 30,
    ):
        """Initialize the Labgrid client.

        Args:
            url: WebSocket URL of the Labgrid Coordinator.
            realm: WAMP realm to join.
            timeout: Connection timeout in seconds.
        """
        self._url = url
        self._realm = realm
        self._timeout = timeout
        self._connected = False
        self._session = None
        self._subscriptions: List[Any] = []
        self._mock_mode = False

        # Mock data for development/testing when coordinator is not available
        self._mock_places: Dict[str, Dict[str, Any]] = {
            "dut-1": {
                "name": "dut-1",
                "acquired": None,
                "acquired_resources": [],
                "allowed": {"*"},
                "changed": 1704067200.0,
                "comment": "Development board 1",
                "matches": {},
                "tags": {"board": "rpi4", "location": "lab-1"},
            },
            "dut-2": {
                "name": "dut-2",
                "acquired": "developer@host",
                "acquired_resources": ["NetworkSerialPort"],
                "allowed": {"*"},
                "changed": 1704067200.0,
                "comment": "Development board 2",
                "matches": {},
                "tags": {"board": "beaglebone", "location": "lab-1"},
            },
            "dut-3": {
                "name": "dut-3",
                "acquired": None,
                "acquired_resources": [],
                "allowed": {"*"},
                "changed": 1704067200.0,
                "comment": "Development board 3 (offline)",
                "matches": {},
                "tags": {"board": "jetson", "location": "lab-2"},
            },
        }

    @property
    def connected(self) -> bool:
        """Check if the client is connected to the coordinator."""
        return self._connected

    @property
    def mock_mode(self) -> bool:
        """Check if the client is running in mock mode."""
        return self._mock_mode

    async def connect(self) -> bool:
        """Connect to the Labgrid Coordinator.

        Returns:
            True if connection was successful, False otherwise.
        """
        settings = get_settings()

        # Check if mock mode is explicitly enabled
        if settings.mock_mode.lower() == "true":
            logger.info("Mock mode explicitly enabled via configuration")
            self._enable_mock_mode()
            return True

        try:
            logger.info(f"Connecting to Labgrid Coordinator at {self._url}...")

            # Try to establish WAMP connection
            try:
                from autobahn.asyncio.wamp import ApplicationSession, ApplicationRunner

                # Create a custom session class for our connection
                connected_event = asyncio.Event()
                session_holder: Dict[str, Any] = {"session": None}

                class LabgridSession(ApplicationSession):
                    async def onJoin(self, details):
                        logger.info(f"Joined WAMP realm: {details.realm}")
                        session_holder["session"] = self
                        connected_event.set()

                    def onDisconnect(self):
                        logger.warning("Disconnected from WAMP router")
                        connected_event.clear()

                runner = ApplicationRunner(url=self._url, realm=self._realm)

                # Start the runner in a background task
                asyncio.create_task(runner.run(LabgridSession, start_loop=False))

                # Wait for connection with timeout
                try:
                    await asyncio.wait_for(connected_event.wait(), timeout=self._timeout)
                    self._session = session_holder["session"]
                    self._connected = True
                    self._mock_mode = False
                    logger.info("Successfully connected to Labgrid Coordinator")
                    return True
                except asyncio.TimeoutError:
                    # Check if auto-fallback to mock is allowed
                    if settings.mock_mode.lower() == "auto":
                        logger.warning(
                            f"Connection timeout after {self._timeout}s, falling back to mock mode"
                        )
                        self._enable_mock_mode()
                        return True
                    else:
                        logger.error(
                            f"Connection timeout after {self._timeout}s, mock mode disabled"
                        )
                        return False

            except ImportError:
                if settings.mock_mode.lower() == "auto":
                    logger.warning("autobahn not available, using mock mode")
                    self._enable_mock_mode()
                    return True
                else:
                    logger.error("autobahn not available and mock mode disabled")
                    return False
            except Exception as e:
                if settings.mock_mode.lower() == "auto":
                    logger.warning(f"Failed to connect to coordinator: {e}, using mock mode")
                    self._enable_mock_mode()
                    return True
                else:
                    logger.error(f"Failed to connect to coordinator: {e}, mock mode disabled")
                    return False

        except Exception as e:
            logger.error(f"Unexpected error during connection: {e}")
            if settings.mock_mode.lower() == "auto":
                self._enable_mock_mode()
                return True
            return False

    def _enable_mock_mode(self) -> None:
        """Enable mock mode for development/testing."""
        self._mock_mode = True
        self._connected = True
        logger.info("Running in mock mode - using simulated data")

    async def disconnect(self) -> None:
        """Disconnect from the Labgrid Coordinator."""
        if self._session:
            try:
                # Unsubscribe from all subscriptions
                for sub in self._subscriptions:
                    try:
                        await sub.unsubscribe()
                    except Exception as e:
                        logger.warning(f"Error unsubscribing: {e}")
                self._subscriptions.clear()

                # Leave the session
                await self._session.leave()
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")

        self._session = None
        self._connected = False
        self._mock_mode = False
        logger.info("Disconnected from Labgrid Coordinator")

    async def get_places(self) -> List[Target]:
        """Get all places/targets from the coordinator.

        Returns:
            List of Target objects representing all places.
        """
        if self._mock_mode:
            return self._get_mock_places()

        if not self._connected or not self._session:
            logger.warning("Not connected to coordinator")
            return []

        try:
            # Call the coordinator's RPC to get places
            places_data = await self._session.call("org.labgrid.coordinator.get_places")
            return self._parse_places(places_data)
        except Exception as e:
            logger.error(f"Failed to get places: {e}")
            return []

    async def get_place_info(self, name: str) -> Optional[Target]:
        """Get detailed information about a specific place.

        Args:
            name: The place name to query.

        Returns:
            Target object if found, None otherwise.
        """
        if self._mock_mode:
            return self._get_mock_place(name)

        if not self._connected or not self._session:
            logger.warning("Not connected to coordinator")
            return None

        try:
            place_data = await self._session.call(
                "org.labgrid.coordinator.get_place", name
            )
            if place_data:
                return self._parse_place(name, place_data)
            return None
        except Exception as e:
            logger.error(f"Failed to get place info for {name}: {e}")
            return None

    async def subscribe_updates(
        self, callback: Callable[[str, Dict[str, Any]], None]
    ) -> bool:
        """Subscribe to real-time place updates.

        Args:
            callback: Function to call when a place is updated.
                     Receives (place_name, place_data) as arguments.

        Returns:
            True if subscription was successful, False otherwise.
        """
        if self._mock_mode:
            logger.info("Mock mode: subscriptions are simulated")
            return True

        if not self._connected or not self._session:
            logger.warning("Not connected to coordinator")
            return False

        try:
            # Subscribe to place change events
            sub = await self._session.subscribe(
                callback, "org.labgrid.coordinator.place_changed"
            )
            self._subscriptions.append(sub)
            logger.info("Subscribed to place updates")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to updates: {e}")
            return False

    async def execute_command(
        self, place_name: str, command: str
    ) -> Tuple[str, int]:
        """Execute a command on a target via the Labgrid Coordinator.

        This method acquires the place, executes the command via the serial
        console, and releases the place.

        Args:
            place_name: The name of the place/target to execute on.
            command: The shell command to execute.

        Returns:
            Tuple of (output, exit_code). exit_code is 0 for success.
        """
        if self._mock_mode:
            return self._mock_execute_command(place_name, command)

        if not self._connected or not self._session:
            logger.warning("Not connected to coordinator")
            return ("Error: Not connected to coordinator", 1)

        try:
            # Get place info to find the serial port resource
            place_data = await self._session.call(
                "org.labgrid.coordinator.get_place", place_name
            )
            if not place_data:
                return (f"Error: Place '{place_name}' not found", 1)

            # Get resources for this place
            resources = await self._get_place_resources(place_name)
            if not resources:
                return (f"Error: No resources found for '{place_name}'", 1)

            # Find NetworkSerialPort resource
            serial_resource = None
            for res in resources:
                if res.get("cls") == "NetworkSerialPort":
                    serial_resource = res
                    break

            if not serial_resource:
                return (f"Error: No NetworkSerialPort resource for '{place_name}'", 1)

            # Execute command via serial connection
            host = serial_resource.get("params", {}).get("host")
            port = serial_resource.get("params", {}).get("port", 5000)

            if not host:
                return ("Error: Serial resource has no host configured", 1)

            output = await self._execute_via_serial(host, port, command)
            return (output, 0)

        except Exception as e:
            logger.error(f"Failed to execute command on {place_name}: {e}")
            return (f"Error: {str(e)}", 1)

    async def _get_place_resources(self, place_name: str) -> List[Dict[str, Any]]:
        """Get resources for a place from the coordinator.

        Args:
            place_name: The place name.

        Returns:
            List of resource dictionaries.
        """
        try:
            resources = await self._session.call(
                "org.labgrid.coordinator.get_resources"
            )
            place_resources = []
            for group_name, group_resources in resources.items():
                for res_name, res_data in group_resources.items():
                    # Check if this resource belongs to our place
                    if place_name in res_name or group_name == place_name:
                        place_resources.append(res_data)
            return place_resources
        except Exception as e:
            logger.error(f"Failed to get resources: {e}")
            return []

    async def _execute_via_serial(
        self, host: str, port: int, command: str
    ) -> str:
        """Execute a command via serial-over-TCP connection.

        Args:
            host: TCP host of the serial server.
            port: TCP port of the serial server.
            command: Command to execute.

        Returns:
            Command output as string.
        """
        loop = asyncio.get_event_loop()

        def _sync_execute():
            """Synchronous execution in thread pool."""
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(COMMAND_TIMEOUT)
                sock.connect((host, port))

                # Send command with newline
                sock.sendall(f"{command}\n".encode("utf-8"))

                # Wait for response
                import time
                time.sleep(COMMAND_DELAY)

                # Read output
                output_parts = []
                sock.setblocking(False)
                try:
                    while True:
                        try:
                            data = sock.recv(READ_BUFFER_SIZE)
                            if not data:
                                break
                            output_parts.append(data.decode("utf-8", errors="replace"))
                        except BlockingIOError:
                            break
                        except socket.timeout:
                            break
                except Exception:
                    pass

                sock.close()
                return "".join(output_parts)

            except socket.timeout:
                return f"Error: Connection timeout to {host}:{port}"
            except ConnectionRefusedError:
                return f"Error: Connection refused to {host}:{port}"
            except Exception as e:
                return f"Error: {str(e)}"

        # Execute in thread pool to avoid blocking
        output = await loop.run_in_executor(None, _sync_execute)
        return output

    def _mock_execute_command(self, place_name: str, command: str) -> Tuple[str, int]:
        """Execute a mock command for development/testing.

        Args:
            place_name: The place name.
            command: The command to execute.

        Returns:
            Tuple of (mock_output, exit_code).
        """
        # Simulate some realistic outputs for common commands
        mock_outputs = {
            "date": "Mon Jan 19 08:30:00 UTC 2026",
            "hostname": place_name,
            "uptime": " 08:30:00 up 1 day,  2:15,  1 user,  load average: 0.15, 0.10, 0.05",
            "uname -a": f"Linux {place_name} 5.15.0-generic #1 SMP PREEMPT x86_64 GNU/Linux",
            "whoami": "root",
            "pwd": "/root",
            "id": "uid=0(root) gid=0(root) groups=0(root)",
            "cat /etc/os-release": 'PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\nNAME="Debian GNU/Linux"\nVERSION_ID="12"',
        }

        if command in mock_outputs:
            return (mock_outputs[command], 0)

        # Default mock output
        return (f"[Mock] Executed '{command}' on {place_name}\nCommand completed.", 0)

    def _parse_places(self, places_data: Dict[str, Any]) -> List[Target]:
        """Parse places data from the coordinator into Target objects.

        Args:
            places_data: Raw places data from the coordinator.

        Returns:
            List of parsed Target objects.
        """
        targets = []
        for name, data in places_data.items():
            target = self._parse_place(name, data)
            if target:
                targets.append(target)
        return targets

    def _parse_place(self, name: str, data: Dict[str, Any]) -> Optional[Target]:
        """Parse a single place into a Target object.

        Args:
            name: The place name.
            data: Raw place data from the coordinator.

        Returns:
            Parsed Target object, or None if parsing fails.
        """
        try:
            # Determine status based on acquired state
            acquired = data.get("acquired")
            if acquired:
                status = "acquired"
            else:
                # Check if place has any resources (indicates it's online)
                status = "available"

            # Parse resources
            resources = []
            for res_type in data.get("acquired_resources", []):
                resources.append(Resource(type=res_type, params={}))

            # Extract additional info from tags
            tags = data.get("tags", {})
            ip_address = tags.get("ip", None)
            web_url = tags.get("web_url", None)

            return Target(
                name=name,
                status=status,
                acquired_by=acquired,
                ip_address=ip_address,
                web_url=web_url,
                resources=resources,
                last_command_outputs=[],
            )
        except Exception as e:
            logger.error(f"Failed to parse place {name}: {e}")
            return None

    def _get_mock_places(self) -> List[Target]:
        """Get mock places for development/testing.

        Returns:
            List of mock Target objects.
        """
        return [
            Target(
                name="dut-1",
                status="available",
                acquired_by=None,
                ip_address="192.168.1.101",
                web_url="http://192.168.1.101:8080",
                resources=[
                    Resource(type="NetworkSerialPort", params={"host": "192.168.1.101", "port": 4001}),
                    Resource(type="NetworkPowerPort", params={"host": "pdu-1", "index": 1}),
                ],
                last_command_outputs=[],
            ),
            Target(
                name="dut-2",
                status="acquired",
                acquired_by="developer@host",
                ip_address="192.168.1.102",
                web_url=None,
                resources=[
                    Resource(type="NetworkSerialPort", params={"host": "192.168.1.102", "port": 4002}),
                ],
                last_command_outputs=[],
            ),
            Target(
                name="dut-3",
                status="offline",
                acquired_by=None,
                ip_address=None,
                web_url=None,
                resources=[],
                last_command_outputs=[],
            ),
        ]

    def _get_mock_place(self, name: str) -> Optional[Target]:
        """Get a specific mock place by name.

        Args:
            name: The place name to find.

        Returns:
            Mock Target object if found, None otherwise.
        """
        mock_places = {p.name: p for p in self._get_mock_places()}
        return mock_places.get(name)
