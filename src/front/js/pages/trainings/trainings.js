import React, { useEffect, useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";

import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";

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
    <>
      <PageHeader
        eyebrow="Gestión deportiva"
        title="Entrenamientos"
        subtitle="Organiza sesiones, consulta el historial y registra la asistencia del club."
        actions={
          <Button onClick={handleCreateTraining}>+ Crear entrenamiento</Button>
        }
      />
      {store.trainings.length === 0 ? (
        <Card>
          <h4>No hay entrenamientos aún</h4>
          <p>Crea tu primer entrenamiento para empezar</p>
        </Card>
      ) : (
        <Card>
          <h4>Entrenamientos del club</h4>
          <p>Historial de sesiones registradas en el club.</p>

          <table>
            <thead>
              <tr>
                <th>Equipo</th>
                <th>Fecha</th>
                <th>Ubicación</th>
              </tr>
            </thead>

            <tbody>
              {store.trainings.map((training) => (
                <tr
                  key={training.id}
                  onClick={() => handleOpenTraining(training.id)}
                  style={{ cursor: "pointer" }}
                >
                  <td>{training.team_name}</td>
                  <td>{formatDate(training.date)}</td>
                  <td>{training.location || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
};
