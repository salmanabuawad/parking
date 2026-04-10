import { useEffect, useState, useMemo } from 'react'
import { ColDef } from 'ag-grid-community'
import { FieldConfiguration } from '../api'
import { loadFieldConfigurations, applyFieldConfigToColumn, getFieldConfigCache, isFieldConfigCacheLoaded } from './fieldConfigUtils'
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
