/**
 * Global font-size store — lives outside React so AG Grid column definitions
 * can read the current font size without being inside a component.
 */

export type FontSize = 'small' | 'normal' | 'large';

const STORAGE_KEY = 'app-font-size';

let current: FontSize = (localStorage.getItem(STORAGE_KEY) as FontSize) || 'normal';
const listeners = new Set<(fs: FontSize) => void>();

export function getFontSize(): FontSize { return current; }

/** Width multiplier for AG Grid column widths based on font size. */
export function getFontSizeWidthMultiplier(): number {
  if (current === 'small') return 0.85;
  if (current === 'large') return 1.55;
  return 1;
}

export function setFontSizeStore(fs: FontSize) {
  current = fs;
  if (fs === 'normal') localStorage.removeItem(STORAGE_KEY);
  else localStorage.setItem(STORAGE_KEY, fs);
  listeners.forEach(fn => fn(fs));
}

export function subscribeFontSize(fn: (fs: FontSize) => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
