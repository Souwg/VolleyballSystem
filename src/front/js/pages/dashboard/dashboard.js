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
        title: "Crea tu primer equipo 🏐",
        message: "Los equipos son la base de tu club",
        action: "go_to_teams",
        buttonText: "Crear equipo",
      };
    }

    if (stats.total_players === 0) {
      return {
        title: "Añade tu primer jugador 👤",
        message: "Empieza a construir tu equipo",
        action: "go_to_players",
        buttonText: "Añadir jugador",
      };
    }

    if (stats.total_trainings === 0) {
      return {
        title: "Crea tu primer entrenamiento 🏐",
        message: "Organiza sesiones para tu equipo",
        action: "create_training",
        buttonText: "Crear entrenamiento",
      };
    }

    return {
      title: "Gestiona tus entrenamientos 📅",
      message: "Consulta sesiones o registra asistencia",
      action: "go_to_trainings",
      buttonText: "Ver entrenamientos",
    };
  };

  useEffect(() => {
    if (!store.token) return;
    actions.getDashboard();
  }, [store.token]);

  if (!store.dashboardStats) {
    return <p>Loading dashboard...</p>;
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

  return (
    <>
      <PageHeader
        title={`Hola, ${store.club?.name} 👋`}
        subtitle="Aquí puedes ver el resumen de tu club"
      />
      <Card className="dashboard-cta">
        <h3>{cta.title}</h3>
        <p>{cta.message}</p>

        <Button onClick={handleCTAAction}>{cta.buttonText}</Button>
      </Card>
      <div className="dashboard-grid">
        <Card>
          <p className="card-label">Equipos</p>
          <h2>{stats.total_teams}</h2>
        </Card>

        <Card>
          <p className="card-label">Jugadores</p>
          <h2>{stats.total_players}</h2>
        </Card>

        <Card>
          <p className="card-label"> Jugadores Activos</p>
          <h2>{stats.active_players}</h2>
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
