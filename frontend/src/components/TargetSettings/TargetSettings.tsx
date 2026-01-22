import { useState, useEffect, useCallback } from "react";
import type { Preset, PresetsResponse, Command } from "../../types";
import { api } from "../../services/api";
import "./TargetSettings.css";

interface TargetSettingsProps {
  targetName: string;
  onPresetChange?: (presetId: string) => void;
  onClose?: () => void;
}

/**
 * Settings panel for configuring target preset
 * Displays available presets with radio button selection
 */
export function TargetSettings({
  targetName,
  onPresetChange,
  onClose,
}: TargetSettingsProps) {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [defaultPreset, setDefaultPreset] = useState<string>("");
  const [currentPresetId, setCurrentPresetId] = useState<string>("");
  const [selectedPresetId, setSelectedPresetId] = useState<string>("");
  const [presetCommands, setPresetCommands] = useState<Command[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch presets and current target preset
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Fetch all presets and current target preset in parallel
        const [presetsResponse, targetPresetResponse] = await Promise.all([
          api.getPresets(),
          api.getTargetPreset(targetName),
        ]);

        const presetsData: PresetsResponse = presetsResponse.data;
        setPresets(presetsData.presets);
        setDefaultPreset(presetsData.default_preset);

        const currentPreset = targetPresetResponse.data.preset_id;
        setCurrentPresetId(currentPreset);
        setSelectedPresetId(currentPreset);

        // Fetch commands for the current preset
        const commandsResponse = await api.getCommands(targetName);
        setPresetCommands(commandsResponse.data);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to load settings";
        setError(message);
        console.error("Error fetching target settings:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [targetName]);

  // Fetch commands when selected preset changes (for preview)
  useEffect(() => {
    const fetchPresetCommands = async () => {
      if (!selectedPresetId || selectedPresetId === currentPresetId) {
        return;
      }

      try {
        // We fetch the commands that would be available for this preset
        // Note: The backend returns commands based on the current preset,
        // so we show the preview based on the preset description
        const selectedPreset = presets.find((p) => p.id === selectedPresetId);
        if (selectedPreset) {
          // Commands will be reloaded after saving
        }
      } catch (err) {
        console.error("Error fetching preset commands:", err);
      }
    };

    fetchPresetCommands();
  }, [selectedPresetId, currentPresetId, presets]);

  const handlePresetSelect = useCallback((presetId: string) => {
    setSelectedPresetId(presetId);
  }, []);

  const handleSave = useCallback(async () => {
    if (selectedPresetId === currentPresetId) {
      onClose?.();
      return;
    }

    try {
      setSaving(true);
      setError(null);

      await api.setTargetPreset(targetName, selectedPresetId);
      setCurrentPresetId(selectedPresetId);
      onPresetChange?.(selectedPresetId);
      onClose?.();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to save preset";
      setError(message);
      console.error("Error saving preset:", err);
    } finally {
      setSaving(false);
    }
  }, [targetName, selectedPresetId, currentPresetId, onPresetChange, onClose]);

  const handleCancel = useCallback(() => {
    setSelectedPresetId(currentPresetId);
    onClose?.();
  }, [currentPresetId, onClose]);

  const hasChanges = selectedPresetId !== currentPresetId;

  if (loading) {
    return (
      <div className="target-settings loading">
        <div className="loading-spinner">
          <span className="spinner-icon">⟳</span>
          <span>Loading settings...</span>
        </div>
      </div>
    );
  }

  const selectedPreset = presets.find((p) => p.id === selectedPresetId);

  return (
    <div className="target-settings">
      <div className="target-settings-header">
        <h4>
          <span className="settings-icon">⚙️</span>
          Target Settings
        </h4>
      </div>

      {error && (
        <div className="settings-error">
          <span className="error-icon">⚠</span>
          <span>{error}</span>
        </div>
      )}

      <div className="settings-content">
        <div className="preset-section">
          <h5>Hardware Preset:</h5>
          <div className="preset-list">
            {presets.map((preset) => (
              <label
                key={preset.id}
                className={`preset-option ${selectedPresetId === preset.id ? "selected" : ""}`}
              >
                <input
                  type="radio"
                  name="preset"
                  value={preset.id}
                  checked={selectedPresetId === preset.id}
                  onChange={() => handlePresetSelect(preset.id)}
                  disabled={saving}
                />
                <div className="preset-info">
                  <span className="preset-name">
                    {preset.name}
                    {preset.id === defaultPreset && (
                      <span className="default-badge">default</span>
                    )}
                    {preset.id === currentPresetId && (
                      <span className="current-badge">current</span>
                    )}
                  </span>
                  <span className="preset-description">
                    {preset.description}
                  </span>
                </div>
              </label>
            ))}
          </div>
        </div>

        {selectedPreset &&
          selectedPresetId === currentPresetId &&
          presetCommands.length > 0 && (
            <div className="commands-preview">
              <h5>Commands in this preset:</h5>
              <ul className="commands-list">
                {presetCommands.map((cmd) => (
                  <li key={cmd.name}>
                    <span className="command-name">{cmd.name}</span>
                    <span className="command-description">
                      - {cmd.description}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

        {selectedPreset && selectedPresetId !== currentPresetId && (
          <div className="commands-preview pending">
            <h5>After saving, commands will be reloaded for:</h5>
            <p className="preset-change-info">
              <strong>{selectedPreset.name}</strong> -{" "}
              {selectedPreset.description}
            </p>
          </div>
        )}
      </div>

      <div className="settings-actions">
        <button className="btn-cancel" onClick={handleCancel} disabled={saving}>
          Cancel
        </button>
        <button
          className="btn-save"
          onClick={handleSave}
          disabled={saving || !hasChanges}
        >
          {saving ? (
            <>
              <span className="spinner">⟳</span>
              Saving...
            </>
          ) : (
            "Save"
          )}
        </button>
      </div>
    </div>
  );
}

export default TargetSettings;
