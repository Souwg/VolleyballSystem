import React, { useContext, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Users } from "lucide-react";
import { Context } from "../../store/appContext";
import { Card } from "../../component/ui/card";
import { PageHeader } from "../../component/ui/pageHeader";
import { Button } from "../../component/ui/button";
import { FormField } from "../../component/ui/formField";
import { Input } from "../../component/ui/input";
import { Select } from "../../component/ui/select";
import {
  validatePlayerAssignment,
  validatePlayerProfile,
} from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";
import {
  getManageableTeams,
  isScopedCoach,
} from "../../utils/coachAccess";
import "../../../styles/playerShared.css";
import "../../../styles/players.css";

const formatBirthDate = (value) => {
  if (!value) return null;
  return new Date(`${value}T00:00:00`).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
};

const candidateTeams = (candidate) =>
  (candidate.teams || [])
    .map((team) => team.team_name || team.name)
    .filter(Boolean)
    .join(" · ");

export const Players = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [errors, setErrors] = useState({});
  const [searchTerm, setSearchTerm] = useState("");
  const [teamFilter, setTeamFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createForm, setCreateForm] = useState({
    first_name: "",
    last_name: "",
    birth_date: "",
    sex: "",
    team_id: "",
    player_number: "",
  });
  const [duplicateCandidates, setDuplicateCandidates] = useState([]);
  const [pendingPayload, setPendingPayload] = useState(null);
  const [assigningPlayer, setAssigningPlayer] = useState(null);
  const [selectedTeam, setSelectedTeam] = useState("");
  const [newNumber, setNewNumber] = useState("");

  const scopedCoach = isScopedCoach(store);
  const canCreateGlobal =
    store.user?.role === "club_owner" ||
    (store.user?.role === "coach" && !scopedCoach);
  const canManageMemberships = ["club_owner", "coach"].includes(
    store.user?.role,
  );
  const canManagePlayerStatus = store.user?.role === "club_owner";
  const manageableTeams = getManageableTeams(store.teams);
  const directoryTeams = useMemo(() => {
    const byId = new Map();
    (store.teams || []).forEach((team) => byId.set(team.id, team));
    (store.players || []).forEach((player) => {
      (player.teams || []).forEach((team) => {
        if (!byId.has(team.id)) byId.set(team.id, team);
      });
    });
    return [...byId.values()].sort((a, b) =>
      a.name.localeCompare(b.name, "es", { sensitivity: "base" }),
    );
  }, [store.teams, store.players]);
  const selectedCreateTeam = store.teams.find(
    (team) => team.id === createForm.team_id,
  );

  const loadDirectory = async () => {
    if (!store.token) return;
    setLoading(true);
    setLoadError(null);
    const [playersResult, teamsResult] = await Promise.all([
      actions.getPlayers(),
      actions.getTeams(),
    ]);
    const failed = !playersResult.ok ? playersResult : !teamsResult.ok ? teamsResult : null;
    if (failed) setLoadError(failed.code || "HTTP_ERROR");
    setLoading(false);
  };

  useEffect(() => {
    loadDirectory();
  }, [store.token]);

  useEffect(() => {
    if (!selectedCreateTeam) return;
    setCreateForm((current) => ({
      ...current,
      sex:
        selectedCreateTeam.gender === "mixed"
          ? current.sex
          : selectedCreateTeam.gender,
    }));
  }, [createForm.team_id]);

  const baseFilteredPlayers = useMemo(
    () =>
      (store.players || []).filter((player) => {
        const fullName = `${player.first_name} ${player.last_name}`.toLowerCase();
        const matchesSearch = fullName.includes(searchTerm.trim().toLowerCase());
        const matchesTeam =
          !teamFilter ||
          (teamFilter === "unassigned"
            ? !player.teams?.length
            : player.teams?.some((team) => team.id === teamFilter));
        return matchesSearch && matchesTeam;
      }),
    [store.players, searchTerm, teamFilter],
  );

  const filteredPlayers = useMemo(
    () =>
      baseFilteredPlayers
        .filter((player) => {
          if (statusFilter === "active") return player.is_active;
          if (statusFilter === "inactive") return !player.is_active;
          return true;
        })
        .sort((a, b) =>
          `${a.last_name} ${a.first_name}`.localeCompare(
            `${b.last_name} ${b.first_name}`,
            "es",
            { sensitivity: "base" },
          ),
        ),
    [baseFilteredPlayers, statusFilter],
  );

  const resetCreate = () => {
    setShowCreateForm(false);
    setCreateForm({
      first_name: "",
      last_name: "",
      birth_date: "",
      sex: "",
      team_id: "",
      player_number: "",
    });
    setDuplicateCandidates([]);
    setPendingPayload(null);
    setErrors({});
  };

  const updateCreateForm = (changes) => {
    setCreateForm((current) => ({ ...current, ...changes }));
    setDuplicateCandidates([]);
    setPendingPayload(null);
  };

  const executeCreate = async (payload) => {
    setCreateLoading(true);
    const result = await actions.createPlayer(payload);
    setCreateLoading(false);
    if (!result.ok) {
      setErrors({ [result.code]: true });
      return;
    }
    resetCreate();
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    if (createLoading) return;
    const profileErrors = validatePlayerProfile(createForm);
    const assignmentErrors = validatePlayerAssignment({
      team_id: createForm.team_id,
      player_number: createForm.player_number,
      requiredTeam: false,
    });
    const nextErrors = { ...profileErrors, ...assignmentErrors };
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }

    const payload = {
      first_name: createForm.first_name.trim(),
      last_name: createForm.last_name.trim(),
      birth_date: createForm.birth_date || null,
      sex: createForm.sex,
    };
    if (createForm.team_id) {
      payload.team_id = createForm.team_id;
      payload.player_number = Number(createForm.player_number);
    }

    setErrors({});
    const result = await actions.getPlayerCandidates({
      firstName: payload.first_name,
      lastName: payload.last_name,
      birthDate: payload.birth_date,
      sex: payload.sex,
    });
    if (!result.ok) {
      setErrors({ [result.code]: true });
      return;
    }
    const candidates = result.data.candidates || [];
    if (candidates.length) {
      setDuplicateCandidates(candidates);
      setPendingPayload(payload);
      return;
    }
    await executeCreate(payload);
  };

  const useCandidate = async (candidate) => {
    if (!pendingPayload?.team_id) {
      navigate(`/players/${candidate.id}`);
      return;
    }
    setCreateLoading(true);
    const result = await actions.addExistingPlayerToTeam(pendingPayload.team_id, {
      player_id: candidate.id,
      player_number: pendingPayload.player_number,
    });
    setCreateLoading(false);
    if (!result.ok) {
      setErrors({ [result.code]: true });
      return;
    }
    resetCreate();
  };

  const handleAssign = async () => {
    const assignmentErrors = validatePlayerAssignment({
      team_id: selectedTeam,
      player_number: newNumber,
    });
    if (Object.keys(assignmentErrors).length) {
      setErrors(assignmentErrors);
      return;
    }
    const result = await actions.addExistingPlayerToTeam(selectedTeam, {
      player_id: assigningPlayer.id,
      player_number: Number(newNumber),
    });
    if (!result.ok) {
      setErrors({ [result.code]: true });
      return;
    }
    setAssigningPlayer(null);
    setSelectedTeam("");
    setNewNumber("");
    setErrors({});
    await actions.getPlayers();
  };

  const handleActiveChange = async (player, isActive) => {
    const confirmed = window.confirm(
      isActive
        ? `¿Reactivar a ${player.first_name}?\n\nRecuperará la elegibilidad global. Su disponibilidad seguirá dependiendo de cada equipo y temporada.`
        : `¿Inactivar a ${player.first_name}?\n\nNo podrá participar en nuevas operaciones deportivas y se detendrán nuevas mensualidades automáticas. Su perfil, histórico y pertenencias a equipos se conservarán.`,
    );
    if (!confirmed) return;
    const result = await actions.updatePlayerActiveStatus(player.id, isActive);
    if (!result.ok) setErrors({ [result.code]: true });
  };

  if (loading) return <p role="status">Cargando deportistas...</p>;

  if (loadError) {
    return (
      <Card className="page-error-state" role="alert">
        <p>
          {loadError === "FORBIDDEN"
            ? "No tienes permisos para consultar deportistas."
            : "No se pudo cargar el directorio de deportistas."}
        </p>
        <Button type="button" variant="secondary" onClick={loadDirectory}>
          Volver a intentar
        </Button>
      </Card>
    );
  }

  const activeCount = baseFilteredPlayers.filter((player) => player.is_active).length;
  const inactiveCount = baseFilteredPlayers.length - activeCount;
  const unassignedCount = (store.players || []).filter(
    (player) => !player.teams?.length,
  ).length;

  return (
    <>
      <PageHeader
        tone="players"
        icon={Users}
        eyebrow="Directorio del club"
        title="Deportistas del club"
        subtitle="Consulta perfiles activos o inactivos, con uno, varios o ningún equipo actual."
        actions={
          canCreateGlobal && !showCreateForm ? (
            <Button type="button" onClick={() => setShowCreateForm(true)}>
              + Crear deportista
            </Button>
          ) : null
        }
      />

      {showCreateForm && (
        <Card className="player-create-card">
          <h3>Crear perfil de deportista</h3>
          <p className="text-muted">
            Crea un perfil en el club. Puedes agregarlo a un equipo ahora o después.
          </p>
          <form className="form" onSubmit={handleCreate}>
            <div className="player-create-section">
              <h4>Datos de identidad</h4>
              <FormField label="Nombre" htmlFor="create-player-first-name" errorId="create-player-first-name-error" error={errors.FIRST_NAME_REQUIRED ? errorMessages.FIRST_NAME_REQUIRED : null}>
                <Input id="create-player-first-name" value={createForm.first_name} aria-describedby={errors.FIRST_NAME_REQUIRED ? "create-player-first-name-error" : undefined} onChange={(event) => updateCreateForm({ first_name: event.target.value })} />
              </FormField>
              <FormField label="Apellido" htmlFor="create-player-last-name" errorId="create-player-last-name-error" error={errors.LAST_NAME_REQUIRED ? errorMessages.LAST_NAME_REQUIRED : null}>
                <Input id="create-player-last-name" value={createForm.last_name} aria-describedby={errors.LAST_NAME_REQUIRED ? "create-player-last-name-error" : undefined} onChange={(event) => updateCreateForm({ last_name: event.target.value })} />
              </FormField>
              <FormField label="Fecha de nacimiento (opcional)" htmlFor="create-player-birth-date" errorId="create-player-birth-date-error" error={errors.INVALID_BIRTH_DATE ? errorMessages.INVALID_BIRTH_DATE : errors.INVALID_DATE_FORMAT ? errorMessages.INVALID_DATE_FORMAT : null}>
                <Input id="create-player-birth-date" type="date" value={createForm.birth_date} aria-describedby={errors.INVALID_BIRTH_DATE || errors.INVALID_DATE_FORMAT ? "create-player-birth-date-error" : undefined} onChange={(event) => updateCreateForm({ birth_date: event.target.value })} />
              </FormField>
              <FormField label="Sexo" htmlFor="create-player-sex" errorId="create-player-sex-error" error={errors.SEX_REQUIRED || errors.INVALID_SEX ? errorMessages[errors.SEX_REQUIRED ? "SEX_REQUIRED" : "INVALID_SEX"] : null}>
                <Select id="create-player-sex" value={createForm.sex} disabled={Boolean(createForm.team_id && selectedCreateTeam?.gender !== "mixed")} onChange={(event) => updateCreateForm({ sex: event.target.value })}>
                  <option value="">Selecciona</option>
                  <option value="female">Femenino</option>
                  <option value="male">Masculino</option>
                </Select>
              </FormField>
            </div>

            <div className="player-create-section">
              <h4>Equipo (opcional)</h4>
              <p className="form-helper">Sin equipo también es un estado válido.</p>
              <FormField label="Equipo" htmlFor="create-player-team">
                <Select id="create-player-team" value={createForm.team_id} onChange={(event) => updateCreateForm({ team_id: event.target.value, player_number: "" })}>
                  <option value="">Agregar después</option>
                  {manageableTeams.map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}
                </Select>
              </FormField>
              {createForm.team_id && (
                <FormField label="Número en el equipo" htmlFor="create-player-number" errorId="create-player-number-error" error={errors.PLAYER_NUMBER_REQUIRED || errors.INVALID_PLAYER_NUMBER || errors.PLAYER_NUMBER_DUPLICATED ? errorMessages[errors.PLAYER_NUMBER_REQUIRED ? "PLAYER_NUMBER_REQUIRED" : errors.INVALID_PLAYER_NUMBER ? "INVALID_PLAYER_NUMBER" : "PLAYER_NUMBER_DUPLICATED"] : null}>
                  <Input id="create-player-number" type="number" min="1" max="99" value={createForm.player_number} onChange={(event) => updateCreateForm({ player_number: event.target.value })} />
                </FormField>
              )}
            </div>

            {duplicateCandidates.length > 0 && (
              <Card className="duplicate-candidates" role="status">
                <h4>Encontramos posibles coincidencias</h4>
                <p>Revisa antes de crear otro perfil. Los nombres iguales no bloquean el alta.</p>
                {duplicateCandidates.map((candidate) => (
                  <div className="duplicate-candidate" key={candidate.id}>
                    <div>
                      <strong>{candidate.first_name} {candidate.last_name}</strong>
                      <span>{formatBirthDate(candidate.birth_date) || "Nacimiento sin definir"} · {candidate.is_active ? "Activo en el club" : "Inactivo en el club"}</span>
                      <span>{candidateTeams(candidate) || "Sin equipo actual"}</span>
                    </div>
                    <Button type="button" variant="secondary" disabled={createLoading} onClick={() => useCandidate(candidate)}>Usar este deportista</Button>
                  </div>
                ))}
                <Button type="button" disabled={createLoading} onClick={() => executeCreate(pendingPayload)}>
                  Crear de todos modos
                </Button>
              </Card>
            )}

            {Object.keys(errors).some((code) => !["FIRST_NAME_REQUIRED", "LAST_NAME_REQUIRED", "SEX_REQUIRED", "INVALID_SEX", "INVALID_BIRTH_DATE", "INVALID_DATE_FORMAT", "PLAYER_NUMBER_REQUIRED", "INVALID_PLAYER_NUMBER", "PLAYER_NUMBER_DUPLICATED"].includes(code)) && (
              <p className="form-error" role="alert">{errorMessages[Object.keys(errors).find((code) => errors[code])] || "No se pudo completar la acción."}</p>
            )}
            <div className="form-actions">
              <Button type="button" variant="secondary" onClick={resetCreate}>Cancelar</Button>
              <Button type="submit" disabled={createLoading}>{createLoading ? "Guardando..." : "Crear deportista"}</Button>
            </div>
          </form>
        </Card>
      )}

      <Card className="players-filter-card">
        <div className="players-filter-top">
          <FormField label="Buscar por nombre" htmlFor="players-search">
            <Input id="players-search" value={searchTerm} placeholder="Nombre o apellido" onChange={(event) => setSearchTerm(event.target.value)} />
          </FormField>
          <button type="button" className="players-filter-toggle" aria-expanded={filtersOpen} aria-controls="players-extra-filters" onClick={() => setFiltersOpen(!filtersOpen)}>{filtersOpen ? "Ocultar filtros" : "Filtros"}</button>
        </div>
        <fieldset className="players-status-fieldset">
          <legend>Estado en el club</legend>
          <div className="players-status-chips">
            {[["all", `Todos (${baseFilteredPlayers.length})`], ["active", `Activos (${activeCount})`], ["inactive", `Inactivos (${inactiveCount})`]].map(([value, label]) => (
              <button key={value} type="button" className={`filter-chip ${statusFilter === value ? "active" : ""}`} aria-pressed={statusFilter === value} onClick={() => setStatusFilter(value)}>{label}</button>
            ))}
          </div>
        </fieldset>
        {filtersOpen && (
          <div id="players-extra-filters" className="players-filter-extra">
            <FormField label="Equipo" htmlFor="players-team-filter">
              <Select id="players-team-filter" value={teamFilter} onChange={(event) => setTeamFilter(event.target.value)}>
                <option value="">Todos los equipos ({store.players.length})</option>
                <option value="unassigned">Sin equipo ({unassignedCount})</option>
                {directoryTeams.map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}
              </Select>
            </FormField>
            {(searchTerm || teamFilter || statusFilter !== "all") && <button type="button" className="players-clear-filters" onClick={() => { setSearchTerm(""); setTeamFilter(""); setStatusFilter("all"); }}>Limpiar filtros</button>}
          </div>
        )}
      </Card>

      <Card>
        {filteredPlayers.length === 0 ? (
          <div className="empty-state">
            {store.players.length === 0 ? (
              <>
                <p>Registra deportistas en el club y agrégalos a equipos cuando corresponda.</p>
                {canCreateGlobal && <Button type="button" onClick={() => setShowCreateForm(true)}>Crear deportista</Button>}
              </>
            ) : (
              <><p>No hay deportistas que coincidan con los filtros.</p><Button type="button" variant="secondary" onClick={() => { setSearchTerm(""); setTeamFilter(""); setStatusFilter("all"); }}>Limpiar filtros</Button></>
            )}
          </div>
        ) : (
          <div className="players-list">
            {filteredPlayers.map((player) => (
              <Card key={player.id} className="player-card">
                <Link className="player-profile-link" to={`/players/${player.id}`} state={{ from: "/players", fromLabel: "Deportistas" }}>
                  <span className="player-info">
                    <span className="player-name">{player.first_name} {player.last_name}</span>
                    {player.birth_date && <span className="player-meta">Nacimiento: {formatBirthDate(player.birth_date)}</span>}
                    <span className="player-meta">{player.teams?.length ? `${player.teams[0].category_name || "Sin categoría"} · ${player.teams[0].name}${player.teams.length > 1 ? ` +${player.teams.length - 1} equipo${player.teams.length > 2 ? "s" : ""}` : ""}` : "Sin equipo actual"}</span>
                  </span>
                  <span className="player-card-side">
                    <span className={`status-badge ${player.is_active ? "status-success" : "status-muted"}`}>{player.is_active ? "Activo en el club" : "Inactivo en el club"}</span>
                    <span className="player-card-arrow" aria-hidden="true">›</span>
                  </span>
                </Link>

                {canManageMemberships && !player.teams?.length && player.is_active && manageableTeams.length > 0 && (
                  <div className="player-actions"><Button type="button" onClick={() => { setAssigningPlayer(player); setErrors({}); }}>Agregar a un equipo</Button></div>
                )}
                {canManagePlayerStatus && (
                  <div className="player-actions"><button type="button" className={`player-state-action ${player.is_active ? "danger" : "success"}`} onClick={() => handleActiveChange(player, !player.is_active)}>{player.is_active ? "Inactivar deportista" : "Reactivar deportista"}</button></div>
                )}
                {assigningPlayer?.id === player.id && (
                  <div className="assign-team-inline">
                    <p>Este perfil es válido sin equipo. Elige uno para crear una pertenencia.</p>
                    <FormField label="Equipo" htmlFor={`assign-team-${player.id}`} error={errors.TEAM_ID_REQUIRED ? errorMessages.TEAM_ID_REQUIRED : null}>
                      <Select id={`assign-team-${player.id}`} value={selectedTeam} onChange={(event) => setSelectedTeam(event.target.value)}><option value="">Selecciona</option>{manageableTeams.filter((team) => team.gender === "mixed" || team.gender === player.sex).map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}</Select>
                    </FormField>
                    <FormField label="Número en el equipo" htmlFor={`assign-number-${player.id}`} error={errors.PLAYER_NUMBER_REQUIRED || errors.INVALID_PLAYER_NUMBER || errors.PLAYER_NUMBER_DUPLICATED ? errorMessages[errors.PLAYER_NUMBER_REQUIRED ? "PLAYER_NUMBER_REQUIRED" : errors.INVALID_PLAYER_NUMBER ? "INVALID_PLAYER_NUMBER" : "PLAYER_NUMBER_DUPLICATED"] : null}>
                      <Input id={`assign-number-${player.id}`} type="number" min="1" max="99" value={newNumber} onChange={(event) => setNewNumber(event.target.value)} />
                    </FormField>
                    <div className="form-actions"><Button type="button" variant="secondary" onClick={() => setAssigningPlayer(null)}>Cancelar</Button><Button type="button" onClick={handleAssign}>Agregar a este equipo</Button></div>
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}
      </Card>
    </>
  );
};
