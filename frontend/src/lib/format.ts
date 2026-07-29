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

// Israeli plate number for display: 7 digits → XX-XXX-XX, 8 digits → XXX-XX-XXX.
// Other lengths (or non-digits) are returned as-is so nothing is ever hidden.
export function formatPlate(value?: string | null): string {
  const d = String(value ?? "").replace(/\D/g, "");
  if (d.length === 7) return `${d.slice(0, 2)}-${d.slice(2, 5)}-${d.slice(5)}`;
  if (d.length === 8) return `${d.slice(0, 3)}-${d.slice(3, 5)}-${d.slice(5)}`;
  return d || String(value ?? "");
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
