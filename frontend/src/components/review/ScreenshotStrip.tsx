export interface SavedScreenshot {
  id: string | number
  url: string
  takenAtIso: string
  currentVideoTimeSec: number
  persisted?: boolean
}

export function ScreenshotStrip({ items, emptyLabel }: { items: SavedScreenshot[]; emptyLabel: string }) {
  if (!items.length) return <div className="strip-empty">{emptyLabel}</div>

  return (
    <div className="screenshot-strip">
      {items.map((item) => (
        <figure className="shot-card" key={item.id}>
          <img src={item.url} alt="Screenshot evidence" className="shot-image" />
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
