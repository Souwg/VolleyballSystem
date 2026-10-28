import React, { useCallback, useContext, useEffect, useState } from "react";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import {
  DashboardAttention,
  DashboardEmpty,
  DashboardFinanceSummary,
  DashboardLink,
  DashboardPanel,
  DashboardSection,
  DashboardToday,
} from "./dashboardComponents";
import {
  formatDashboardDate,
  formatDashboardTime,
  getDashboardPaymentMethodLabel,
  getDashboardPaymentTypeLabel,
  getMatchResultLabel,
  getPaymentConfigurationLabel,
} from "../../utils/dashboardFormatters";
import { formatMoney } from "../../utils/money";
import "../../../styles/dashboard.css";

const ROLE_COPY = {
  club_owner: {
    eyebrow: "Panel del club",
    subtitle: "Prioridades, finanzas y operación del club",
  },
  coach: {
    eyebrow: "Agenda deportiva",
    subtitle: "Actividades y tareas deportivas que requieren atención",
  },
  staff: {
    eyebrow: "Bandeja administrativa",
    subtitle: "Cobros, recibos y datos pendientes de completar",
  },
};

const PaymentList = ({ payments = [], mode = "paid", emptyMessage }) => {
  if (payments.length === 0) {
    return <DashboardEmpty title={emptyMessage || "Sin movimientos"} />;
  }

  return (
    <ul className="dashboard-record-list">
      {payments.map((payment) => (
        <li key={payment.payment_id}>
          <div className="dashboard-record-main">
            <DashboardLink to={`/players/${payment.player_id}/payments`}>
              {payment.player_name}
            </DashboardLink>
            <span>
              {mode === "due"
                ? `Vence ${formatDashboardDate(payment.due_date)}`
                : `${getDashboardPaymentTypeLabel(payment.payment_type)} · ${
                    payment.payment_date
                      ? formatDashboardDate(payment.payment_date)
                      : "Fecha no registrada"
                  }`}
            </span>
            {mode === "paid" && payment.payment_method && (
              <small>
                {getDashboardPaymentMethodLabel(payment.payment_method)}
              </small>
            )}
          </div>
          <strong>{formatMoney(payment.amount, payment.currency_code)}</strong>
        </li>
      ))}
    </ul>
  );
};

const EventList = ({ items = [], type, emptyMessage }) => {
  if (items.length === 0) {
    return (
      <DashboardEmpty title={emptyMessage || "Sin actividades próximas"} />
    );
  }

  return (
    <ul className="dashboard-record-list dashboard-event-list">
      {items.map((item) => {
        const isTraining = type === "training";
        const destination = isTraining
          ? `/trainings/${item.id}`
          : `/matches/${item.id}`;
        const title = isTraining
          ? item.team_name
          : `${item.team_name} vs. ${item.opponent_name}`;

        return (
          <li key={`${type}-${item.id}`}>
            <div className="dashboard-record-main">
              <DashboardLink to={destination}>{title}</DashboardLink>
              <span>
                {formatDashboardDate(item.date)}
                {isTraining ? ` · ${formatDashboardTime(item.start_time)}` : ""}
              </span>
              {!isTraining && Number.isFinite(Number(item.roster_count)) && (
                <small>{item.roster_count} convocadas</small>
              )}
            </div>
            {item.is_today && <span className="dashboard-badge">Hoy</span>}
          </li>
        );
      })}
    </ul>
  );
};

const LiveMatchCard = ({ match }) => {
  if (!match) return null;

  return (
    <Card className="dashboard-live-card">
      <div>
        <span className="dashboard-kicker">Partido en curso</span>
        <h3>
          {match.team_name} vs. {match.opponent_name}
        </h3>
        <p>
          {formatDashboardDate(match.date)}
          {match.location ? ` · ${match.location}` : ""}
        </p>
      </div>
      <DashboardLink
        className="dashboard-link-primary"
        to={`/matches/${match.id}/live`}
      >
        Continuar LiveMatch
      </DashboardLink>
    </Card>
  );
};

const AgingPanel = ({ aging = {}, currencyCode }) => {
  const rows = [
    ["0–7 días", aging.days_0_7],
    ["8–30 días", aging.days_8_30],
    ["31+ días", aging.days_31_plus],
  ];

  return (
    <div className="dashboard-aging-list">
      {rows.map(([label, bucket]) => (
        <div key={label}>
          <span>{label}</span>
          <strong>{formatMoney(bucket?.amount, currencyCode)}</strong>
          <small>{bucket?.count || 0} pagos</small>
        </div>
      ))}
    </div>
  );
};

const OutstandingList = ({ players = [], currencyCode }) => {
  if (players.length === 0) {
    return <DashboardEmpty title="No hay saldos pendientes" />;
  }

  return (
    <ul className="dashboard-record-list">
      {players.map((player) => (
        <li key={player.player_id}>
          <div className="dashboard-record-main">
            <DashboardLink to={`/players/${player.player_id}/payments`}>
              {player.player_name}
            </DashboardLink>
            <span>{player.payment_count} obligaciones</span>
            {player.overdue_amount > 0 && (
              <small>
                {formatMoney(player.overdue_amount, currencyCode)} vencido
              </small>
            )}
          </div>
          <strong>{formatMoney(player.outstanding_amount, currencyCode)}</strong>
        </li>
      ))}
    </ul>
  );
};

const PaymentConfigurationList = ({ configuration }) => {
  const players = configuration?.players || [];

  if (players.length === 0) {
    return <DashboardEmpty title="Configuración al día" />;
  }

  return (
    <ul className="dashboard-record-list">
      {players.map((player) => (
        <li key={player.player_id}>
          <div className="dashboard-record-main">
            <DashboardLink to={`/players/${player.player_id}/payments`}>
              {player.player_name}
            </DashboardLink>
            <span>{getPaymentConfigurationLabel(player.reason)}</span>
          </div>
        </li>
      ))}
    </ul>
  );
};

const ReceiptAttentionList = ({ attention }) => {
  const receipts = attention?.receipts || [];

  if (receipts.length === 0) {
    return <DashboardEmpty title="Recibos al día" />;
  }

  return (
    <ul className="dashboard-record-list">
      {receipts.map((receipt) => (
        <li key={receipt.receipt_id}>
          <div className="dashboard-record-main">
            <strong>{receipt.player_name}</strong>
            <span>Recibo {receipt.receipt_number}</span>
            <small>Sin actividad de compartir desde la aplicación</small>
          </div>
        </li>
      ))}
    </ul>
  );
};

const OrganizationPanel = ({ sections, role }) => {
  const playersWithoutTeam = sections.players_without_team;
  const emptyTeams = sections.empty_teams;
  const tournaments = sections.active_tournaments || [];
  const inactive = sections.inactive_people;
  const hasContent =
    playersWithoutTeam?.count > 0 ||
    emptyTeams?.count > 0 ||
    tournaments.length > 0 ||
    inactive?.inactive_players_count > 0 ||
    inactive?.inactive_users_count > 0;

  if (!hasContent) return null;

  return (
    <DashboardSection
      className="dashboard-secondary-section"
      title="Organización"
      description="Contexto secundario para mantener el club ordenado."
    >
      <Card className="dashboard-organization-card">
        <ul className="dashboard-organization-list">
          {playersWithoutTeam?.count > 0 && (
            <li>
              <span>
                <strong>{playersWithoutTeam.count}</strong> jugadoras activas
                sin equipo
              </span>
              <DashboardLink to="/players">Ver jugadoras</DashboardLink>
            </li>
          )}
          {emptyTeams?.count > 0 && (
            <li>
              <span>
                <strong>{emptyTeams.count}</strong> equipos sin jugadoras
                activas
              </span>
              <DashboardLink to="/categories">Ver equipos</DashboardLink>
            </li>
          )}
          {tournaments.length > 0 && (
            <li>
              <span>
                <strong>{tournaments.length}</strong> torneos activos visibles
              </span>
              <DashboardLink to="/tournaments">Ver torneos</DashboardLink>
            </li>
          )}
          {role === "club_owner" && inactive?.inactive_players_count > 0 && (
            <li>
              <span>
                <strong>{inactive.inactive_players_count}</strong> jugadoras
                inactivas
              </span>
              <DashboardLink to="/players">Revisar</DashboardLink>
            </li>
          )}
          {role === "club_owner" && inactive?.inactive_users_count > 0 && (
            <li>
              <span>
                <strong>{inactive.inactive_users_count}</strong> usuarios del
                club inactivos
              </span>
              <DashboardLink to="/club/users">Revisar</DashboardLink>
            </li>
          )}
        </ul>
      </Card>
    </DashboardSection>
  );
};

const FinancialDetails = ({ sections, currencyCode }) => {
  const hasUpcoming = sections.upcoming_due?.payments?.length > 0;
  const hasRecent = sections.recent_payments?.payments?.length > 0;
  const hasOutstanding = sections.top_outstanding_players?.length > 0;
  const hasAging = Boolean(
    sections.overdue_aging?.days_0_7?.count ||
      sections.overdue_aging?.days_8_30?.count ||
      sections.overdue_aging?.days_31_plus?.count
  );

  return (
    <div className="dashboard-two-column">
      {hasUpcoming && (
        <DashboardPanel
          title="Próximos vencimientos"
          subtitle={`${sections.upcoming_due.today_count || 0} vencen hoy · ${
            sections.upcoming_due.next_7_days_count || 0
          } en los próximos 7 días`}
          action={<DashboardLink to="/payments">Ver pagos</DashboardLink>}
        >
          <PaymentList mode="due" payments={sections.upcoming_due.payments} />
        </DashboardPanel>
      )}
      {hasRecent && (
        <DashboardPanel
          title="Cobros recientes"
          subtitle="Últimos pagos registrados"
          action={<DashboardLink to="/payments">Ver pagos</DashboardLink>}
        >
          <PaymentList payments={sections.recent_payments.payments} />
        </DashboardPanel>
      )}
      {hasOutstanding && (
        <DashboardPanel
          title="Jugadoras con saldo pendiente"
          subtitle="Prioridad administrativa por saldo total"
        >
          <OutstandingList
            players={sections.top_outstanding_players}
            currencyCode={currencyCode}
          />
        </DashboardPanel>
      )}
      {hasAging && (
        <DashboardPanel
          title="Antigüedad de vencidos"
          subtitle="Distribución de pagos ya marcados como vencidos"
        >
          <AgingPanel
            aging={sections.overdue_aging}
            currencyCode={currencyCode}
          />
        </DashboardPanel>
      )}
    </div>
  );
};

const AdministrativeDetails = ({ sections, includeContacts = false }) => (
  <div className="dashboard-two-column">
    {sections.paid_without_receipt?.count > 0 && (
      <DashboardPanel
        title="Pagos que necesitan recibo"
        subtitle={`${sections.paid_without_receipt.count} pagos pagados sin recibo vigente`}
        action={<DashboardLink to="/payments">Ver pagos</DashboardLink>}
      >
        <PaymentList payments={sections.paid_without_receipt.payments} />
      </DashboardPanel>
    )}
    {sections.payment_configuration?.requires_review_count > 0 && (
      <DashboardPanel
        title="Configuración de pagos"
        subtitle={`${sections.payment_configuration.requires_review_count} jugadoras requieren revisión`}
        action={<DashboardLink to="/players">Ver jugadoras</DashboardLink>}
      >
        <PaymentConfigurationList
          configuration={sections.payment_configuration}
        />
      </DashboardPanel>
    )}
    {sections.receipt_share_attention?.issued_without_application_share_count >
      0 && (
      <DashboardPanel
        title="Recibos pendientes de compartir"
        subtitle="Recibos emitidos sin actividad de compartir desde SportFlow"
        action={<DashboardLink to="/payments">Ver pagos</DashboardLink>}
      >
        <ReceiptAttentionList attention={sections.receipt_share_attention} />
      </DashboardPanel>
    )}
    {includeContacts &&
      sections.missing_payment_contacts
        ?.outstanding_players_without_contact_count > 0 && (
        <DashboardPanel
          title="Contactos por completar"
          subtitle={`${
            sections.missing_payment_contacts
              ?.outstanding_players_without_contact_count || 0
          } jugadoras con deuda no tienen teléfono del representante`}
          action={<DashboardLink to="/players">Ver jugadoras</DashboardLink>}
        >
          <ul className="dashboard-record-list">
            {sections.missing_payment_contacts.players.map((player) => (
              <li key={player.player_id}>
                <DashboardLink to={`/players/${player.player_id}`}>
                  {player.player_name}
                </DashboardLink>
              </li>
            ))}
          </ul>
        </DashboardPanel>
      )}
  </div>
);

const OwnerDashboard = ({ sections, currencyCode }) => {
  const operations = sections.operations || {};
  const attention = sections.attention_summary || {};
  const hasOperations = Boolean(
    operations.live_match ||
      operations.open_matches_count ||
      operations.pending_attendance?.count ||
      operations.upcoming_trainings?.length ||
      operations.upcoming_matches?.length
  );
  const hasFinancialDetails = Boolean(
    sections.upcoming_due?.payments?.length ||
      sections.recent_payments?.payments?.length ||
      sections.top_outstanding_players?.length ||
      sections.overdue_aging?.days_0_7?.count ||
      sections.overdue_aging?.days_8_30?.count ||
      sections.overdue_aging?.days_31_plus?.count
  );
  const hasAdministrativeDetails = Boolean(
    sections.paid_without_receipt?.count ||
      sections.payment_configuration?.requires_review_count ||
      sections.receipt_share_attention?.issued_without_application_share_count
  );

  return (
    <div className="dashboard-role-content">
      <DashboardSection title="Hoy">
        <DashboardToday
          items={[
            {
              label: "Entrenamientos",
              value: sections.today?.trainings_today_count || 0,
            },
            {
              label: "Partidos",
              value: sections.today?.matches_today_count || 0,
            },
            {
              label: "Cobrado",
              value: formatMoney(
                sections.today?.paid_today_amount,
                currencyCode,
              ),
              detail: `${sections.today?.paid_today_count || 0} pagos`,
            },
            { label: "Vencidos", value: sections.today?.overdue_count || 0 },
          ]}
        />
      </DashboardSection>

      <DashboardSection
        title="Requiere atención"
        description="Pendientes con impacto operativo o administrativo."
      >
        <DashboardAttention
          items={[
            {
              count: attention.overdue_payments,
              label: "pagos vencidos",
              to: "/payments",
            },
            {
              count: attention.paid_without_receipt,
              label: "pagos necesitan recibo",
              to: "/payments",
            },
            {
              count: attention.open_matches,
              label: "partidos pendientes de finalizar",
              to: "/matches",
            },
            {
              count: attention.pending_attendance,
              label: "entrenamientos con asistencia pendiente",
              to: "/trainings",
            },
            {
              count: attention.payment_configuration_review,
              label: "configuraciones de pago requieren revisión",
              to: "/players",
            },
            {
              count: attention.issued_without_application_share,
              label: "recibos sin actividad de compartir",
              to: "/payments",
            },
          ]}
        />
      </DashboardSection>

      <DashboardSection
        title="Finanzas"
        description="Estado actual de cobranza del club."
        action={<DashboardLink to="/payments">Ver pagos</DashboardLink>}
      >
        <DashboardFinanceSummary
          finance={sections.finance}
          currencyCode={currencyCode}
        />
      </DashboardSection>

      <DashboardSection
        title="Operación deportiva"
        description="Partidos abiertos, asistencia y próximas actividades."
      >
        {!hasOperations ? (
          <DashboardEmpty title="Sin actividades pendientes">
            No hay actividades próximas ni tareas deportivas por completar.
          </DashboardEmpty>
        ) : (
          <>
            <LiveMatchCard match={operations.live_match} />
            <div className="dashboard-two-column">
              <DashboardPanel
                title="Partidos abiertos"
                subtitle={`${
                  operations.open_matches_count || 0
                } pendientes de finalizar`}
                action={
                  <DashboardLink to="/matches">Ver partidos</DashboardLink>
                }
              >
                <EventList
                  type="match"
                  items={operations.open_matches}
                  emptyMessage="No hay partidos pendientes de finalizar"
                />
              </DashboardPanel>
              <DashboardPanel
                title="Asistencia pendiente"
                subtitle={`${
                  operations.pending_attendance?.count || 0
                } entrenamientos requieren revisión`}
                action={
                  <DashboardLink to="/trainings">
                    Ver entrenamientos
                  </DashboardLink>
                }
              >
                <EventList
                  type="training"
                  items={operations.pending_attendance?.trainings}
                  emptyMessage="No hay asistencias pendientes"
                />
              </DashboardPanel>
              <DashboardPanel title="Próximos entrenamientos">
                <EventList
                  type="training"
                  items={operations.upcoming_trainings}
                />
              </DashboardPanel>
              <DashboardPanel title="Próximos partidos">
                <EventList type="match" items={operations.upcoming_matches} />
              </DashboardPanel>
            </div>
          </>
        )}
      </DashboardSection>

      {hasFinancialDetails && (
        <DashboardSection
          title="Próximos movimientos financieros"
          description="Vencimientos, cobros y saldos que conviene revisar."
        >
          <FinancialDetails
            sections={sections}
            currencyCode={currencyCode}
          />
        </DashboardSection>
      )}

      {hasAdministrativeDetails && (
        <DashboardSection
          className="dashboard-secondary-section"
          title="Acciones administrativas"
        >
          <AdministrativeDetails sections={sections} />
        </DashboardSection>
      )}

      <OrganizationPanel sections={sections} role="club_owner" />
    </div>
  );
};

const CoachDashboard = ({ sections }) => {
  const agenda = sections.agenda || {};
  const todayTrainings = (agenda.upcoming_trainings || []).filter(
    (item) => item.is_today
  );
  const todayMatches = (agenda.upcoming_matches || []).filter(
    (item) => item.is_today
  );
  const futureTrainings = (agenda.upcoming_trainings || []).filter(
    (item) => !item.is_today
  );
  const futureMatches = (agenda.upcoming_matches || []).filter(
    (item) => !item.is_today
  );
  const lastMatch = sections.last_official_match;
  const hasFutureActivities =
    futureTrainings.length > 0 || futureMatches.length > 0;

  return (
    <div className="dashboard-role-content dashboard-coach">
      <DashboardSection title="Hoy">
        <DashboardToday
          items={[
            {
              label: "Entrenamientos",
              value: sections.today?.trainings_today_count || 0,
            },
            {
              label: "Partidos",
              value: sections.today?.matches_today_count || 0,
            },
            {
              label: "Asistencias pendientes",
              value: sections.today?.pending_attendance_count || 0,
            },
            {
              label: "Partidos abiertos",
              value: sections.today?.open_matches_count || 0,
            },
          ]}
        />
      </DashboardSection>

      <DashboardSection title="Requiere atención">
        <DashboardAttention
          items={[
            {
              count: agenda.pending_attendance?.count,
              label: "entrenamientos con asistencia pendiente",
              to: "/trainings",
            },
            {
              count: agenda.open_matches_count,
              label: "partidos pendientes de finalizar",
              to: "/matches",
            },
            {
              count: sections.players_without_team?.count,
              label: "jugadoras activas sin equipo",
              to: "/players",
            },
            {
              count: sections.empty_teams?.count,
              label: "equipos sin jugadoras activas",
              to: "/categories",
            },
          ]}
        />
      </DashboardSection>

      <DashboardSection
        title="Agenda de hoy"
        description="Actividades programadas para el día."
      >
        {todayTrainings.length === 0 && todayMatches.length === 0 ? (
          <DashboardEmpty title="Sin actividades para hoy">
            La próxima actividad aparecerá en la agenda.
          </DashboardEmpty>
        ) : (
          <div className="dashboard-two-column">
            <DashboardPanel title="Entrenamientos">
              <EventList type="training" items={todayTrainings} />
            </DashboardPanel>
            <DashboardPanel title="Partidos">
              <EventList type="match" items={todayMatches} />
            </DashboardPanel>
          </div>
        )}
      </DashboardSection>

      <LiveMatchCard match={agenda.live_match} />

      <DashboardSection
        title="Próximamente"
        description="Actividades posteriores a hoy."
      >
        {!hasFutureActivities ? (
          <DashboardEmpty title="Sin actividades próximas" />
        ) : (
          <div className="dashboard-two-column">
            <DashboardPanel title="Entrenamientos">
              <EventList type="training" items={futureTrainings} />
            </DashboardPanel>
            <DashboardPanel title="Partidos">
              <EventList type="match" items={futureMatches} />
            </DashboardPanel>
          </div>
        )}
      </DashboardSection>

      {lastMatch && (
        <DashboardSection
          className="dashboard-secondary-section"
          title="Último partido oficial"
        >
          <Card className="dashboard-last-match">
            <div>
              <span>
                {formatDashboardDate(lastMatch.date, { year: "numeric" })}
              </span>
              <h3>
                {lastMatch.team_name} vs. {lastMatch.opponent_name}
              </h3>
              <p>
                {getMatchResultLabel(lastMatch.result)} · {lastMatch.home_sets}–
                {lastMatch.opponent_sets}
              </p>
            </div>
            <DashboardLink to={`/matches/${lastMatch.match_id}`}>
              Ver resumen
            </DashboardLink>
          </Card>
        </DashboardSection>
      )}

      <OrganizationPanel sections={sections} role="coach" />
    </div>
  );
};

const StaffDashboard = ({ sections, currencyCode }) => {
  const attention = sections.attention_summary || {};
  const hasFinancialDetails = Boolean(
    sections.upcoming_due?.payments?.length ||
      sections.recent_payments?.payments?.length ||
      sections.top_outstanding_players?.length ||
      sections.overdue_aging?.days_0_7?.count ||
      sections.overdue_aging?.days_8_30?.count ||
      sections.overdue_aging?.days_31_plus?.count
  );
  const hasAdministrativeDetails = Boolean(
    sections.paid_without_receipt?.count ||
      sections.payment_configuration?.requires_review_count ||
      sections.receipt_share_attention
        ?.issued_without_application_share_count ||
      sections.missing_payment_contacts
        ?.outstanding_players_without_contact_count
  );

  return (
    <div className="dashboard-role-content dashboard-staff">
      <DashboardSection title="Hoy">
        <DashboardToday
          items={[
            {
              label: "Cobrado",
              value: formatMoney(
                sections.today?.paid_today_amount,
                currencyCode,
              ),
              detail: `${sections.today?.paid_today_count || 0} pagos`,
            },
            { label: "Vencidos", value: sections.today?.overdue_count || 0 },
            {
              label: "Vencen hoy",
              value: sections.today?.due_today_count || 0,
              detail: formatMoney(
                sections.today?.due_today_amount,
                currencyCode,
              ),
            },
          ]}
        />
      </DashboardSection>

      <DashboardSection
        title="Requiere atención"
        description="Cobros, recibos y datos administrativos pendientes."
      >
        <DashboardAttention
          items={[
            {
              count: attention.overdue_payments,
              label: "pagos vencidos",
              to: "/payments",
            },
            {
              count: attention.paid_without_receipt,
              label: "pagos necesitan recibo",
              to: "/payments",
            },
            {
              count: attention.issued_without_application_share,
              label: "recibos pendientes de compartir",
              to: "/payments",
            },
            {
              count: attention.payment_configuration_review,
              label: "configuraciones de pago requieren revisión",
              to: "/players",
            },
            {
              count: attention.missing_payment_contacts,
              label: "jugadoras con deuda no tienen contacto",
              to: "/players",
            },
          ]}
        />
      </DashboardSection>

      <DashboardSection
        title="Cobranza"
        description="Estado financiero actual del club."
        action={<DashboardLink to="/payments">Ver pagos</DashboardLink>}
      >
        <DashboardFinanceSummary
          finance={sections.finance}
          currencyCode={currencyCode}
        />
      </DashboardSection>

      {hasFinancialDetails && (
        <DashboardSection title="Vencimientos y saldos">
          <FinancialDetails
            sections={sections}
            currencyCode={currencyCode}
          />
        </DashboardSection>
      )}

      {hasAdministrativeDetails && (
        <DashboardSection title="Gestión administrativa">
          <AdministrativeDetails sections={sections} includeContacts />
        </DashboardSection>
      )}
    </div>
  );
};

export const Dashboard = () => {
  const { store, actions } = useContext(Context);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const dashboard = store.dashboardData;
  const userRole = store.user?.role;
  const getDashboard = actions.getDashboard;

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError("");

    const result = await getDashboard();

    if (!result?.ok) {
      setError(result?.message || "No pudimos cargar el Dashboard.");
    }

    setLoading(false);
  }, [getDashboard]);

  useEffect(() => {
    if (!store.token) return;
    loadDashboard();
  }, [store.token, userRole, loadDashboard]);

  if (loading) {
    return (
      <div className="dashboard-loading" role="status" aria-live="polite">
        Cargando Dashboard...
      </div>
    );
  }

  if (error) {
    return (
      <Card className="dashboard-error" role="alert">
        <h2>No pudimos cargar el Dashboard</h2>
        <p>{error}</p>
        <Button type="button" onClick={loadDashboard}>
          Volver a intentar
        </Button>
      </Card>
    );
  }

  if (!dashboard || dashboard.role !== userRole) {
    return null;
  }

  const roleCopy = ROLE_COPY[dashboard.role] || ROLE_COPY.club_owner;
  const sections = dashboard.sections || {};
  const currencyCode = dashboard.club?.currency_code;

  return (
    <div className={`dashboard-page dashboard-page-${dashboard.role}`}>
      <PageHeader
        className="dashboard-header"
        eyebrow={roleCopy.eyebrow}
        title={dashboard.club?.name || "SportFlow"}
        subtitle={roleCopy.subtitle}
        avatar={dashboard.club?.image_url}
        fallback={dashboard.club?.name}
      />

      {dashboard.role === "club_owner" && (
        <OwnerDashboard sections={sections} currencyCode={currencyCode} />
      )}
      {dashboard.role === "coach" && <CoachDashboard sections={sections} />}
      {dashboard.role === "staff" && (
        <StaffDashboard sections={sections} currencyCode={currencyCode} />
      )}
    </div>
  );
};
