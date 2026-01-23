"""
gRPC client for Labgrid Coordinator communication.

This service handles the connection to the Labgrid Coordinator using gRPC protocol
(labgrid 24.0+). It provides methods to query places/targets, subscribe
to real-time updates, and execute commands on targets.

Note: Labgrid switched from WAMP to gRPC in version 24.0.
"""

import asyncio
import logging
import socket
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.models.target import CommandOutput, Resource, Target

logger = logging.getLogger(__name__)

# Constants for command execution
COMMAND_TIMEOUT = 30  # seconds


class LabgridConnectionError(Exception):
    """Raised when connection to Labgrid Coordinator fails."""

    pass


class LabgridClient:
    """Async gRPC client for Labgrid Coordinator communication (labgrid 24.0+)."""

    def __init__(
        self,
        url: str = "localhost:20408",  # gRPC address (host:port, no protocol prefix)
        realm: str = "realm1",  # Kept for compatibility, not used in gRPC
        timeout: int = 30,
    ):
        """Initialize the Labgrid client.

        Args:
            url: gRPC address of the Labgrid Coordinator (host:port format).
            realm: Not used in gRPC mode, kept for API compatibility.
            timeout: Connection timeout in seconds.
        """
        # Clean URL: remove ws:// prefix if present (migration from WAMP config)
        self._url = url.replace("ws://", "").replace("/ws", "").rstrip("/")
        self._realm = realm
        self._timeout = timeout
        self._connected = False
        self._session = None  # labgrid ClientSession
        self._subscriptions: List[Any] = []
        self._resources_cache: Dict[str, Dict[str, Any]] = {}
        self._places_cache: Dict[str, Dict[str, Any]] = {}
        # Cache of all known exporters (persists offline exporters)
        self._known_exporters_cache: Dict[str, Dict[str, Any]] = {}

    @property
    def connected(self) -> bool:
        """Check if the client is connected to the coordinator."""
        return self._connected

    async def connect(self) -> bool:
        """Connect to the Labgrid Coordinator using labgrid's ClientSession.

        Returns:
            True if connection was successful.

        Raises:
            LabgridConnectionError: If connection fails.
        """
        try:
            logger.info(f"Connecting to Labgrid Coordinator at {self._url}...")

            # Try to establish connection using labgrid's ClientSession
            try:
                from labgrid.remote.client import ClientSession

                logger.info("labgrid ClientSession imported successfully")

                # Get the current event loop
                loop = asyncio.get_event_loop()

                # Create ClientSession with address and loop
                self._session = ClientSession(self._url, loop)

                # Start the session (connects to coordinator)
                await self._session.start()
                logger.info("ClientSession started successfully")

                # Wait for initial sync with coordinator
                await asyncio.sleep(1)

                # Refresh our cache from the session
                await self._refresh_cache()

                self._connected = True
                logger.info("Successfully connected to Labgrid Coordinator")
                logger.info(
                    f"Found {len(self._resources_cache)} resources, "
                    f"{len(self._places_cache)} places"
                )
                return True

            except ImportError as e:
                logger.error(f"Import error (labgrid not available): {e}")
                raise LabgridConnectionError(
                    f"labgrid library not available: {e}"
                ) from e
            except asyncio.TimeoutError as e:
                logger.error(f"Connection timeout after {self._timeout}s")
                raise LabgridConnectionError(
                    f"Connection timeout after {self._timeout}s"
                ) from e
            except Exception as e:
                logger.error(f"Exception during connection: {type(e).__name__}: {e}")
                import traceback

                logger.error(f"Traceback: {traceback.format_exc()}")
                raise LabgridConnectionError(
                    f"Failed to connect to coordinator: {e}"
                ) from e

        except LabgridConnectionError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during connection: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            raise LabgridConnectionError(
                f"Unexpected error during connection: {e}"
            ) from e

    async def _refresh_cache(self) -> None:
        """Refresh the local cache of resources and places from the session.

        This method preserves knowledge of previously seen exporters. When an
        exporter goes offline, it remains in _known_exporters_cache with
        avail=False instead of being removed entirely.
        """
        if not self._session:
            return

        try:
            # Get resources from session (exporter -> group -> resource_type -> ResourceEntry)
            current_resources: Dict[str, Dict[str, Any]] = {}
            current_exporter_names: set = set()

            for exporter_name, exporter_data in self._session.resources.items():
                current_exporter_names.add(exporter_name)
                for group_name, group_resources in exporter_data.items():
                    for res_type, res_entry in group_resources.items():
                        # ResourceEntry attributes need careful handling
                        # - properties may raise KeyError
                        params = {}
                        cls_name = res_type
                        acquired = None
                        avail = True
                        params_available = True  # Track if params could be loaded

                        try:
                            # Try to get params - labgrid property may raise KeyError
                            # when offline
                            params = dict(res_entry.params) if res_entry.params else {}
                        except (KeyError, AttributeError):
                            # Fallback to data dict
                            if hasattr(res_entry, "data") and isinstance(
                                res_entry.data, dict
                            ):
                                params = res_entry.data.get("params", {})
                            # Mark that params couldn't be loaded from property
                            params_available = False

                        try:
                            # Get cls attribute
                            cls_name = res_entry.cls
                        except (KeyError, AttributeError):
                            if hasattr(res_entry, "data") and isinstance(
                                res_entry.data, dict
                            ):
                                cls_name = res_entry.data.get("cls", res_type)

                        try:
                            # Get acquired attribute
                            acquired = res_entry.acquired
                        except (KeyError, AttributeError):
                            if hasattr(res_entry, "data") and isinstance(
                                res_entry.data, dict
                            ):
                                acquired = res_entry.data.get("acquired")

                        try:
                            # Get avail attribute - key indicator of online/offline status
                            avail = res_entry.avail
                        except (KeyError, AttributeError):
                            if hasattr(res_entry, "data") and isinstance(
                                res_entry.data, dict
                            ):
                                avail = res_entry.data.get("avail", True)
                            else:
                                avail = True  # Default, will be overridden below

                        # If params couldn't be loaded, the exporter is likely offline
                        # Labgrid returns the exporter but with empty/missing data
                        if not params_available or not params:
                            avail = False
                            logger.debug(
                                f"Exporter '{exporter_name}' marked offline "
                                "(no params available)"
                            )

                        current_resources[exporter_name] = {
                            res_type: {
                                "cls": cls_name,
                                "params": params,
                                "acquired": acquired,
                                "avail": avail,
                            }
                        }

            # Update known exporters cache with current online exporters
            for exporter_name, resources in current_resources.items():
                self._known_exporters_cache[exporter_name] = resources

            # Mark previously known exporters that are now offline
            for exporter_name in list(self._known_exporters_cache.keys()):
                if exporter_name not in current_exporter_names:
                    # Exporter is offline - mark all its resources as unavailable
                    for res_type in self._known_exporters_cache[exporter_name]:
                        self._known_exporters_cache[exporter_name][res_type][
                            "avail"
                        ] = False
                    logger.info(f"Exporter '{exporter_name}' is now offline")

            # _resources_cache now includes all known exporters (online + offline)
            self._resources_cache = dict(self._known_exporters_cache)

            # Get places from session (place_name -> Place object)
            self._places_cache = {}
            for place_name, place_obj in self._session.places.items():
                self._places_cache[place_name] = {
                    "name": place_name,
                    "acquired": getattr(place_obj, "acquired", None),
                    "comment": getattr(place_obj, "comment", ""),
                    "tags": dict(getattr(place_obj, "tags", {})),
                }

            online_count = len(current_exporter_names)
            offline_count = len(self._known_exporters_cache) - online_count
            logger.debug(
                f"Cache refreshed: {online_count} online, {offline_count} offline "
                f"exporters, {len(self._places_cache)} places"
            )

        except Exception as e:
            logger.error(f"Failed to refresh cache: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")

    async def disconnect(self) -> None:
        """Disconnect from the Labgrid Coordinator."""
        if self._session:
            try:
                await self._session.close()
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")

        self._session = None
        self._connected = False
        self._resources_cache = {}
        self._places_cache = {}
        self._known_exporters_cache = {}
        logger.info("Disconnected from Labgrid Coordinator")

    def _resolve_hostname_to_ip(self, hostname: str) -> Optional[str]:
        """Resolve a hostname to its IP address.

        Args:
            hostname: The hostname to resolve.

        Returns:
            The IP address as string, or None if resolution fails.
        """
        try:
            ip = socket.gethostbyname(hostname)
            return ip
        except socket.gaierror as e:
            logger.debug(f"Could not resolve hostname '{hostname}': {e}")
            return None

    async def get_places(self) -> List[Target]:
        """Get all places/targets from the coordinator.

        Returns:
            List of Target objects representing all places.
        """
        if not self._connected or not self._session:
            logger.warning("Not connected to coordinator")
            return []

        try:
            # Refresh cache and return parsed places
            await self._refresh_cache()

            # Convert resources cache to targets
            # In labgrid, resources are organized by exporter name
            targets = []
            for exporter_name, exporter_resources in self._resources_cache.items():
                # Collect all resources for this exporter
                resources_list = []
                ip_address = None
                acquired_by = None
                is_available = True

                for res_type, res_data in exporter_resources.items():
                    params = res_data.get("params", {})

                    # Track acquired status
                    if res_data.get("acquired"):
                        acquired_by = res_data.get("acquired")

                    # Track availability
                    if not res_data.get("avail", True):
                        is_available = False

                    # Create Resource with correct field names (type and params)
                    resources_list.append(
                        Resource(
                            type=res_data.get("cls", res_type),
                            params=params,
                        )
                    )

                    # Extract exporter hostname from params.extra.proxy
                    # This is the hostname of the exporter machine
                    extra = params.get("extra", {})
                    exporter_hostname = extra.get("proxy") or exporter_name

                    # Only resolve IP for online exporters to avoid DNS timeouts
                    # The hostname resolution can block if the host is unreachable
                    if (
                        exporter_hostname
                        and not ip_address
                        and res_data.get("avail", True)
                    ):
                        ip_address = self._resolve_hostname_to_ip(exporter_hostname)

                # Determine status based on availability and acquisition
                if not is_available:
                    status = "offline"
                elif acquired_by:
                    status = "acquired"
                else:
                    status = "available"

                target = Target(
                    name=exporter_name,
                    status=status,
                    acquired_by=acquired_by,
                    ip_address=ip_address,
                    resources=resources_list,
                )
                targets.append(target)

            return targets
        except Exception as e:
            logger.error(f"Failed to get places: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    async def get_place_info(self, name: str) -> Optional[Target]:
        """Get detailed information about a specific place.

        Args:
            name: The place name to query.

        Returns:
            Target object if found, None otherwise.
        """
        if not self._connected or not self._session:
            logger.warning("Not connected to coordinator")
            return None

        try:
            # Refresh cache first
            await self._refresh_cache()

            # Look for the exporter matching the name
            if name in self._resources_cache:
                exporter_resources = self._resources_cache[name]
                resources = []
                avail = True
                for res_type, res_data in exporter_resources.items():
                    resources.append(
                        Resource(
                            name=res_type,
                            type=res_data.get("cls", res_type),
                            info=res_data.get("params", {}),
                        )
                    )
                    if not res_data.get("avail", False):
                        avail = False

                return Target(
                    name=name,
                    status="available" if avail else "offline",
                    acquired_by=None,
                    resources=resources,
                    tags={},
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get place info for {name}: {e}")
            return None

    async def subscribe_updates(
        self, callback: Callable[[str, Dict[str, Any]], None]
    ) -> bool:
        """Subscribe to real-time place updates.

        Note: gRPC streaming not yet implemented. Uses polling instead.

        Args:
            callback: Function to call when a place is updated.
                     Receives (place_name, place_data) as arguments.

        Returns:
            True if subscription was successful, False otherwise.
        """
        if not self._connected or not self._session:
            logger.warning("Not connected to coordinator")
            return False

        # TODO: Implement gRPC streaming subscription
        # For now, we use polling via _refresh_cache()
        logger.info(
            "Subscriptions use polling mode (gRPC streaming not yet implemented)"
        )
        return True

    async def execute_command(self, place_name: str, command: str) -> Tuple[str, int]:
        """Execute a command on a target via labgrid-client CLI.

        This properly routes through: Backend -> Coordinator -> Exporter -> DUT

        Args:
            place_name: The name of the place/target to execute on.
            command: The shell command to execute.

        Returns:
            Tuple of (output, exit_code). exit_code is 0 for success.
        """
        if not self._connected or not self._session:
            logger.warning("Not connected to coordinator")
            return ("Error: Not connected to coordinator", 1)

        try:
            output = await self._execute_via_labgrid_client(place_name, command)
            return (output, 0)

        except FileNotFoundError as e:
            logger.error(f"labgrid-client not found: {e}")
            return ("Error: labgrid-client CLI not found", 1)
        except TimeoutError as e:
            logger.error(f"Command timeout on {place_name}: {e}")
            return (f"Error: {str(e)}", 1)
        except RuntimeError as e:
            logger.error(f"labgrid-client error on {place_name}: {e}")
            return (f"Error: {str(e)}", 1)
        except Exception as e:
            logger.error(f"Failed to execute command on {place_name}: {e}")
            return (f"Error: {str(e)}", 1)

    def _get_place_resources_from_cache(self, place_name: str) -> List[Dict[str, Any]]:
        """Get resources for a place from the local cache.

        Args:
            place_name: The place name.

        Returns:
            List of resource dictionaries.
        """
        place_resources = []

        # Look for exact match first
        if place_name in self._resources_cache:
            for res_name, res_data in self._resources_cache[place_name].items():
                place_resources.append(res_data)
            return place_resources

        # Search for partial matches
        for group_name, group_resources in self._resources_cache.items():
            if place_name in group_name:
                for res_name, res_data in group_resources.items():
                    place_resources.append(res_data)

        return place_resources

    async def _execute_via_labgrid_client(self, place_name: str, command: str) -> str:
        """Execute a command via labgrid-client subprocess.

        This properly routes through: Backend -> Coordinator -> Exporter -> DUT

        Args:
            place_name: The place/target name.
            command: The shell command to execute.

        Returns:
            Command output as string.

        Raises:
            FileNotFoundError: If labgrid-client is not found.
            TimeoutError: If command times out.
            RuntimeError: If labgrid-client returns an error.
        """
        proc = await asyncio.create_subprocess_exec(
            "labgrid-client",
            "-p",
            place_name,
            "-x",
            self._url,
            "console",
            "--command",
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=COMMAND_TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise TimeoutError(f"Command timeout after {COMMAND_TIMEOUT}s")

        if proc.returncode != 0:
            error = stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"labgrid-client error: {error}")

        return stdout.decode("utf-8", errors="replace").strip()

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
