import React, { useEffect, useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";

import { Container } from "../../component/ui/container";
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

  useEffect(() => {
    loadTrainings();
  }, []);

  if (loading) {
    return (
      <Container>
        <p>Cargando entrenamientos...</p>
      </Container>
    );
  }
  return (
    <>
      <PageHeader
        title="Entrenamientos"
        subtitle="Gestiona todos los entrenamientos del club"
        actions={
          <Button
            className="button-primary"
            onClick={() => navigate("/trainings/new")}
          >
            + Crear entrenamiento
          </Button>
        }
      />

      {store.trainings.length === 0 ? (
        <Card>
          <h4>No hay entrenamientos aún</h4>
          <p>Crea tu primer entrenamiento para empezar</p>

          <Button
            className="button-primary"
            onClick={() => navigate("/trainings/new")}
          >
            Crear entrenamiento
          </Button>
        </Card>
      ) : (
        <Card>
          <h4>Entrenamientos del club</h4>
          <p>Lista global de entrenamientos</p>

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
                  onClick={() => navigate(`/trainings/${training.id}`)}
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
