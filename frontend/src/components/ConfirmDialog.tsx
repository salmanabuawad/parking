import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'

export type ConfirmOptions = {
  message: string
  title?: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
}

type ConfirmFn = (opts: ConfirmOptions | string) => Promise<boolean>

const ConfirmContext = createContext<ConfirmFn>(async () => window.confirm('?'))

/** In-app replacement for window.confirm(). Usage:
 *    const confirm = useConfirm()
 *    if (!(await confirm({ message: 'למחוק?', confirmText: 'מחק', danger: true }))) return
 */
export function useConfirm(): ConfirmFn {
  return useContext(ConfirmContext)
}

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [opts, setOpts] = useState<ConfirmOptions | null>(null)
  const resolver = useRef<((v: boolean) => void) | null>(null)

  const confirm = useCallback<ConfirmFn>((o) => {
    setOpts(typeof o === 'string' ? { message: o } : o)
    return new Promise<boolean>((resolve) => { resolver.current = resolve })
  }, [])

  const close = useCallback((v: boolean) => {
    resolver.current?.(v)
    resolver.current = null
    setOpts(null)
  }, [])

  useEffect(() => {
    if (!opts) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close(false)
      else if (e.key === 'Enter') close(true)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [opts, close])

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {opts && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 p-4" dir="rtl" onClick={() => close(false)}>
          <div className="app-card w-full max-w-sm p-5 flex flex-col gap-3" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold text-theme-text-primary text-base m-0">{opts.title || 'אישור פעולה'}</h3>
            <p className="text-theme-text-primary text-theme-sm whitespace-pre-line m-0">{opts.message}</p>
            <div className="flex justify-end gap-2 pt-1">
              <button type="button" className="btn-cancel" onClick={() => close(false)}>{opts.cancelText || 'ביטול'}</button>
              <button type="button" autoFocus className={opts.danger ? 'btn-danger' : 'btn-primary'} onClick={() => close(true)}>{opts.confirmText || 'אישור'}</button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  )
}
