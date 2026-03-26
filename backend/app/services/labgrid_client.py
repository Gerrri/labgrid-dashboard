"""
gRPC client for Labgrid Coordinator communication.

This service handles the connection to the Labgrid Coordinator using gRPC protocol
(labgrid 24.0+). It provides methods to query places/targets, subscribe
to real-time updates, and execute commands on targets.

Note: Labgrid switched from WAMP to gRPC in version 24.0.
"""

import asyncio
import contextlib
import fnmatch
import logging
import os
import socket
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from app.config import LABGRID_DASHBOARD_USER, get_settings
from app.models.target import CommandOutput, Resource, Target

logger = logging.getLogger(__name__)

# Constants for release retry logic
RELEASE_MAX_RETRIES = 3
RELEASE_INITIAL_DELAY = 1.0  # seconds
RELEASE_BACKOFF_FACTOR = 2.0


class LabgridConnectionError(Exception):
    """Raised when connection to Labgrid Coordinator fails."""

    pass


class TargetAcquiredByOtherError(Exception):
    """Raised when target is acquired by another user."""

    def __init__(self, target_name: str, acquired_by: str):
        self.target_name = target_name
        self.acquired_by = acquired_by
        super().__init__(f"Target '{target_name}' is acquired by '{acquired_by}'")


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
        self._poll_interval = get_settings().labgrid_poll_interval_seconds
        self._poll_task: Optional[asyncio.Task] = None
        self._command_locks: Dict[str, asyncio.Lock] = {}

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
                os.environ["LG_USERNAME"] = LABGRID_DASHBOARD_USER

                # Create ClientSession with address and loop
                # Using keyword arguments for attrs-generated constructor
                # type: ignore - Pylance doesn't understand attrs-generated __init__
                self._session = ClientSession(address=self._url, loop=loop)  # type: ignore

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
                        if not params_available:
                            avail = False
                            logger.debug(
                                f"Exporter '{exporter_name}' marked offline "
                                "(no params available)"
                            )

                        if exporter_name not in current_resources:
                            current_resources[exporter_name] = {}

                        resource_key = (
                            res_type
                            if group_name == "default"
                            else f"{group_name}/{res_type}"
                        )

                        current_resources[exporter_name][resource_key] = {
                            "name": group_name,
                            "resource_type": res_type,
                            "cls": cls_name,
                            "params": params,
                            "acquired": acquired,
                            "avail": avail,
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
                    "matches": list(getattr(place_obj, "matches", [])),
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

        if self._poll_task:
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
            self._poll_task = None

        self._session = None
        self._connected = False
        self._resources_cache = {}
        self._places_cache = {}
        logger.info("Disconnected from Labgrid Coordinator")

    async def _resolve_hostname_to_ip(self, hostname: str) -> Optional[str]:
        """Resolve a hostname to its IP address.

        Args:
            hostname: The hostname to resolve.

        Returns:
            The IP address as string, or None if resolution fails.
        """
        try:
            loop = asyncio.get_running_loop()
            addr_info = await loop.getaddrinfo(
                hostname,
                None,
                family=socket.AF_INET,
                type=socket.SOCK_STREAM,
            )
            if not addr_info:
                return None
            return addr_info[0][4][0]
        except OSError as e:
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
            targets = []
            place_infos = self._places_cache.values()
            if not self._places_cache:
                place_infos = (
                    {
                        "name": exporter_name,
                        "acquired": None,
                        "comment": "",
                        "tags": {},
                        "matches": [],
                    }
                    for exporter_name in self._resources_cache
                )

            for place_info in place_infos:
                place_name = place_info.get("name", "")
                resource_entries = self._get_place_resource_entries(place_name)
                if not place_name or not resource_entries:
                    continue

                resources_list = []
                tags = place_info.get("tags", {})
                ip_address = tags.get("ip")
                acquired_by = None
                has_acquired_resource = False
                has_available_resource = False
                place_acquired = place_info.get("acquired")
                if isinstance(place_acquired, str):
                    place_acquired = place_acquired.strip()
                if place_acquired and isinstance(place_acquired, str):
                    acquired_by = place_acquired

                for exporter_name, res_type, res_data in resource_entries:
                    params = res_data.get("params", {})

                    if res_data.get("acquired"):
                        has_acquired_resource = True

                    if res_data.get("avail", True):
                        has_available_resource = True

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
                        ip_address = await self._resolve_hostname_to_ip(exporter_hostname)

                if not has_available_resource:
                    status = "offline"
                elif place_acquired or has_acquired_resource:
                    status = "acquired"
                else:
                    status = "available"

                if not acquired_by and (place_acquired or has_acquired_resource):
                    acquired_by = "N/A"

                target = Target(
                    name=place_name,
                    status=status,
                    acquired_by=acquired_by,
                    ip_address=ip_address,
                    web_url=tags.get("web_url"),
                    resources=resources_list,
                )
                targets.append(target)

            return targets
        except Exception as e:
            logger.error(f"Failed to get places: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    async def get_schedulable_places(self) -> List[Target]:
        """Get targets that map to real coordinator places.

        Scheduler commands use `labgrid-client -p <place> ...`, which only works
        for existing places. Targets backed only by exporter resources are filtered
        out here to avoid acquire errors.

        Returns:
            List of targets with names present in the coordinator place cache.
        """
        targets = await self.get_places()
        if not targets:
            return []

        if not self._places_cache:
            logger.info(
                "Scheduler: no places defined in coordinator; skipping scheduled command execution"
            )
            return []

        schedulable_targets = [t for t in targets if t.name in self._places_cache]
        skipped_targets = len(targets) - len(schedulable_targets)
        if skipped_targets > 0:
            logger.info(
                "Scheduler: skipping %d target(s) without matching coordinator place",
                skipped_targets,
            )

        return schedulable_targets

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
            place_data = self._places_cache.get(name)
            if not place_data and name not in self._resources_cache:
                return None

            if not place_data:
                place_data = {
                    "name": name,
                    "acquired": None,
                    "comment": "",
                    "tags": {},
                    "matches": [],
                }

            resource_entries = self._get_place_resource_entries(name)
            if not resource_entries:
                return None

            resources = []
            has_available_resource = False
            ip_address = place_data.get("tags", {}).get("ip")
            for exporter_name, res_type, res_data in resource_entries:
                params = res_data.get("params", {})
                resources.append(
                    Resource(
                        type=res_data.get("cls", res_type),
                        params=params,
                    )
                )
                if res_data.get("avail", True):
                    has_available_resource = True
                if not ip_address and res_data.get("avail", True):
                    extra = params.get("extra", {})
                    exporter_hostname = extra.get("proxy") or exporter_name
                    if exporter_hostname:
                        ip_address = await self._resolve_hostname_to_ip(exporter_hostname)

            place_acquired = place_data.get("acquired")
            if isinstance(place_acquired, str):
                place_acquired = place_acquired.strip() or None

            acquired_by = place_acquired
            if not acquired_by:
                for _, _, res_data in resource_entries:
                    if res_data.get("acquired"):
                        acquired_by = res_data["acquired"]
                        break

            if not has_available_resource:
                status = "offline"
            elif acquired_by:
                status = "acquired"
            else:
                status = "available"

            return Target(
                name=name,
                status=status,
                acquired_by=acquired_by,
                ip_address=ip_address,
                web_url=place_data.get("tags", {}).get("web_url"),
                resources=resources,
            )
        except Exception as e:
            logger.error(f"Failed to get place info for {name}: {e}")
            return None

    async def subscribe_updates(
        self, callback: Callable[[str, Dict[str, Any]], Awaitable[None] | None]
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

        if self._poll_task and not self._poll_task.done():
            return True

        logger.info(
            "Subscriptions use polling mode (gRPC streaming not yet implemented)"
        )
        self._poll_task = asyncio.create_task(self._poll_updates(callback))
        return True

    def _target_snapshot(
        self, target: Target
    ) -> Tuple[str, Optional[str], Optional[str]]:
        return (target.status, target.acquired_by, target.ip_address)

    async def _poll_updates(
        self, callback: Callable[[str, Dict[str, Any]], Awaitable[None] | None]
    ) -> None:
        last_snapshots: Dict[str, Tuple[str, Optional[str], Optional[str]]] = {}

        while self._connected:
            try:
                targets = await self.get_places()
                for target in targets:
                    snapshot = self._target_snapshot(target)
                    if last_snapshots.get(target.name) != snapshot:
                        await self._notify_update(callback, target)
                        last_snapshots[target.name] = snapshot
            except Exception as e:
                logger.warning(f"Failed to poll targets: {e}")

            await asyncio.sleep(self._poll_interval)

    async def _notify_update(
        self,
        callback: Callable[[str, Dict[str, Any]], Awaitable[None] | None],
        target: Target,
    ) -> None:
        result = callback(target.name, target.model_dump(mode="json"))
        if asyncio.iscoroutine(result):
            await result

    async def _get_acquired_by(self, place_name: str) -> Optional[str]:
        """Get the user who has acquired a target.

        Args:
            place_name: The place name to check.

        Returns:
            The username who acquired the target, or None if not acquired.
        """
        await self._refresh_cache()
        place_data = self._places_cache.get(place_name, {})
        place_acquired = place_data.get("acquired")
        if place_acquired:
            return place_acquired

        for _, _, res_data in self._get_place_resource_entries(place_name):
            acquired = res_data.get("acquired")
            if acquired:
                return acquired
        return None

    def _get_place_resource_entries(
        self, place_name: str
    ) -> List[Tuple[str, str, Dict[str, Any]]]:
        """Get all resource entries that belong to a coordinator place."""
        place_data = self._places_cache.get(place_name, {})
        exporters = self._get_place_exporters(place_name, place_data)
        matched_resources = self._get_place_matched_resources(place_data)

        entries: List[Tuple[str, str, Dict[str, Any]]] = []
        seen_entries: set[Tuple[str, str]] = set()
        if matched_resources:
            for exporter_name, resource_key in matched_resources:
                exporter_resources = self._resources_cache.get(exporter_name, {})
                for resolved_key in self._resolve_matched_resource_keys(
                    exporter_resources,
                    resource_key,
                ):
                    res_data = exporter_resources.get(resolved_key)
                    if res_data is None:
                        continue

                    entry_key = (exporter_name, resolved_key)
                    if entry_key in seen_entries:
                        continue
                    seen_entries.add(entry_key)
                    entries.append((exporter_name, resolved_key, res_data))

            return entries

        for exporter_name in exporters:
            exporter_resources = self._resources_cache.get(exporter_name, {})
            for res_type, res_data in exporter_resources.items():
                entry_key = (exporter_name, res_type)
                if entry_key in seen_entries:
                    continue
                seen_entries.add(entry_key)
                entries.append((exporter_name, res_type, res_data))

        return entries

    def get_place_resource_entries(
        self, place_name: str
    ) -> List[Tuple[str, str, Dict[str, Any]]]:
        """Public wrapper for cached place resource entries."""
        return self._get_place_resource_entries(place_name)

    def _get_place_exporters(
        self, place_name: str, place_data: Dict[str, Any]
    ) -> List[str]:
        """Resolve exporter names for a place from matches, with exact-name fallback."""
        exporters: List[str] = []
        for match in place_data.get("matches", []):
            exporter_name = self._extract_match_exporter(match)
            if (
                exporter_name
                and exporter_name in self._resources_cache
                and exporter_name not in exporters
            ):
                exporters.append(exporter_name)

        if place_name in self._resources_cache and place_name not in exporters:
            exporters.append(place_name)

        return exporters

    def _get_place_matched_resources(
        self, place_data: Dict[str, Any]
    ) -> List[Tuple[str, Optional[str]]]:
        """Resolve exporter/resource pairs from coordinator match entries."""
        matches: List[Tuple[str, Optional[str]]] = []
        for match in place_data.get("matches", []):
            resolved = self._extract_match_resource(match)
            if resolved and resolved not in matches:
                matches.append(resolved)
        return matches

    def _extract_match_resource(
        self, match: Any
    ) -> Optional[Tuple[str, Optional[str]]]:
        """Best-effort exporter/resource extraction from a labgrid match entry."""
        if isinstance(match, str):
            exporter_name, resource_key = self._parse_string_match(match)
            if not exporter_name:
                return None
            return (exporter_name, resource_key)

        exporter_name = self._extract_match_exporter(match)
        if not exporter_name:
            return self._parse_match_fallback(match)

        resource_key = self._extract_match_resource_key(match, exporter_name)
        if resource_key is None:
            fallback_exporter, fallback_resource_key = self._parse_match_fallback(match)
            if fallback_exporter == exporter_name:
                resource_key = fallback_resource_key
        return (exporter_name, resource_key)

    def _extract_match_resource_key(
        self, match: Any, exporter_name: str
    ) -> Optional[str]:
        """Extract the resource portion from a non-string match entry."""
        raw_resource: Optional[str] = None

        if isinstance(match, dict):
            for key in ("resource", "resource_key", "path", "match"):
                value = match.get(key)
                if isinstance(value, str) and value:
                    raw_resource = value
                    break
        elif isinstance(match, (list, tuple)):
            for value in match:
                if isinstance(value, str) and value.startswith(f"{exporter_name}/"):
                    raw_resource = value
                    break
        else:
            for attr in ("resource", "resource_key", "path", "match"):
                value = getattr(match, attr, None)
                if isinstance(value, str) and value:
                    raw_resource = value
                    break

        if not raw_resource:
            fallback_exporter, fallback_resource_key = self._parse_match_fallback(match)
            if fallback_exporter == exporter_name:
                return fallback_resource_key
            return None

        if raw_resource.startswith(f"{exporter_name}/"):
            raw_resource = raw_resource[len(exporter_name) + 1 :]

        return raw_resource.strip("/") or None

    def _extract_match_exporter(self, match: Any) -> Optional[str]:
        """Best-effort exporter extraction from a labgrid place match entry."""
        if isinstance(match, str):
            exporter_name, _ = self._parse_string_match(match)
            return exporter_name

        if isinstance(match, dict):
            for key in ("exporter", "name"):
                value = match.get(key)
                if isinstance(value, str) and value and value != "*":
                    return value
            fallback_exporter, _ = self._parse_match_fallback(match)
            return fallback_exporter

        if isinstance(match, (list, tuple)):
            for value in match:
                if isinstance(value, str) and value in self._resources_cache:
                    return value
            fallback_exporter, _ = self._parse_match_fallback(match)
            return fallback_exporter

        for attr in ("exporter", "name"):
            value = getattr(match, attr, None)
            if isinstance(value, str) and value and value != "*":
                return value

        fallback_exporter, _ = self._parse_match_fallback(match)
        return fallback_exporter

    def _parse_string_match(self, match: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse string-based labgrid matches, including wildcard variants."""
        parts = [part for part in match.split("/") if part]
        if not parts:
            return (None, None)

        exporter_index = self._find_exporter_index(parts)
        if exporter_index is None:
            return (None, None)

        exporter_name = parts[exporter_index]
        resource_key = "/".join(parts[exporter_index + 1 :]).strip("/") or None
        return (exporter_name, self._normalize_match_resource_pattern(resource_key))

    def _parse_match_fallback(
        self, match: Any
    ) -> Tuple[Optional[str], Optional[str]]:
        """Fallback parser for match objects whose useful data only exists in their repr()."""
        for candidate in (str(match), repr(match)):
            if not isinstance(candidate, str) or "/" not in candidate:
                continue

            exporter_name, resource_key = self._parse_string_match(candidate)
            if exporter_name:
                return (exporter_name, resource_key)

        return (None, None)

    def _find_exporter_index(self, parts: List[str]) -> Optional[int]:
        """Locate the exporter segment inside a match path."""
        for index, part in enumerate(parts):
            if part in self._resources_cache:
                return index

        non_wildcard_indices = [
            index for index, part in enumerate(parts) if part and part != "*"
        ]
        if not non_wildcard_indices:
            return None

        if parts[0] == "*":
            return non_wildcard_indices[0]

        return 0

    def _normalize_match_resource_pattern(
        self, resource_key: Optional[str]
    ) -> Optional[str]:
        """Normalize resource patterns from coordinator match strings."""
        if not resource_key:
            return None

        normalized = resource_key.strip("/")
        if normalized in {"", "*"}:
            return None

        if normalized.startswith("default/"):
            normalized = normalized[len("default/") :]

        return normalized or None

    def _resolve_matched_resource_keys(
        self,
        exporter_resources: Dict[str, Any],
        resource_key: Optional[str],
    ) -> List[str]:
        """Resolve exact or wildcard resource patterns against cached resources."""
        if resource_key is None:
            return list(exporter_resources.keys())

        resolved_keys: List[str] = []
        for candidate_key in exporter_resources:
            candidate_aliases = {candidate_key}
            if "/" not in candidate_key:
                candidate_aliases.add(f"default/{candidate_key}")

            if "*" in resource_key:
                if any(
                    fnmatch.fnmatch(candidate_alias, resource_key)
                    for candidate_alias in candidate_aliases
                ):
                    resolved_keys.append(candidate_key)
                continue

            if resource_key in candidate_aliases:
                resolved_keys.append(candidate_key)

        return resolved_keys

    async def acquire_target(self, place_name: str) -> bool:
        """Acquire a target for command execution.

        Args:
            place_name: The place name to acquire.

        Returns:
            True if this call acquired the target, False if it was already held
            by the dashboard user.

        Raises:
            TargetAcquiredByOtherError: If target is acquired by another user.
            RuntimeError: If acquisition fails for other reasons.
        """
        logger.info(f"Acquiring target '{place_name}' as '{LABGRID_DASHBOARD_USER}'")
        proc = await asyncio.create_subprocess_exec(
            "labgrid-client",
            "-p",
            place_name,
            "-x",
            self._url,
            "acquire",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "LG_USERNAME": LABGRID_DASHBOARD_USER},
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error = stderr.decode("utf-8", errors="replace")
            if "already acquired" in error.lower():
                acquired_by = self._parse_acquired_by_from_error(error)
                if acquired_by == LABGRID_DASHBOARD_USER:
                    logger.debug(f"Target '{place_name}' already acquired by us")
                    return False
                raise TargetAcquiredByOtherError(place_name, acquired_by)
            raise RuntimeError(f"Failed to acquire target: {error}")

        logger.info(f"Successfully acquired target '{place_name}'")
        return True

    def _parse_acquired_by_from_error(self, error: str) -> str:
        """Parse the username from an 'already acquired' error message.

        Args:
            error: The error message from labgrid-client.

        Returns:
            The username who acquired the target, or 'unknown' if parsing fails.
        """
        # Try to parse "place X is already acquired by Y"
        try:
            if "acquired by" in error.lower():
                parts = error.lower().split("acquired by")
                if len(parts) > 1:
                    return parts[1].strip().split()[0]
        except Exception:
            pass
        return "unknown"

    async def release_target(self, place_name: str) -> bool:
        """Release a previously acquired target.

        Args:
            place_name: The place name to release.

        Returns:
            True if successfully released, False otherwise.
        """
        logger.info(f"Releasing target '{place_name}'")
        proc = await asyncio.create_subprocess_exec(
            "labgrid-client",
            "-p",
            place_name,
            "-x",
            self._url,
            "release",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "LG_USERNAME": LABGRID_DASHBOARD_USER},
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error = stderr.decode("utf-8", errors="replace")
            logger.warning(f"Failed to release target '{place_name}': {error}")
            return False

        logger.info(f"Successfully released target '{place_name}'")
        return True

    async def release_target_with_retry(
        self,
        place_name: str,
        max_retries: int = RELEASE_MAX_RETRIES,
    ) -> bool:
        """Release a target with retry logic to prevent permanent locks.

        Uses exponential backoff: 1s, 2s, 4s

        Args:
            place_name: The place name to release.
            max_retries: Maximum number of retry attempts.

        Returns:
            True if successfully released, False if all retries failed.
        """
        delay = RELEASE_INITIAL_DELAY
        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                success = await self.release_target(place_name)
                if success:
                    if attempt > 0:
                        logger.info(
                            f"Released '{place_name}' after {attempt + 1} attempts"
                        )
                    return True
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Release attempt {attempt + 1}/{max_retries + 1} "
                    f"failed for '{place_name}': {e}"
                )

            if attempt < max_retries:
                logger.debug(f"Retrying release in {delay}s...")
                await asyncio.sleep(delay)
                delay *= RELEASE_BACKOFF_FACTOR

        # All retries failed - log critical error
        logger.error(
            f"CRITICAL: Failed to release '{place_name}' after "
            f"{max_retries + 1} attempts. Last error: {last_error}"
        )
        return False

    async def execute_command(self, place_name: str, command: str) -> Tuple[str, int]:
        """Execute a command with automatic acquire/release.

        Flow: acquire -> execute -> release (with retry)

        This properly routes through: Backend -> Coordinator -> Exporter -> DUT

        Args:
            place_name: The name of the place/target to execute on.
            command: The shell command to execute.

        Returns:
            Tuple of (output, exit_code). exit_code is 0 for success.

        Raises:
            TargetAcquiredByOtherError: If target is acquired by another user.
        """
        if not self._connected or not self._session:
            logger.warning("Not connected to coordinator")
            return ("Error: Not connected to coordinator", 1)

        target_lock = self._command_locks.setdefault(place_name, asyncio.Lock())

        try:
            async with target_lock:
                acquired_here = await self.acquire_target(place_name)

                try:
                    output = await self._execute_via_labgrid_client(place_name, command)
                    return (output, 0)
                finally:
                    if acquired_here:
                        released = await self.release_target_with_retry(place_name)
                        if not released:
                            logger.error(
                                f"Command succeeded but release failed for '{place_name}'"
                            )

        except TargetAcquiredByOtherError:
            # Re-raise for API layer to handle
            raise
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

        This uses 'labgrid-client ssh' to execute commands on targets with
        SSHDriver configured. The ssh command passes additional arguments
        to the ssh subprocess, allowing command execution.

        Route: Backend -> Coordinator -> Exporter -> DUT (via SSH)

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
        # Use 'labgrid-client ssh' with the command as additional argument
        # This requires an SSHDriver to be configured for the target
        proc = await asyncio.create_subprocess_exec(
            "labgrid-client",
            "-p",
            place_name,
            "-x",
            self._url,
            "ssh",
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "LG_USERNAME": LABGRID_DASHBOARD_USER},
        )

        try:
            timeout = get_settings().labgrid_command_timeout
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            timeout = get_settings().labgrid_command_timeout
            raise TimeoutError(f"Command timeout after {timeout}s")

        if proc.returncode != 0:
            error = stderr.decode("utf-8", errors="replace")
            output = stdout.decode("utf-8", errors="replace")
            # If there's stdout content, return it with the error appended
            if output.strip():
                return (
                    f"{output.strip()}\n[Exit code: {proc.returncode}] {error.strip()}"
                )
            raise RuntimeError(f"labgrid-client error: {error}")

        return stdout.decode("utf-8", errors="replace").strip()
