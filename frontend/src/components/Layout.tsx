import { ReactNode } from "react";

type LayoutProps = {
  sidebar: ReactNode;
  sectionTitle: string;
  breadcrumb?: string;
  center: ReactNode;
  detail: ReactNode;
  statusBar?: ReactNode;
  detailCollapsed?: boolean;
};

export function Layout({
  sidebar,
  sectionTitle,
  breadcrumb,
  center,
  detail,
  statusBar,
  detailCollapsed = false
}: LayoutProps) {
  return (
    <div className="app-shell">
      {sidebar}
      <div className="app-main">
        {statusBar}
        <header className="app-section-header">
          <h1 className="app-section-title">{sectionTitle}</h1>
          {breadcrumb ? <div className="app-section-breadcrumb">{breadcrumb}</div> : null}
        </header>
        <div className={`app-workspace ${detailCollapsed ? "detail-collapsed" : ""}`}>
          <section className="app-center fade-tab">{center}</section>
          <aside className={`app-detail ${detailCollapsed ? "is-collapsed" : ""}`}>{detail}</aside>
        </div>
      </div>
    </div>
  );
}
