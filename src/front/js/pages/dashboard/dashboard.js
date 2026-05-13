import React, { useEffect, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import "../../../styles/dashboard.css";

export const Dashboard = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();
  const stats = store.dashboardStats;

  const getDashboardCTA = () => {
    if (stats.total_teams === 0) {
      return {
        title: "Crea tu primera categoría",
        message:
          "Organiza tu club por categorías para gestionar jugadoras, entrenamientos y partidos.",
        action: "go_to_teams",
        buttonText: "Crear categoría",
      };
    }

    if (stats.total_players === 0) {
      return {
        title: "Añade tu primer jugador",
        message:
          "Empieza a construir el roster de tu club y mantén la información centralizada.",
        action: "go_to_players",
        buttonText: "Añadir jugador",
      };
    }

    if (stats.total_trainings === 0) {
      return {
        title: "Crea tu primer entrenamiento",
        message:
          "Organiza sesiones, controla asistencia y empieza a medir el progreso del equipo.",
        action: "create_training",
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
      go_to_teams: "/teams",
      go_to_players: "/players",
      create_training: "/trainings",
      go_to_trainings: "/trainings",
    };

    navigate(routes[cta.action]);
  };

  const goToTeams = () => navigate("/teams");
  const goToPlayers = () => navigate("/players");
  const goToTrainings = () => navigate("/trainings");

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
        title={<>{store.club?.name}</>}
        subtitle="Resumen operativo del club"
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
        <Card className="metric-card">
          <p className="card-label">Equipos</p>

          <div className="metric-content">
            <h2>{stats.total_teams}</h2>
            <span>categorías creadas</span>
          </div>
        </Card>

        <Card className="metric-card">
          <p className="card-label">Jugadores</p>

          <div className="metric-content">
            <h2>{stats.total_players}</h2>
            <span>registrados en el club</span>
          </div>
        </Card>

        <Card className="metric-card metric-success">
          <p className="card-label">Jugadores activos</p>

          <div className="metric-content">
            <h2>{stats.active_players}</h2>
            <span>disponibles actualmente</span>
          </div>
        </Card>
      </div>

      <Card className="dashboard-shortcuts">
        <h4>Accesos rápidos</h4>

        <div className="dashboard-actions">
          <Button onClick={goToTeams}>Ver equipos</Button>

          <Button variant="secondary" onClick={goToPlayers}>
            Ver jugadores
          </Button>

          <Button variant="secondary" onClick={goToTrainings}>
            Ver entrenamientos
          </Button>
        </div>
      </Card>
    </>
  );
};
