/**
 * Simple module-level cache for preset details to avoid duplicate fetching
 * across multiple components and re-renders.
 */

import type { Preset, PresetDetail } from "../types";
import api from "../services/api";

// Module-level cache
const presetDetailCache = new Map<string, PresetDetail>();

/**
 * Load preset details for a list of presets, using cache when available.
 * Only fetches missing presets from the API.
 *
 * @param presets - List of presets to load details for
 * @returns Map of preset ID to preset detail
 */
export const loadPresetDetails = async (
  presets: Preset[]
): Promise<Map<string, PresetDetail>> => {
  // Identify presets not in cache
  const missing = presets.filter((p) => !presetDetailCache.has(p.id));

  // Fetch missing presets in parallel
  if (missing.length > 0) {
    const responses = await Promise.all(
      missing.map((p) => api.getPresetDetail(p.id))
    );

    // Update cache
    responses.forEach((r) => {
      presetDetailCache.set(r.data.id, r.data);
    });
  }

  // Return current cache state for requested presets
  const result = new Map<string, PresetDetail>();
  presets.forEach((p) => {
    const detail = presetDetailCache.get(p.id);
    if (detail) {
      result.set(p.id, detail);
    }
  });

  return result;
};

/**
 * Clear the preset details cache.
 * Useful for testing or when presets are updated.
 */
export const clearPresetCache = (): void => {
  presetDetailCache.clear();
};
