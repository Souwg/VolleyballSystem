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

  useEffect(() => {
    if (!store.token) return;
    actions.getDashboard();
  }, [store.token]);

  if (!store.dashboardStats) {
    return <p>Loading dashboard...</p>;
  }

  let ctaTitle = "";
  let ctaMessage = "";
  let ctaAction = null;

  // 🧠 UX FLOW REAL

  if (stats.total_teams === 0) {
    ctaTitle = "Crea tu primer equipo 🏐";
    ctaMessage = "Los equipos son la base de tu club";
    ctaAction = "go_to_teams";
  } else if (stats.total_players === 0) {
    ctaTitle = "Añade tu primer jugador 👤";
    ctaMessage = "Empieza a construir tu equipo";
    ctaAction = "go_to_players";
  } else if (stats.total_trainings === 0) {
    ctaTitle = "Crea tu primer entrenamiento 🏐";
    ctaMessage = "Organiza sesiones para tu equipo";
    ctaAction = "create_training";
  } else {
    ctaTitle = "Gestiona tus entrenamientos 📅";
    ctaMessage = "Consulta sesiones o registra asistencia";
    ctaAction = "go_to_trainings";
  }
  return (
    <>
      <PageHeader
        title={`Hola, ${store.club?.name} 👋`}
        subtitle="Aquí puedes ver el resumen de tu club"
      />
      <Card className="dashboard-cta">
        <h3>{ctaTitle}</h3>
        <p>{ctaMessage}</p>

        {ctaAction === "go_to_teams" && (
          <Button onClick={() => navigate("/teams")}>Crear equipo</Button>
        )}

        {ctaAction === "go_to_players" && (
          <Button onClick={() => navigate("/players")}>Añadir jugador</Button>
        )}

        {ctaAction === "go_to_trainings" && (
          <Button onClick={() => navigate("/trainings")}>
            Ver entrenamientos
          </Button>
        )}
        {ctaAction === "create_training" && (
          <Button onClick={() => navigate("/trainings")}>
            Crear entrenamiento
          </Button>
        )}
      </Card>
      <div className="dashboard-grid">
        <Card>
          <p className="card-label">Equipos</p>
          <h2>{store.dashboardStats.total_teams}</h2>
        </Card>

        <Card>
          <p className="card-label">Jugadores</p>
          <h2>{store.dashboardStats.total_players}</h2>
        </Card>

        <Card>
          <p className="card-label"> Jugadores Activos</p>
          <h2>{store.dashboardStats.active_players}</h2>
        </Card>
      </div>

      <Card className="dashboard-shortcuts">
        <h4>Accesos rápidos</h4>

        <div className="dashboard-actions">
          <Button onClick={() => navigate("/teams")}>Ver equipos</Button>

          <Button variant="secondary" onClick={() => navigate("/players")}>
            Ver jugadores
          </Button>

          <Button variant="secondary" onClick={() => navigate("/trainings")}>
            Ver entrenamientos
          </Button>
        </div>
      </Card>
    </>
  );
};
