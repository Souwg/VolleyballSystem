import React, { useEffect, useContext } from "react";
import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";

import { Container } from "../../component/ui/container";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";

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

  useEffect(() => {
    loadTrainings();
  }, [team_id]);

  const loadTrainings = async () => {
    setLoading(true);
    await actions.getTeamTrainings(team_id);
    setLoading(false);
  };
  if (loading) {
    return (
      <Container>
        <p>Cargando entrenamientos...</p>
      </Container>
    );
  }
  return (
    <Container>
      <PageHeader
        title="Entrenamientos del equipo"
        subtitle="Gestiona y crea entrenamientos para este equipo"
        actions={
          <Button
            className="button-primary"
            onClick={() => navigate(`/teams/${team_id}/trainings/new`)}
          >
            + Crear entrenamiento
          </Button>
        }
      />
      <Card>
        {store.trainings.length === 0 ? (
          <div className="empty-state">
            <h4>No hay entrenamientos aún</h4>
            <p>Crea el primer entrenamiento para este equipo</p>
            <Button
              className="button-primary"
              onClick={() => navigate(`/teams/${team_id}/trainings/new`)}
            >
              Crear entrenamiento
            </Button>
          </div>
        ) : (
          store.trainings.map((training) => (
            <Card
              key={training.id}
              className="training-card"
              onClick={() => navigate(`/trainings/${training.id}`)}
            >
              <p>{formatDate(training.date)}</p>
              <p>{training.location}</p>
            </Card>
          ))
        )}
      </Card>
    </Container>
  );
};
