import { useState, useEffect, useCallback } from "react";
import type {
  Target,
  PresetDetail,
  Preset,
  ScheduledCommandOutput,
} from "../types";
import { api } from "../services/api";

/**
 * Represents a preset group with its targets and details
 */
export interface PresetGroup {
  preset: PresetDetail;
  targets: Target[];
}

interface UsePresetsWithTargetsResult {
  presetGroups: PresetGroup[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  defaultPresetId: string;
  updateTargetFromWebSocket: (target: Target) => boolean;
  setTargetStatus: (
    targetName: string,
    status: Target["status"],
    acquiredBy?: string | null,
  ) => boolean;
  updateTargetScheduledOutput: (
    targetName: string,
    commandName: string,
    output: ScheduledCommandOutput,
  ) => boolean;
}

/**
 * Custom hook for fetching targets grouped by their preset assignment
 * Each preset group contains the preset details (including scheduled_commands) and its targets
 */
export function usePresetsWithTargets(): UsePresetsWithTargetsResult {
  const [presetGroups, setPresetGroups] = useState<PresetGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [defaultPresetId, setDefaultPresetId] = useState<string>("basic");

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch all data in parallel
      const [targetsResponse, presetsResponse] = await Promise.all([
        api.getTargets(),
        api.getPresets(),
      ]);

      const targets = targetsResponse.data.targets;
      const presets = presetsResponse.data.presets;
      const defaultPreset = presetsResponse.data.default_preset;
      setDefaultPresetId(defaultPreset);

      // Fetch preset assignments for all targets in parallel
      const presetAssignments = await Promise.all(
        targets.map(async (target) => {
          try {
            const response = await api.getTargetPreset(target.name);
            return {
              targetName: target.name,
              presetId: response.data.preset_id,
            };
          } catch {
            // If we can't get the preset, use default
            return { targetName: target.name, presetId: defaultPreset };
          }
        }),
      );

      // Create a map of target name to preset ID
      const targetPresetMap = new Map<string, string>();
      presetAssignments.forEach(({ targetName, presetId }) => {
        targetPresetMap.set(targetName, presetId);
      });

      // Fetch preset details for all presets
      const presetDetailsMap = new Map<string, PresetDetail>();
      await Promise.all(
        presets.map(async (preset: Preset) => {
          try {
            const response = await api.getPresetDetail(preset.id);
            presetDetailsMap.set(preset.id, response.data);
          } catch (err) {
            console.error(
              `Failed to fetch details for preset ${preset.id}:`,
              err,
            );
            // Create a basic preset detail from the summary
            presetDetailsMap.set(preset.id, {
              ...preset,
              commands: [],
              scheduled_commands: [],
              auto_refresh_commands: [],
            });
          }
        }),
      );

      // Group targets by preset
      const groupsMap = new Map<string, Target[]>();
      targets.forEach((target) => {
        const presetId = targetPresetMap.get(target.name) || defaultPreset;
        const existing = groupsMap.get(presetId) || [];
        existing.push(target);
        groupsMap.set(presetId, existing);
      });

      // Build the final preset groups array (only include presets with targets)
      const groups: PresetGroup[] = [];
      presets.forEach((preset: Preset) => {
        const targetsInPreset = groupsMap.get(preset.id) || [];
        // Only include presets that have at least one target
        if (targetsInPreset.length > 0) {
          const presetDetail = presetDetailsMap.get(preset.id);
          if (presetDetail) {
            groups.push({
              preset: presetDetail,
              targets: targetsInPreset,
            });
          }
        }
      });

      setPresetGroups(groups);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to fetch data";
      setError(errorMessage);
      console.error("Error fetching presets with targets:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const updateTargetScheduledOutput = useCallback(
    (
      targetName: string,
      commandName: string,
      output: ScheduledCommandOutput,
    ) => {
      let applied = false;

      setPresetGroups((groups) => {
        const next = groups.map((group) => {
          const index = group.targets.findIndex(
            (target) => target.name === targetName,
          );

          if (index === -1) {
            return group;
          }

          applied = true;
          const updatedTargets = [...group.targets];
          const target = updatedTargets[index];
          updatedTargets[index] = {
            ...target,
            scheduled_outputs: {
              ...target.scheduled_outputs,
              [commandName]: output,
            },
          };

          return { ...group, targets: updatedTargets };
        });

        return applied ? next : groups;
      });

      return applied;
    },
    [],
  );

  const updateTargetFromWebSocket = useCallback((target: Target) => {
    let applied = false;

    setPresetGroups((groups) => {
      const next = groups.map((group) => {
        const index = group.targets.findIndex(
          (existingTarget) => existingTarget.name === target.name,
        );

        if (index === -1) {
          return group;
        }

        applied = true;
        const updatedTargets = [...group.targets];
        const existingTarget = updatedTargets[index];
        updatedTargets[index] = {
          ...existingTarget,
          ...target,
          scheduled_outputs: {
            ...existingTarget.scheduled_outputs,
            ...target.scheduled_outputs,
          },
        };

        return { ...group, targets: updatedTargets };
      });

      return applied ? next : groups;
    });

    return applied;
  }, []);

  const setTargetStatus = useCallback(
    (
      targetName: string,
      status: Target["status"],
      acquiredBy?: string | null,
    ) => {
      let applied = false;

      setPresetGroups((groups) => {
        const next = groups.map((group) => {
          const index = group.targets.findIndex(
            (existingTarget) => existingTarget.name === targetName,
          );

          if (index === -1) {
            return group;
          }

          applied = true;
          const updatedTargets = [...group.targets];
          const existingTarget = updatedTargets[index];
          updatedTargets[index] = {
            ...existingTarget,
            status,
            acquired_by:
              acquiredBy !== undefined ? acquiredBy : existingTarget.acquired_by,
          };

          return { ...group, targets: updatedTargets };
        });

        return applied ? next : groups;
      });

      return applied;
    },
    [],
  );

  return {
    presetGroups,
    loading,
    error,
    refetch: fetchData,
    defaultPresetId,
    updateTargetFromWebSocket,
    setTargetStatus,
    updateTargetScheduledOutput,
  };
}

export default usePresetsWithTargets;
