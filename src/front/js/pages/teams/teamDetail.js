import React, { useEffect, useState, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";
import { useParams } from "react-router-dom";
import {
  validatePlayerProfile,
  validatePlayerAssignment,
} from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";
import { useToast } from "../../../../context/toastContext";

import { Container } from "../../component/ui/container";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";

export const TeamDetail = () => {
  const { actions } = useContext(Context);
  const { showToast } = useToast();
  const { team_id } = useParams();
  const navigate = useNavigate();

  const [team, setTeam] = useState(null);
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(true);

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [playerNumber, setPlayerNumber] = useState("");
  const [sex, setSex] = useState("");

  const [errors, setErrors] = useState({});
  const [loadingSubmit, setLoadingSubmit] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [showAddOptions, setShowAddOptions] = useState(false);
  const [selectedExistingPlayer, setSelectedExistingPlayer] = useState(null);
  const [availablePlayers, setAvailablePlayers] = useState([]);
  const [existingPlayerNumber, setExistingPlayerNumber] = useState("");
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
    setLoadingSubmit(false);
  };

  const loadTeamPlayers = async () => {
    try {
      const result = await actions.getTeamPlayers(team_id);

      if (!result.ok) return;

      setTeam(result.data.team);
      setPlayers(result.data.players);
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

  const registerPlayer = async (e) => {
    e.preventDefault();

    if (loadingSubmit) return;

    const profileErrors = validatePlayerProfile({
      first_name: firstName,
      last_name: lastName,
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
    setLoadingSubmit(true);

    const result = await actions.createPlayer({
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      player_number: Number(playerNumber),
      sex,
      team_id,
    });

    if (!result.ok) {
      setErrors({ [result.code]: true });
      setLoadingSubmit(false);
      return;
    }

    setFirstName("");
    setLastName("");
    setPlayerNumber("");
    setSex(team?.gender === "mixed" ? "" : team.gender);

    await loadTeamPlayers();

    setLoadingSubmit(false);
    setShowForm(false);
  };

  const handleDeleteTeam = async () => {
    const confirmed = window.confirm(
      `¿Seguro que deseas eliminar la categoría ${team.name}?`,
    );

    if (!confirmed) return;

    const result = await actions.deleteTeam(team_id);

    if (!result.ok) {
      showToast("No se pudo eliminar la categoría", "error");
      return;
    }

    navigate("/teams");
  };

  const handleRemovePlayer = async (e, player) => {
    e.stopPropagation();

    const confirmed = window.confirm(
      `¿Quitar a ${player.first_name} de ${team.name}?`,
    );

    if (!confirmed) return;

    const result = await actions.removePlayerFromTeam(team_id, player.id);

    if (!result.ok) {
      showToast("No se pudo quitar la jugadora", "error");
      return;
    }

    await loadTeamPlayers();

    await actions.getPlayers();
  };

  const handleLoadExistingPlayers = async () => {
    const result = await actions.getPlayers();

    if (!result.ok || !result.data.players.length) {
      showToast("No hay jugadores existentes en el club", "info");
      return;
    }

    const filteredPlayers = result.data.players.filter((p) => {
      const alreadyInTeam = players.some((tp) => tp.id === p.id);

      const validGender = team.gender === "mixed" || p.sex === team.gender;

      return !alreadyInTeam && validGender;
    });

    if (!filteredPlayers.length) {
      showToast("Todos los jugadores ya están en este equipo", "info");
      return;
    }

    setAvailablePlayers(filteredPlayers);
    setShowAddOptions(false);
    setShowForm(false);
  };

  useEffect(() => {
    loadTeamPlayers();
  }, [team_id]);

  if (loading) {
    return <p>Loading team...</p>;
  }

  return (
    <>
      <PageHeader
        title={team.name}
        subtitle={`Categoría ${
          team.gender === "female"
            ? "Femenina"
            : team.gender === "male"
            ? "Masculina"
            : "Mixta"
        }`}
        actions={
          <>
            <Button
              className="button-primary"
              onClick={() => {
                setShowAddOptions(true);
                setErrors({});
              }}
            >
              + Añadir jugador
            </Button>
            <Button
              className="button-secondary"
              onClick={() => navigate(`/teams/${team_id}/trainings`)}
            >
              Trainings
            </Button>
            <Button
              variant="secondary"
              onClick={() => navigate(`/teams/${team.id}/matches`)}
            >
              Match Sessions
            </Button>
            <div className="team-actions">
              <Button className="button-danger" onClick={handleDeleteTeam}>
                Eliminar categoría
              </Button>
            </div>
          </>
        }
      />
      {showAddOptions && (
        <Card className="add-player-options">
          <h4>Añadir jugador</h4>

          <Button
            className="button-secondary"
            onClick={() => {
              setShowAddOptions(false);
              setAvailablePlayers([]);
              setSelectedExistingPlayer(null);
              setExistingPlayerNumber("");
              setShowForm(true);
            }}
          >
            Crear jugador nuevo
          </Button>

          <Button
            className="button-primary"
            onClick={handleLoadExistingPlayers}
          >
            Agregar existente
          </Button>

          <Button
            className="button-secondary"
            onClick={() => setShowAddOptions(false)}
          >
            Cancelar
          </Button>
        </Card>
      )}
      {availablePlayers.length > 0 && (
        <Card>
          <h4>Selecciona jugador</h4>

          <div className="players-list">
            {availablePlayers.map((player) => (
              <Card
                key={player.id}
                className="player-card selectable-player"
                onClick={() => {
                  setSelectedExistingPlayer(player);
                  setAvailablePlayers([]);
                }}
              >
                <p className="player-name">
                  {player.first_name} {player.last_name}
                </p>

                {player.teams?.length > 0 && (
                  <p className="player-meta">
                    Actualmente en:{" "}
                    {player.teams.map((team) => team.name).join(" · ")}
                  </p>
                )}
              </Card>
            ))}
          </div>

          <Button
            className="button-secondary"
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
                  {team.name} · #{team.player_number}
                </div>
              ))}
            </div>
          )}
          <Input
            type="number"
            placeholder="Número en este equipo"
            value={existingPlayerNumber}
            onChange={(e) => {
              const value = e.target.value;

              if (value === "") {
                setExistingPlayerNumber("");
                return;
              }

              if (value.length > 2) return;
              if (Number(value) <= 0) return;

              setExistingPlayerNumber(value);
            }}
          />
          {errors.PLAYER_NUMBER_REQUIRED && (
            <p className="form-error">{errorMessages.PLAYER_NUMBER_REQUIRED}</p>
          )}

          {errors.PLAYER_NUMBER_DUPLICATED && (
            <p className="form-error">
              {errorMessages.PLAYER_NUMBER_DUPLICATED}
            </p>
          )}

          <div className="form-actions">
            <Button
              className="button-secondary"
              onClick={() => {
                setSelectedExistingPlayer(null);
                setExistingPlayerNumber("");
              }}
            >
              Cancelar
            </Button>

            <Button
              className="button-primary"
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

                setSelectedExistingPlayer(null);
                setExistingPlayerNumber("");
                await loadTeamPlayers();
              }}
            >
              Guardar
            </Button>
          </div>
        </Card>
      )}
      {showForm && (
        <Card>
          <h4>Nuevo jugador</h4>

          <form onSubmit={registerPlayer} className="form">
            <Input
              value={firstName}
              className={errors.FIRST_NAME_REQUIRED ? "input-error" : ""}
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
              <p className="form-error">{errorMessages.FIRST_NAME_REQUIRED}</p>
            )}

            <Input
              value={lastName}
              className={errors.LAST_NAME_REQUIRED ? "input-error" : ""}
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
              <p className="form-error">{errorMessages.LAST_NAME_REQUIRED}</p>
            )}

            <Input
              type="number"
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
              placeholder="Número de jugador"
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
            {team?.gender === "mixed" && (
              <select
                className={`select ${
                  errors.SEX_REQUIRED || errors.INVALID_SEX ? "input-error" : ""
                }`}
                value={sex}
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
              <p className="form-error">{errorMessages.SEX_REQUIRED}</p>
            )}
            <div className="form-actions">
              <Button
                type="button"
                className="button-secondary"
                onClick={() => {
                  setShowForm(false);
                  setErrors({});
                }}
              >
                Cancelar
              </Button>

              <Button
                type="submit"
                className="button-primary"
                disabled={loadingSubmit}
              >
                {loadingSubmit ? "Guardando..." : "Guardar"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* LISTA DE JUGADORES */}
      <Card>
        <h4>Jugadores</h4>

        {players.length === 0 ? (
          <p>No hay jugadores registrados en esta categoría.</p>
        ) : (
          <div className="players-list">
            {players.map((player) => (
              <Card key={player.id} className="player-card">
                <div className="player-row">
                  {editingPlayerId === player.id ? (
                    //MODO EDICIÓN
                    <div className="player-edit">
                      <Input
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
                      {errors.FIRST_NAME_REQUIRED && (
                        <p className="form-error">
                          {errorMessages.FIRST_NAME_REQUIRED}
                        </p>
                      )}

                      <Input
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
                      {errors.LAST_NAME_REQUIRED && (
                        <p className="form-error">
                          {errorMessages.LAST_NAME_REQUIRED}
                        </p>
                      )}
                      <Input
                        type="number"
                        value={editData.player_number}
                        className={
                          errors.PLAYER_NUMBER_REQUIRED ||
                          errors.INVALID_PLAYER_NUMBER
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
                      {team?.gender === "mixed" && (
                        <select
                          value={editData.sex}
                          className={errors.SEX_REQUIRED ? "input-error" : ""}
                          onChange={(e) => {
                            setEditData({ ...editData, sex: e.target.value });
                            setErrors((prev) => ({
                              ...prev,
                              SEX_REQUIRED: false,
                            }));
                          }}
                        >
                          <option value="male">Masculino</option>
                          <option value="female">Femenino</option>
                        </select>
                      )}
                      {errors.SEX_REQUIRED && (
                        <p className="form-error">
                          {errorMessages.SEX_REQUIRED}
                        </p>
                      )}
                      <Button className="button-primary" onClick={saveEdit}>
                        💾
                      </Button>

                      <Button
                        className="button-secondary"
                        onClick={() => {
                          setEditingPlayerId(null);
                          setErrors({});
                        }}
                      >
                        ❌
                      </Button>
                    </div>
                  ) : (
                    //MODO NORMAL
                    <>
                      <div
                        className="player-header"
                        onClick={() => startEdit(player)}
                      >
                        <div className="player-info">
                          <p className="player-name">
                            {player.first_name} {player.last_name}
                          </p>
                          <p className="player-meta">
                            #{player.player_number} ·{" "}
                            {player.sex === "female" ? "Femenino" : "Masculino"}
                          </p>
                        </div>

                        <div className="player-status">{player.status}</div>
                        <Button
                          className="button-danger button-small"
                          onClick={(e) => handleRemovePlayer(e, player)}
                        >
                          Quitar
                        </Button>
                      </div>
                    </>
                  )}
                </div>
              </Card>
            ))}
          </div>
        )}
      </Card>
    </>
  );
};
