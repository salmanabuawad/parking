import { useEffect, useState, useMemo, useRef } from 'react'
import { ColDef } from 'ag-grid-community'
import { FieldConfiguration, fieldConfigApi } from '../api'
import { loadFieldConfigurations, applyFieldConfigToColumn, getFieldConfigCache, isFieldConfigCacheLoaded, addConfigsToCache } from './fieldConfigUtils'
import { useFieldConfigVersion } from '../context/FieldConfigContext'
import { subscribeFontSize, getFontSizeWidthMultiplier } from './fontSizeStore'

export function useFieldConfig<T = any>(columnDefs: ColDef<T>[], gridName?: string): [ColDef<T>[], boolean] {
  const configVersion = useFieldConfigVersion()
  const [, forceUpdate] = useState(0)

  useEffect(() => {
    return subscribeFontSize(() => forceUpdate((n) => n + 1))
  }, [])

  const getInitial = (): Map<string, FieldConfiguration> => {
    if (isFieldConfigCacheLoaded()) {
      const cache = getFieldConfigCache()
      if (cache) {
        if (gridName) {
          const filtered = new Map<string, FieldConfiguration>()
          cache.forEach((config) => {
            if (config.grid_name === gridName) {
              filtered.set(`${gridName}:${config.field_name}`, config)
              filtered.set(config.field_name, config)
            }
          })
          return filtered
        }
        return cache
      }
    }
    return new Map()
  }

  const [fieldConfigs, setFieldConfigs] = useState<Map<string, FieldConfiguration>>(getInitial)
  const [loading, setLoading] = useState(!isFieldConfigCacheLoaded())

  useEffect(() => {
    if (isFieldConfigCacheLoaded()) {
      const cache = getFieldConfigCache()
      if (cache) {
        if (gridName) {
          const filtered = new Map<string, FieldConfiguration>()
          cache.forEach((config) => {
            if (config.grid_name === gridName) {
              filtered.set(`${gridName}:${config.field_name}`, config)
              filtered.set(config.field_name, config)
            }
          })
          setFieldConfigs(filtered)
        } else {
          setFieldConfigs(cache)
        }
        setLoading(false)
        return
      }
    }

    setLoading(true)
    loadFieldConfigurations(gridName)
      .then(setFieldConfigs)
      .catch((e) => console.error('[useFieldConfig]', e))
      .finally(() => setLoading(false))
  }, [gridName, configVersion])

  // Auto-register: the first time a grid mounts, any of its columns missing from the config table
  // are inserted with their current appearance (fixed columns keep their pixel width; flex columns
  // register as width_chars=0 = "auto"). This populates the field-config manager for every grid
  // without a manual seed, and is idempotent — subsequent mounts find nothing missing.
  const registeredRef = useRef(false)
  useEffect(() => {
    if (!gridName || loading || registeredRef.current) return
    const cache = getFieldConfigCache()
    if (!cache) return
    registeredRef.current = true

    const multiplier = getFontSizeWidthMultiplier() || 1
    const missing: Omit<FieldConfiguration, 'id'>[] = []
    columnDefs.forEach((colDef, index) => {
      const fieldName = (colDef.field || (colDef as any).colId) as string | undefined
      if (!fieldName) return                              // action / unidentified columns: not managed
      if (cache.get(`${gridName}:${fieldName}`)) return   // already registered

      const numericWidth = typeof (colDef as any).width === 'number' ? (colDef as any).width : null
      let width_chars = 0                                 // 0 = keep original flex/auto sizing
      let padding = 8
      if (numericWidth != null) {
        const target = numericWidth / multiplier          // px at multiplier 1
        width_chars = Math.max(1, Math.round((target - 16) / 8))
        padding = Math.max(0, Math.round((target - width_chars * 8) / 2))  // absorb the remainder → exact round-trip
      }
      const pinned = (colDef as any).pinned
      missing.push({
        grid_name: gridName,
        field_name: fieldName,
        hebrew_name: (colDef.headerName as string) || fieldName,
        width_chars,
        padding,
        pinned: pinned === 'left' || pinned === 'right' || pinned === true,
        pin_side: pinned === 'left' || pinned === 'right' ? pinned : null,
        visible: (colDef as any).hide ? false : true,
        column_order: index,
      })
    })
    if (missing.length === 0) return

    fieldConfigApi.upsertBulk(missing)
      .then(() => {
        addConfigsToCache(missing as FieldConfiguration[])
        setFieldConfigs((prev) => {
          const next = new Map(prev)
          for (const c of missing) {
            next.set(`${gridName}:${c.field_name}`, c as FieldConfiguration)
            next.set(c.field_name, c as FieldConfiguration)
          }
          return next
        })
      })
      .catch((e) => console.error('[useFieldConfig auto-register]', e))
  }, [gridName, loading, columnDefs])

  const configuredColumnDefs = useMemo(() => {
    if (loading) return columnDefs

    const multiplier = getFontSizeWidthMultiplier()

    const withConfig = columnDefs.map((colDef) => {
      const fieldName = colDef.field || (colDef as any).colId
      if (!fieldName) return { colDef, order: Infinity, visible: true }

      let config: FieldConfiguration | undefined
      if (gridName) config = fieldConfigs.get(`${gridName}:${fieldName}`)
      if (!config) config = fieldConfigs.get(fieldName)

      if (!config) return { colDef, order: Infinity, visible: true }

      return {
        colDef: applyFieldConfigToColumn(colDef, config, { largeFontMultiplier: multiplier }),
        order: config.column_order ?? Infinity,
        visible: config.visible !== false,
      }
    })

    const visible = withConfig.filter((x) => x.visible)
    visible.sort((a, b) => {
      if (a.order !== Infinity && b.order !== Infinity) return a.order - b.order
      if (a.order !== Infinity) return -1
      if (b.order !== Infinity) return 1
      return 0
    })

    return visible.map((x) => x.colDef)
  }, [columnDefs, fieldConfigs, loading, gridName])

  return [configuredColumnDefs, loading]
}
