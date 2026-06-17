import React, { useEffect, useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";

import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { CalendarCheck } from "lucide-react";

import "../../../styles/trainings.css";

const formatDate = (date) =>
  new Date(date).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });

export const Trainings = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);

  const loadTrainings = async () => {
    setLoading(true);
    await actions.getAllTrainings();
    setLoading(false);
  };

  const handleCreateTraining = () => {
    navigate("/trainings/new");
  };

  const handleOpenTraining = (trainingId) => {
    navigate(`/trainings/${trainingId}`);
  };

  useEffect(() => {
    loadTrainings();
  }, []);

  if (loading) {
    return <p>Cargando entrenamientos...</p>;
  }
  return (
    <div className="trainings-page">
      <PageHeader
        tone="trainings"
        icon={CalendarCheck}
        eyebrow="Gestión deportiva"
        title="Entrenamientos"
        subtitle="Consulta y registra las sesiones de entrenamiento de tus equipos."
        actions={
          <Button onClick={handleCreateTraining}>+ Crear entrenamiento</Button>
        }
      />

      {store.trainings.length === 0 ? (
        <Card>
          <div className="empty-state">
            <h4>No hay entrenamientos aún</h4>
            <p>
              Crea tu primer entrenamiento para empezar a registrar asistencia.
            </p>
          </div>
        </Card>
      ) : (
        <Card>
          <div className="section-header">
            <h4>Entrenamientos del club</h4>
            <p>Historial de sesiones registradas en el club.</p>
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
                    <span className="training-card-label">
                      {training.team_name}
                    </span>

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
