import type { ColDef } from 'ag-grid-community'
import ExcelLikeFilter from '../components/grid/ExcelLikeFilter'

/** Shared AG Grid column defaults (Excel-style filter, sortable, resizable) for all list grids. */
export const DEFAULT_COL_DEF: ColDef = { sortable: true, filter: ExcelLikeFilter, resizable: true }
