import React, { useEffect, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { Context } from "../../store/appContext";
import { Card } from "../../component/ui/card";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
import { Button } from "../../component/ui/button";
import { validatePlayer } from "../../utils/validators";
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
  const [statusFilter, setStatusFilter] = useState("active");
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!store.token) return;

    actions.getPlayers();
    actions.getTeams();
  }, [store.token]);

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

    const newErrors = validatePlayer({
      first_name: firstName,
      last_name: lastName,
      player_number: playerNumber,
      sex,
      team_id: editingPlayer.team_id,
    });

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

    if (!result?.ok) {
      setErrors({ [result.code]: true });
      setLoading(false); // 🔥 TAMBIÉN AQUÍ
      return;
    }

    setLoading(false);
    setEditingPlayer(null);
  };

  const getTeamName = (teamId) => {
    const team = store.teams.find((t) => t.id === teamId);
    return team ? team.name : "Unknown";
  };

  const filteredPlayers = store.players.filter((player) => {
    const fullName = `${player.first_name} ${player.last_name}`.toLowerCase();
    const matchesSearch = fullName.includes(searchTerm.toLowerCase());
    const matchesTeam = teamFilter === "" || player.team_id === teamFilter;
    const matchesStatus =
      statusFilter === "all" || player.status === statusFilter;

    return matchesSearch && matchesTeam && matchesStatus;
  });

  return (
    <>
      <PageHeader title="Players" />

      <div>
        <div>
          <Input
            placeholder="Search player..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div>
          <div className="filter-chips">
            <button
              className={statusFilter === "active" ? "chip active" : "chip"}
              onClick={() => setStatusFilter("active")}
            >
              Activos
            </button>

            <button
              className={statusFilter === "inactive" ? "chip active" : "chip"}
              onClick={() => setStatusFilter("inactive")}
            >
              Inactivos
            </button>

            <button
              className={statusFilter === "all" ? "chip active" : "chip"}
              onClick={() => setStatusFilter("all")}
            >
              Todos
            </button>
          </div>

          {/* 🏐 TEAM FILTER */}
          <p className="filter-label">Equipo</p>
          <div className="filter-chips">
            <button
              className={teamFilter === "" ? "chip active" : "chip"}
              onClick={() => setTeamFilter("")}
            >
              Todos
            </button>

            {store.teams.map((team) => (
              <button
                key={team.id}
                className={teamFilter === team.id ? "chip active" : "chip"}
                onClick={() => setTeamFilter(team.id)}
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
                <p>No hay jugadores en este equipo 😕</p>
                <Button onClick={() => setTeamFilter("")}>Ver todos</Button>
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
                        <option value="male">Male</option>
                        <option value="female">Female</option>
                      </select>

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
                          #{player.player_number} ·{" "}
                          {getTeamName(player.team_id)}
                        </p>
                      </div>

                      <div
                        className={`status-badge ${
                          player.status === "active"
                            ? "status-active"
                            : player.status === "injured"
                            ? "status-injured"
                            : "status-inactive"
                        }`}
                      >
                        {player.status}
                      </div>
                    </div>

                    <div className="player-actions">
                      <Button
                        className="button-secondary"
                        onClick={(e) => {
                          e.stopPropagation();
                          startEdit(player);
                        }}
                      >
                        Editar
                      </Button>
                      {player.status === "inactive" ? (
                        <Button
                          className="button-success"
                          onClick={async (e) => {
                            e.stopPropagation();
                            const result = await actions.updatePlayerStatus(
                              player.id,
                              "active",
                            );

                            if (!result?.ok) {
                              setErrors({ GENERIC_ERROR: true });
                              return;
                            }

                            setStatusFilter("active");
                          }}
                        >
                          Activar
                        </Button>
                      ) : (
                        <Button
                          className="button-danger"
                          onClick={async (e) => {
                            e.stopPropagation();
                            const result = await actions.updatePlayerStatus(
                              player.id,
                              "inactive",
                            );

                            if (!result?.ok) {
                              setErrors({ GENERIC_ERROR: true });
                              return;
                            }

                            setStatusFilter("inactive");
                          }}
                        >
                          Desactivar
                        </Button>
                      )}
                    </div>
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
