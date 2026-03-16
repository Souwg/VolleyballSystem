import React, { useEffect, useState, useContext } from "react";
import { Context } from "../../store/appContext";
import { useParams } from "react-router-dom";

import { Container } from "../../component/ui/container";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";

export const TeamDetail = () => {
  const { actions } = useContext(Context);
  const { team_id } = useParams();

  const [team, setTeam] = useState(null);
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(true);

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [playerNumber, setPlayerNumber] = useState("");
  const [sex, setSex] = useState("");

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

    const playerData = {
      first_name: firstName,
      last_name: lastName,
      player_number: playerNumber,
      sex: sex,
      team_id: team_id,
    };

    const result = await actions.createPlayer(playerData, team_id);

    if (!result?.ok) {
      alert(result.message);
      return;
    }

    setFirstName("");
    setLastName("");
    setPlayerNumber("");
    setSex("");

    await loadTeamPlayers();
  };

  useEffect(() => {
    loadTeamPlayers();
  }, [team_id]);

  if (loading) {
    return <p>Loading team...</p>;
  }

  return (
    <Container>
      <PageHeader title={team.name} />

      {/* FORMULARIO */}
      <Card>
        <h4>Add Player</h4>

        <form onSubmit={registerPlayer}>
          <Input
            type="text"
            placeholder="First name"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            required
          />

          <Input
            type="text"
            placeholder="Last name"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            required
          />

          <Input
            type="number"
            placeholder="Number"
            value={playerNumber}
            onChange={(e) => setPlayerNumber(e.target.value)}
            required
          />

          <select
            className="select"
            value={sex}
            onChange={(e) => setSex(e.target.value)}
            required
          >
            <option value="">Sex</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
          </select>

          <Button type="submit">Add Player</Button>
        </form>
      </Card>

      {/* LISTA DE JUGADORES */}
      <Card>
        <h4>Players</h4>

        {players.length === 0 ? (
          <p>No hay jugadores registrados en este equipo.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Name</th>
                <th>Sex</th>
                <th>Status</th>
              </tr>
            </thead>

            <tbody>
              {players.map((player) => (
                <tr key={player.id}>
                  <td>{player.player_number}</td>
                  <td>
                    {player.first_name} {player.last_name}
                  </td>
                  <td>{player.sex}</td>
                  <td>{player.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </Container>
  );
};
