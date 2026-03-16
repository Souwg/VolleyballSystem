import React, { useEffect, useContext } from "react";
import { useState } from "react";
import { Context } from "../../store/appContext";
import { Container } from "../../component/ui/container";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
import { Button } from "../../component/ui/button";

export const Players = () => {
  const { store, actions } = useContext(Context);
  const [editingPlayer, setEditingPlayer] = useState(null);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [playerNumber, setPlayerNumber] = useState("");
  const [sex, setSex] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [teamFilter, setTeamFilter] = useState("");

  useEffect(() => {
    if (!store.token) return;

    actions.getPlayers();
    actions.getTeams();
  }, [store.token]);

  const startEdit = (player) => {
    setEditingPlayer(player);
    setFirstName(player.first_name);
    setLastName(player.last_name);
    setPlayerNumber(player.player_number);
    setSex(player.sex);
  };

  const savePlayer = async (e) => {
    e.preventDefault();
    const playerData = {
      first_name: firstName,
      last_name: lastName,
      player_number: playerNumber,
      sex: sex,
      team_id: editingPlayer.team_id,
    };
    const result = await actions.updatePlayer(editingPlayer.id, playerData);
    if (!result?.ok) {
      alert(result.message);
      return;
    }
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
    return matchesSearch && matchesTeam;
  });

  return (
    <Container>
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
          <select
            className="select"
            value={teamFilter}
            onChange={(e) => setTeamFilter(e.target.value)}
          >
            <option value="">All teams</option>

            {store.teams.map((team) => (
              <option key={team.id} value={team.id}>
                {team.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {editingPlayer && (
        <form onSubmit={savePlayer}>
          <h5>Edit Player</h5>

          <div>
            <div>
              <Input
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
              />
            </div>

            <div>
              <Input
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
              />
            </div>

            <div>
              <Input
                type="number"
                value={playerNumber}
                onChange={(e) => setPlayerNumber(e.target.value)}
              />
            </div>

            <div>
              <select value={sex} onChange={(e) => setSex(e.target.value)}>
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </div>

            <div>
              <Button type="submit">Save</Button>
            </div>
          </div>
        </form>
      )}

      {store.players.length === 0 ? (
        <div>No hay jugadores registrados.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Name</th>
              <th>Team</th>
              <th>Status</th>
              <th>Edit</th>
              <th>Delete</th>
            </tr>
          </thead>

          <tbody>
            {filteredPlayers.map((player) => (
              <tr key={player.id}>
                <td>{player.player_number}</td>

                <td>
                  {player.first_name} {player.last_name}
                </td>

                <td>{getTeamName(player.team_id)}</td>

                <td>{player.status}</td>

                <td>
                  <Button onClick={() => startEdit(player)}>Edit</Button>
                </td>

                <td>
                  <Button
                    onClick={async () => {
                      if (!confirm("¿Eliminar este jugador?")) return;

                      const result = await actions.deletePlayer(player.id);

                      if (!result?.ok) {
                        alert(result.message);
                        return;
                      }

                      await actions.getPlayers();
                    }}
                  >
                    Delete
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Container>
  );
};
