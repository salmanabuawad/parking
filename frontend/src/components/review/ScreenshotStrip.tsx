import { useEffect, useRef, useState } from 'react'
import api from '../../api'
import { t } from '../../i18n'

export interface SavedScreenshot {
  id: string | number
  url: string
  takenAtIso: string
  currentVideoTimeSec: number
  persisted?: boolean
}

function ScreenshotImage({ url }: { url: string }) {
  const [src, setSrc] = useState<string>(url.startsWith('data:') ? url : '')
  const blobUrlRef = useRef<string | null>(null)
  useEffect(() => {
    if (url.startsWith('data:')) return
    api
      .get(url, { responseType: 'blob' })
      .then((res) => {
        if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current)
        const blobUrl = URL.createObjectURL(res.data as Blob)
        blobUrlRef.current = blobUrl
        setSrc(blobUrl)
      })
      .catch(() => setSrc(''))
    return () => {
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current)
        blobUrlRef.current = null
      }
    }
  }, [url])
  if (!src) return <div className="shot-image shot-image-loading" />
  return <img src={src} alt={t('screenshotEvidence')} className="shot-image" />
}

export function ScreenshotStrip({ items, emptyLabel }: { items: SavedScreenshot[]; emptyLabel: string }) {
  if (!items.length) return <div className="strip-empty">{emptyLabel}</div>

  return (
    <div className="screenshot-strip">
      {items.map((item) => (
        <figure className="shot-card" key={item.id}>
          <ScreenshotImage url={item.url} />
          <figcaption className="shot-meta">
            <div>{new Date(item.takenAtIso).toLocaleString('he-IL')}</div>
            <div>{Math.floor(item.currentVideoTimeSec)}s</div>
            <div>{item.persisted ? 'נשמר בשרת' : 'מקומי בלבד'}</div>
          </figcaption>
        </figure>
      ))}
    </div>
  )
}
