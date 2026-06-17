import React, { useEffect, useContext } from "react";
import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";

import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
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

  const loadTrainings = async () => {
    setLoading(true);
    await actions.getTeamTrainings(team_id);
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

  return (
    <div className="team-trainings-page">
      <PageHeader
        variant="detail"
        eyebrow="Categoría"
        title="Entrenamientos"
        subtitle="Consulta y crea sesiones para esta categoría."
        onBack={() => navigate(`/teams/${team_id}`)}
        actions={
          <Button onClick={handleCreateTraining}>+ Crear entrenamiento</Button>
        }
      />

      {store.trainings.length === 0 ? (
        <Card>
          <div className="empty-state">
            <h4>No hay entrenamientos aún</h4>
            <p>
              Cuando crees una sesión, aparecerá aquí el historial de
              entrenamientos de esta categoría.
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
            {store.trainings.map((training) => (
              <Card
                key={training.id}
                className="training-card card-interactive"
                onClick={() => handleOpenTraining(training.id)}
              >
                <div className="training-card-content">
                  <div className="training-card-main">
                    <span className="training-card-label">Sesión</span>

                    <h3>{formatDate(training.date)}</h3>

                    <p>{training.location || "Sin ubicación"}</p>
                  </div>

                  <span className="training-card-arrow">→</span>
                </div>
              </Card>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};
