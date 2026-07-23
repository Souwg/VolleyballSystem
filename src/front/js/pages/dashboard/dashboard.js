import React, { useEffect, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import "../../../styles/dashboard.css";

const MetricIcon = ({ type }) => {
  const icons = {
    teams: (
      <>
        <path d="M12 3 4.5 6.5v5c0 4.6 3.1 7.7 7.5 9.5 4.4-1.8 7.5-4.9 7.5-9.5v-5L12 3Z" />
        <path d="M9.5 12 11 13.5l3.5-3.5" />
      </>
    ),

    players: (
      <>
        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </>
    ),

    active: (
      <>
        <path d="M3 12h4l2-7 4 14 2-7h6" />
      </>
    ),
  };

  return (
    <svg
      className="dashboard-metric-icon-svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {icons[type]}
    </svg>
  );
};

const MiniTrend = ({ values = [], tone = "primary" }) => {
  const normalizedValues =
    Array.isArray(values) && values.length > 0
      ? values.map(Number)
      : [0, 0, 0, 0];

  const maxValue = Math.max(...normalizedValues);
  const minValue = Math.min(...normalizedValues);
  const difference = maxValue - minValue;

  const points = normalizedValues.map((value, index) => {
    const x =
      normalizedValues.length === 1
        ? 50
        : (index / (normalizedValues.length - 1)) * 100;

    const y =
      difference === 0 ? 20 : 32 - ((value - minValue) / difference) * 24;

    return {
      x,
      y,
    };
  });

  const polylinePoints = points
    .map((point) => `${point.x},${point.y}`)
    .join(" ");

  const areaPoints = `0,40 ${polylinePoints} 100,40`;

  const lastPoint = points[points.length - 1];

  return (
    <svg
      className={`dashboard-mini-trend dashboard-mini-trend-${tone}`}
      viewBox="0 0 100 40"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <polygon className="dashboard-mini-trend-area" points={areaPoints} />

      <polyline className="dashboard-mini-trend-line" points={polylinePoints} />

      <circle
        className="dashboard-mini-trend-point"
        cx={lastPoint.x}
        cy={lastPoint.y}
        r="2.5"
      />
    </svg>
  );
};

export const Dashboard = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();
  const stats = store.dashboardStats;

  const subscriptionStatus = store.user?.subscription_status;

  const clubStatus =
    subscriptionStatus === "active"
      ? {
          label: "Activo",
          className: "status-success",
        }
      : {
          label: "Revisar",
          className: "status-warning",
        };

  const teamsThisWeek = Number(stats?.teams_this_week ?? 0);
  const playersThisWeek = Number(stats?.players_this_week ?? 0);

  const activePlayersPercentage = Math.min(
    100,
    Math.max(0, Number(stats?.active_players_percentage ?? 0)),
  );

  const teamsWeeklyTrend = Array.isArray(stats?.teams_weekly_trend)
    ? stats.teams_weekly_trend
    : [0, 0, 0, 0];

  const playersWeeklyTrend = Array.isArray(stats?.players_weekly_trend)
    ? stats.players_weekly_trend
    : [0, 0, 0, 0];

  const getDashboardCTA = () => {
    if (stats.total_categories === 0) {
      return {
        title: "Crea tu primera categoría",
        message:
          "Organiza tu club por etapas como Iniciación, U12, U14 o Juvenil.",
        action: "go_to_categories",
        buttonText: "Crear categoría",
      };
    }

    if (stats.total_teams === 0) {
      return {
        title: "Crea tu primer equipo",
        message:
          "Divide una categoría en equipos o grupos para gestionar entrenamientos y deportistas.",
        action: "go_to_categories",
        buttonText: "Crear equipo",
      };
    }

    if (stats.total_players === 0) {
      return {
        title: "Añade tu primer deportista",
        message:
          "Empieza a construir el roster de tu equipo y mantén la información centralizada.",
        action: "go_to_players",
        buttonText: "Añadir deportista",
      };
    }

    if (stats.total_trainings === 0) {
      return {
        title: "Crea tu primer entrenamiento",
        message:
          "Organiza sesiones, controla asistencia y empieza a medir el progreso del equipo.",
        action: "go_to_trainings",
        buttonText: "Crear entrenamiento",
      };
    }

    return {
      title: "Gestiona tus entrenamientos",
      message:
        "Consulta sesiones, registra asistencia y mantén el seguimiento del equipo.",
      action: "go_to_trainings",
      buttonText: "Ver entrenamientos",
    };
  };

  useEffect(() => {
    if (!store.token) return;
    actions.getDashboard();
  }, [store.token]);

  if (!store.dashboardStats) {
    return <p>Cargando resumen del club...</p>;
  }

  const cta = getDashboardCTA();

  const handleCTAAction = () => {
    const routes = {
      go_to_categories: "/categories",
      go_to_players: "/players",
      go_to_trainings: "/trainings",
    };

    navigate(routes[cta.action] || "/dashboard");
  };

  const today = new Date().toISOString().slice(0, 10);

  const isPastMatch = (match) => {
    if (!match?.date) return false;
    return match.date < today;
  };

  const getMatchCardLabel = (match) => {
    if (isPastMatch(match)) return "Partido pendiente de cierre";

    if (match.match_step >= 3) return "Partido en curso";

    return "Próximo partido";
  };

  const getMatchButtonText = (match) => {
    if (isPastMatch(match)) return "Cerrar partido";

    if (match.match_step >= 3) return "Continuar partido";

    return "Preparar partido";
  };

  const getMatchStatusText = (match) => {
    if (match.match_step === 0) return "Faltan convocadas";
    if (match.match_step === 1) return "Falta confirmar asistencia";
    if (match.match_step === 2) return "Falta definir participación";
    if (match.match_step === 3) return "Listo para registrar estadísticas";
    if (match.match_step >= 4) return "Pendiente de resultado";

    return "Pendiente de preparación";
  };

  return (
    <>
      <PageHeader
        className="dashboard-header"
        eyebrow="Panel del club"
        title={store.club?.name}
        subtitle="Resumen operativo del club"
        avatar={store.club?.image_url}
        fallback={store.club?.name}
        badge={
          subscriptionStatus ? (
            <span
              className={`status-badge ${clubStatus.className} dashboard-club-status`}
            >
              <span className="dashboard-club-status-dot" aria-hidden="true" />

              {clubStatus.label}
            </span>
          ) : null
        }
      />
      {store.nextMatch && (
        <Card className="dashboard-feature-card dashboard-feature-match">
          <p className="card-label">{getMatchCardLabel(store.nextMatch)}</p>

          <h3>
            {store.nextMatch.team_name} vs{" "}
            {store.nextMatch.opponent_name || "Scrimmage interno"}
          </h3>

          <p>
            {store.nextMatch.date}
            {store.nextMatch.location ? ` · ${store.nextMatch.location}` : ""}
          </p>

          <span className="dashboard-match-status">
            {getMatchStatusText(store.nextMatch)}
          </span>

          <Button onClick={() => navigate(`/matches/${store.nextMatch.id}`)}>
            {getMatchButtonText(store.nextMatch)}
          </Button>
        </Card>
      )}
      {!store.nextMatch && (
        <Card className="dashboard-feature-card">
          <h3>{cta.title}</h3>
          <p>{cta.message}</p>

          <Button onClick={handleCTAAction}>{cta.buttonText}</Button>
        </Card>
      )}

      <div className="dashboard-grid">
        <Card className="dashboard-metric-card">
          <div className="dashboard-metric-header">
            <div className="dashboard-metric-title">
              <span className="dashboard-metric-icon">
                <MetricIcon type="teams" />
              </span>

              <span>Equipos</span>
            </div>

            <span
              className={`dashboard-metric-badge ${
                teamsThisWeek === 0 ? "dashboard-metric-badge-muted" : ""
              }`}
            >
              {teamsThisWeek > 0 ? `↗ +${teamsThisWeek}` : "+0"}
            </span>
          </div>

          <div className="dashboard-metric-main">
            <div className="dashboard-metric-value">
              <strong>{stats.total_teams}</strong>
              <span>equipos creados</span>
            </div>

            <MiniTrend values={teamsWeeklyTrend} tone="primary" />
          </div>
        </Card>

        <Card className="dashboard-metric-card">
          <div className="dashboard-metric-header">
            <div className="dashboard-metric-title">
              <span className="dashboard-metric-icon">
                <MetricIcon type="players" />
              </span>

              <span>Jugadores</span>
            </div>

            <span
              className={`dashboard-metric-badge ${
                playersThisWeek === 0 ? "dashboard-metric-badge-muted" : ""
              }`}
            >
              {playersThisWeek > 0 ? `↗ +${playersThisWeek}` : "+0"}
            </span>
          </div>

          <div className="dashboard-metric-main">
            <div className="dashboard-metric-value">
              <strong>{stats.total_players}</strong>
              <span>registrados en el club</span>
            </div>

            <MiniTrend values={playersWeeklyTrend} tone="primary" />
          </div>
        </Card>

        <Card className="dashboard-metric-card dashboard-metric-card-success">
          <div className="dashboard-metric-header">
            <div className="dashboard-metric-title">
              <span className="dashboard-metric-icon">
                <MetricIcon type="active" />
              </span>

              <span>Jugadores activos</span>
            </div>

            <span className="dashboard-metric-badge dashboard-metric-badge-success">
              {activePlayersPercentage}% del club
            </span>
          </div>

          <div className="dashboard-metric-main dashboard-metric-main-active">
            <div className="dashboard-metric-value">
              <strong>{stats.active_players}</strong>
              <span>disponibles actualmente</span>
            </div>

            <div
              className="dashboard-active-indicator"
              aria-label={`${activePlayersPercentage}% de jugadores activos`}
            >
              <div className="dashboard-active-indicator-track">
                <span
                  className="dashboard-active-indicator-value"
                  style={{
                    width: `${activePlayersPercentage}%`,
                  }}
                />
              </div>

              <small>
                {stats.active_players} de {stats.total_players}
              </small>
            </div>
          </div>
        </Card>
      </div>
    </>
  );
};
