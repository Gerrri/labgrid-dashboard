"""
Service for managing target-to-preset assignments.

This service loads and saves target preset assignments to a JSON file,
providing persistence across server restarts.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

from app.models.target import TargetPresetsFile

logger = logging.getLogger(__name__)

# Default file location
DEFAULT_PRESETS_FILE = "target_presets.json"


class PresetService:
    """Service for managing target preset assignments."""

    def __init__(
        self,
        presets_file: str = DEFAULT_PRESETS_FILE,
        default_preset_id: str = "basic",
    ):
        """Initialize the preset service.

        Args:
            presets_file: Path to the JSON file storing target-preset assignments.
            default_preset_id: Default preset ID when no assignment exists.
        """
        self._presets_file = Path(presets_file)
        self._default_preset_id = default_preset_id
        self._assignments: Dict[str, str] = {}
        self._loaded = False

    def set_default_preset_id(self, preset_id: str) -> None:
        """Set the default preset ID (usually from commands.yaml config).

        Args:
            preset_id: The default preset ID.
        """
        self._default_preset_id = preset_id
        logger.info(f"Default preset ID set to: {preset_id}")

    def load(self) -> None:
        """Load target-preset assignments from the JSON file.

        Creates an empty file if it doesn't exist.
        """
        if not self._presets_file.exists():
            logger.info(f"Presets file not found, creating: {self._presets_file}")
            self._assignments = {}
            self._save()
            self._loaded = True
            return

        try:
            with open(self._presets_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Validate and load using Pydantic model
            presets_data = TargetPresetsFile(**data)
            self._assignments = presets_data.assignments

            logger.info(
                f"Loaded {len(self._assignments)} target-preset assignments from {self._presets_file}"
            )
            self._loaded = True

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse presets file: {e}")
            self._assignments = {}
            self._loaded = True
        except Exception as e:
            logger.error(f"Failed to load presets file: {e}")
            self._assignments = {}
            self._loaded = True

    def _save(self) -> None:
        """Save target-preset assignments to the JSON file."""
        try:
            presets_data = TargetPresetsFile(assignments=self._assignments)
            with open(self._presets_file, "w", encoding="utf-8") as f:
                json.dump(presets_data.model_dump(), f, indent=2)
            logger.debug(
                f"Saved {len(self._assignments)} assignments to {self._presets_file}"
            )
        except Exception as e:
            logger.error(f"Failed to save presets file: {e}")
            raise

    def _ensure_loaded(self) -> None:
        """Ensure data is loaded before accessing."""
        if not self._loaded:
            self.load()

    def get_target_preset(self, target_name: str) -> str:
        """Get the preset ID assigned to a target.

        Args:
            target_name: The target name.

        Returns:
            The assigned preset ID, or the default preset ID if not assigned.
        """
        self._ensure_loaded()
        return self._assignments.get(target_name, self._default_preset_id)

    def set_target_preset(self, target_name: str, preset_id: str) -> None:
        """Set the preset ID for a target.

        Args:
            target_name: The target name.
            preset_id: The preset ID to assign.
        """
        self._ensure_loaded()

        # If setting to default, remove the explicit assignment
        if preset_id == self._default_preset_id:
            if target_name in self._assignments:
                del self._assignments[target_name]
                logger.info(
                    f"Removed explicit preset assignment for '{target_name}' (using default)"
                )
        else:
            self._assignments[target_name] = preset_id
            logger.info(f"Set preset for '{target_name}' to '{preset_id}'")

        self._save()

    def get_all_assignments(self) -> Dict[str, str]:
        """Get all explicit target-preset assignments.

        Returns:
            Dictionary of target_name -> preset_id for all explicit assignments.
        """
        self._ensure_loaded()
        return self._assignments.copy()

    def get_default_preset_id(self) -> str:
        """Get the default preset ID.

        Returns:
            The default preset ID.
        """
        return self._default_preset_id

    def remove_target_assignment(self, target_name: str) -> bool:
        """Remove the preset assignment for a target (revert to default).

        Args:
            target_name: The target name.

        Returns:
            True if an assignment was removed, False if no assignment existed.
        """
        self._ensure_loaded()

        if target_name in self._assignments:
            del self._assignments[target_name]
            self._save()
            logger.info(f"Removed preset assignment for '{target_name}'")
            return True

        return False

    def reload(self) -> None:
        """Reload assignments from the file."""
        self._loaded = False
        self.load()
