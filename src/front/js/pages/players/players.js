import React, { useEffect, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { Context } from "../../store/appContext";
import { Card } from "../../component/ui/card";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
import { Button } from "../../component/ui/button";
import {
  validatePlayerProfile,
  validatePlayerAssignment,
} from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";

export const Players = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();
  const [editingPlayer, setEditingPlayer] = useState(null);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [playerNumber, setPlayerNumber] = useState("");
  const [sex, setSex] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [teamFilter, setTeamFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [loadingPlayers, setLoadingPlayers] = useState(true);
  const [assigningPlayer, setAssigningPlayer] = useState(null);
  const [selectedTeam, setSelectedTeam] = useState("");
  const [newNumber, setNewNumber] = useState("");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createFirstName, setCreateFirstName] = useState("");
  const [createLastName, setCreateLastName] = useState("");
  const [createPlayerNumber, setCreatePlayerNumber] = useState("");
  const [createSex, setCreateSex] = useState("");
  const [createTeamId, setCreateTeamId] = useState("");
  const [createLoading, setCreateLoading] = useState(false);

  const editingPlayerTeam = store.teams.find(
    (team) => team.id === editingPlayer?.team_id,
  );

  const selectedCreateTeam = store.teams.find(
    (team) => team.id === createTeamId,
  );

  useEffect(() => {
    const loadPlayers = async () => {
      if (!store.token) return;

      setLoadingPlayers(true);

      await Promise.all([actions.getPlayers(), actions.getTeams()]);

      setLoadingPlayers(false);
    };

    loadPlayers();
  }, [store.token]);

  useEffect(() => {
    if (!selectedCreateTeam) return;

    if (selectedCreateTeam.gender === "female") {
      setCreateSex("female");
    } else if (selectedCreateTeam.gender === "male") {
      setCreateSex("male");
    } else {
      setCreateSex("");
    }
  }, [createTeamId, selectedCreateTeam]);

  const openCreateForm = () => {
    setShowCreateForm(true);
    setErrors({});
  };

  const closeCreateForm = () => {
    setShowCreateForm(false);
    setCreateFirstName("");
    setCreateLastName("");
    setCreateSex("");
    setCreateTeamId("");
    setCreatePlayerNumber("");
    setErrors({});
  };

  const handleCreatePlayer = async (e) => {
    e.preventDefault();
    if (createLoading) return;

    setErrors({});

    const profileErrors = validatePlayerProfile({
      first_name: createFirstName,
      last_name: createLastName,
      sex: createSex,
    });

    const assignmentErrors = validatePlayerAssignment({
      team_id: createTeamId,
      player_number: createPlayerNumber,
    });

    const newErrors = {
      ...profileErrors,
      ...assignmentErrors,
    };

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setCreateLoading(true);

    const payload = {
      first_name: createFirstName.trim(),
      last_name: createLastName.trim(),
      sex: createSex,
    };

    if (createTeamId) {
      payload.team_id = createTeamId;
      payload.player_number = Number(createPlayerNumber);
    }

    const result = await actions.createPlayer(payload);

    if (!result.ok) {
      setErrors({ [result.code]: true });
      setCreateLoading(false);
      return;
    }

    await actions.getPlayers();
    closeCreateForm();
    setCreateLoading(false);
  };

  const startEdit = (player) => {
    setErrors({});
    setEditingPlayer(player);
    setFirstName(player.first_name);
    setLastName(player.last_name);
    setPlayerNumber(player.player_number);
    setSex(player.sex);
  };

  const savePlayer = async (e) => {
    e.preventDefault();

    if (loading) return;

    const profileErrors = validatePlayerProfile({
      first_name: firstName,
      last_name: lastName,
      sex,
    });

    const assignmentErrors = editingPlayer.team_id
      ? validatePlayerAssignment({
          team_id: editingPlayer.team_id,
          player_number: playerNumber,
        })
      : {};

    const newErrors = {
      ...profileErrors,
      ...assignmentErrors,
    };

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setErrors({});
    setLoading(true);

    const result = await actions.updatePlayer(editingPlayer.id, {
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      player_number: Number(playerNumber),
      sex: sex,
      team_id: editingPlayer.team_id,
    });

    if (!result.ok) {
      setErrors({ [result.code]: true });
      setLoading(false);
      return;
    }

    setErrors({});
    setEditingPlayer(null);
    setLoading(false);
  };

  const getTeamName = (teamId) => {
    const team = store.teams.find((t) => t.id === teamId);
    return team ? team.name : "Unknown";
  };

  const filteredPlayers = store.players
    .filter((player) => {
      const fullName = `${player.first_name} ${player.last_name}`.toLowerCase();

      const matchesSearch = fullName.includes(searchTerm.toLowerCase());

      const matchesTeam =
        teamFilter === ""
          ? true
          : teamFilter === "unassigned"
          ? !player.team_id
          : player.team_id === teamFilter;

      const matchesStatus =
        statusFilter === "all" || player.status === statusFilter;

      return matchesSearch && matchesTeam && matchesStatus;
    })
    .sort((a, b) => {
      const numA = Number(a.player_number) || 999;
      const numB = Number(b.player_number) || 999;

      return numA - numB;
    });

  const handleStatusFilter = (status) => {
    setStatusFilter(status);
  };

  const handleTeamFilter = (teamId) => {
    setTeamFilter(teamId);
  };

  const clearFilters = () => {
    setTeamFilter("");
    setStatusFilter("all");
    setSearchTerm("");
  };

  const closeAssignTeam = () => {
    setAssigningPlayer(null);
    setSelectedTeam("");
    setNewNumber("");
    setErrors({});
  };

  const openAssignTeam = (e, player) => {
    e.stopPropagation();
    setAssigningPlayer(player);
    setSelectedTeam("");
    setNewNumber("");
    setErrors({});
  };

  const validateAssignTeam = () => {
    const assignmentErrors = validatePlayerAssignment({
      team_id: selectedTeam,
      player_number: newNumber,
    });

    if (Object.keys(assignmentErrors).length > 0) {
      setErrors(assignmentErrors);
      return false;
    }

    return true;
  };

  const handleAssignPlayer = async (player) => {
    if (!validateAssignTeam()) return;

    const result = await actions.addExistingPlayerToTeam(selectedTeam, {
      player_id: player.id,
      player_number: Number(newNumber),
    });

    if (!result.ok) {
      setErrors({ [result.code]: true });
      return;
    }

    await actions.getPlayers();
    closeAssignTeam();
  };

  const handleStatusChange = async (e, player, newStatus) => {
    e.stopPropagation();

    const actionText = newStatus === "inactive" ? "desactivar" : "activar";

    const confirmed = window.confirm(
      `¿Seguro que deseas ${actionText} a ${player.first_name}?`,
    );

    if (!confirmed) return;

    const result = await actions.updatePlayerStatus(player.id, newStatus);

    if (!result.ok) {
      setErrors({ GENERIC_ERROR: true });
      return;
    }

    setStatusFilter(newStatus);
  };

  const handleStartEdit = (e, player) => {
    e.stopPropagation();
    startEdit(player);
  };

  const activeCount = store.players.filter((p) => p.status === "active").length;

  const inactiveCount = store.players.filter(
    (p) => p.status === "inactive",
  ).length;

  const unassignedCount = store.players.filter((p) => !p.team_id).length;

  if (loadingPlayers) {
    return <p>Cargando jugadoras...</p>;
  }
  return (
    <>
      <PageHeader title="Players" />

      <div className="players-top-actions">
        {!showCreateForm && (
          <Button className="button-primary" onClick={openCreateForm}>
            + Añadir jugadora
          </Button>
        )}
      </div>
      {showCreateForm && (
        <Card className="player-create-card">
          <h4>Nueva jugadora</h4>

          <form onSubmit={handleCreatePlayer} className="form">
            <Input
              value={createFirstName}
              placeholder="Nombre"
              className={errors.FIRST_NAME_REQUIRED ? "input-error" : ""}
              onChange={(e) => {
                setCreateFirstName(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  FIRST_NAME_REQUIRED: false,
                }));
              }}
            />
            {errors.FIRST_NAME_REQUIRED && (
              <p className="form-error">{errorMessages.FIRST_NAME_REQUIRED}</p>
            )}

            <Input
              value={createLastName}
              placeholder="Apellido"
              className={errors.LAST_NAME_REQUIRED ? "input-error" : ""}
              onChange={(e) => {
                setCreateLastName(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  LAST_NAME_REQUIRED: false,
                }));
              }}
            />
            {errors.LAST_NAME_REQUIRED && (
              <p className="form-error">{errorMessages.LAST_NAME_REQUIRED}</p>
            )}
            <select
              value={createTeamId}
              onChange={(e) => {
                setCreateTeamId(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  TEAM_ID_REQUIRED: false,
                  PLAYER_NUMBER_REQUIRED: false,
                  INVALID_PLAYER_NUMBER: false,
                  PLAYER_NUMBER_DUPLICATED: false,
                }));
              }}
            >
              <option value="">Sin categoría</option>
              {store.teams.map((team) => (
                <option key={team.id} value={team.id}>
                  {team.name}
                </option>
              ))}
            </select>
            {(!createTeamId || selectedCreateTeam?.gender === "mixed") && (
              <>
                <select
                  value={createSex}
                  className={
                    errors.SEX_REQUIRED || errors.INVALID_SEX
                      ? "input-error"
                      : ""
                  }
                  onChange={(e) => {
                    setCreateSex(e.target.value);
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
                </select>

                {errors.SEX_REQUIRED && (
                  <p className="form-error">{errorMessages.SEX_REQUIRED}</p>
                )}

                {errors.INVALID_SEX && (
                  <p className="form-error">{errorMessages.INVALID_SEX}</p>
                )}
              </>
            )}

            {createTeamId && (
              <>
                <Input
                  type="number"
                  min="1"
                  max="99"
                  value={createPlayerNumber}
                  placeholder="Número en la categoría"
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
                      setCreatePlayerNumber("");
                      setErrors((prev) => ({
                        ...prev,
                        PLAYER_NUMBER_REQUIRED: false,
                        INVALID_PLAYER_NUMBER: false,
                        PLAYER_NUMBER_DUPLICATED: false,
                      }));
                      return;
                    }

                    if (value.length > 2) return;

                    setCreatePlayerNumber(value);

                    setErrors((prev) => ({
                      ...prev,
                      PLAYER_NUMBER_REQUIRED: false,
                      INVALID_PLAYER_NUMBER: false,
                      PLAYER_NUMBER_DUPLICATED: false,
                    }));
                  }}
                />

                {errors.PLAYER_NUMBER_REQUIRED && (
                  <p className="form-error">
                    {errorMessages.PLAYER_NUMBER_REQUIRED}
                  </p>
                )}

                {errors.INVALID_PLAYER_NUMBER && (
                  <p className="form-error">
                    {errorMessages.INVALID_PLAYER_NUMBER}
                  </p>
                )}

                {errors.PLAYER_NUMBER_DUPLICATED && (
                  <p className="form-error">
                    {errorMessages.PLAYER_NUMBER_DUPLICATED}
                  </p>
                )}
              </>
            )}
            <div className="form-actions">
              <Button
                type="button"
                className="button-secondary"
                onClick={closeCreateForm}
              >
                Cancelar
              </Button>

              <Button
                type="submit"
                className="button-primary"
                disabled={createLoading}
              >
                {createLoading ? "Guardando..." : "Guardar"}
              </Button>
            </div>
          </form>
        </Card>
      )}
      <div>
        {/* 🔎 SEARCH */}
        <div>
          <Input
            placeholder="Buscar jugadora..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        {/* 📌 STATUS FILTER */}
        <div>
          <p>Estado</p>
          <div className="filter-chips">
            <button
              type="button"
              className={statusFilter === "active" ? "chip active" : "chip"}
              onClick={() => handleStatusFilter("active")}
            >
              Activos ({activeCount})
            </button>

            <button
              type="button"
              className={statusFilter === "inactive" ? "chip active" : "chip"}
              onClick={() => handleStatusFilter("inactive")}
            >
              Inactivos ({inactiveCount})
            </button>

            <button
              type="button"
              className={statusFilter === "all" ? "chip active" : "chip"}
              onClick={() => handleStatusFilter("all")}
            >
              Todos ({store.players.length})
            </button>
          </div>
        </div>

        {/* 🏐 TEAM FILTER */}
        <div>
          <p>Categoría</p>
          <div className="filter-chips">
            <button
              type="button"
              className={teamFilter === "" ? "chip active" : "chip"}
              onClick={() => handleTeamFilter("")}
            >
              Todas las categorías ({store.players.length})
            </button>

            <button
              type="button"
              className={teamFilter === "unassigned" ? "chip active" : "chip"}
              onClick={() => handleTeamFilter("unassigned")}
            >
              Sin categoría ({unassignedCount})
            </button>

            {store.teams.map((team) => (
              <button
                type="button"
                key={team.id}
                className={teamFilter === team.id ? "chip active" : "chip"}
                onClick={() => handleTeamFilter(team.id)}
              >
                {team.name}
              </button>
            ))}
          </div>
        </div>
      </div>
      <Card>
        {filteredPlayers.length === 0 ? (
          <div className="empty-state">
            {store.players.length === 0 ? (
              <>
                <p>Aún no tienes jugadores 👀</p>
                <Button onClick={() => navigate("/teams")}>
                  Crear primer jugador
                </Button>
              </>
            ) : (
              <>
                <p>No hay jugadores que coincidan con los filtros</p>
                <Button onClick={clearFilters}>Limpiar filtros</Button>
              </>
            )}
          </div>
        ) : (
          <div className="players-list">
            {filteredPlayers.map((player) => (
              <Card key={player.id} className="player-card">
                {editingPlayer?.id === player.id ? (
                  <>
                    {/* 🔥 MODO EDICIÓN */}
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        savePlayer(e);
                      }}
                      className="player-edit"
                    >
                      <Input
                        value={firstName}
                        className={
                          errors.FIRST_NAME_REQUIRED ? "input-error" : ""
                        }
                        placeholder="Nombre"
                        onChange={(e) => {
                          setFirstName(e.target.value);
                          setErrors((prev) => ({
                            ...prev,
                            FIRST_NAME_REQUIRED: false,
                          }));
                        }}
                      />
                      {errors.FIRST_NAME_REQUIRED && (
                        <p className="form-error">
                          {errorMessages.FIRST_NAME_REQUIRED}
                        </p>
                      )}
                      <Input
                        value={lastName}
                        className={
                          errors.LAST_NAME_REQUIRED ? "input-error" : ""
                        }
                        placeholder="Apellido"
                        onChange={(e) => {
                          setLastName(e.target.value);
                          setErrors((prev) => ({
                            ...prev,
                            LAST_NAME_REQUIRED: false,
                          }));
                        }}
                      />

                      {errors.LAST_NAME_REQUIRED && (
                        <p className="form-error">
                          {errorMessages.LAST_NAME_REQUIRED}
                        </p>
                      )}
                      <Input
                        type="number"
                        min="1"
                        max="99"
                        value={playerNumber}
                        placeholder="Número de jugador"
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

                      {errors.PLAYER_NUMBER_REQUIRED && (
                        <p className="form-error">
                          {errorMessages.PLAYER_NUMBER_REQUIRED}
                        </p>
                      )}

                      {errors.INVALID_PLAYER_NUMBER && (
                        <p className="form-error">
                          {errorMessages.INVALID_PLAYER_NUMBER}
                        </p>
                      )}

                      {errors.PLAYER_NUMBER_DUPLICATED && (
                        <p className="form-error">
                          {errorMessages.PLAYER_NUMBER_DUPLICATED}
                        </p>
                      )}
                      {editingPlayerTeam?.gender === "mixed" && (
                        <select
                          value={sex}
                          className={
                            errors.SEX_REQUIRED || errors.INVALID_SEX
                              ? "input-error"
                              : ""
                          }
                          onChange={(e) => {
                            setSex(e.target.value);
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
                        </select>
                      )}
                      {errors.SEX_REQUIRED && (
                        <p className="form-error">
                          {errorMessages.SEX_REQUIRED}
                        </p>
                      )}

                      {errors.INVALID_SEX && (
                        <p className="form-error">
                          {errorMessages.INVALID_SEX}
                        </p>
                      )}

                      <div className="edit-actions">
                        <Button type="submit" disabled={loading}>
                          {loading ? "Guardando..." : "Guardar"}
                        </Button>

                        <Button
                          type="button"
                          className="button-secondary"
                          onClick={() => {
                            setEditingPlayer(null);
                          }}
                        >
                          Cancelar
                        </Button>
                      </div>
                    </form>
                  </>
                ) : (
                  <>
                    {/* 👇 MODO NORMAL */}
                    <div
                      className="player-header"
                      onClick={() => navigate(`/players/${player.id}`)}
                    >
                      <div className="player-info">
                        <p className="player-name">
                          {player.first_name} {player.last_name}
                        </p>
                        <p className="player-meta">
                          {player.teams?.length > 0 ? (
                            <>
                              {player.teams.map((team, index) => (
                                <span key={team.id}>
                                  #{team.player_number} · {team.name}
                                  {index < player.teams.length - 1 ? " • " : ""}
                                </span>
                              ))}{" "}
                              ·{" "}
                              {player.sex === "female"
                                ? "♀"
                                : player.sex === "male"
                                ? "♂"
                                : "—"}
                            </>
                          ) : (
                            "Sin categoría"
                          )}
                        </p>
                      </div>

                      <div
                        className={`status-badge ${
                          player.status === "active"
                            ? "status-active"
                            : "status-inactive"
                        }`}
                      >
                        {player.status}
                      </div>
                    </div>

                    <div className="player-actions">
                      <Button
                        className="button-secondary"
                        onClick={(e) => handleStartEdit(e, player)}
                      >
                        Editar
                      </Button>

                      {!player.team_id ? (
                        <Button
                          className="button-primary"
                          onClick={(e) => openAssignTeam(e, player)}
                        >
                          Asignar categoría
                        </Button>
                      ) : player.status === "inactive" ? (
                        <Button
                          className="button-success"
                          onClick={(e) =>
                            handleStatusChange(e, player, "active")
                          }
                        >
                          Activar
                        </Button>
                      ) : (
                        <Button
                          className="button-danger"
                          onClick={(e) =>
                            handleStatusChange(e, player, "inactive")
                          }
                        >
                          Desactivar
                        </Button>
                      )}
                    </div>

                    {assigningPlayer?.id === player.id && (
                      <Card className="assign-team-inline">
                        <h4>Asignar categoría</h4>

                        <select
                          value={selectedTeam}
                          onChange={(e) => {
                            setSelectedTeam(e.target.value);
                            setErrors((prev) => ({
                              ...prev,
                              TEAM_ID_REQUIRED: false,
                            }));
                          }}
                          className={
                            errors.TEAM_ID_REQUIRED ? "input-error" : ""
                          }
                        >
                          <option value="">Selecciona categoría</option>
                          {store.teams.map((team) => (
                            <option key={team.id} value={team.id}>
                              {team.name}
                            </option>
                          ))}
                        </select>
                        {errors.TEAM_ID_REQUIRED && (
                          <p className="form-error">
                            {errorMessages.TEAM_ID_REQUIRED}
                          </p>
                        )}

                        <Input
                          type="number"
                          placeholder="Número"
                          value={newNumber}
                          onChange={(e) => {
                            const value = e.target.value;

                            if (value === "") {
                              setNewNumber("");
                              setErrors((prev) => ({
                                ...prev,
                                PLAYER_NUMBER_REQUIRED: false,
                                INVALID_PLAYER_NUMBER: false,
                                PLAYER_NUMBER_DUPLICATED: false,
                              }));
                              return;
                            }

                            if (value.length > 2) return;

                            setNewNumber(value);

                            setErrors((prev) => ({
                              ...prev,
                              PLAYER_NUMBER_REQUIRED: false,
                              INVALID_PLAYER_NUMBER: false,
                              PLAYER_NUMBER_DUPLICATED: false,
                            }));
                          }}
                          className={
                            errors.PLAYER_NUMBER_REQUIRED ||
                            errors.INVALID_PLAYER_NUMBER ||
                            errors.PLAYER_NUMBER_DUPLICATED
                              ? "input-error"
                              : ""
                          }
                        />

                        {errors.PLAYER_NUMBER_REQUIRED && (
                          <p className="form-error">
                            {errorMessages.PLAYER_NUMBER_REQUIRED}
                          </p>
                        )}

                        {errors.INVALID_PLAYER_NUMBER && (
                          <p className="form-error">
                            {errorMessages.INVALID_PLAYER_NUMBER}
                          </p>
                        )}

                        {errors.PLAYER_NUMBER_DUPLICATED && (
                          <p className="form-error">
                            {errorMessages.PLAYER_NUMBER_DUPLICATED}
                          </p>
                        )}

                        <div className="form-actions">
                          <Button
                            className="button-secondary"
                            onClick={closeAssignTeam}
                          >
                            Cancelar
                          </Button>

                          <Button
                            className="button-primary"
                            onClick={() => handleAssignPlayer(player)}
                          >
                            Guardar
                          </Button>
                        </div>
                      </Card>
                    )}
                  </>
                )}
              </Card>
            ))}
          </div>
        )}
      </Card>
    </>
  );
};
