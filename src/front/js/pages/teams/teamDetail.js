import React, { useEffect, useState, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";
import { useParams } from "react-router-dom";
import { validatePlayer } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";

import { Container } from "../../component/ui/container";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";

export const TeamDetail = () => {
  const { actions } = useContext(Context);
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
      sex: player.sex,
    });
  };

  const saveEdit = async () => {
    setErrors({});
    if (loadingSubmit) return;
    const newErrors = validatePlayer({
      first_name: editData.first_name,
      last_name: editData.last_name,
      player_number: editData.player_number,
      sex: editData.sex,
      team_id,
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }
    setErrors({});
    setLoadingSubmit(true);
    const result = await actions.updatePlayer(editingPlayerId, {
      ...editData,
      team_id: team_id,
    });

    if (!result?.ok) {
      setErrors({ [result.code]: true });
      setLoadingSubmit(false);
      return;
    }

    setPlayers((prev) =>
      prev.map((p) => (p.id === editingPlayerId ? { ...p, ...editData } : p)),
    );

    setEditingPlayerId(null);
    setLoadingSubmit(false);
  };

  const loadTeamPlayers = async () => {
    try {
      const result = await actions.getTeamPlayers(team_id);

      if (!result) {
        alert("No se pudieron cargar los jugadores");
        return;
      }

      setTeam(result.team);
      setPlayers(result.players);
    } catch (error) {
      console.error("Error loading team players:", error);
    } finally {
      setLoading(false);
    }
  };

  const registerPlayer = async (e) => {
    e.preventDefault();

    if (loadingSubmit) return;

    const newErrors = validatePlayer({
      first_name: firstName,
      last_name: lastName,
      player_number: playerNumber,
      sex,
      team_id,
    });

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

    if (!result?.ok) {
      setErrors({ [result.code]: true });
      setLoadingSubmit(false);
      return;
    }

    setFirstName("");
    setLastName("");
    setPlayerNumber("");
    setSex("");

    await loadTeamPlayers();

    setLoadingSubmit(false);
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
        subtitle="Aquí puedes gestionar los jugadores de esta categoría"
        actions={
          <>
            <Button
              className="button-primary"
              onClick={() => {
                setShowForm(true);
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
            <div className="team-actions">
              <Button
                className="button-danger"
                onClick={async () => {
                  if (!confirm("¿Eliminar esta categoría?")) return;

                  const result = await actions.deleteTeam(team_id);

                  if (!result?.ok) {
                    alert(result.message);
                    return;
                  }

                  navigate("/teams");
                }}
              >
                Eliminar categoría
              </Button>
            </div>
          </>
        }
      />

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
                            #{player.player_number} · {player.sex}
                          </p>
                        </div>

                        <div className="player-status">{player.status}</div>
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
