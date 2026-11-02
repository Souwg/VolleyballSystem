import React, { useEffect, useContext } from "react";
import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";

import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { ReadOnlyBadge } from "../../component/ui/readOnlyNotice";
import { canManage, isTeamOperational } from "../../utils/coachAccess";
import { getTrainingStatus } from "../../utils/trainingStatus";
import "../../../styles/trainings.css";

const formatDate = (date) => {
  return new Date(date).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
};

export const TeamTrainings = () => {
  const { store, actions } = useContext(Context);
  const { team_id } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [team, setTeam] = useState(null);

  const loadTrainings = async () => {
    setLoading(true);

    const [, teamResult] = await Promise.all([
      actions.getTeamTrainings(team_id),
      actions.getTeamDetail(team_id),
    ]);

    setTeam(teamResult.ok ? teamResult.data.team : null);
    setLoading(false);
  };

  useEffect(() => {
    loadTrainings();
  }, [team_id]);

  const handleCreateTraining = () => {
    navigate(`/teams/${team_id}/trainings/new`);
  };

  const handleOpenTraining = (trainingId) => {
    navigate(`/trainings/${trainingId}`);
  };

  if (loading) {
    return <p>Cargando entrenamientos...</p>;
  }

  const canCreateTraining = canManage(team) && isTeamOperational(team);

  return (
    <div className="team-trainings-page">
      <PageHeader
        variant="detail"
        eyebrow="Categoría"
        title="Entrenamientos"
        subtitle="Consulta y crea sesiones para esta categoría."
        onBack={() => navigate(`/teams/${team_id}`)}
        actions={
          canCreateTraining && (
            <Button onClick={handleCreateTraining}>+ Crear entrenamiento</Button>
          )
        }
      />

      {store.trainings.length === 0 ? (
        <Card>
          <div className="empty-state">
            <h4>No hay entrenamientos aún</h4>
            <p>
              {canCreateTraining
                ? "Cuando crees una sesión, aparecerá aquí el historial de entrenamientos de esta categoría."
                : "Esta categoría no tiene sesiones registradas."}
            </p>
          </div>
        </Card>
      ) : (
        <Card>
          <div className="section-header">
            <h4>Entrenamientos de la categoría</h4>
            <p>Sesiones registradas para este equipo.</p>
          </div>

          <div className="trainings-list">
            {store.trainings.map((training) => {
              const trainingStatus = getTrainingStatus(training.status);

              return (
                <Card
                  key={training.id}
                  className="training-card card-interactive"
                  onClick={() => handleOpenTraining(training.id)}
                >
                  <div className="training-card-content">
                    <div className="training-card-main">
                      <div className="training-card-heading">
                        <span className="training-card-label">Sesión</span>
                        <span
                          className={`status-badge ${trainingStatus.className}`}
                        >
                          {trainingStatus.label}
                        </span>
                        {!canManage(training) && <ReadOnlyBadge />}
                      </div>

                      <h3>{formatDate(training.date)}</h3>

                      <p>{training.location || "Sin ubicación"}</p>
                    </div>

                    <span className="training-card-arrow">→</span>
                  </div>
                </Card>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
};
