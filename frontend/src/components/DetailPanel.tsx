import { ReactNode, useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronUp, PanelRightClose, PanelRightOpen } from "lucide-react";

export type DetailSection = {
  id: string;
  title: string;
  content: ReactNode;
  defaultOpen?: boolean;
};

type DetailPanelProps = {
  title?: string;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
  sections: DetailSection[];
  footerActions?: ReactNode;
};

export function DetailPanel({
  title = "Detalhes",
  collapsed = false,
  onToggleCollapsed,
  sections,
  footerActions
}: DetailPanelProps) {
  const defaults = useMemo(() => {
    const entries = sections.map((section) => [section.id, section.defaultOpen ?? true]);
    return Object.fromEntries(entries) as Record<string, boolean>;
  }, [sections]);
  const [openMap, setOpenMap] = useState<Record<string, boolean>>(defaults);

  useEffect(() => {
    setOpenMap(defaults);
  }, [defaults]);

  const toggleSection = (id: string) => {
    setOpenMap((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="detail-panel">
      <div className="detail-panel-header">
        <span className="detail-panel-title">{title}</span>
        {onToggleCollapsed ? (
          <button type="button" className="btn btn-secondary" onClick={onToggleCollapsed} aria-label="Alternar painel">
            {collapsed ? <PanelRightOpen size={14} /> : <PanelRightClose size={14} />}
          </button>
        ) : null}
      </div>

      {!collapsed ? (
        <div className="detail-panel-content">
          {sections.map((section) => {
            const open = openMap[section.id] ?? true;
            return (
              <section className="detail-section" key={section.id}>
                <button type="button" className="detail-section-toggle" onClick={() => toggleSection(section.id)}>
                  <span>{section.title}</span>
                  {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>
                {open ? <div className="detail-section-body">{section.content}</div> : null}
              </section>
            );
          })}
        </div>
      ) : null}

      {!collapsed && footerActions ? <footer className="detail-panel-footer">{footerActions}</footer> : null}
    </div>
  );
}
