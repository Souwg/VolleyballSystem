import React, { useEffect, useContext, useRef, useState } from "react";
import { Link, useLocation, useParams, useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";

import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { ReadOnlyBadge } from "../../component/ui/readOnlyNotice";
import { canManage, isTeamOperational } from "../../utils/coachAccess";
import { getTrainingStatus } from "../../utils/trainingStatus";
import { formatDateOnly } from "../../utils/dateOnly";
import { errorMessages } from "../../utils/errorMessages";
import "../../../styles/trainings.css";

const formatDate = (date) => formatDateOnly(date, {
  day: "2-digit",
  month: "long",
  year: "numeric",
});

const formatTime = (time) => time ? time.slice(0, 5) : "Sin horario";

export const TeamTrainings = () => {
  const { actions } = useContext(Context);
  const { team_id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [team, setTeam] = useState(null);
  const [trainings, setTrainings] = useState([]);
  const [error, setError] = useState(null);
  const loadRequestId = useRef(0);

  const loadTrainings = async () => {
    const requestId = loadRequestId.current + 1;
    loadRequestId.current = requestId;
    setLoading(true);
    setError(null);
    setTeam(null);
    setTrainings([]);

    const [trainingResult, teamResult] = await Promise.all([
      actions.getTeamTrainings(team_id),
      actions.getTeamDetail(team_id),
    ]);

    if (requestId !== loadRequestId.current) return;

    if (!trainingResult.ok || !teamResult.ok) {
      setError(!teamResult.ok ? teamResult : trainingResult);
      setLoading(false);
      return;
    }

    setTrainings(trainingResult.data.trainings || []);
    setTeam(teamResult.data.team);
    setLoading(false);
  };

  useEffect(() => {
    loadTrainings();
    return () => {
      loadRequestId.current += 1;
    };
  }, [team_id]);

  if (loading) {
    return <p role="status">Cargando entrenamientos...</p>;
  }

  if (error) {
    return (
      <Card className="page-error-state" role="alert">
        <h2>No pudimos cargar los entrenamientos</h2>
        <p>{errorMessages[error.code] || error.message || "Ocurrió un error temporal."}</p>
        <Button type="button" onClick={loadTrainings}>Volver a intentar</Button>
      </Card>
    );
  }

  const canCreateTraining = canManage(team) && isTeamOperational(team);
  const categoryName = team?.category?.name || "Sin categoría";
  const seasonName = team?.season?.name || "Sin temporada";

  return (
    <div className="team-trainings-page">
      <PageHeader
        variant="detail"
        eyebrow={categoryName}
        title={`Entrenamientos · ${team?.name || "Equipo"}`}
        subtitle={`${seasonName} · Consulta y prepara las sesiones de este equipo.`}
        onBack={() => navigate(`/teams/${team_id}${location.search}`)}
        actions={canCreateTraining && (
          <Button
            onClick={() => navigate(
              `/teams/${team_id}/trainings/new${location.search}`,
              { state: { from: `${location.pathname}${location.search}` } },
            )}
          >
            + Crear entrenamiento
          </Button>
        )}
      />

      {trainings.length === 0 ? (
        <Card>
          <div className="empty-state">
            <h2>No hay entrenamientos aún</h2>
            <p>
              {canCreateTraining
                ? "Cuando crees una sesión, aparecerá aquí el historial de este equipo."
                : "Este equipo no tiene sesiones registradas."}
            </p>
          </div>
        </Card>
      ) : (
        <div className="trainings-list">
          {trainings.map((training) => {
            const trainingStatus = getTrainingStatus(training.status);
            const progress = training.roster_count === 0
              ? "Sin participantes"
              : training.attendance_complete
              ? "Asistencia completa"
              : `${training.attendance_count || 0} de ${training.roster_count} registrados`;

            return (
              <Link
                key={training.id}
                className="training-card-link"
                to={`/trainings/${training.id}${location.search}`}
                state={{ from: `${location.pathname}${location.search}` }}
              >
                <Card className="training-card">
                  <div className="training-card-content">
                    <div className="training-card-main">
                      <div className="training-card-heading">
                        <span className={`status-badge ${trainingStatus.className}`}>
                          {trainingStatus.label}
                        </span>
                        {!canManage(training) && <ReadOnlyBadge />}
                      </div>
                      <h3>{formatDate(training.date)}</h3>
                      <p className="training-card-time">
                        {formatTime(training.start_time)} – {formatTime(training.end_time)}
                      </p>
                      <p>{training.location || "Sin ubicación"}</p>
                      <p className={`training-card-progress ${
                        training.attendance_complete ? "is-complete" : ""
                      }`}>
                        {progress}
                      </p>
                    </div>
                    <span className="training-card-arrow" aria-hidden="true">→</span>
                  </div>
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
};
