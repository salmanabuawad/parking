import { useState, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';

/* ── Types ── */
export interface NavItem {
  id:        string;
  label:     string;
  icon:      ReactNode;
  children?: NavItem[];
  badge?:    string | number;
  disabled?: boolean;
}

interface SidebarProps {
  items:    NavItem[];
  activeId: string;
  onSelect: (id: string) => void;
  footer?:  ReactNode;
}

/* ── Single nav row ── */
function NavRow({
  item, depth, activeId, onSelect,
}: {
  item: NavItem; depth: number; activeId: string; onSelect: (id: string) => void;
}) {
  const hasChildren = !!item.children?.length;
  const isActive    = activeId === item.id;
  const isAncestor  = hasChildren && item.children!.some(
    c => c.id === activeId || c.children?.some(gc => gc.id === activeId)
  );
  const [open, setOpen] = useState(isAncestor);

  const baseClasses = `
    group relative flex items-center gap-2 w-full text-right transition-all duration-150
    ${depth === 0 ? 'px-3 py-2.5 text-sm' : 'px-3 py-2 text-xs'}
    ${item.disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}
    ${isActive
      ? 'bg-theme-sidebar-active text-white font-semibold'
      : 'text-white/80 hover:bg-theme-sidebar-hover hover:text-white'}
  `;

  /* Active stripe — on the right edge for RTL */
  const stripe = isActive ? (
    <span className="absolute right-0 top-1/2 -translate-y-1/2 h-[60%] w-1 rounded-l-full bg-theme-sidebar-stripe" />
  ) : null;

  const indentPx = depth * 16;

  const handleClick = () => {
    if (item.disabled) return;
    if (hasChildren) setOpen(v => !v);
    else onSelect(item.id);
  };

  return (
    <>
      <button
        className={baseClasses}
        onClick={handleClick}
        style={{ paddingRight: `${12 + indentPx}px` }}
        dir="rtl"
      >
        {stripe}
        {/* Icon */}
        <span className="w-4 h-4 flex-shrink-0 flex items-center justify-center opacity-90">
          {item.icon}
        </span>
        {/* Label */}
        <span className="flex-1 truncate leading-tight text-right">{item.label}</span>
        {/* Badge */}
        {item.badge != null && (
          <span className="mr-auto flex-shrink-0 min-w-[18px] h-[18px] px-1 rounded-full
                           bg-theme-sidebar-stripe/30 text-white text-[10px] font-bold
                           flex items-center justify-center">
            {item.badge}
          </span>
        )}
        {/* Chevron for parent items */}
        {hasChildren && (
          <span
            className="mr-auto flex-shrink-0 text-white/50 transition-transform duration-200"
            style={{ transform: open ? 'rotate(0deg)' : 'rotate(90deg)' }}
          >
            <ChevronDown className="w-3.5 h-3.5" />
          </span>
        )}
      </button>

      {/* Submenu */}
      {hasChildren && open && (
        <div className="overflow-hidden">
          {item.children!.map(child => (
            <NavRow
              key={child.id}
              item={child}
              depth={depth + 1}
              activeId={activeId}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </>
  );
}

/* ── Sidebar shell ── */
export function Sidebar({ items, activeId, onSelect, footer }: SidebarProps) {
  return (
    <aside className="app-sidebar bg-theme-sidebar w-theme-sidebar min-w-theme-sidebar flex-shrink-0 select-none">
      <nav className="flex-1 py-2 overflow-y-auto overflow-x-hidden">
        {items.map(item => (
          <NavRow
            key={item.id}
            item={item}
            depth={0}
            activeId={activeId}
            onSelect={onSelect}
          />
        ))}
      </nav>

      {footer && (
        <div className="border-t border-white/10 px-3 py-3 text-white/50 text-xs">
          {footer}
        </div>
      )}
    </aside>
  );
}
