import { LucideIcon } from "lucide-react";

export type SidebarItem = {
  id: string;
  label: string;
  icon: LucideIcon;
  disabled?: boolean;
  placement?: "top" | "bottom";
};

type SidebarProps = {
  items: SidebarItem[];
  activeId: string;
  onSelect: (id: string) => void;
};

function SidebarButton({
  item,
  active,
  onSelect
}: {
  item: SidebarItem;
  active: boolean;
  onSelect: (id: string) => void;
}) {
  const Icon = item.icon;
  return (
    <div className="sidebar-item-wrap">
      <button
        type="button"
        className={`sidebar-item ${active ? "is-active" : ""}`}
        onClick={() => onSelect(item.id)}
        disabled={item.disabled}
        aria-label={item.label}
        title={item.label}
      >
        <Icon size={18} strokeWidth={1.9} />
        {active ? <span className="sidebar-dot" aria-hidden /> : null}
      </button>
      <span className="sidebar-tooltip" role="tooltip">
        {item.label}
      </span>
    </div>
  );
}

export function Sidebar({ items, activeId, onSelect }: SidebarProps) {
  const topItems = items.filter((item) => item.placement !== "bottom");
  const bottomItems = items.filter((item) => item.placement === "bottom");

  return (
    <nav className="sidebar" aria-label="Navegação principal">
      <div className="sidebar-group">
        {topItems.map((item) => (
          <SidebarButton key={item.id} item={item} active={item.id === activeId} onSelect={onSelect} />
        ))}
      </div>
      <div className="sidebar-group">
        {bottomItems.map((item) => (
          <SidebarButton key={item.id} item={item} active={item.id === activeId} onSelect={onSelect} />
        ))}
      </div>
    </nav>
  );
}

