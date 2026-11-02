import React, { useEffect, useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";

import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { CalendarCheck } from "lucide-react";
import { ReadOnlyBadge } from "../../component/ui/readOnlyNotice";
import {
  canManage,
  getManageableTeams,
  isScopedCoach,
} from "../../utils/coachAccess";
import { getTrainingStatus } from "../../utils/trainingStatus";
import {
  SeasonSelector,
  useSeasonSelection,
} from "../../component/seasonSelector";

import "../../../styles/trainings.css";

const formatDate = (date) =>
  new Date(date).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });

const formatTime = (time) => {
  if (!time) return "Sin horario";

  const [hours, minutes] = time.slice(0, 5).split(":");

  return new Date(
    2000,
    0,
    1,
    Number(hours),
    Number(minutes),
  ).toLocaleTimeString("es-ES", {
    hour: "numeric",
    minute: "2-digit",
  });
};

export const Trainings = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const {
    loadingSeasons,
    seasonId,
    seasons,
    selectedSeason,
    selectSeason,
  } = useSeasonSelection();
  const readOnlySeason = selectedSeason?.status !== "active";
  const scopedCoach = isScopedCoach(store);
  const canCreateTraining =
    !readOnlySeason &&
    (!scopedCoach || getManageableTeams(store.teams).length > 0);

  const loadTrainings = async () => {
    setLoading(true);
    await Promise.all([
      actions.getAllTrainings({ seasonId }),
      scopedCoach ? actions.getTeams() : null,
    ]);
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
  }, [seasonId]);

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
          canCreateTraining && (
            <Button onClick={handleCreateTraining}>+ Crear entrenamiento</Button>
          )
        }
      />
      <SeasonSelector
        loading={loadingSeasons}
        onChange={selectSeason}
        seasons={seasons}
        selectedSeason={selectedSeason}
      />

      {store.trainings.length === 0 ? (
        <Card>
          <div className="empty-state">
            <CalendarCheck size={30} />
            <h4>No hay datos en esta temporada</h4>
            <p>
              {readOnlySeason
                ? "No hay entrenamientos registrados en la temporada seleccionada."
                : canCreateTraining
                ? "Crea tu primer entrenamiento para empezar a registrar asistencia."
                : "Los entrenamientos del club aparecerán aquí cuando se registren."}
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
                        <span className="training-card-label">
                          {training.team_name}
                        </span>
                        <span
                          className={`status-badge ${trainingStatus.className}`}
                        >
                          {trainingStatus.label}
                        </span>
                        {!canManage(training) && <ReadOnlyBadge />}
                      </div>

                      <h3>{formatDate(training.date)}</h3>

                      {training.start_time && training.end_time && (
                        <p className="training-card-time">
                          {formatTime(training.start_time)} –{" "}
                          {formatTime(training.end_time)}
                        </p>
                      )}

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
