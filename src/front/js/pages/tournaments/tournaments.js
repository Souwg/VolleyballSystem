import React, { useContext, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { CalendarDays, CircleDot, Trophy, Users } from "lucide-react";

import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
import { Select } from "../../component/ui/select";
import { FormField } from "../../component/ui/formField";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";
import { validateTournament } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";
import {
  SeasonSelector,
  useSeasonSelection,
} from "../../component/seasonSelector";
import {
  canConfigureSportsFinance,
  isScopedCoach,
} from "../../utils/coachAccess";
import "../../../styles/tournaments.css";

const STATUS_OPTIONS = [
  ["", "Todos"],
  ["active", "Activos"],
  ["completed", "Completados"],
  ["cancelled", "Cancelados"],
];

const formatDate = (value) =>
  value
    ? new Intl.DateTimeFormat("es", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        timeZone: "UTC",
      }).format(new Date(`${value}T00:00:00Z`))
    : null;

const getStatusData = (status) =>
  ({
    active: { label: "Activo", className: "status-success" },
    completed: { label: "Completado", className: "status-info" },
    cancelled: { label: "Cancelado", className: "status-danger" },
  }[status] || { label: status || "Sin estado", className: "status-muted" });

const TournamentCard = ({ contextQuery, tournament }) => {
  const status = getStatusData(tournament.status);
  const readonly = tournament.status !== "active" || !tournament.can_manage;

  return (
    <Link
      className="tournament-card-link"
      to={`/tournaments/${tournament.id}${contextQuery ? `?${contextQuery}` : ""}`}
    >
      <Card className="tournament-card">
        <div className="tournament-card-header">
          <div className="tournament-card-icon"><Trophy size={20} /></div>
          <span className={`status-badge ${status.className}`}>{status.label}</span>
        </div>
        <div className="tournament-card-content">
          <h3>{tournament.name}</h3>
          <p>{tournament.season_name || "Temporada sin nombre"}</p>
          <p className="tournament-organizer">
            {tournament.organizer_name || "Organizador no especificado"}
          </p>
        </div>
        <div className="tournament-card-details">
          <div className="tournament-detail-row">
            <CalendarDays size={16} />
            <span>
              {formatDate(tournament.start_date)}
              {tournament.end_date ? ` — ${formatDate(tournament.end_date)}` : ""}
            </span>
          </div>
          <div className="tournament-detail-row">
            <Users size={16} />
            <span>
              {tournament.total_teams || 0} equipos · {tournament.active_roster_count || 0}/
              {tournament.total_roster_count || 0} deportistas
            </span>
          </div>
          <div className="tournament-detail-row">
            <CircleDot size={16} />
            <span>
              {tournament.open_matches_count || 0} abiertos · {tournament.completed_matches_count || 0} completados
            </span>
          </div>
          {readonly && <span className="status-badge status-muted">Solo consulta</span>}
        </div>
      </Card>
    </Link>
  );
};

export const Tournaments = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const loadRequestId = useRef(0);
  const club = store.club || store.user?.club;
  const canConfigureFinance = canConfigureSportsFinance(store);
  const statusFilter = searchParams.get("status") || "";

  const [tournaments, setTournaments] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [loadingTournaments, setLoadingTournaments] = useState(false);
  const [loadingCreate, setLoadingCreate] = useState(false);
  const [errors, setErrors] = useState({});
  const [name, setName] = useState("");
  const [organizerName, setOrganizerName] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [defaultRefereeFee, setDefaultRefereeFee] = useState("");
  const {
    activeSeason,
    loadingSeasons,
    reloadSeasons,
    seasonId,
    seasons,
    selectedSeason,
    seasonError,
    selectSeason,
  } = useSeasonSelection();

  const readOnlySeason = selectedSeason?.status !== "active";
  const canCreateTournament =
    selectedSeason?.status === "active" && !isScopedCoach(store);
  const contextQuery = searchParams.toString();

  const loadTournaments = async () => {
    const requestId = ++loadRequestId.current;
    setTournaments([]);
    setLoadError(null);

    if (!store.token || !selectedSeason || seasonError) {
      setLoadingTournaments(false);
      return;
    }

    setLoadingTournaments(true);
    const result = await actions.getTournaments({
      seasonId: selectedSeason.id,
      status: statusFilter,
    });

    if (requestId !== loadRequestId.current || result.code === "STALE_RESPONSE") return;

    if (result.ok) {
      setTournaments(result.data.tournaments || []);
    } else {
      setLoadError(result);
    }
    setLoadingTournaments(false);
  };

  useEffect(() => {
    if (!loadingSeasons) loadTournaments();
    return () => { loadRequestId.current += 1; };
  }, [store.token, selectedSeason?.id, statusFilter, loadingSeasons, seasonError]);

  useEffect(() => {
    if (readOnlySeason) setShowForm(false);
  }, [readOnlySeason]);

  const resetForm = () => {
    setName("");
    setOrganizerName("");
    setStartDate("");
    setEndDate("");
    setDefaultRefereeFee("");
    setErrors({});
  };

  const closeForm = () => {
    resetForm();
    setShowForm(false);
  };

  const clearError = (...codes) => setErrors((current) => {
    const next = { ...current };
    codes.forEach((code) => { next[code] = false; });
    return next;
  });

  const changeStatus = (status) => {
    const next = new URLSearchParams(searchParams);
    if (status) next.set("status", status);
    else next.delete("status");
    setSearchParams(next, { replace: true });
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    if (loadingCreate) return;

    const financePayload = canConfigureFinance
      ? { default_referee_fee: defaultRefereeFee === "" ? 0 : defaultRefereeFee }
      : {};
    const payload = {
      name,
      organizer_name: organizerName,
      start_date: startDate,
      end_date: endDate,
      ...financePayload,
    };
    const validationErrors = validateTournament(payload);

    if (Object.keys(validationErrors).length) {
      setErrors(validationErrors);
      return;
    }

    setErrors({});
    setLoadingCreate(true);
    const result = await actions.createTournament({
      ...payload,
      name: name.trim(),
      organizer_name: organizerName.trim(),
      end_date: endDate || null,
    });
    setLoadingCreate(false);

    if (!result.ok) {
      setErrors({ [result.code || "NETWORK_ERROR"]: true });
      return;
    }

    const next = new URLSearchParams(searchParams);
    if (activeSeason?.id) next.set("season", activeSeason.id);
    navigate(`/tournaments/${result.data.tournament.id}?${next.toString()}`);
  };

  const active = tournaments.filter((item) => item.status === "active");
  const historical = tournaments.filter((item) => item.status !== "active");
  const noActiveSeason = !loadingSeasons && !seasonError && !activeSeason;

  const renderGroup = (title, items) => items.length > 0 && (
    <section className="tournament-list-section" aria-labelledby={`tournament-${title}`}>
      <div className="tournament-section-heading">
        <h2 id={`tournament-${title}`}>{title === "active" ? "Activos" : "Históricos"}</h2>
        <span>{items.length}</span>
      </div>
      <div className="tournaments-grid">
        {items.map((item) => (
          <TournamentCard key={item.id} tournament={item} contextQuery={contextQuery} />
        ))}
      </div>
    </section>
  );

  return (
    <>
      <PageHeader
        tone="tournaments"
        icon={Trophy}
        eyebrow="Competencias"
        title="Torneos"
        subtitle="Prepara equipos y roster, opera partidos y conserva el histórico del club."
        actions={!showForm && canCreateTournament ? (
          <Button onClick={() => { resetForm(); setShowForm(true); }}>+ Crear torneo</Button>
        ) : null}
      />

      <div className="tournament-filters">
        <SeasonSelector
          loading={loadingSeasons}
          onChange={selectSeason}
          onRetry={reloadSeasons}
          seasons={seasons}
          selectedSeason={selectedSeason}
          error={seasonError}
        />
        <div className="season-filter">
          <label htmlFor="tournament-status-filter">Estado</label>
          <Select
            id="tournament-status-filter"
            value={statusFilter}
            onChange={(event) => changeStatus(event.target.value)}
            disabled={!selectedSeason || Boolean(seasonError)}
          >
            {STATUS_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </Select>
        </div>
      </div>

      {selectedSeason?.status === "planned" && (
        <div className="tournament-context-banner" role="status">
          <span>Los torneos estarán disponibles cuando esta temporada esté activa.</span>
          {store.user?.role === "club_owner" && (
            <Button variant="secondary" onClick={() => navigate("/seasons")}>Ir a Temporadas</Button>
          )}
        </div>
      )}
      {selectedSeason?.status === "closed" && (
        <div className="tournament-context-banner historical" role="status">
          Consulta histórica · Temporada {selectedSeason.name} cerrada
        </div>
      )}
      {noActiveSeason && !selectedSeason && (
        <Card><div className="empty-state">
          <Trophy size={30} /><h4>No hay una temporada activa</h4>
          <p>Los torneos se crean cuando el club tiene una temporada activa.</p>
          {store.user?.role === "club_owner" && <Button onClick={() => navigate("/seasons")}>Ir a Temporadas</Button>}
        </div></Card>
      )}

      {showForm && selectedSeason?.status === "active" && (
        <Card className="tournament-form-card">
          <div className="tournament-section-heading"><div>
            <h4>Nuevo torneo</h4>
            <p>Se creará en la temporada activa <strong>{selectedSeason.name}</strong>.</p>
          </div></div>
          <form onSubmit={handleCreate} className="form">
            <FormField label="Nombre del torneo" error={errors.TOURNAMENT_NAME_REQUIRED ? errorMessages.TOURNAMENT_NAME_REQUIRED : errors.TOURNAMENT_ALREADY_EXISTS ? errorMessages.TOURNAMENT_ALREADY_EXISTS : null}>
              <Input value={name} placeholder="Ej: Copa Regional 2026" onChange={(event) => { setName(event.target.value); clearError("TOURNAMENT_NAME_REQUIRED", "TOURNAMENT_ALREADY_EXISTS"); }} />
            </FormField>
            <FormField label="Organizador">
              <Input value={organizerName} placeholder="Ej: Liga Municipal" onChange={(event) => setOrganizerName(event.target.value)} />
            </FormField>
            <div className="tournament-form-grid">
              <FormField label="Fecha de inicio" error={errors.TOURNAMENT_START_DATE_REQUIRED ? errorMessages.TOURNAMENT_START_DATE_REQUIRED : null}>
                <Input type="date" value={startDate} onChange={(event) => { setStartDate(event.target.value); clearError("TOURNAMENT_START_DATE_REQUIRED", "INVALID_TOURNAMENT_DATE_RANGE"); }} />
              </FormField>
              <FormField label="Fecha de finalización" error={errors.INVALID_TOURNAMENT_DATE_RANGE ? errorMessages.INVALID_TOURNAMENT_DATE_RANGE : null}>
                <Input type="date" min={startDate || undefined} value={endDate} onChange={(event) => { setEndDate(event.target.value); clearError("INVALID_TOURNAMENT_DATE_RANGE"); }} />
              </FormField>
            </div>
            {canConfigureFinance && (
              <FormField label={`Arbitraje predeterminado (${club?.currency_code || "moneda"})`} helper="Se utilizará en nuevos partidos. Los partidos existentes no se modifican.">
                <Input type="number" min="0" step="0.01" value={defaultRefereeFee} onChange={(event) => setDefaultRefereeFee(event.target.value)} />
              </FormField>
            )}
            {Object.keys(errors).some((code) => errors[code] && !["TOURNAMENT_NAME_REQUIRED", "TOURNAMENT_ALREADY_EXISTS", "TOURNAMENT_START_DATE_REQUIRED", "INVALID_TOURNAMENT_DATE_RANGE"].includes(code)) && (
              <p className="form-error" role="alert">{errorMessages[Object.keys(errors).find((code) => errors[code])] || errorMessages.NETWORK_ERROR}</p>
            )}
            <div className="form-actions">
              <Button type="button" variant="secondary" onClick={closeForm}>Cancelar</Button>
              <Button type="submit" disabled={loadingCreate}>{loadingCreate ? "Creando..." : "Crear torneo"}</Button>
            </div>
          </form>
        </Card>
      )}

      {!showForm && selectedSeason && !seasonError && (
        loadingTournaments ? (
          <p role="status">Cargando torneos...</p>
        ) : loadError ? (
          <Card><div className="empty-state" role="alert">
            <h4>No se pudieron cargar los torneos</h4>
            <p>{loadError.message || errorMessages.NETWORK_ERROR}</p>
            <Button onClick={loadTournaments}>Volver a intentar</Button>
          </div></Card>
        ) : tournaments.length === 0 ? (
          <Card><div className="empty-state">
            <Trophy size={30} /><h4>No hay torneos en este contexto</h4>
            <p>{selectedSeason.status === "planned" ? "Los torneos estarán disponibles cuando esta temporada esté activa." : selectedSeason.status === "closed" ? "No hay torneos históricos con este filtro." : statusFilter ? "No hay torneos con el estado seleccionado." : "Crea un torneo para comenzar a inscribir equipos."}</p>
          </div></Card>
        ) : (
          <div className="tournament-groups">
            {renderGroup("active", active)}
            {renderGroup("historical", historical)}
          </div>
        )
      )}
    </>
  );
};
