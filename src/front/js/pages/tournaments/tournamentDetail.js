import React, { useContext, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
import { FormField } from "../../component/ui/formField";
import { Select } from "../../component/ui/select";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";
import { errorMessages } from "../../utils/errorMessages";
import { Trophy, Users, CalendarDays, DollarSign } from "lucide-react";

import "../../../styles/tournaments.css";

const formatDate = (dateValue) => {
  if (!dateValue) return "Sin fecha";

  return new Intl.DateTimeFormat("es", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${dateValue}T00:00:00Z`));
};

const getStatusData = (status) => {
  const statuses = {
    active: {
      label: "Activo",
      className: "status-success",
    },
    completed: {
      label: "Finalizado",
      className: "status-info",
    },
    cancelled: {
      label: "Cancelado",
      className: "status-danger",
    },
  };

  return (
    statuses[status] || {
      label: status || "Sin estado",
      className: "status-muted",
    }
  );
};

export const TournamentDetail = () => {
  const { store, actions } = useContext(Context);
  const { tournament_id } = useParams();
  const navigate = useNavigate();

  const [tournament, setTournament] = useState(null);
  const [tournamentTeams, setTournamentTeams] = useState([]);
  const [loadingTournament, setLoadingTournament] = useState(true);

  const [showAddTeamForm, setShowAddTeamForm] = useState(false);
  const [teamId, setTeamId] = useState("");
  const [registrationFee, setRegistrationFee] = useState("");
  const [errors, setErrors] = useState({});
  const [loadingSubmit, setLoadingSubmit] = useState(false);

  const loadTournamentDetail = async () => {
    setLoadingTournament(true);

    try {
      const result = await actions.getTournamentDetail(tournament_id);

      if (result.ok) {
        const loadedTournament = result.data.tournament;

        setTournament(loadedTournament);
        setTournamentTeams(loadedTournament?.teams || []);
        return;
      }

      setTournament(null);
      setTournamentTeams([]);
    } finally {
      setLoadingTournament(false);
    }
  };

  useEffect(() => {
    loadTournamentDetail();
  }, [tournament_id]);

  useEffect(() => {
    const loadTeams = async () => {
      if (!store.teams || store.teams.length === 0) {
        await actions.getTeams();
      }
    };

    loadTeams();
  }, []);

  const closeAddTeamForm = () => {
    setShowAddTeamForm(false);
    setTeamId("");
    setRegistrationFee("");
    setErrors({});
  };

  const clearError = (...codes) => {
    setErrors((previousErrors) => {
      const updatedErrors = { ...previousErrors };

      codes.forEach((code) => {
        updatedErrors[code] = false;
      });

      return updatedErrors;
    });
  };

  const handleAddTeam = async (event) => {
    event.preventDefault();

    if (loadingSubmit) return;

    setErrors({});

    const newErrors = {};

    if (!teamId) {
      newErrors.TEAM_ID_REQUIRED = true;
    }

    if (registrationFee !== "") {
      const parsedRegistrationFee = Number(registrationFee);

      if (Number.isNaN(parsedRegistrationFee) || parsedRegistrationFee < 0) {
        newErrors.INVALID_AMOUNT = true;
      }
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setLoadingSubmit(true);

    const result = await actions.addTeamToTournament(tournament_id, {
      team_id: teamId,
      registration_fee: registrationFee === "" ? 0 : registrationFee,
    });

    if (!result.ok) {
      setErrors({
        [result.code || "NETWORK_ERROR"]: true,
      });

      setLoadingSubmit(false);
      return;
    }

    await loadTournamentDetail();

    closeAddTeamForm();
    setLoadingSubmit(false);
  };

  const availableTeams = (store.teams || []).filter((team) => {
    const alreadyAdded = tournamentTeams.some(
      (entry) => entry.team_id === team.id,
    );

    return !alreadyAdded;
  });

  if (loadingTournament) {
    return <p>Cargando torneo...</p>;
  }

  if (!tournament) {
    return <p>Torneo no encontrado.</p>;
  }

  const statusData = getStatusData(tournament.status);
  const canAddTeam = tournament.status === "active";

  return (
    <div className="tournament-detail-page">
      <PageHeader
        variant="detail"
        eyebrow="Torneo"
        title={tournament.name}
        subtitle={`${tournamentTeams.length} ${
          tournamentTeams.length === 1 ? "equipo inscrito" : "equipos inscritos"
        } · ${formatDate(tournament.start_date)}${
          tournament.end_date ? ` — ${formatDate(tournament.end_date)}` : ""
        }`}
        onBack={() => navigate("/tournaments")}
        actions={
          !showAddTeamForm &&
          canAddTeam && (
            <Button
              onClick={() => {
                setShowAddTeamForm(true);
                setErrors({});
              }}
            >
              + Inscribir equipo
            </Button>
          )
        }
      />

      <Card className="tournament-mobile-summary-card">
        <div className="tournament-mobile-summary-row">
          <span>Estado</span>

          <span className={`status-badge ${statusData.className}`}>
            {statusData.label}
          </span>
        </div>

        <div className="tournament-mobile-summary-row">
          <span>Fechas</span>

          <strong>
            {formatDate(tournament.start_date)}
            {tournament.end_date ? ` — ${formatDate(tournament.end_date)}` : ""}
          </strong>
        </div>

        <div className="tournament-mobile-summary-row">
          <span>Arbitraje base</span>

          <strong>
            ${Number(tournament.default_referee_fee || 0).toFixed(2)} por
            partido
          </strong>
        </div>

        <div className="tournament-mobile-summary-row">
          <span>Organizador</span>

          <strong>{tournament.organizer_name || "No especificado"}</strong>
        </div>
      </Card>

      <div className="tournament-summary-grid tournament-summary-grid-desktop">
        <Card className="tournament-summary-card">
          <span className={`status-badge ${statusData.className}`}>
            {statusData.label}
          </span>

          <h4>Estado del torneo</h4>

          <p>{tournament.organizer_name || "Organizador no especificado"}</p>
        </Card>

        <Card className="tournament-summary-card">
          <div className="tournament-summary-icon">
            <CalendarDays size={18} />
          </div>

          <h4>Fechas</h4>

          <p>
            {formatDate(tournament.start_date)}
            {tournament.end_date ? ` — ${formatDate(tournament.end_date)}` : ""}
          </p>
        </Card>

        <Card className="tournament-summary-card">
          <div className="tournament-summary-icon">
            <DollarSign size={18} />
          </div>

          <h4>Arbitraje base</h4>

          <p>
            ${Number(tournament.default_referee_fee || 0).toFixed(2)} por
            partido
          </p>
        </Card>
      </div>

      {showAddTeamForm && (
        <Card className="tournament-form-card">
          <div className="tournament-section-heading">
            <div>
              <h4>Inscribir equipo</h4>
              <p>
                Selecciona un equipo del club y define el costo de inscripción
                total para este torneo.
              </p>
            </div>
          </div>

          <form onSubmit={handleAddTeam} className="form">
            <FormField
              label="Equipo"
              error={
                errors.TEAM_ID_REQUIRED
                  ? errorMessages.TEAM_ID_REQUIRED
                  : errors.TEAM_ALREADY_IN_TOURNAMENT
                  ? errorMessages.TEAM_ALREADY_IN_TOURNAMENT
                  : errors.TEAM_NOT_FOUND
                  ? errorMessages.TEAM_NOT_FOUND
                  : null
              }
            >
              <Select
                value={teamId}
                className={
                  errors.TEAM_ID_REQUIRED ||
                  errors.TEAM_ALREADY_IN_TOURNAMENT ||
                  errors.TEAM_NOT_FOUND
                    ? "input-error"
                    : ""
                }
                onChange={(event) => {
                  setTeamId(event.target.value);
                  clearError(
                    "TEAM_ID_REQUIRED",
                    "TEAM_ALREADY_IN_TOURNAMENT",
                    "TEAM_NOT_FOUND",
                  );
                }}
              >
                <option value="">Selecciona un equipo</option>

                {availableTeams.map((team) => (
                  <option key={team.id} value={team.id}>
                    {team.name}
                    {team.category?.name ? ` · ${team.category.name}` : ""}
                  </option>
                ))}
              </Select>
            </FormField>

            <FormField
              label="Costo total de inscripción"
              helper="Luego podrás dividir este monto entre las deportistas inscritas."
              error={
                errors.INVALID_AMOUNT ? errorMessages.INVALID_AMOUNT : null
              }
            >
              <Input
                type="number"
                min="0"
                step="0.01"
                placeholder="Ej: 100.00"
                value={registrationFee}
                className={errors.INVALID_AMOUNT ? "input-error" : ""}
                onChange={(event) => {
                  setRegistrationFee(event.target.value);
                  clearError("INVALID_AMOUNT");
                }}
              />
            </FormField>

            {(errors.FORBIDDEN ||
              errors.TOURNAMENT_NOT_ACTIVE ||
              errors.NETWORK_ERROR) && (
              <p className="form-error">
                {errors.FORBIDDEN
                  ? errorMessages.FORBIDDEN
                  : errors.TOURNAMENT_NOT_ACTIVE
                  ? errorMessages.TOURNAMENT_NOT_ACTIVE
                  : errorMessages.NETWORK_ERROR}
              </p>
            )}

            <div className="form-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={closeAddTeamForm}
              >
                Cancelar
              </Button>

              <Button type="submit" disabled={loadingSubmit}>
                {loadingSubmit ? "Inscribiendo..." : "Inscribir equipo"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {!showAddTeamForm &&
        (tournamentTeams.length === 0 ? (
          <Card>
            <div className="empty-state">
              <Trophy size={30} />

              <h4>Aún no hay equipos inscritos</h4>

              <p>
                Inscribe un equipo para seleccionar jugadoras, asociar partidos
                y generar cargos.
              </p>

              {canAddTeam && (
                <Button onClick={() => setShowAddTeamForm(true)}>
                  Inscribir equipo
                </Button>
              )}
            </div>
          </Card>
        ) : (
          <div className="tournament-teams-list">
            {tournamentTeams.map((entry) => {
              const entryStatus = getStatusData(entry.status);

              return (
                <Card
                  key={entry.id}
                  className="tournament-team-card card-interactive"
                  onClick={() => {
                    navigate(`/tournament-teams/${entry.id}`);
                  }}
                >
                  <div className="tournament-team-main">
                    <div className="tournament-card-icon">
                      <Users size={20} />
                    </div>

                    <div className="tournament-team-info">
                      <h3>{entry.team?.name || "Equipo sin nombre"}</h3>

                      <p>
                        {entry.team?.category?.name
                          ? `${entry.team.category.name} · `
                          : ""}
                        {entry.team?.gender === "female"
                          ? "Femenino"
                          : entry.team?.gender === "male"
                          ? "Masculino"
                          : "Mixto"}
                      </p>
                    </div>
                  </div>

                  <div className="tournament-team-meta">
                    <span className={`status-badge ${entryStatus.className}`}>
                      {entryStatus.label}
                    </span>

                    <span>{entry.total_players || 0} deportistas</span>

                    <span>{entry.total_matches || 0} partidos</span>

                    <strong>
                      ${Number(entry.registration_fee || 0).toFixed(2)}
                    </strong>
                  </div>
                </Card>
              );
            })}
          </div>
        ))}
    </div>
  );
};
