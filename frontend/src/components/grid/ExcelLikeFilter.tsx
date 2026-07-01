/**
 * ExcelLikeFilter – AG Grid React custom filter (Excel-style checkbox filter).
 * Ported from buildingsmanager for grid-filter parity. Uses CustomFilterProps + useGridFilter
 * (stable v31→v35 API). Popup close uses the official hidePopup from afterGuiAttached.
 *
 *  ┌─────────────────────────┐
 *  │ 🔍 חיפוש...             │
 *  ├─────────────────────────┤
 *  │ ☑ (בחר הכל)             │
 *  │ ☑ value1                │
 *  ├─────────────────────────┤
 *  │  [אישור]    [ביטול]     │
 *  └─────────────────────────┘
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useGridFilter } from 'ag-grid-react';
import type { CustomFilterProps, IAfterGuiAttachedParams, IDoesFilterPassParams } from 'ag-grid-community';

const BLANK_LABEL = '(ריק)';

export interface ExcelLikeFilterModel {
  values: string[]; // display-values that are checked (kept visible)
}

function toDisplayValue(raw: unknown): string {
  if (raw === null || raw === undefined || raw === '') return BLANK_LABEL;
  return String(raw);
}

const ExcelLikeFilter = ({
  model,
  onModelChange,
  onUiChange,
  api,
  getValue,
}: CustomFilterProps<any, any, ExcelLikeFilterModel>) => {
  const hidePopupRef = useRef<(() => void) | undefined>();

  const collectAllValues = useCallback((): string[] => {
    const seen = new Set<string>();
    api.forEachNode((node: any) => {
      if (!node.data) return;
      seen.add(toDisplayValue(getValue(node)));
    });
    return Array.from(seen).sort((a, b) => {
      if (a === BLANK_LABEL) return 1;
      if (b === BLANK_LABEL) return -1;
      return a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });
    });
  }, [api, getValue]);

  const [allValues, setAllValues] = useState<string[]>(() => collectAllValues());
  const [pending, setPending] = useState<Set<string>>(() =>
    model ? new Set(model.values) : new Set(collectAllValues())
  );
  const [search, setSearch] = useState('');

  const modelRef = useRef<ExcelLikeFilterModel | null>(model);
  useEffect(() => { modelRef.current = model; }, [model]);

  useGridFilter({
    doesFilterPass(params: IDoesFilterPassParams): boolean {
      if (!modelRef.current) return true;
      return modelRef.current.values.includes(toDisplayValue(getValue(params.node)));
    },
    afterGuiAttached(params?: IAfterGuiAttachedParams) {
      hidePopupRef.current = params?.hidePopup;
      const fresh = collectAllValues();
      setAllValues(fresh);
      if (!modelRef.current) setPending(new Set(fresh));
    },
  });

  useEffect(() => {
    if (model) setPending(new Set(model.values));
    else setPending(new Set(collectAllValues()));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [model]);

  const visible = search
    ? allValues.filter((v) => v.toLowerCase().includes(search.toLowerCase()))
    : allValues;

  const allVisibleSelected = visible.length > 0 && visible.every((v) => pending.has(v));
  const someVisibleSelected = visible.some((v) => pending.has(v));

  const toggleValue = (value: string) => {
    setPending((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
    onUiChange();
  };

  const toggleSelectAll = () => {
    setPending((prev) => {
      const next = new Set(prev);
      if (allVisibleSelected) visible.forEach((v) => next.delete(v));
      else visible.forEach((v) => next.add(v));
      return next;
    });
    onUiChange();
  };

  const handleOk = () => {
    const isAll = allValues.every((v) => pending.has(v));
    onModelChange(isAll ? null : { values: Array.from(pending) });
    hidePopupRef.current?.();
  };

  const handleCancel = () => {
    if (model) setPending(new Set(model.values));
    else setPending(new Set(allValues));
    setSearch('');
    hidePopupRef.current?.();
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const next = e.target.value;
    if (next && !search) {
      setPending(new Set());
      onUiChange();
    }
    setSearch(next);
  };

  return (
    <div style={styles.container} dir="rtl">
      <div style={styles.searchRow}>
        <input
          type="text"
          placeholder="חיפוש..."
          value={search}
          onChange={handleSearchChange}
          style={styles.searchInput}
          autoFocus
        />
      </div>

      <div style={styles.listContainer}>
        <label style={styles.itemLabel}>
          <input
            type="checkbox"
            checked={allVisibleSelected}
            ref={(el) => { if (el) el.indeterminate = !allVisibleSelected && someVisibleSelected; }}
            onChange={toggleSelectAll}
            style={styles.checkbox}
          />
          <span style={styles.selectAllText}>(בחר הכל)</span>
        </label>

        {visible.length === 0 ? (
          <div style={styles.noResults}>אין תוצאות</div>
        ) : (
          visible.map((value) => (
            <label key={value} style={styles.itemLabel}>
              <input
                type="checkbox"
                checked={pending.has(value)}
                onChange={() => toggleValue(value)}
                style={styles.checkbox}
              />
              <span style={value === BLANK_LABEL ? styles.blankText : undefined}>{value}</span>
            </label>
          ))
        )}
      </div>

      <div style={styles.buttonRow}>
        <button onClick={handleOk} style={styles.okBtn} type="button">אישור</button>
        <button onClick={handleCancel} style={styles.cancelBtn} type="button">ביטול</button>
      </div>
    </div>
  );
};

export default ExcelLikeFilter;

const styles: Record<string, React.CSSProperties> = {
  container: {
    width: 220, padding: '6px', boxSizing: 'border-box', fontFamily: 'inherit', fontSize: 13,
    backgroundColor: '#fff', direction: 'rtl', border: '1px solid #b0b0b0',
    boxShadow: '2px 2px 6px rgba(0,0,0,0.15)',
  },
  searchRow: { marginBottom: 4 },
  searchInput: {
    width: '100%', boxSizing: 'border-box', padding: '3px 6px', border: '1px solid #b0b0b0',
    borderRadius: 2, fontSize: 12, direction: 'rtl', textAlign: 'right', outline: 'none',
  },
  listContainer: {
    maxHeight: 150, overflowY: 'auto', border: '1px solid #b0b0b0', marginBottom: 6, backgroundColor: '#fff',
  },
  itemLabel: {
    display: 'flex', alignItems: 'center', gap: 5, padding: '2px 6px', cursor: 'pointer',
    userSelect: 'none', direction: 'rtl', fontSize: 12, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
  },
  selectAllText: { fontWeight: 500 },
  noResults: { padding: '6px', color: '#999', textAlign: 'center', fontSize: 12 },
  blankText: { color: '#999', fontStyle: 'italic' },
  checkbox: { cursor: 'pointer', flexShrink: 0, margin: 0, accentColor: '#1565c0' },
  buttonRow: { display: 'flex', gap: 4, justifyContent: 'flex-end' },
  okBtn: { padding: '3px 12px', backgroundColor: '#fff', color: '#000', border: '1px solid #767676', borderRadius: 2, cursor: 'pointer', fontSize: 12 },
  cancelBtn: { padding: '3px 12px', backgroundColor: '#fff', color: '#000', border: '1px solid #767676', borderRadius: 2, cursor: 'pointer', fontSize: 12 },
};
