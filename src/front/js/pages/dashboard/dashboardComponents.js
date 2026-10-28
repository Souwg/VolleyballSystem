import React from "react";
import { Link } from "react-router-dom";
import { Card } from "../../component/ui/card";
import { formatMoney } from "../../utils/money";

export const DashboardSection = ({
  title,
  description,
  action,
  className = "",
  children,
}) => (
  <section className={`dashboard-section ${className}`}>
    <div className="dashboard-section-heading">
      <div>
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {action}
    </div>
    {children}
  </section>
);

export const DashboardLink = ({ to, children, className = "" }) => (
  <Link className={`dashboard-link ${className}`} to={to}>
    {children}
  </Link>
);

export const DashboardEmpty = ({ title = "Todo al día", children }) => (
  <div className="dashboard-empty" role="status">
    <strong>{title}</strong>
    {children && <span>{children}</span>}
  </div>
);

export const DashboardToday = ({ items }) => (
  <div className="dashboard-today" aria-label="Resumen de hoy">
    {items.map((item) => (
      <div className="dashboard-today-item" key={item.label}>
        <span>{item.label}</span>
        <strong>{item.value}</strong>
        {item.detail && <small>{item.detail}</small>}
      </div>
    ))}
  </div>
);

export const DashboardAttention = ({ items, emptyMessage }) => {
  const activeItems = items.filter((item) => Number(item.count || 0) > 0);

  if (activeItems.length === 0) {
    return (
      <DashboardEmpty>
        {emptyMessage || "No hay acciones pendientes en este momento."}
      </DashboardEmpty>
    );
  }

  return (
    <Card className="dashboard-attention-card">
      <ul className="dashboard-attention-list">
        {activeItems.map((item) => (
          <li key={item.label}>
            <div>
              <strong>{item.count}</strong>
              <span>{item.label}</span>
            </div>
            {item.to && <DashboardLink to={item.to}>Revisar</DashboardLink>}
          </li>
        ))}
      </ul>
    </Card>
  );
};

export const DashboardFinanceSummary = ({ finance, currencyCode }) => {
  const metrics = [
    {
      label: "Deuda total",
      value: finance?.outstanding_amount,
      detail: `${finance?.outstanding_count || 0} obligaciones`,
    },
    {
      label: "Vencido",
      value: finance?.overdue_amount,
      detail: `${finance?.overdue_count || 0} pagos`,
      tone: "warning",
    },
    {
      label: "Cobrado hoy",
      value: finance?.paid_today_amount,
      detail: `${finance?.paid_today_count || 0} pagos`,
      tone: "success",
    },
    {
      label: "Cobrado este mes",
      value: finance?.paid_this_month_amount,
      detail: `${finance?.paid_this_month_count || 0} pagos`,
      tone: "success",
    },
  ];

  return (
    <div className="dashboard-finance-grid">
      {metrics.map((metric) => (
        <Card
          className={`dashboard-finance-metric dashboard-tone-${
            metric.tone || "default"
          }`}
          key={metric.label}
        >
          <span>{metric.label}</span>
          <strong>{formatMoney(metric.value, currencyCode)}</strong>
          <small>{metric.detail}</small>
        </Card>
      ))}
    </div>
  );
};

export const DashboardPanel = ({ title, subtitle, action, children }) => (
  <Card className="dashboard-panel">
    <div className="dashboard-panel-heading">
      <div>
        <h3>{title}</h3>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {action}
    </div>
    {children}
  </Card>
);
