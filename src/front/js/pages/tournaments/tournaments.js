import React, { useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
import { FormField } from "../../component/ui/formField";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";
import { validateTournament } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";
import { Trophy, CalendarDays, Users } from "lucide-react";

import "../../../styles/tournaments.css";

const formatDate = (dateValue) => {
  if (!dateValue) return null;

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

export const Tournaments = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();

  const [showForm, setShowForm] = useState(false);
  const [loadingTournaments, setLoadingTournaments] = useState(true);
  const [loadingCreate, setLoadingCreate] = useState(false);
  const [errors, setErrors] = useState({});

  const [name, setName] = useState("");
  const [organizerName, setOrganizerName] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [defaultRefereeFee, setDefaultRefereeFee] = useState("");

  useEffect(() => {
    const loadTournaments = async () => {
      if (!store.token) {
        setLoadingTournaments(false);
        return;
      }

      setLoadingTournaments(true);
      await actions.getTournaments();
      setLoadingTournaments(false);
    };

    loadTournaments();
  }, [store.token]);

  const resetForm = () => {
    setName("");
    setOrganizerName("");
    setStartDate("");
    setEndDate("");
    setDefaultRefereeFee("");
    setErrors({});
  };

  const openCreateForm = () => {
    resetForm();
    setShowForm(true);
  };

  const closeCreateForm = () => {
    resetForm();
    setShowForm(false);
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

  const handleCreateTournament = async (event) => {
    event.preventDefault();

    if (loadingCreate) return;

    setErrors({});

    const tournamentData = {
      name,
      organizer_name: organizerName,
      start_date: startDate,
      end_date: endDate,
      default_referee_fee: defaultRefereeFee === "" ? 0 : defaultRefereeFee,
    };

    const validationErrors = validateTournament(tournamentData);

    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setLoadingCreate(true);

    const result = await actions.createTournament({
      name: name.trim(),
      organizer_name: organizerName.trim(),
      start_date: startDate,
      end_date: endDate || null,
      default_referee_fee: defaultRefereeFee === "" ? 0 : defaultRefereeFee,
    });

    setLoadingCreate(false);

    if (!result.ok) {
      setErrors({
        [result.code || "NETWORK_ERROR"]: true,
      });
      return;
    }

    closeCreateForm();
  };

  if (loadingTournaments) {
    return <p>Cargando torneos...</p>;
  }

  return (
    <>
      <PageHeader
        tone="tournaments"
        icon={Trophy}
        eyebrow="Competencias"
        title="Torneos"
        subtitle="Organiza las competencias del club, los equipos inscritos y los cargos asociados."
        actions={
          !showForm && <Button onClick={openCreateForm}>+ Crear torneo</Button>
        }
      />

      {showForm && (
        <Card className="tournament-form-card">
          <div className="tournament-section-heading">
            <div>
              <h4>Nuevo torneo</h4>
              <p>Registra la información general de la competencia.</p>
            </div>
          </div>

          <form onSubmit={handleCreateTournament} className="form">
            <FormField
              label="Nombre del torneo"
              error={
                errors.TOURNAMENT_NAME_REQUIRED
                  ? errorMessages.TOURNAMENT_NAME_REQUIRED
                  : errors.TOURNAMENT_ALREADY_EXISTS
                  ? errorMessages.TOURNAMENT_ALREADY_EXISTS
                  : null
              }
            >
              <Input
                type="text"
                placeholder="Ej: Copa Regional 2026"
                value={name}
                className={
                  errors.TOURNAMENT_NAME_REQUIRED ||
                  errors.TOURNAMENT_ALREADY_EXISTS
                    ? "input-error"
                    : ""
                }
                onChange={(event) => {
                  setName(event.target.value);
                  clearError(
                    "TOURNAMENT_NAME_REQUIRED",
                    "TOURNAMENT_ALREADY_EXISTS",
                  );
                }}
              />
            </FormField>

            <FormField label="Organizador">
              <Input
                type="text"
                placeholder="Ej: Liga Municipal de Voleibol"
                value={organizerName}
                onChange={(event) => {
                  setOrganizerName(event.target.value);
                }}
              />
            </FormField>

            <div className="tournament-form-grid">
              <FormField
                label="Fecha de inicio"
                error={
                  errors.TOURNAMENT_START_DATE_REQUIRED
                    ? errorMessages.TOURNAMENT_START_DATE_REQUIRED
                    : errors.INVALID_DATE_FORMAT
                    ? errorMessages.INVALID_DATE_FORMAT
                    : null
                }
              >
                <Input
                  type="date"
                  value={startDate}
                  className={
                    errors.TOURNAMENT_START_DATE_REQUIRED ||
                    errors.INVALID_DATE_FORMAT
                      ? "input-error"
                      : ""
                  }
                  onChange={(event) => {
                    setStartDate(event.target.value);
                    clearError(
                      "TOURNAMENT_START_DATE_REQUIRED",
                      "INVALID_DATE_FORMAT",
                      "INVALID_TOURNAMENT_DATE_RANGE",
                    );
                  }}
                />
              </FormField>

              <FormField
                label="Fecha de finalización"
                error={
                  errors.INVALID_TOURNAMENT_DATE_RANGE
                    ? errorMessages.INVALID_TOURNAMENT_DATE_RANGE
                    : null
                }
              >
                <Input
                  type="date"
                  value={endDate}
                  min={startDate || undefined}
                  className={
                    errors.INVALID_TOURNAMENT_DATE_RANGE ? "input-error" : ""
                  }
                  onChange={(event) => {
                    setEndDate(event.target.value);
                    clearError("INVALID_TOURNAMENT_DATE_RANGE");
                  }}
                />
              </FormField>
            </div>

            <FormField
              label="Arbitraje predeterminado por partido"
              helper="Podrás modificar este monto individualmente al crear cada partido."
              error={
                errors.INVALID_AMOUNT ? errorMessages.INVALID_AMOUNT : null
              }
            >
              <Input
                type="number"
                min="0"
                step="0.01"
                placeholder="Ej: 25.00"
                value={defaultRefereeFee}
                className={errors.INVALID_AMOUNT ? "input-error" : ""}
                onChange={(event) => {
                  setDefaultRefereeFee(event.target.value);
                  clearError("INVALID_AMOUNT");
                }}
              />
            </FormField>

            {(errors.NETWORK_ERROR || errors.FORBIDDEN) && (
              <p className="form-error">
                {errors.NETWORK_ERROR
                  ? errorMessages.NETWORK_ERROR
                  : errorMessages.FORBIDDEN}
              </p>
            )}

            <div className="form-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={closeCreateForm}
              >
                Cancelar
              </Button>

              <Button type="submit" disabled={loadingCreate}>
                {loadingCreate ? "Creando..." : "Crear torneo"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {!showForm &&
        (store.tournaments?.length === 0 ? (
          <Card>
            <div className="empty-state">
              <Trophy size={30} />

              <h4>Aún no tienes torneos</h4>

              <p>
                Registra una competencia para asociar equipos, deportistas,
                partidos y pagos.
              </p>
            </div>
          </Card>
        ) : (
          <div className="tournaments-grid">
            {store.tournaments?.map((tournament) => {
              const statusData = getStatusData(tournament.status);

              return (
                <Card
                  key={tournament.id}
                  className="tournament-card card-interactive"
                  onClick={() => navigate(`/tournaments/${tournament.id}`)}
                >
                  <div className="tournament-card-header">
                    <div className="tournament-card-icon">
                      <Trophy size={20} />
                    </div>

                    <span className={`status-badge ${statusData.className}`}>
                      {statusData.label}
                    </span>
                  </div>

                  <div className="tournament-card-content">
                    <h3>{tournament.name}</h3>

                    <p className="tournament-organizer">
                      {tournament.organizer_name ||
                        "Organizador no especificado"}
                    </p>
                  </div>

                  <div className="tournament-card-details">
                    <div className="tournament-detail-row">
                      <CalendarDays size={16} />

                      <span>
                        {formatDate(tournament.start_date)}
                        {tournament.end_date
                          ? ` — ${formatDate(tournament.end_date)}`
                          : ""}
                      </span>
                    </div>

                    <div className="tournament-detail-row">
                      <Users size={16} />

                      <span>
                        {tournament.total_teams || 0}{" "}
                        {tournament.total_teams === 1
                          ? "equipo inscrito"
                          : "equipos inscritos"}
                      </span>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        ))}
    </>
  );
};
