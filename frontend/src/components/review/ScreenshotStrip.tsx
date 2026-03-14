
export interface SavedScreenshot {
  id: string
  url: string
  takenAtIso: string
  currentVideoTimeSec: number
  persisted?: boolean
}

export function ScreenshotStrip({
  items,
  emptyLabel,
}: {
  items: SavedScreenshot[]
  emptyLabel: string
}) {
  if (!items.length) return <div className="empty-note">{emptyLabel}</div>

  return (
    <div className="shot-strip">
      {items.map((item) => (
        <div key={item.id} className="shot-item">
          <img src={item.url} alt={item.takenAtIso} />
          <div className="shot-caption">
            <div>{new Date(item.takenAtIso).toLocaleString('he-IL')}</div>
            <div>{Math.floor(item.currentVideoTimeSec)}s</div>
            <div>{item.persisted ? 'נשמר בשרת' : 'מקומי'}</div>
          </div>
        </div>
      ))}
    </div>
  )
}
