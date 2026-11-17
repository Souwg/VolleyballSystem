import React, { useEffect, useState, useContext } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Context } from "../../store/appContext";
import { useParams } from "react-router-dom";
import {
  validatePlayerProfile,
  validatePlayerAssignment,
} from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";
import { useToast } from "../../../../context/toastContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
import { FormField } from "../../component/ui/formField";
import { Select } from "../../component/ui/select";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";
import { ReadOnlyNotice } from "../../component/ui/readOnlyNotice";
import { canManage, useTeamAccessLost } from "../../utils/coachAccess";
import { TeamCoachesSection } from "./teamCoachesSection";
import "../../../styles/playerShared.css";
import "../../../styles/teamDetails.css";

const TEAM_DELETE_BLOCKED_CODES = [
  "TEAM_HAS_PLAYERS",
  "TEAM_HAS_TRAININGS",
  "TEAM_HAS_HISTORY",
];

export const TeamDetail = () => {
  const { store, actions } = useContext(Context);
  const { showToast } = useToast();
  const { team_id } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const seasonId = searchParams.get("season");
  const seasonQuery = seasonId ? `?season=${seasonId}` : "";

  const [team, setTeam] = useState(null);
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [playerNumber, setPlayerNumber] = useState("");
  const [sex, setSex] = useState("");

  const [errors, setErrors] = useState({});
  const [loadingSubmit, setLoadingSubmit] = useState(false);
  const [updatingStatusPlayerId, setUpdatingStatusPlayerId] = useState(null);
  const [assignedCoachCount, setAssignedCoachCount] = useState(0);
  const [lifecycleAction, setLifecycleAction] = useState(null);
  const [lifecycleError, setLifecycleError] = useState(null);
  const [deleteBlockedCode, setDeleteBlockedCode] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [showAddOptions, setShowAddOptions] = useState(false);
  const [selectedExistingPlayer, setSelectedExistingPlayer] = useState(null);
  const [availablePlayers, setAvailablePlayers] = useState([]);
  const [existingSearch, setExistingSearch] = useState("");
  const [existingPlayerNumber, setExistingPlayerNumber] = useState("");
  const [createCandidates, setCreateCandidates] = useState([]);
  const [pendingCreatePayload, setPendingCreatePayload] = useState(null);
  const [editingPlayerId, setEditingPlayerId] = useState(null);
  const [editData, setEditData] = useState({
    first_name: "",
    last_name: "",
    player_number: "",
    sex: "",
  });

  const startEdit = (player) => {
    setEditingPlayerId(player.id);
    setEditData({
      first_name: player.first_name,
      last_name: player.last_name,
      player_number: player.player_number,
      sex: team?.gender === "mixed" ? player.sex : team.gender,
    });
    setErrors({});
  };

  const saveEdit = async () => {
    setErrors({});
    if (loadingSubmit) return;

    const profileErrors = validatePlayerProfile({
      first_name: editData.first_name,
      last_name: editData.last_name,
      sex: editData.sex,
    });

    const assignmentErrors = validatePlayerAssignment({
      team_id,
      player_number: editData.player_number,
    });

    const newErrors = {
      ...profileErrors,
      ...assignmentErrors,
    };

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setLoadingSubmit(true);

    const result = await actions.updatePlayer(editingPlayerId, {
      ...editData,
      team_id,
      player_number: Number(editData.player_number),
    });

    if (!result.ok) {
      setErrors({ [result.code]: true });
      setLoadingSubmit(false);
      return;
    }

    setPlayers((prev) =>
      prev.map((p) =>
        p.id === editingPlayerId
          ? {
              ...p,
              ...editData,
              player_number: Number(editData.player_number),
            }
          : p,
      ),
    );

    setEditingPlayerId(null);
    setErrors({});
    setLoadingSubmit(false);
  };

  useTeamAccessLost(() => loadTeamPlayers());

  const loadTeamPlayers = async () => {
    try {
      const [rosterResult, detailResult] = await Promise.all([
        actions.getTeamPlayers(team_id),
        actions.getTeamDetail(team_id),
      ]);

      if (!rosterResult.ok || !detailResult.ok) {
        setLoadError(
          rosterResult.code || detailResult.code || "HTTP_ERROR",
        );
        return;
      }

      setTeam({ ...rosterResult.data.team, ...detailResult.data.team });
      setPlayers(rosterResult.data.players);
      setLoadError(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!team) return;

    if (team.gender === "female") {
      setSex("female");
    }

    if (team.gender === "male") {
      setSex("male");
    }

    if (team.gender === "mixed") {
      setSex("");
    }
  }, [team]);

  const persistNewPlayer = async (payload) => {
    setLoadingSubmit(true);
    const result = await actions.createPlayer(payload);

    if (!result.ok) {
      setErrors({ [result.code]: true });
      setLoadingSubmit(false);
      return;
    }

    setFirstName("");
    setLastName("");
    setBirthDate("");
    setPlayerNumber("");
    setSex(team?.gender === "mixed" ? "" : team.gender);
    setCreateCandidates([]);
    setPendingCreatePayload(null);
    setPlayers((prev) => [...prev, result.data.player]);
    setLoadingSubmit(false);
    setShowForm(false);
  };

  const registerPlayer = async (e) => {
    e.preventDefault();

    if (loadingSubmit) return;

    const profileErrors = validatePlayerProfile({
      first_name: firstName,
      last_name: lastName,
      birth_date: birthDate,
      sex,
    });

    const assignmentErrors = validatePlayerAssignment({
      team_id,
      player_number: playerNumber,
    });

    const newErrors = {
      ...profileErrors,
      ...assignmentErrors,
    };

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setErrors({});
    const payload = {
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      birth_date: birthDate || null,
      player_number: Number(playerNumber),
      sex,
      team_id,
    };
    const candidatesResult = await actions.getPlayerCandidates({
      firstName: payload.first_name,
      lastName: payload.last_name,
      birthDate: payload.birth_date,
      sex: payload.sex,
    });
    if (!candidatesResult.ok) {
      setErrors({ [candidatesResult.code]: true });
      return;
    }
    const candidates = (candidatesResult.data.candidates || []).filter(
      (candidate) =>
        candidate.is_active &&
        !players.some((player) => player.id === candidate.id),
    );
    if (candidates.length) {
      setCreateCandidates(candidates);
      setPendingCreatePayload(payload);
      return;
    }
    await persistNewPlayer(payload);
  };

  const handleDeleteTeam = async () => {
    const confirmed = window.confirm(
      `¿Seguro que deseas eliminar el equipo ${team.name}?`,
    );

    if (!confirmed) return;

    const result = await actions.deleteTeam(team_id);

    if (!result.ok) {
      showToast(
        errorMessages[result.code] || "No se pudo eliminar el equipo",
        "error",
      );

      // El historial no se ve desde aquí: el backend decide y la salida es archivar.
      if (TEAM_DELETE_BLOCKED_CODES.includes(result.code)) {
        setDeleteBlockedCode(result.code);
      }

      return;
    }
    navigate(`/categories/${team.category_id}${seasonQuery}`);
  };

  const handleTeamLifecycle = async (action) => {
    if (lifecycleAction) return;

    const isArchive = action === "archive";
    const confirmed = window.confirm(
      isArchive
        ? `¿Archivar el equipo ${team.name}?\n\nEl equipo dejará de admitir nuevas operaciones deportivas, pero conservará su historial. Sus actividades abiertas no se cancelan.`
        : `¿Reactivar el equipo ${team.name}?\n\nVolverá a admitir operaciones deportivas. Lo que ya estaba finalizado no se reabre.`,
    );

    if (!confirmed) return;

    setLifecycleAction(action);
    setLifecycleError(null);

    let result;
    if (isArchive) {
      result = await actions.archiveTeam(team_id);
    } else {
      result = await actions.reactivateTeam(team_id);
    }

    if (!result.ok) {
      setLifecycleError(result.code || "HTTP_ERROR");
      setLifecycleAction(null);
      return;
    }

    await loadTeamPlayers();
    setLifecycleAction(null);
  };

  const handleRemovePlayer = async (e, player) => {
    e.stopPropagation();

    const confirmed = window.confirm(
      `¿Quitar a este deportista del equipo?\n\nSe cerrará esta pertenencia. ${player.first_name} conservará su perfil y su histórico; sus otros equipos no cambiarán.`,
    );

    if (!confirmed) return;

    const result = await actions.removePlayerFromTeam(team_id, player.id);

    if (!result.ok) {
      showToast(
        errorMessages[result.code] || "No se pudo quitar el deportista",
        "error",
      );
      return;
    }

    setPlayers((prev) => prev.filter((p) => p.id !== player.id));
  };

  const handleOpenPlayer = (playerId) => {
    navigate(`/players/${playerId}`, {
      state: {
        from: `/teams/${team_id}${seasonQuery}`,
        fromLabel: team?.name || "Equipo",
      },
    });
  };

  const handlePlayerStatusChange = async (event, player) => {
    event.stopPropagation();

    const status = event.target.value;
    if (status === player.status || updatingStatusPlayerId) return;

    setUpdatingStatusPlayerId(player.id);
    const result = await actions.updatePlayerStatus(player.id, team_id, status);

    if (!result.ok) {
      showToast(
        errorMessages[result.code] || "No se pudo actualizar la disponibilidad",
        "error",
      );
      setUpdatingStatusPlayerId(null);
      return;
    }

    setPlayers((currentPlayers) =>
      currentPlayers.map((currentPlayer) =>
        currentPlayer.id === player.id
          ? { ...currentPlayer, status }
          : currentPlayer,
      ),
    );
    setUpdatingStatusPlayerId(null);
  };

  const handleLoadExistingPlayers = async () => {
    const result = await actions.getPlayers();

    if (!result.ok || !result.data.players.length) {
      showToast("No hay deportistas existentes en el club", "info");
      return;
    }

    const filteredPlayers = result.data.players.filter((p) => {
      const alreadyInTeam = players.some((tp) => tp.id === p.id);

      const validGender = team.gender === "mixed" || p.sex === team.gender;

      const isActive = p.is_active === true;

      return !alreadyInTeam && validGender && isActive;
    });

    if (!filteredPlayers.length) {
      showToast(
        "Todos los deportistas disponibles ya están en este equipo",
        "info",
      );
      return;
    }

    setAvailablePlayers(filteredPlayers);
    setExistingSearch("");
    setShowAddOptions(false);
    setShowForm(false);
  };

  useEffect(() => {
    setDeleteBlockedCode(null);
    loadTeamPlayers();
  }, [team_id]);

  if (loading) {
    return <p role="status">Cargando equipo...</p>;
  }

  if (!team) {
    return (
      <Card className="page-error-state" role="alert">
        <p>
          {loadError === "TEAM_NOT_FOUND"
            ? "Equipo no encontrado."
            : errorMessages[loadError] || "No se pudo cargar el equipo."}
        </p>
        <Button variant="secondary" onClick={loadTeamPlayers}>
          Volver a intentar
        </Button>
      </Card>
    );
  }

  const playerCountLabel =
    players.length === 1 ? "1 deportista" : `${players.length} deportistas`;
  const canUpdatePlayerStatus =
    canManage(team) &&
    team.status === "active" &&
    ((store.user?.role === "club_owner" &&
      ["active", "planned"].includes(team.season_status)) ||
      (store.user?.role === "coach" && team.season_status === "active"));
  const canManageStructure = store.user?.role === "club_owner";
  const isArchived = team.status === "archived";
  const isClosedSeason = team.season_status === "closed";
  const seasonStatusLabel =
    team.season_status === "planned"
      ? "Planificada"
      : team.season_status === "closed"
      ? "Cerrada"
      : "Activa";
  const genderLabel =
    team.gender === "female"
      ? "femenina"
      : team.gender === "male"
      ? "masculina"
      : "mixta";
  const filteredAvailablePlayers = availablePlayers.filter((player) =>
    `${player.first_name} ${player.last_name}`
      .toLowerCase()
      .includes(existingSearch.trim().toLowerCase()),
  );

  return (
    <div className="team-detail-page">
      <nav className="breadcrumbs" aria-label="Migas de pan">
        <Link to={`/categories${seasonQuery}`}>Categorías</Link>
        <span aria-hidden="true">/</span>
        <Link to={`/categories/${team.category_id}${seasonQuery}`}>
          {team.category?.name || "Categoría"}
        </Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">{team.name}</span>
      </nav>
      <PageHeader
        variant="detail"
        eyebrow="Equipo"
        title={team.name}
        subtitle={`${team.category?.name || "Sin categoría"} · ${
          team.season?.name || "Sin temporada"
        } · ${seasonStatusLabel}`}
        onBack={() => navigate(`/categories/${team.category_id}${seasonQuery}`)}
        actions={
          <div className="team-detail-header-actions">
            {canUpdatePlayerStatus &&
              !showAddOptions &&
              !showForm &&
              availablePlayers.length === 0 &&
              !selectedExistingPlayer && (
                <Button
                  onClick={() => {
                    setShowAddOptions(true);
                    setShowForm(false);
                    setAvailablePlayers([]);
                    setSelectedExistingPlayer(null);
                    setExistingPlayerNumber("");
                    setErrors({});
                  }}
                >
                  + Añadir deportista
                </Button>
              )}

            <Button
              variant="secondary"
              onClick={() => navigate(`/teams/${team_id}/trainings`)}
            >
              Entrenamientos
            </Button>

            <Button
              variant="secondary"
              onClick={() => navigate(`/teams/${team.id}/matches`)}
            >
              Partidos
            </Button>
          </div>
        }
      />
      <p className="team-status-line">
        Rama {genderLabel} · {isArchived ? "Equipo archivado" : "Equipo activo"} · {playerCountLabel}
      </p>
      {isArchived && (
        <ReadOnlyNotice>
          Equipo archivado. Conserva su histórico y no admite nuevas operaciones.
        </ReadOnlyNotice>
      )}
      {isClosedSeason && (
        <ReadOnlyNotice>
          Histórico · {team.season?.name || "Temporada"} — Cerrada. Esta información es de solo consulta.
        </ReadOnlyNotice>
      )}
      {!canManage(team) && (
        <ReadOnlyNotice>
          Estás consultando este equipo. Solo quien lo tiene asignado puede
          modificarlo.
        </ReadOnlyNotice>
      )}
      {store.user?.role === "coach" &&
        canManage(team) &&
        !isArchived &&
        !isClosedSeason && (
        <p className="team-operation-note" role="note">
          Tienes permiso operativo sobre este equipo.
        </p>
      )}
      {showAddOptions && (
        <Card className="add-player-options">
          <h4>Añadir deportista</h4>
          <p className="team-context-line">
            {team.category?.name || "Sin categoría"} · {team.name} · {team.season?.name || "Sin temporada"} · Rama {genderLabel}
          </p>

          <Button
            variant="secondary"
            onClick={() => {
              setShowAddOptions(false);
              setAvailablePlayers([]);
              setSelectedExistingPlayer(null);
              setExistingPlayerNumber("");
              setShowForm(true);
            }}
          >
            Crear nuevo deportista
          </Button>

          <Button onClick={handleLoadExistingPlayers}>
            Agregar deportista existente del club
          </Button>

          <Button variant="secondary" onClick={() => setShowAddOptions(false)}>
            Cancelar
          </Button>
        </Card>
      )}
      {availablePlayers.length > 0 && (
        <Card>
          <h4>Selecciona deportista</h4>

          <FormField label="Buscar por nombre" htmlFor="existing-player-search">
            <Input
              id="existing-player-search"
              type="search"
              value={existingSearch}
              placeholder="Nombre o apellido"
              onChange={(event) => setExistingSearch(event.target.value)}
            />
          </FormField>

          <div className="players-list">
            {filteredAvailablePlayers.map((player) => (
              <button
                type="button"
                key={player.id}
                className="card player-card selectable-player selectable-player-button"
                onClick={() => {
                  setSelectedExistingPlayer(player);
                  setAvailablePlayers([]);
                }}
              >
                <span className="player-name">
                  {player.first_name} {player.last_name}
                </span>

                <span className="player-meta">
                  {player.birth_date
                    ? `Nacimiento: ${new Date(`${player.birth_date}T00:00:00`).toLocaleDateString("es-ES")}`
                    : "Nacimiento sin definir"} · Activo en el club
                </span>

                {player.teams?.length > 0 && (
                  <span className="player-meta">
                    Actualmente en:{" "}
                    {player.teams.map((team) => `${team.name}${team.season_name ? ` (${team.season_name})` : ""}`).join(" · ")}
                  </span>
                )}
              </button>
            ))}
          </div>

          <Button
            className="mt-2"
            variant="secondary"
            onClick={() => setAvailablePlayers([])}
          >
            Cancelar
          </Button>
        </Card>
      )}
      {selectedExistingPlayer && (
        <Card>
          <h4>
            Añadir a {selectedExistingPlayer.first_name}{" "}
            {selectedExistingPlayer.last_name}
          </h4>
          {selectedExistingPlayer.teams?.length > 0 && (
            <div className="player-team-history">
              <p className="helper-label">Actualmente juega en:</p>

              {selectedExistingPlayer.teams.map((team) => (
                <div key={team.id} className="team-pill">
                  {team.name} ·{" "}
                  {team.gender === "female"
                    ? "Femenina"
                    : team.gender === "male"
                    ? "Masculina"
                    : "Mixta"}{" "}
                  · #{team.player_number}
                </div>
              ))}
              <p className="helper-label">
                Seguirá perteneciendo a sus otros equipos.
              </p>
            </div>
          )}
          <FormField
            label="Número en el equipo"
            helper="Dorsal, si aplica"
            htmlFor="existing-player-number"
            errorId="existing-player-number-error"
            error={
              errors.PLAYER_NUMBER_REQUIRED
                ? errorMessages.PLAYER_NUMBER_REQUIRED
                : errors.INVALID_PLAYER_NUMBER
                ? errorMessages.INVALID_PLAYER_NUMBER
                : errors.PLAYER_NUMBER_DUPLICATED
                ? errorMessages.PLAYER_NUMBER_DUPLICATED
                : errors.PLAYER_INACTIVE
                ? errorMessages.PLAYER_INACTIVE
                : errors.PLAYER_ALREADY_IN_TEAM
                ? errorMessages.PLAYER_ALREADY_IN_TEAM
                : errors.PLAYER_GENDER_MISMATCH
                ? errorMessages.PLAYER_GENDER_MISMATCH
                : errors.PLAYER_NOT_FOUND
                ? errorMessages.PLAYER_NOT_FOUND
                : null
            }
          >
            <Input
              type="number"
              id="existing-player-number"
              aria-describedby={
                Object.keys(errors).length > 0
                  ? "existing-player-number-error"
                  : undefined
              }
              placeholder="Número del deportista en este equipo"
              value={existingPlayerNumber}
              className={
                errors.PLAYER_NUMBER_REQUIRED ||
                errors.INVALID_PLAYER_NUMBER ||
                errors.PLAYER_NUMBER_DUPLICATED
                  ? "input-error"
                  : ""
              }
              onChange={(e) => {
                const value = e.target.value;

                if (value === "") {
                  setExistingPlayerNumber("");
                  setErrors((prev) => ({
                    ...prev,
                    PLAYER_NUMBER_REQUIRED: false,
                    INVALID_PLAYER_NUMBER: false,
                    PLAYER_NUMBER_DUPLICATED: false,
                    PLAYER_INACTIVE: false,
                    PLAYER_ALREADY_IN_TEAM: false,
                    PLAYER_GENDER_MISMATCH: false,
                    PLAYER_NOT_FOUND: false,
                  }));
                  return;
                }

                if (value.length > 2) return;
                if (Number(value) <= 0) return;

                setExistingPlayerNumber(value);

                setErrors((prev) => ({
                  ...prev,
                  PLAYER_NUMBER_REQUIRED: false,
                  PLAYER_NUMBER_DUPLICATED: false,
                  INVALID_PLAYER_NUMBER: false,
                  PLAYER_INACTIVE: false,
                  PLAYER_ALREADY_IN_TEAM: false,
                  PLAYER_GENDER_MISMATCH: false,
                  PLAYER_NOT_FOUND: false,
                }));
              }}
            />
          </FormField>

          <div className="form-actions mt-2">
            <Button
              variant="secondary"
              onClick={() => {
                setSelectedExistingPlayer(null);
                setExistingPlayerNumber("");
              }}
            >
              Cancelar
            </Button>

            <Button
              onClick={async () => {
                if (!existingPlayerNumber) {
                  setErrors({ PLAYER_NUMBER_REQUIRED: true });
                  return;
                }

                const result = await actions.addExistingPlayerToTeam(team_id, {
                  player_id: selectedExistingPlayer.id,
                  player_number: Number(existingPlayerNumber),
                });

                if (!result.ok) {
                  setErrors({ [result.code]: true });
                  return;
                }

                setPlayers((prev) => [
                  ...prev,
                  {
                    id: selectedExistingPlayer.id,
                    first_name: selectedExistingPlayer.first_name,
                    last_name: selectedExistingPlayer.last_name,
                    sex: selectedExistingPlayer.sex,
                    player_number: Number(existingPlayerNumber),
                    status: "active",
                  },
                ]);

                setSelectedExistingPlayer(null);
                setExistingPlayerNumber("");
              }}
            >
              {selectedExistingPlayer.teams?.length > 0
                ? "Agregar también a este equipo"
                : selectedExistingPlayer.previous_team_ids?.includes(team_id)
                ? "Volver a agregar"
                : "Agregar a este equipo"}
            </Button>
          </div>
        </Card>
      )}

      {showForm && (
        <Card>
          <h4>Nuevo deportista</h4>

          <form onSubmit={registerPlayer} className="form">
            <FormField
              label="Nombre"
              htmlFor="new-player-first-name"
              errorId="new-player-first-name-error"
              error={
                errors.FIRST_NAME_REQUIRED
                  ? errorMessages.FIRST_NAME_REQUIRED
                  : null
              }
            >
              <Input
                id="new-player-first-name"
                autoFocus
                aria-describedby={
                  errors.FIRST_NAME_REQUIRED
                    ? "new-player-first-name-error"
                    : undefined
                }
                value={firstName}
                className={errors.FIRST_NAME_REQUIRED ? "input-error" : ""}
                placeholder="Nombre"
                onChange={(e) => {
                  setFirstName(e.target.value);
                  setCreateCandidates([]);
                  setPendingCreatePayload(null);
                  setErrors((prev) => ({
                    ...prev,
                    FIRST_NAME_REQUIRED: false,
                  }));
                }}
              />
            </FormField>
            <FormField
              label="Apellido"
              htmlFor="new-player-last-name"
              errorId="new-player-last-name-error"
              error={
                errors.LAST_NAME_REQUIRED
                  ? errorMessages.LAST_NAME_REQUIRED
                  : null
              }
            >
              <Input
                id="new-player-last-name"
                aria-describedby={
                  errors.LAST_NAME_REQUIRED
                    ? "new-player-last-name-error"
                    : undefined
                }
                value={lastName}
                className={errors.LAST_NAME_REQUIRED ? "input-error" : ""}
                placeholder="Apellido"
                onChange={(e) => {
                  setLastName(e.target.value);
                  setCreateCandidates([]);
                  setPendingCreatePayload(null);
                  setErrors((prev) => ({
                    ...prev,
                    LAST_NAME_REQUIRED: false,
                  }));
                }}
              />
            </FormField>
            <FormField
              label="Fecha de nacimiento (opcional)"
              htmlFor="new-player-birth-date"
              errorId="new-player-birth-date-error"
              error={
                errors.INVALID_BIRTH_DATE
                  ? errorMessages.INVALID_BIRTH_DATE
                  : errors.INVALID_DATE_FORMAT
                  ? errorMessages.INVALID_DATE_FORMAT
                  : null
              }
            >
              <Input
                id="new-player-birth-date"
                type="date"
                value={birthDate}
                aria-describedby={
                  errors.INVALID_BIRTH_DATE || errors.INVALID_DATE_FORMAT
                    ? "new-player-birth-date-error"
                    : undefined
                }
                onChange={(event) => {
                  setBirthDate(event.target.value);
                  setCreateCandidates([]);
                  setPendingCreatePayload(null);
                  setErrors((current) => ({
                    ...current,
                    INVALID_BIRTH_DATE: false,
                    INVALID_DATE_FORMAT: false,
                  }));
                }}
              />
            </FormField>
            <FormField
              label="Número en el equipo"
              helper="Dorsal, si aplica"
              htmlFor="new-player-number"
              errorId="new-player-number-error"
              error={
                errors.PLAYER_NUMBER_REQUIRED
                  ? errorMessages.PLAYER_NUMBER_REQUIRED
                  : errors.INVALID_PLAYER_NUMBER
                  ? errorMessages.INVALID_PLAYER_NUMBER
                  : errors.PLAYER_NUMBER_DUPLICATED
                  ? errorMessages.PLAYER_NUMBER_DUPLICATED
                  : null
              }
            >
              <Input
                type="number"
                id="new-player-number"
                aria-describedby={
                  errors.PLAYER_NUMBER_REQUIRED ||
                  errors.INVALID_PLAYER_NUMBER ||
                  errors.PLAYER_NUMBER_DUPLICATED
                    ? "new-player-number-error"
                    : undefined
                }
                min="1"
                max="99"
                value={playerNumber}
                className={
                  errors.PLAYER_NUMBER_REQUIRED ||
                  errors.INVALID_PLAYER_NUMBER ||
                  errors.PLAYER_NUMBER_DUPLICATED
                    ? "input-error"
                    : ""
                }
                placeholder="Número del deportista en este equipo"
                onChange={(e) => {
                  const value = e.target.value;

                  if (value === "") {
                    setPlayerNumber("");
                    setErrors((prev) => ({
                      ...prev,
                      PLAYER_NUMBER_REQUIRED: false,
                      INVALID_PLAYER_NUMBER: false,
                      PLAYER_NUMBER_DUPLICATED: false,
                    }));
                    return;
                  }

                  if (value.length > 2) return;

                  setPlayerNumber(value);

                  setErrors((prev) => ({
                    ...prev,
                    PLAYER_NUMBER_REQUIRED: false,
                    INVALID_PLAYER_NUMBER: false,
                    PLAYER_NUMBER_DUPLICATED: false,
                  }));
                }}
              />
            </FormField>
            {team?.gender === "mixed" && (
              <FormField
                label="Sexo"
                htmlFor="new-player-sex"
                errorId="new-player-sex-error"
                error={
                  errors.SEX_REQUIRED
                    ? errorMessages.SEX_REQUIRED
                    : errors.INVALID_SEX
                    ? errorMessages.INVALID_SEX
                    : null
                }
              >
                <Select
                  id="new-player-sex"
                  aria-describedby={
                    errors.SEX_REQUIRED || errors.INVALID_SEX
                      ? "new-player-sex-error"
                      : undefined
                  }
                  value={sex}
                  className={
                    errors.SEX_REQUIRED || errors.INVALID_SEX
                      ? "input-error"
                      : ""
                  }
                  onChange={(e) => {
                    setSex(e.target.value);
                    setCreateCandidates([]);
                    setPendingCreatePayload(null);
                    setErrors((prev) => ({
                      ...prev,
                      SEX_REQUIRED: false,
                      INVALID_SEX: false,
                    }));
                  }}
                >
                  <option value="">Selecciona sexo</option>
                  <option value="male">Masculino</option>
                  <option value="female">Femenino</option>
                </Select>
              </FormField>
            )}

            {createCandidates.length > 0 && (
              <Card className="duplicate-candidates" role="status">
                <h4>Encontramos posibles coincidencias</h4>
                <p>Elige un perfil existente o crea uno nuevo de todos modos.</p>
                {createCandidates.map((candidate) => (
                  <div className="duplicate-candidate" key={candidate.id}>
                    <div>
                      <strong>{candidate.first_name} {candidate.last_name}</strong>
                      <span>
                        {candidate.birth_date
                          ? new Date(`${candidate.birth_date}T00:00:00`).toLocaleDateString("es-ES")
                          : "Nacimiento sin definir"} · Activo en el club
                      </span>
                      <span>
                        {(candidate.teams || []).map((row) => row.team_name).join(" · ") || "Sin equipo actual"}
                      </span>
                    </div>
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={loadingSubmit}
                      onClick={async () => {
                        setLoadingSubmit(true);
                        const result = await actions.addExistingPlayerToTeam(team_id, {
                          player_id: candidate.id,
                          player_number: Number(playerNumber),
                        });
                        setLoadingSubmit(false);
                        if (!result.ok) {
                          setErrors({ [result.code]: true });
                          return;
                        }
                        await loadTeamPlayers();
                        setShowForm(false);
                        setCreateCandidates([]);
                        setPendingCreatePayload(null);
                      }}
                    >
                      Usar este deportista
                    </Button>
                  </div>
                ))}
                <Button
                  type="button"
                  disabled={loadingSubmit}
                  onClick={() => persistNewPlayer(pendingCreatePayload)}
                >
                  Crear de todos modos
                </Button>
              </Card>
            )}

            <div className="form-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setShowForm(false);
                  setErrors({});
                }}
              >
                Cancelar
              </Button>

              <Button type="submit" disabled={loadingSubmit}>
                {loadingSubmit ? "Guardando..." : "Guardar"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      <Card>
        <h4>Deportistas del equipo</h4>
        {canUpdatePlayerStatus && (
          <p className="team-context-line">
            Disponibilidad en el equipo: Lesionado/a puede participar en entrenamientos, pero no en nuevos partidos o torneos.
          </p>
        )}

        {players.length === 0 ? (
          <div className="empty-state">
            <p>Este equipo aún no tiene deportistas.</p>
            {canUpdatePlayerStatus && (
              <Button
                onClick={() => {
                  setShowAddOptions(true);
                  setShowForm(false);
                  setAvailablePlayers([]);
                  setSelectedExistingPlayer(null);
                  setErrors({});
                }}
              >
                Añadir deportista
              </Button>
            )}
          </div>
        ) : (
          <div className="players-list">
            {players.map((player) => (
              <Card key={player.id} className="player-card">
                <div className="player-row">
                  {editingPlayerId === player.id ? (
                    //MODO EDICIÓN
                    <div className="player-edit">
                      <FormField
                        label="Nombre"
                        htmlFor="edit-player-first-name"
                        errorId="edit-player-first-name-error"
                        error={
                          errors.FIRST_NAME_REQUIRED
                            ? errorMessages.FIRST_NAME_REQUIRED
                            : null
                        }
                      >
                        <Input
                          id="edit-player-first-name"
                          autoFocus
                          aria-describedby={
                            errors.FIRST_NAME_REQUIRED
                              ? "edit-player-first-name-error"
                              : undefined
                          }
                          value={editData.first_name}
                          className={
                            errors.FIRST_NAME_REQUIRED ? "input-error" : ""
                          }
                          onChange={(e) => {
                            setEditData({
                              ...editData,
                              first_name: e.target.value,
                            });
                            setErrors((prev) => ({
                              ...prev,
                              FIRST_NAME_REQUIRED: false,
                            }));
                          }}
                        />
                      </FormField>

                      <FormField
                        label="Apellido"
                        htmlFor="edit-player-last-name"
                        errorId="edit-player-last-name-error"
                        error={
                          errors.LAST_NAME_REQUIRED
                            ? errorMessages.LAST_NAME_REQUIRED
                            : null
                        }
                      >
                        <Input
                          id="edit-player-last-name"
                          aria-describedby={
                            errors.LAST_NAME_REQUIRED
                              ? "edit-player-last-name-error"
                              : undefined
                          }
                          value={editData.last_name}
                          className={
                            errors.LAST_NAME_REQUIRED ? "input-error" : ""
                          }
                          onChange={(e) => {
                            setEditData({
                              ...editData,
                              last_name: e.target.value,
                            });
                            setErrors((prev) => ({
                              ...prev,
                              LAST_NAME_REQUIRED: false,
                            }));
                          }}
                        />
                      </FormField>
                      <FormField
                        label="Número en el equipo"
                        helper="Dorsal, si aplica"
                        htmlFor="edit-player-number"
                        errorId="edit-player-number-error"
                        error={
                          errors.PLAYER_NUMBER_REQUIRED
                            ? errorMessages.PLAYER_NUMBER_REQUIRED
                            : errors.INVALID_PLAYER_NUMBER
                            ? errorMessages.INVALID_PLAYER_NUMBER
                            : errors.PLAYER_NUMBER_DUPLICATED
                            ? errorMessages.PLAYER_NUMBER_DUPLICATED
                            : null
                        }
                      >
                        <Input
                          type="number"
                          id="edit-player-number"
                          aria-describedby={
                            errors.PLAYER_NUMBER_REQUIRED ||
                            errors.INVALID_PLAYER_NUMBER ||
                            errors.PLAYER_NUMBER_DUPLICATED
                              ? "edit-player-number-error"
                              : undefined
                          }
                          value={editData.player_number}
                          className={
                            errors.PLAYER_NUMBER_REQUIRED ||
                            errors.INVALID_PLAYER_NUMBER ||
                            errors.PLAYER_NUMBER_DUPLICATED
                              ? "input-error"
                              : ""
                          }
                          onChange={(e) => {
                            const value = e.target.value;

                            if (value === "") {
                              setEditData({
                                ...editData,
                                player_number: "",
                              });
                              setErrors((prev) => ({
                                ...prev,
                                PLAYER_NUMBER_REQUIRED: false,
                                INVALID_PLAYER_NUMBER: false,
                                PLAYER_NUMBER_DUPLICATED: false,
                              }));
                              return;
                            }

                            const num = Number(value);

                            if (num <= 0) return;
                            if (value.length > 2) return;

                            setEditData({
                              ...editData,
                              player_number: value,
                            });

                            setErrors((prev) => ({
                              ...prev,
                              PLAYER_NUMBER_REQUIRED: false,
                              INVALID_PLAYER_NUMBER: false,
                              PLAYER_NUMBER_DUPLICATED: false,
                            }));
                          }}
                        />
                      </FormField>

                      <Button type="button" onClick={saveEdit}>
                        Guardar
                      </Button>

                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() => {
                          setEditingPlayerId(null);
                          setErrors({});
                        }}
                      >
                        Cancelar
                      </Button>
                    </div>
                  ) : (
                    //MODO NORMAL
                    <>
                      <div className="player-header">
                        <button
                          type="button"
                          className="player-profile-link"
                          onClick={() => handleOpenPlayer(player.id)}
                        >
                          <span className="player-info">
                            <span className="player-name">
                              {player.first_name} {player.last_name}
                            </span>

                            <span className="player-meta">
                              #{player.player_number} ·{" "}
                              {player.sex === "female" ? "Femenino" : "Masculino"}
                            </span>
                            {player.is_active === false && (
                              <span className="status-badge status-muted player-global-status">
                                Inactivo en el club
                              </span>
                            )}
                          </span>
                          <span className="player-card-arrow" aria-hidden="true">
                            →
                          </span>
                        </button>

                        <div className="player-card-side">
                          {canUpdatePlayerStatus ? (
                            <Select
                              aria-label={`Disponibilidad de ${player.first_name} en el equipo`}
                              disabled={updatingStatusPlayerId === player.id}
                              onClick={(event) => event.stopPropagation()}
                              onChange={(event) =>
                                handlePlayerStatusChange(event, player)
                              }
                              value={player.status}
                            >
                              <option value="active">Disponible para este equipo</option>
                              <option value="injured">Lesionado/a</option>
                              <option value="inactive">No disponible para este equipo</option>
                            </Select>
                          ) : (
                            <span
                              className={`status-badge ${
                                player.status === "active"
                                  ? "status-success"
                                  : player.status === "injured"
                                  ? "status-warning"
                                  : "status-muted"
                              }`}
                            >
                              {player.status === "active"
                                ? "Disponible para este equipo"
                                : player.status === "injured"
                                ? "Lesionado/a"
                                : "No disponible para este equipo"}
                            </span>
                          )}
                        </div>
                      </div>

                      {canUpdatePlayerStatus && (
                        <button
                          type="button"
                          className="player-remove-link"
                          onClick={(e) => handleRemovePlayer(e, player)}
                        >
                          Quitar del equipo
                        </button>
                      )}
                    </>
                  )}
                </div>
              </Card>
            ))}
          </div>
        )}
      </Card>
      {canManageStructure && (
        <TeamCoachesSection
          team={team}
          onTeamChanged={loadTeamPlayers}
          onCoachesChange={setAssignedCoachCount}
        />
      )}
      {canManageStructure && (
        <Card className="team-lifecycle-card">
          <div className="team-lifecycle-header">
            <h4>Estado del equipo</h4>
            <span
              className={`status-badge ${
                isArchived ? "status-muted" : "status-success"
              }`}
            >
              {isArchived ? "Equipo archivado" : "Equipo activo"}
            </span>
          </div>

          {deleteBlockedCode && (
            <p className="form-error">{errorMessages[deleteBlockedCode]}</p>
          )}
          {lifecycleError && (
            <p className="form-error lifecycle-error" role="alert">
              {errorMessages[lifecycleError] ||
                "No se pudo actualizar el estado del equipo. Intenta nuevamente."}
            </p>
          )}

          {isClosedSeason ? (
            <p>
              Este equipo pertenece a una temporada cerrada: se conserva como
              histórico y no admite cambios de estado.
            </p>
          ) : isArchived ? (
            <>
              <p>
                El equipo se conserva como histórico y no admite nuevas
                operaciones deportivas.
              </p>
              <Button
                variant="secondary"
                disabled={Boolean(lifecycleAction)}
                onClick={() => handleTeamLifecycle("reactivate")}
              >
                {lifecycleAction === "reactivate"
                  ? "Reactivando..."
                  : "Reactivar equipo"}
              </Button>
            </>
          ) : (
            <>
              <p>
                Al archivarlo dejará de admitir nuevas operaciones deportivas,
                pero conservará su historial.
              </p>
              <Button
                variant="secondary"
                disabled={Boolean(lifecycleAction)}
                onClick={() => handleTeamLifecycle("archive")}
              >
                {lifecycleAction === "archive"
                  ? "Archivando..."
                  : "Archivar equipo"}
              </Button>
            </>
          )}
        </Card>
      )}
      {canManageStructure &&
        !isClosedSeason &&
        !deleteBlockedCode &&
        !(isArchived && players.length > 0) && (
      <Card className="danger-zone">
        <h4>Zona peligrosa</h4>

        {players.length > 0 ? (
          <p>
            No puedes eliminar este equipo porque todavía tiene miembros
            asignados. Primero quítalos o reasígnalos.
          </p>
        ) : assignedCoachCount > 0 ? (
          <p>
            No puedes eliminar este equipo porque tiene entrenadores asignados.
          </p>
        ) : (
          <p>
            Este equipo no tiene miembros asignados. Si nunca tuvo actividad
            puedes eliminarlo; si tiene historial, archívalo para conservarlo.
          </p>
        )}

        <Button
          variant="danger"
          onClick={handleDeleteTeam}
          disabled={players.length > 0 || assignedCoachCount > 0}
        >
          Eliminar equipo
        </Button>
      </Card>
      )}
    </div>
  );
};
