import React, {
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
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

const buildAgenda = (trainings = [], matches = []) =>
  [
    ...trainings.map((item) => ({ ...item, activityType: "training" })),
    ...matches.map((item) => ({ ...item, activityType: "match" })),
  ].sort((first, second) => {
    const firstKey = `${first.date || ""} ${first.start_time || "23:59"}`;
    const secondKey = `${second.date || ""} ${second.start_time || "23:59"}`;
    return (
      firstKey.localeCompare(secondKey) ||
      String(first.id).localeCompare(String(second.id))
    );
  });

const AgendaList = ({ items = [], emptyMessage }) => {
  if (items.length === 0) {
    return (
      <DashboardEmpty title={emptyMessage || "Sin actividades próximas"} />
    );
  }

  return (
    <ul className="dashboard-record-list dashboard-event-list">
      {items.map((item) => {
        const isTraining = item.activityType === "training";
        const destination = isTraining
          ? `/trainings/${item.id}`
          : `/matches/${item.id}`;
        const title = isTraining
          ? item.team_name
          : `${item.team_name} vs. ${item.opponent_name}`;

        return (
          <li key={`${item.activityType}-${item.id}`}>
            <div className="dashboard-record-main">
              <small className="dashboard-activity-type">
                {isTraining ? "Entrenamiento" : "Partido"}
              </small>
              <DashboardLink to={destination}>{title}</DashboardLink>
              <span>
                {formatDashboardDate(item.date)}
                {isTraining ? ` · ${formatDashboardTime(item.start_time)}` : ""}
              </span>
              {!isTraining && Number.isFinite(Number(item.roster_count)) && (
                <small>{item.roster_count} en convocatoria</small>
              )}
            </div>
            {item.is_today && <span className="dashboard-badge">Hoy</span>}
          </li>
        );
      })}
    </ul>
  );
};

const AgendaCard = ({ items, emptyMessage }) => (
  <Card className="dashboard-panel dashboard-agenda-card">
    <AgendaList items={items} emptyMessage={emptyMessage} />
  </Card>
);

const LiveRegistrationCard = ({ match }) => {
  if (!match) return null;

  return (
    <Card className="dashboard-live-card">
      <div>
        <span className="dashboard-kicker">
          Partido preparado para registro en vivo
        </span>
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
        Abrir registro en vivo
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
            <span>{player.payment_count} cargos pendientes</span>
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
            <small>Recibo aún no compartido desde SportFlow</small>
          </div>
        </li>
      ))}
    </ul>
  );
};

const SetupContinuation = ({ setup }) => {
  if (!setup) return null;

  return (
    <DashboardSection
      className="dashboard-setup-section"
      title={setup.title || "Termina de preparar tu club"}
    >
      <Card className="dashboard-setup-card">
        <p>{setup.message}</p>
        <DashboardLink
          className="dashboard-link-primary"
          to={setup.action_path}
        >
          {setup.action_label}
        </DashboardLink>
      </Card>
    </DashboardSection>
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
                <strong>{playersWithoutTeam.count}</strong> deportistas activos
                sin equipo
              </span>
              <DashboardLink to="/players">Asignar deportistas</DashboardLink>
            </li>
          )}
          {emptyTeams?.count > 0 && (
            <li>
              <span>
                Agrega deportistas a <strong>{emptyTeams.count}</strong>{" "}
                {emptyTeams.count === 1 ? "equipo" : "equipos"}
              </span>
              <DashboardLink
                to={
                  emptyTeams.count === 1 && emptyTeams.teams?.[0]?.team_id
                    ? `/teams/${emptyTeams.teams[0].team_id}`
                    : "/categories"
                }
              >
                Agregar deportistas
              </DashboardLink>
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
                <strong>{inactive.inactive_players_count}</strong> deportistas
                inactivas
              </span>
              <DashboardLink to="/players">
                Revisar deportistas inactivos
              </DashboardLink>
            </li>
          )}
          {role === "club_owner" && inactive?.inactive_users_count > 0 && (
            <li>
              <span>
                <strong>{inactive.inactive_users_count}</strong> usuarios del
                club inactivos
              </span>
              <DashboardLink to="/club/users">
                Revisar usuarios inactivos
              </DashboardLink>
            </li>
          )}
        </ul>
      </Card>
    </DashboardSection>
  );
};

const FinancialDetails = ({
  sections,
  currencyCode,
  includeAnalysis = true,
}) => {
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
      {includeAnalysis && hasOutstanding && (
        <DashboardPanel
          title="Deportistas con saldo pendiente"
          subtitle="Prioridad administrativa por saldo total"
        >
          <OutstandingList
            players={sections.top_outstanding_players}
            currencyCode={currencyCode}
          />
        </DashboardPanel>
      )}
      {includeAnalysis && hasAging && (
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
        title="Pagos sin recibo"
        subtitle={`${sections.paid_without_receipt.count} pagos pagados sin recibo vigente`}
        action={<DashboardLink to="/payments">Revisar pagos</DashboardLink>}
      >
        <PaymentList payments={sections.paid_without_receipt.payments} />
      </DashboardPanel>
    )}
    {sections.payment_configuration?.requires_review_count > 0 && (
      <DashboardPanel
        title="Configuración de pagos"
        subtitle={`${sections.payment_configuration.requires_review_count} deportistas tienen datos de cobro por completar`}
        action={
          <DashboardLink to="/players">
            Completar datos de cobro
          </DashboardLink>
        }
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
        subtitle="Recibos aún no compartidos desde SportFlow"
        action={<DashboardLink to="/payments">Revisar recibos</DashboardLink>}
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
          } deportistas con deuda no tienen teléfono del representante`}
          action={
            <DashboardLink to="/players">Completar contactos</DashboardLink>
          }
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
  const setup = sections.setup_continuation;
  const preparedMatch = operations.live_match;
  const agenda = buildAgenda(
    operations.upcoming_trainings,
    operations.upcoming_matches,
  ).filter(
    (item) =>
      item.activityType !== "match" ||
      !preparedMatch ||
      item.id !== preparedMatch.id,
  );
  const todayAgenda = agenda.filter((item) => item.is_today);
  const futureAgenda = agenda.filter((item) => !item.is_today);
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
      <SetupContinuation setup={setup} />

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
              actionLabel: "Revisar pagos vencidos",
              tone: "urgent",
            },
            {
              count: attention.paid_without_receipt,
              label: "pagos sin recibo",
              to: "/payments",
              actionLabel: "Revisar pagos sin recibo",
              tone: "pending",
            },
            {
              count: attention.open_matches,
              label: "partidos pendientes de finalizar",
              to: "/matches",
              actionLabel: "Finalizar partidos",
              tone: "pending",
            },
            {
              count: attention.pending_attendance,
              label: "entrenamientos con asistencia por revisar",
              to: "/trainings",
              actionLabel: "Registrar asistencia",
              tone: "pending",
            },
            {
              count: attention.payment_configuration_review,
              label: "deportistas con datos de cobro por completar",
              to: "/players",
              actionLabel: "Completar datos de cobro",
              tone: "info",
            },
            {
              count: attention.issued_without_application_share,
              label: "recibos aún no compartidos desde SportFlow",
              to: "/payments",
              actionLabel: "Revisar recibos",
              tone: "info",
            },
          ]}
          emptyTitle={setup ? "Sin otros pendientes" : "Todo al día"}
          emptyMessage={
            setup
              ? "Continúa con la preparación del club para empezar a operar."
              : "No hay acciones pendientes en este momento."
          }
        />
        <LiveRegistrationCard match={preparedMatch} />
      </DashboardSection>

      <DashboardSection
        title="Agenda de hoy"
        description="Entrenamientos y partidos programados para el día."
      >
        <AgendaCard
          items={todayAgenda}
          emptyMessage="Sin actividades programadas para hoy"
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

      {futureAgenda.length > 0 && (
        <DashboardSection
          title="Próximas actividades"
          description="Agenda deportiva posterior a hoy, en orden cronológico."
        >
          <AgendaCard items={futureAgenda} />
        </DashboardSection>
      )}

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

const CoachDashboard = ({ sections, hasTeamAssignments }) => {
  const agenda = sections.agenda || {};
  const preparedMatch = agenda.live_match;
  const activities = buildAgenda(
    agenda.upcoming_trainings,
    agenda.upcoming_matches,
  ).filter(
    (item) =>
      item.activityType !== "match" ||
      !preparedMatch ||
      item.id !== preparedMatch.id,
  );
  const todayActivities = activities.filter((item) => item.is_today);
  const futureActivities = activities.filter((item) => !item.is_today);
  const lastMatch = sections.last_official_match;

  // El flag solo llega en team_assigned: su ausencia no es "sin equipos".
  if (hasTeamAssignments === false) {
    return (
      <div className="dashboard-role-content dashboard-coach">
        <DashboardSection title="Tus equipos">
          <DashboardEmpty title="Aún no tienes equipos asignados">
            Puedes consultar la estructura del club, pero necesitarás una
            asignación para operar un equipo.
          </DashboardEmpty>
          <DashboardLink to="/categories">
            Consultar equipos del club
          </DashboardLink>
        </DashboardSection>
      </div>
    );
  }

  return (
    <div className="dashboard-role-content dashboard-coach">
      <DashboardSection
        title="Agenda de hoy"
        description="Actividades programadas para el día."
      >
        <AgendaCard
          items={todayActivities}
          emptyMessage="Sin actividades programadas para hoy"
        />
      </DashboardSection>

      <DashboardSection title="Requiere atención">
        <DashboardAttention
          items={[
            {
              count: agenda.pending_attendance?.count,
              label: "entrenamientos con asistencia por revisar",
              to: "/trainings",
              actionLabel: "Registrar asistencia",
              tone: "pending",
            },
            {
              count: agenda.open_matches_count,
              label: "partidos pendientes de finalizar",
              to: "/matches",
              actionLabel: "Finalizar partidos",
              tone: "pending",
            },
            {
              count: sections.players_without_team?.count,
              label: "deportistas activos sin equipo",
              to: "/players",
              actionLabel: "Asignar deportistas",
              tone: "info",
            },
            {
              count: sections.empty_teams?.count,
              label: "equipos que necesitan deportistas",
              to:
                sections.empty_teams?.count === 1 &&
                sections.empty_teams?.teams?.[0]?.team_id
                  ? `/teams/${sections.empty_teams.teams[0].team_id}`
                  : "/categories",
              actionLabel: "Agregar deportistas",
              tone: "info",
            },
          ]}
        />
        <LiveRegistrationCard match={preparedMatch} />
      </DashboardSection>

      {futureActivities.length > 0 && (
        <DashboardSection
          title="Próximas actividades"
          description="Agenda deportiva posterior a hoy, en orden cronológico."
        >
          <AgendaCard items={futureActivities} />
        </DashboardSection>
      )}

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
      sections.recent_payments?.payments?.length
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
              actionLabel: "Revisar pagos vencidos",
              tone: "urgent",
            },
            {
              count: attention.paid_without_receipt,
              label: "pagos sin recibo",
              to: "/payments",
              actionLabel: "Revisar pagos sin recibo",
              tone: "pending",
            },
            {
              count: attention.issued_without_application_share,
              label: "recibos aún no compartidos desde SportFlow",
              to: "/payments",
              actionLabel: "Revisar recibos",
              tone: "pending",
            },
            {
              count: attention.payment_configuration_review,
              label: "deportistas con datos de cobro por completar",
              to: "/players",
              actionLabel: "Completar datos de cobro",
              tone: "info",
            },
            {
              count: attention.missing_payment_contacts,
              label: "deportistas con deuda sin contacto",
              to: "/players",
              actionLabel: "Completar contactos",
              tone: "info",
            },
          ]}
        />
      </DashboardSection>

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

      {hasFinancialDetails && (
        <DashboardSection title="Vencimientos y cobros">
          <FinancialDetails
            sections={sections}
            currencyCode={currencyCode}
            includeAnalysis={false}
          />
        </DashboardSection>
      )}

      <DashboardSection
        title="Resumen financiero"
        description="Estado financiero actual del club."
        action={<DashboardLink to="/payments">Ver pagos</DashboardLink>}
      >
        <DashboardFinanceSummary
          finance={sections.finance}
          currencyCode={currencyCode}
        />
      </DashboardSection>

      {hasAdministrativeDetails && (
        <DashboardSection title="Gestión administrativa">
          <AdministrativeDetails sections={sections} includeContacts />
        </DashboardSection>
      )}
    </div>
  );
};

const DashboardErrorState = ({ error, userRole, onRetry }) => {
  if (error?.code === "ACTIVE_SEASON_REQUIRED") {
    const isOwner = userRole === "club_owner";

    return (
      <Card className="dashboard-error" role="alert">
        <h2>No hay una temporada activa</h2>
        <p>
          {isOwner
            ? "Necesitas una temporada activa para mostrar la operación deportiva del club."
            : "El administrador del club debe activar una temporada para habilitar la operación deportiva."}
        </p>
        {isOwner ? (
          <DashboardLink className="dashboard-link-primary" to="/seasons">
            Gestionar temporadas
          </DashboardLink>
        ) : (
          <Button type="button" variant="secondary" onClick={onRetry}>
            Comprobar de nuevo
          </Button>
        )}
      </Card>
    );
  }

  return (
    <Card className="dashboard-error" role="alert">
      <h2>No pudimos cargar el Dashboard</h2>
      <p>{error?.message || "Ocurrió un error temporal."}</p>
      <Button type="button" onClick={onRetry}>
        Volver a intentar
      </Button>
    </Card>
  );
};

export const Dashboard = () => {
  const { store, actions } = useContext(Context);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const dashboard = store.dashboardData;
  const userRole = store.user?.role;
  const getDashboard = actions.getDashboard;
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;

    return () => {
      mounted.current = false;
    };
  }, []);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);

    const result = await getDashboard();

    // Respondió otra carga más reciente, o ya se salió de la pantalla.
    if (!mounted.current || result?.code === "STALE_RESPONSE") return;

    if (!result?.ok) {
      setError({
        code: result?.code,
        message: result?.message || "No pudimos cargar el Dashboard.",
      });
    }

    setLoading(false);
  }, [getDashboard]);

  useEffect(() => {
    if (!store.token) return;
    loadDashboard();
  }, [store.token, userRole, loadDashboard]);

  const activeRole = dashboard?.role || userRole;
  const roleCopy = ROLE_COPY[activeRole] || ROLE_COPY.club_owner;
  const club = dashboard?.club || store.club || store.user?.club;
  const sections = dashboard?.sections || {};
  const currencyCode = dashboard?.club?.currency_code;
  const canRenderDashboard = dashboard?.role === userRole;

  return (
    <div className={`dashboard-page dashboard-page-${activeRole || "loading"}`}>
      <PageHeader
        className="dashboard-header"
        eyebrow={roleCopy.eyebrow}
        title={club?.name || "SportFlow"}
        subtitle={roleCopy.subtitle}
        avatar={club?.image_url}
        fallback={club?.name}
      />

      {loading && (
        <div className="dashboard-loading" role="status" aria-live="polite">
          Cargando prioridades y actividades...
        </div>
      )}

      {!loading && error && (
        <DashboardErrorState
          error={error}
          userRole={userRole}
          onRetry={loadDashboard}
        />
      )}

      {!loading && !error && canRenderDashboard && activeRole === "club_owner" && (
        <OwnerDashboard sections={sections} currencyCode={currencyCode} />
      )}
      {!loading && !error && canRenderDashboard && activeRole === "coach" && (
        <CoachDashboard
          sections={sections}
          hasTeamAssignments={dashboard.has_team_assignments}
        />
      )}
      {!loading && !error && canRenderDashboard && activeRole === "staff" && (
        <StaffDashboard sections={sections} currencyCode={currencyCode} />
      )}
    </div>
  );
};
