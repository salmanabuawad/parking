// Shared display formatters — keep user-facing text consistent across pages.
// The whole UI is Hebrew (RTL); these humanize raw data before it reaches a user.

// A "0,0" (or empty) location string means a mobile upload with no GPS fix.
export function isBlankLocation(s?: string | null): boolean {
  return !s || /^\s*0\.?0*\s*,\s*0\.?0*\s*$/.test(s);
}

// Location for a grid/label: humanize the no-GPS case instead of showing "0,0".
export function formatLocation(s?: string | null): string {
  return isBlankLocation(s) ? "אין מיקום" : (s as string);
}

// Camera connection protocol → friendly label (raw enum should never reach a user).
export const CONNECTION_TYPE_LABELS: Record<string, string> = {
  ip: "IP",
  bluetooth: "Bluetooth",
  wifi: "Wi-Fi",
  rtsp: "RTSP",
  usb: "USB",
  other: "אחר",
};
export const formatConnectionType = (v?: string | null): string =>
  v ? (CONNECTION_TYPE_LABELS[v] ?? v) : "—";
