import { FieldConfiguration, fieldConfigApi } from '../api'

let fieldConfigCache: Map<string, FieldConfiguration> | null = null
let fieldConfigCachePromise: Promise<Map<string, FieldConfiguration>> | null = null
let isCacheLoaded = false

function createConfigKey(gridName: string, fieldName: string): string {
  return `${gridName}:${fieldName}`
}

export async function loadFieldConfigurations(gridName?: string): Promise<Map<string, FieldConfiguration>> {
  if (isCacheLoaded && fieldConfigCache) {
    if (!gridName) return fieldConfigCache
    const filtered = new Map<string, FieldConfiguration>()
    fieldConfigCache.forEach((config, key) => {
      if (config.grid_name === gridName) {
        filtered.set(key, config)
        filtered.set(config.field_name, config)
      }
    })
    return filtered
  }

  if (fieldConfigCachePromise) {
    const all = await fieldConfigCachePromise
    if (!gridName) return all
    const filtered = new Map<string, FieldConfiguration>()
    all.forEach((config, key) => {
      if (config.grid_name === gridName) {
        filtered.set(key, config)
        filtered.set(config.field_name, config)
      }
    })
    return filtered
  }

  fieldConfigCachePromise = (async () => {
    try {
      const configs = await fieldConfigApi.getAll()
      const map = new Map<string, FieldConfiguration>()
      for (const config of configs) {
        map.set(createConfigKey(config.grid_name, config.field_name), config)
        map.set(config.field_name, config)
      }
      fieldConfigCache = map
      isCacheLoaded = true
      return map
    } catch (err) {
      console.error('[fieldConfigUtils] Failed to load', err)
      const empty = new Map<string, FieldConfiguration>()
      fieldConfigCache = empty
      isCacheLoaded = true
      return empty
    } finally {
      fieldConfigCachePromise = null
    }
  })()

  return fieldConfigCachePromise
}

export function calculateWidthFromChars(chars: number, padding = 8): number {
  return chars * 8 + padding * 2
}

export function applyFieldConfigToColumn(colDef: any, config: FieldConfiguration, opts?: { largeFontMultiplier?: number }): any {
  const multiplier = (opts?.largeFontMultiplier ?? 1) * 1.0

  const result: any = {
    ...colDef,
    headerName: config.hebrew_name || colDef.headerName,
  }

  // width_chars > 0 → lock the column to a fixed width. width_chars <= 0 is a "flex/auto" marker:
  // keep the column's original sizing (flex or its own width) untouched so responsive grids that
  // mix flex and fixed columns still fill their width. This lets every column be registered/managed
  // without forcing flex columns into a wrong fixed width.
  if (config.width_chars && config.width_chars > 0) {
    const base = calculateWidthFromChars(config.width_chars, config.padding)
    const width = Math.round(base * multiplier)
    result.width = width
    result.minWidth = width
    result.maxWidth = width
    result.resizable = false
    delete result.flex   // an explicit fixed width overrides any flex on the original colDef
  }

  if (config.pinned && config.pin_side) {
    result.pinned = config.pin_side
    result.lockPinned = true
    result.lockPosition = false
  } else {
    result.pinned = null
    result.lockPosition = false
  }

  if (config.visible === false) result.hide = true

  return result
}

// Merge newly-registered rows into the in-memory cache (used by grid auto-registration) so the
// manager and other grids see them without a full reload.
export function addConfigsToCache(configs: FieldConfiguration[]): void {
  if (!fieldConfigCache) fieldConfigCache = new Map()
  for (const c of configs) {
    fieldConfigCache.set(createConfigKey(c.grid_name, c.field_name), c)
    fieldConfigCache.set(c.field_name, c)
  }
  isCacheLoaded = true
}

export function clearFieldConfigCache(): void {
  fieldConfigCache = null
  fieldConfigCachePromise = null
  isCacheLoaded = false
}

export function isFieldConfigCacheLoaded(): boolean {
  return isCacheLoaded && fieldConfigCache !== null
}

export function getFieldConfigCache(): Map<string, FieldConfiguration> | null {
  return fieldConfigCache
}
