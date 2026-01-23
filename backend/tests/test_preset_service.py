"""
Tests for the PresetService.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest
from app.services.preset_service import PresetService


class TestPresetService:
    """Tests for the PresetService class."""

    def test_load_creates_file_if_not_exists(self):
        """Test that load() creates the presets file if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            presets_file = os.path.join(tmpdir, "target_presets.json")
            service = PresetService(presets_file=presets_file)
            service.load()

            # File should be created
            assert os.path.exists(presets_file)

            # File should contain empty assignments
            with open(presets_file, "r") as f:
                data = json.load(f)
            assert data == {"assignments": {}}

    def test_load_existing_file(self):
        """Test that load() correctly loads existing assignments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            presets_file = os.path.join(tmpdir, "target_presets.json")

            # Create a presets file with some assignments
            with open(presets_file, "w") as f:
                json.dump({"assignments": {"dut-1": "hardware1", "dut-2": "basic"}}, f)

            service = PresetService(presets_file=presets_file)
            service.load()

            assert service.get_target_preset("dut-1") == "hardware1"
            assert service.get_target_preset("dut-2") == "basic"

    def test_get_target_preset_returns_default_when_not_assigned(self):
        """Test that get_target_preset returns default preset when target not assigned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            presets_file = os.path.join(tmpdir, "target_presets.json")
            service = PresetService(
                presets_file=presets_file, default_preset_id="basic"
            )
            service.load()

            # Target not in assignments should return default
            assert service.get_target_preset("unknown-target") == "basic"

    def test_set_target_preset(self):
        """Test that set_target_preset correctly sets and persists an assignment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            presets_file = os.path.join(tmpdir, "target_presets.json")
            service = PresetService(
                presets_file=presets_file, default_preset_id="basic"
            )
            service.load()

            # Set a preset
            service.set_target_preset("dut-1", "hardware1")

            # Should return the new preset
            assert service.get_target_preset("dut-1") == "hardware1"

            # Should be persisted to file
            with open(presets_file, "r") as f:
                data = json.load(f)
            assert data["assignments"]["dut-1"] == "hardware1"

    def test_set_target_preset_to_default_removes_assignment(self):
        """Test that setting a target to default preset removes the explicit assignment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            presets_file = os.path.join(tmpdir, "target_presets.json")
            service = PresetService(
                presets_file=presets_file, default_preset_id="basic"
            )
            service.load()

            # First set to non-default
            service.set_target_preset("dut-1", "hardware1")
            assert "dut-1" in service.get_all_assignments()

            # Then set to default
            service.set_target_preset("dut-1", "basic")
            assert "dut-1" not in service.get_all_assignments()

    def test_get_all_assignments(self):
        """Test that get_all_assignments returns all explicit assignments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            presets_file = os.path.join(tmpdir, "target_presets.json")
            service = PresetService(
                presets_file=presets_file, default_preset_id="basic"
            )
            service.load()

            service.set_target_preset("dut-1", "hardware1")
            service.set_target_preset("dut-2", "hardware2")

            assignments = service.get_all_assignments()
            assert len(assignments) == 2
            assert assignments["dut-1"] == "hardware1"
            assert assignments["dut-2"] == "hardware2"

    def test_remove_target_assignment(self):
        """Test that remove_target_assignment removes an assignment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            presets_file = os.path.join(tmpdir, "target_presets.json")
            service = PresetService(
                presets_file=presets_file, default_preset_id="basic"
            )
            service.load()

            service.set_target_preset("dut-1", "hardware1")
            assert service.get_target_preset("dut-1") == "hardware1"

            # Remove assignment
            result = service.remove_target_assignment("dut-1")
            assert result is True
            assert (
                service.get_target_preset("dut-1") == "basic"
            )  # Falls back to default

    def test_remove_target_assignment_returns_false_if_not_exists(self):
        """Test that remove_target_assignment returns False if no assignment exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            presets_file = os.path.join(tmpdir, "target_presets.json")
            service = PresetService(presets_file=presets_file)
            service.load()

            result = service.remove_target_assignment("non-existent")
            assert result is False

    def test_set_default_preset_id(self):
        """Test that set_default_preset_id updates the default preset."""
        with tempfile.TemporaryDirectory() as tmpdir:
            presets_file = os.path.join(tmpdir, "target_presets.json")
            service = PresetService(
                presets_file=presets_file, default_preset_id="basic"
            )
            service.load()

            # Default should be "basic"
            assert service.get_default_preset_id() == "basic"

            # Change default
            service.set_default_preset_id("hardware1")
            assert service.get_default_preset_id() == "hardware1"

            # Unassigned targets should now get the new default
            assert service.get_target_preset("unassigned-target") == "hardware1"

    def test_reload(self):
        """Test that reload() reloads the file from disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            presets_file = os.path.join(tmpdir, "target_presets.json")
            service = PresetService(
                presets_file=presets_file, default_preset_id="basic"
            )
            service.load()

            service.set_target_preset("dut-1", "hardware1")

            # Manually modify the file
            with open(presets_file, "w") as f:
                json.dump({"assignments": {"dut-1": "hardware2"}}, f)

            # Before reload, should still have old value
            assert service.get_target_preset("dut-1") == "hardware1"

            # After reload, should have new value
            service.reload()
            assert service.get_target_preset("dut-1") == "hardware2"

    def test_handles_invalid_json_gracefully(self):
        """Test that invalid JSON in the file is handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            presets_file = os.path.join(tmpdir, "target_presets.json")

            # Write invalid JSON
            with open(presets_file, "w") as f:
                f.write("this is not valid json")

            service = PresetService(
                presets_file=presets_file, default_preset_id="basic"
            )
            service.load()

            # Should fall back to empty assignments
            assert service.get_all_assignments() == {}
            assert service.get_target_preset("any-target") == "basic"
