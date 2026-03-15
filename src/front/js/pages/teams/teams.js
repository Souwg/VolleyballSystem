import React, { useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";
import { Container } from "../../component/ui/container";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";

export const Teams = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();
  const [teamName, setTeamName] = useState("");

  useEffect(() => {
    if (!store.token) return;

    actions.getTeams();
  }, [store.token]);

  const handleCreateTeam = async (e) => {
    e.preventDefault();

    const cleanName = teamName.trim();

    if (!cleanName) {
      alert("Debes escribir el nombre del equipo");
      return;
    }

    const result = await actions.createTeam(cleanName);

    if (!result?.ok) {
      alert(result?.message || "No se pudo crear el equipo");
      return;
    }

    setTeamName("");
  };

  return (
    <Container>
      <PageHeader title="Teamssssssssssssss" />

      <form onSubmit={handleCreateTeam}>
        <div>
          <div>
            <Input
              type="text"
              placeholder="Ej: Sub12, Juvenil, Adulto..."
              value={teamName}
              onChange={(e) => setTeamName(e.target.value)}
            />
          </div>

          <Button type="submit">Create Team</Button>
        </div>
      </form>

      {store.teams.length === 0 ? (
        <div>No hay equipos registrados todavía.</div>
      ) : (
        <div className="teams-grid">
          {store.teams.map((team) => (
            <Card key={team.id} onClick={() => navigate(`/teams/${team.id}`)}>
              <div>
                <div>
                  <h5>{team.name}</h5>
                  <p>Team ID: {team.id}</p>
                </div>

                <Button
                  onClick={async (e) => {
                    e.stopPropagation();

                    if (!confirm("¿Eliminar este equipo?")) return;

                    const result = await actions.deleteTeam(team.id);

                    if (!result?.ok) {
                      alert(result.message);
                    }
                  }}
                >
                  Delete
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </Container>
  );
};
