import React, {
  useEffect,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Link,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import { Context } from "../../store/appContext";

import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { Select } from "../../component/ui/select";
import { CalendarCheck } from "lucide-react";
import { ReadOnlyBadge } from "../../component/ui/readOnlyNotice";
import { canManage, isScopedCoach } from "../../utils/coachAccess";
import { getTrainingStatus } from "../../utils/trainingStatus";
import {
  formatDateOnly,
  getLocalDateOnlyValue,
} from "../../utils/dateOnly";
import { errorMessages } from "../../utils/errorMessages";
import {
  SeasonSelector,
  useSeasonSelection,
} from "../../component/seasonSelector";

import "../../../styles/trainings.css";

const formatDate = (date) => formatDateOnly(date, {
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

const sortAscending = (first, second) =>
  `${first.date} ${first.start_time || ""}`.localeCompare(
    `${second.date} ${second.start_time || ""}`,
  );

const sortDescending = (first, second) => sortAscending(second, first);

const TrainingCard = ({ training, from }) => {
  const trainingStatus = getTrainingStatus(training.status);
  const progressLabel = training.roster_count === 0
    ? "Sin participantes"
    : training.attendance_complete
    ? "Asistencia completa"
    : `${training.attendance_count || 0} de ${training.roster_count} registrados`;

  return (
    <Link
      className="training-card-link"
      to={`/trainings/${training.id}${from.search}`}
      state={{ from: `${from.pathname}${from.search}` }}
    >
      <Card className="training-card">
        <div className="training-card-content">
          <div className="training-card-main">
            <div className="training-card-heading">
              <span className="training-card-label">
                {training.team_name}
              </span>
              {training.category_name && (
                <span className="training-card-category">
                  {training.category_name}
                </span>
              )}
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
              {progressLabel}
            </p>
          </div>

          <span className="training-card-arrow" aria-hidden="true">→</span>
        </div>
      </Card>
    </Link>
  );
};

const TrainingGroup = ({ title, sectionId, subtitle, trainings, location }) => {
  if (trainings.length === 0) return null;

  return (
    <section className="training-group" aria-labelledby={sectionId}>
      <div className="section-header">
        <h2 id={sectionId}>{title}</h2>
        {subtitle && <p>{subtitle}</p>}
      </div>
      <div className="trainings-list">
        {trainings.map((training) => (
          <TrainingCard
            key={training.id}
            training={training}
            from={location}
          />
        ))}
      </div>
    </section>
  );
};

export const Trainings = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [trainings, setTrainings] = useState([]);
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState(null);
  const loadRequestId = useRef(0);
  const {
    loadingSeasons,
    reloadSeasons,
    seasonError,
    seasonId,
    seasons,
    selectedSeason,
    selectSeason,
  } = useSeasonSelection();
  const teamFilter = searchParams.get("team") || "all";
  const statusFilter = searchParams.get("status") || (
    searchParams.get("pending") === "1" ? "pending" : "all"
  );
  const readOnlySeason = selectedSeason?.status !== "active";
  const scopedCoach = isScopedCoach(store);
  const canCreateTraining = Boolean(
    selectedSeason?.status === "active" &&
    (!scopedCoach || teams.some((team) => canManage(team))),
  );

  const loadTrainings = async () => {
    const requestId = loadRequestId.current + 1;
    loadRequestId.current = requestId;

    if (loadingSeasons) return;

    if (seasonError) {
      setTrainings([]);
      setTeams([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    setListError(null);
    setTrainings([]);
    setTeams([]);

    if (!selectedSeason) {
      setListError({ code: "ACTIVE_SEASON_REQUIRED" });
      setLoading(false);
      return;
    }

    const [trainingResult, teamResult] = await Promise.all([
      actions.getAllTrainings({ seasonId }),
      actions.getTeams({ seasonId }),
    ]);

    if (requestId !== loadRequestId.current) return;

    if (!trainingResult.ok) {
      setListError(trainingResult);
      setLoading(false);
      return;
    }

    setTrainings(trainingResult.data.trainings || []);
    setTeams(teamResult.ok ? teamResult.data.teams || [] : []);
    setLoading(false);
  };

  useEffect(() => {
    loadTrainings();
    return () => {
      loadRequestId.current += 1;
    };
  }, [loadingSeasons, seasonError, seasonId, selectedSeason?.id]);

  const setFilter = (key, value) => {
    const next = new URLSearchParams(searchParams);
    next.delete("pending");

    if (!value || value === "all") next.delete(key);
    else next.set(key, value);

    setSearchParams(next, { replace: true });
  };

  const filteredTrainings = useMemo(() => {
    const today = getLocalDateOnlyValue();

    return trainings.filter((training) => {
      if (teamFilter !== "all" && training.team_id !== teamFilter) {
        return false;
      }

      if (statusFilter === "pending") {
        return (
          training.status === "scheduled" &&
          training.date <= today &&
          !training.attendance_complete
        );
      }

      return statusFilter === "all" || training.status === statusFilter;
    });
  }, [statusFilter, teamFilter, trainings]);

  const groups = useMemo(() => {
    const today = getLocalDateOnlyValue();
    const scheduled = filteredTrainings.filter(
      (training) => training.status === "scheduled",
    );

    return {
      today: scheduled.filter((training) => training.date === today)
        .sort(sortAscending),
      pending: scheduled.filter((training) => training.date < today)
        .sort(sortDescending),
      upcoming: scheduled.filter((training) => training.date > today)
        .sort(sortAscending),
      historical: filteredTrainings.filter(
        (training) => ["completed", "cancelled"].includes(training.status),
      ).sort(sortDescending),
    };
  }, [filteredTrainings]);

  const teamOptions = useMemo(() => {
    const byId = new Map();

    [...teams, ...trainings].forEach((item) => {
      const id = item.id && !item.team_id ? item.id : item.team_id;
      const name = item.name || item.team_name;
      if (id && name) byId.set(id, name);
    });

    return [...byId.entries()].sort((first, second) =>
      first[1].localeCompare(second[1]),
    );
  }, [teams, trainings]);

  if (loading || loadingSeasons) {
    return <p role="status">Cargando entrenamientos...</p>;
  }

  const hasVisibleTrainings = filteredTrainings.length > 0;
  const isOwner = store.user?.role === "club_owner";
  const errorCode = seasonError || listError?.code;

  return (
    <div className="trainings-page">
      <PageHeader
        tone="trainings"
        icon={CalendarCheck}
        eyebrow="Gestión deportiva"
        title="Entrenamientos"
        subtitle="Prepara sesiones, registra asistencia y conserva su historial."
        actions={canCreateTraining && (
          <Button onClick={() => navigate("/trainings/new")}>
            + Crear entrenamiento
          </Button>
        )}
      />

      <SeasonSelector
        loading={loadingSeasons}
        onChange={selectSeason}
        seasons={seasons}
        selectedSeason={selectedSeason}
        error={seasonError}
        onRetry={reloadSeasons}
      />

      {errorCode && (
        <Card className="page-error-state" role="alert">
          <h2>
            {errorCode === "ACTIVE_SEASON_REQUIRED"
              ? "No hay una temporada activa"
              : "No pudimos cargar los entrenamientos"}
          </h2>
          <p>
            {errorCode === "ACTIVE_SEASON_REQUIRED"
              ? isOwner
                ? "Activa una temporada para comenzar a operar entrenamientos."
                : "El administrador del club debe activar una temporada para habilitar los entrenamientos."
              : errorMessages[errorCode] || listError?.message || "Ocurrió un error temporal."}
          </p>
          <div className="training-error-actions">
            {errorCode === "ACTIVE_SEASON_REQUIRED" && isOwner && (
              <Link className="button button-primary" to="/seasons">
                Gestionar temporadas
              </Link>
            )}
            {errorCode !== "ACTIVE_SEASON_REQUIRED" && (
              <Button type="button" onClick={loadTrainings}>
                Volver a intentar
              </Button>
            )}
          </div>
        </Card>
      )}

      {!errorCode && selectedSeason?.status === "planned" && (
        <Card className="training-lifecycle-notice" role="note">
          <p>
            Los entrenamientos estarán disponibles cuando esta temporada esté activa.
          </p>
          {isOwner && <Link to="/seasons">Gestionar temporadas</Link>}
        </Card>
      )}

      {!errorCode && trainings.length > 0 && (
        <Card className="training-filters" aria-label="Filtros de entrenamientos">
          <div className="training-filter-field">
            <label htmlFor="training-team-filter">Equipo</label>
            <Select
              id="training-team-filter"
              value={teamFilter}
              onChange={(event) => setFilter("team", event.target.value)}
            >
              <option value="all">Todos los equipos</option>
              {teamOptions.map(([id, name]) => (
                <option key={id} value={id}>{name}</option>
              ))}
            </Select>
          </div>
          <div className="training-filter-field">
            <label htmlFor="training-status-filter">Estado</label>
            <Select
              id="training-status-filter"
              value={statusFilter}
              onChange={(event) => setFilter("status", event.target.value)}
            >
              <option value="all">Todos los estados</option>
              <option value="pending">Asistencia pendiente</option>
              <option value="scheduled">Programados</option>
              <option value="completed">Completados</option>
              <option value="cancelled">Cancelados</option>
            </Select>
          </div>
        </Card>
      )}

      {!errorCode && !hasVisibleTrainings && (
        <Card>
          <div className="empty-state">
            <CalendarCheck size={30} aria-hidden="true" />
            <h2>
              {trainings.length > 0
                ? "No hay entrenamientos con estos filtros"
                : readOnlySeason
                ? "No hay datos en esta temporada"
                : "No hay entrenamientos aún"}
            </h2>
            <p>
              {selectedSeason?.status === "planned"
                ? "Podrás crear entrenamientos cuando la temporada esté activa."
                : selectedSeason?.status === "closed"
                ? "No hay entrenamientos registrados en esta temporada cerrada."
                : trainings.length > 0
                ? "Prueba con otro equipo o estado."
                : canCreateTraining
                ? "Crea tu primer entrenamiento para empezar a registrar asistencia."
                : "Los entrenamientos del club aparecerán aquí cuando se registren."}
            </p>
          </div>
        </Card>
      )}

      {!errorCode && hasVisibleTrainings && (
        <div className="training-groups">
          <TrainingGroup
            title="Hoy"
            sectionId="training-group-today"
            subtitle="Sesiones programadas para hoy."
            trainings={groups.today}
            location={location}
          />
          <TrainingGroup
            title="Pasados pendientes"
            sectionId="training-group-pending"
            subtitle="Sesiones programadas que todavía requieren cierre."
            trainings={groups.pending}
            location={location}
          />
          <TrainingGroup
            title="Próximos"
            sectionId="training-group-upcoming"
            subtitle="Sesiones futuras en orden cronológico."
            trainings={groups.upcoming}
            location={location}
          />
          <TrainingGroup
            title="Históricos"
            sectionId="training-group-history"
            subtitle="Entrenamientos completados o cancelados."
            trainings={groups.historical}
            location={location}
          />
        </div>
      )}
    </div>
  );
};
