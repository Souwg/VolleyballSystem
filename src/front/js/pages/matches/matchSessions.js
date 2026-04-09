import React, { useEffect, useState, useContext } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";

export const MatchSessions = () => {
  const { store, actions } = useContext(Context);
  const { team_id } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadMatches();
  }, [team_id]);

  const loadMatches = async () => {
    setLoading(true);

    const result = await actions.getTeamMatches(team_id);

    if (!result.ok) {
      setLoading(false);
      return;
    }

    setLoading(false);
  };

  if (loading) {
    return (
      <div className="page-container">
        <PageHeader title="Partidos" subtitle="Cargando partidos..." />
      </div>
    );
  }

  return (
    <div className="page-container">
      <PageHeader
        title="Match Sessions"
        subtitle="Gestiona partidos y rendimiento"
      />

      <div className="mb-4">
        <Button
          variant="primary"
          onClick={() => navigate(`/teams/${team_id}/matches/new`)}
        >
          + Crear partido
        </Button>
      </div>

      {store.matches.length === 0 ? (
        <Card>
          <p>No hay partidos creados todavía</p>
        </Card>
      ) : (
        store.matches.map((match) => (
          <Card
            key={match.id}
            className="mb-3 cursor-pointer"
            onClick={() => navigate(`/matches/${match.id}`)}
          >
            <h3>vs {match.opponent_name || "Scrimmage interno"}</h3>

            <p>{match.date}</p>

            <p>{match.match_type}</p>
          </Card>
        ))
      )}
    </div>
  );
};
