import { themeQuartz } from 'ag-grid-community'
import { useTheme, type Brightness } from '../context/ThemeContext'

function buildTheme(brightness: Brightness) {
  if (brightness === 'dark') {
    return themeQuartz.withParams({
      backgroundColor:             '#111a2c',
      oddRowBackgroundColor:       '#111a2c',
      headerBackgroundColor:       '#0f172a',
      foregroundColor:             '#e5e7eb',
      headerTextColor:             '#cbd5e1',
      secondaryForegroundColor:    '#94a3b8',
      borderColor:                 '#2a3550',
      rowHoverColor:               'rgba(255,255,255,0.06)',
      selectedRowBackgroundColor:  'rgba(96,165,250,0.18)',
      inputBackgroundColor:        '#1a2439',
      inputBorderColor:            '#2a3550',
    })
  }
  if (brightness === 'contrast') {
    return themeQuartz.withParams({
      backgroundColor:             '#ffffff',
      oddRowBackgroundColor:       '#ffffff',
      headerBackgroundColor:       '#ffffff',
      foregroundColor:             '#000000',
      headerTextColor:             '#000000',
      secondaryForegroundColor:    '#1a1a1a',
      borderColor:                 '#000000',
      rowHoverColor:               '#e8e8e8',
      selectedRowBackgroundColor:  '#c8d4e0',
    })
  }
  if (brightness === 'light') {
    return themeQuartz.withParams({
      backgroundColor:             '#ffffff',
      oddRowBackgroundColor:       '#fcfdfe',
      headerBackgroundColor:       '#f0f4f7',
      rowHoverColor:               '#eef6fa',
    })
  }
  // normal — default Quartz
  return themeQuartz
}

export function useAgGridTheme() {
  const { brightness } = useTheme()
  return buildTheme(brightness)
}
