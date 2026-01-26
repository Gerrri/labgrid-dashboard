#!/usr/bin/env python3
"""Test script to execute commands via labgrid remote resources."""
import asyncio
import sys

from labgrid import Target
from labgrid.driver import SerialDriver, ShellDriver
from labgrid.protocol import CommandProtocol
from labgrid.remote.client import ClientSession


async def test_command_execution(place_name: str, command: str):
    """Test command execution on a remote place."""
    print(f"Connecting to coordinator...")
    session = ClientSession("coordinator:20408", asyncio.get_event_loop())
    await session.start()
    await asyncio.sleep(1)  # Wait for sync

    try:
        # Get the place
        if place_name not in session.places:
            print(f"ERROR: Place '{place_name}' not found")
            print(f"Available places: {list(session.places.keys())}")
            return

        print(f"Found place: {place_name}")

        # Acquire the place
        print(f"Acquiring place...")
        place = session.get_place(place_name)
        place.acquire()
        await asyncio.sleep(0.5)

        print(f"Creating target and binding resources...")
        # Create a local target and bind the remote resources
        target = Target(place_name)

        # Get remote resources and bind them to target
        remote_place = session.get_acquired_place(place_name)
        if not remote_place:
            print("ERROR: Could not get acquired place")
            return

        print(f"Remote resources: {remote_place.acquired_resources}")

        # Bind resources from the remote place to our local target
        for resource in remote_place.acquired_resources:
            target.set_binding_map({resource.cls: resource})

        # Activate drivers
        serial_driver = SerialDriver(target, "serial")
        shell_driver = ShellDriver(
            target, "shell", prompt="/ # ", login_prompt="login: ", username="root"
        )

        target.activate(serial_driver)
        target.activate(shell_driver)

        print(f"Executing command: {command}")
        result = shell_driver.run_check(command)
        print(f"Result: {result}")

        # Release place
        print("Releasing place...")
        place.release()

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await session.close()


if __name__ == "__main__":
    place = sys.argv[1] if len(sys.argv) > 1 else "exporter-3"
    cmd = sys.argv[2] if len(sys.argv) > 2 else "echo test"
    asyncio.run(test_command_execution(place, cmd))
