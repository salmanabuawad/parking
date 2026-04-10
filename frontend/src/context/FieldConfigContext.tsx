import { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import { clearFieldConfigCache } from '../lib/fieldConfigUtils'

interface FieldConfigContextType {
  configVersion: number
  invalidate: () => void
}

const FieldConfigContext = createContext<FieldConfigContextType | undefined>(undefined)

export function FieldConfigProvider({ children }: { children: ReactNode }) {
  const [configVersion, setConfigVersion] = useState(0)

  const invalidate = useCallback(() => {
    clearFieldConfigCache()
    setConfigVersion((v) => v + 1)
  }, [])

  return (
    <FieldConfigContext.Provider value={{ configVersion, invalidate }}>
      {children}
    </FieldConfigContext.Provider>
  )
}

export function useFieldConfigVersion() {
  return useContext(FieldConfigContext)?.configVersion ?? 0
}

export function useFieldConfigInvalidate() {
  return useContext(FieldConfigContext)?.invalidate ?? (() => {})
}
