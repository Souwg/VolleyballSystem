import React, { useEffect, useState, useContext, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";

const STEPS = ["Convocadas", "Estado", "Participación", "Stats"];

export const MatchDetail = () => {
  const { actions } = useContext(Context);
  const { match_id } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [match, setMatch] = useState(null);
  const [roster, setRoster] = useState([]);
  const [currentStep, setCurrentStep] = useState(0);

  const [teamPlayers, setTeamPlayers] = useState([]);
  const [selectedPlayers, setSelectedPlayers] = useState([]);
  const MATCH_STATES = ["present", "late", "absent", "injured"];

  useEffect(() => {
    loadMatch();
  }, [match_id]);

  const loadMatch = async () => {
    setLoading(true);

    const matchResult = await actions.getMatchDetail(match_id);

    if (!matchResult.ok) {
      setLoading(false);
      return;
    }

    const matchData = matchResult.data.match;

    setMatch(matchData);

    const playersResult = await actions.getTeamPlayersOnly(matchData.team_id);

    if (playersResult.ok) {
      setTeamPlayers(playersResult.data || []);
    }

    const rosterResult = await actions.getMatchRoster(match_id);

    if (rosterResult.ok) {
      setRoster(rosterResult.data || []);
      setSelectedPlayers((rosterResult.data || []).map((p) => p.player_id));
    }

    setLoading(false);
  };

  const togglePlayerSelection = (player) => {
    setSelectedPlayers((prev) => {
      const exists = prev.includes(player.id);

      if (exists) {
        return prev.filter((id) => id !== player.id);
      }

      return [...prev, player.id];
    });
  };

  const toggleMatchStatus = (matchPlayerId) => {
    setRoster((prev) =>
      prev.map((player) => {
        if (player.match_player_id !== matchPlayerId) return player;

        const currentIndex = MATCH_STATES.indexOf(
          player.attendance_status || "present",
        );

        const nextStatus =
          MATCH_STATES[(currentIndex + 1) % MATCH_STATES.length];

        return {
          ...player,
          attendance_status: nextStatus,
        };
      }),
    );
  };

  const toggleDidPlay = (matchPlayerId) => {
    setRoster((prev) =>
      prev.map((player) => {
        if (player.match_player_id !== matchPlayerId) return player;

        return {
          ...player,
          did_play: !player.did_play,
        };
      }),
    );
  };

  const saveStepOne = async () => {
    const playersPayload = teamPlayers
      .filter((p) => selectedPlayers.includes(p.id))
      .map((p) => ({
        player_id: p.id,
        player_number: p.player_number,
      }));

    const result = await actions.saveMatchRoster(match_id, playersPayload);

    if (result?.ok) {
      await loadMatch();
      setCurrentStep(1);
    }
  };

  const saveStepTwo = async () => {
    const playersPayload = roster.map((player) => ({
      match_player_id: player.match_player_id,
      attendance_status: player.attendance_status || "present",
    }));

    const result = await actions.saveMatchStatus(match_id, playersPayload);

    if (result?.ok) {
      await loadMatch();
      setCurrentStep(2);
    }
  };

  const saveStepThree = async () => {
    const playersPayload = roster
      .filter((player) => player.attendance_status === "present")
      .map((player) => ({
        match_player_id: player.match_player_id,
        did_play: player.did_play || false,
      }));

    const result = await actions.saveMatchParticipation(
      match_id,
      playersPayload,
    );

    if (result?.ok) {
      await loadMatch();
      setCurrentStep(3);
    }
  };

  const filteredPlayers = useMemo(() => {
    if (currentStep === 0) return roster;

    if (currentStep === 1) {
      return roster;
    }

    if (currentStep === 2) {
      return roster.filter((p) => p.attendance_status === "present");
    }

    if (currentStep === 3) {
      return roster.filter(
        (p) => p.attendance_status === "present" && p.did_play,
      );
    }

    return roster;
  }, [roster, currentStep]);

  const maxUnlockedStep = useMemo(() => {
    if (roster.length === 0) return 0;

    const hasParticipation = roster.some((p) => p.did_play);
    const allHaveStatus = roster.every((p) => p.attendance_status);

    if (!allHaveStatus) return 1;
    if (!hasParticipation) return 2;

    return 3;
  }, [roster]);

  if (loading) {
    return (
      <div className="page-container">
        <PageHeader title="Partido" subtitle="Cargando partido..." />
      </div>
    );
  }

  return (
    <div className="page-container">
      <PageHeader
        title={`vs ${match?.opponent_name || "Scrimmage"}`}
        subtitle={match?.date}
      />

      {/* Stepper */}
      <div className="stepper-mobile mb-4">
        {STEPS.map((step, index) => {
          const isLocked = index > maxUnlockedStep;

          return (
            <Button
              key={step}
              variant={currentStep === index ? "primary" : "secondary"}
              disabled={isLocked}
              onClick={() => {
                if (isLocked) return;
                setCurrentStep(index);
              }}
              className={`me-2 mb-2 ${isLocked ? "opacity-50" : ""}`}
            >
              {index + 1}. {step}
            </Button>
          );
        })}
      </div>

      {/* Players list */}
      {currentStep === 0
        ? teamPlayers.map((player) => {
            const isSelected = selectedPlayers.includes(player.id);

            return (
              <Card
                key={player.id}
                className={`mb-3 cursor-pointer ${
                  isSelected ? "border-primary" : ""
                }`}
                onClick={() => togglePlayerSelection(player)}
              >
                <h3>
                  #{player.player_number} {player.first_name} {player.last_name}
                </h3>

                <p>{isSelected ? "✅ Convocada" : "Tap para convocar"}</p>
              </Card>
            );
          })
        : filteredPlayers.map((player) => (
            <Card
              key={player.match_player_id}
              className="mb-3 cursor-pointer"
              onClick={() => {
                if (currentStep === 1) {
                  toggleMatchStatus(player.match_player_id);
                }

                if (currentStep === 2) {
                  toggleDidPlay(player.match_player_id);
                }

                if (currentStep === 3) {
                  navigate(`/match-players/${player.match_player_id}/stats`);
                }
              }}
            >
              <h3>
                #{player.player_number} {player.first_name} {player.last_name}
              </h3>

              {currentStep >= 1 && (
                <p>Estado: {player.attendance_status || "present"}</p>
              )}

              {currentStep >= 2 && (
                <p>
                  Participación: {player.did_play ? "✅ Sí jugó" : "⭕ No jugó"}
                </p>
              )}
            </Card>
          ))}

      {/* Footer CTA */}
      <div className="mt-4 d-flex gap-2">
        {currentStep > 0 && (
          <Button
            variant="secondary"
            onClick={() => setCurrentStep((prev) => prev - 1)}
          >
            Atrás
          </Button>
        )}

        {currentStep === 0 ? (
          <Button variant="primary" onClick={saveStepOne}>
            Guardar convocadas
          </Button>
        ) : currentStep === 1 ? (
          <Button variant="primary" onClick={saveStepTwo}>
            Guardar estado
          </Button>
        ) : currentStep === 2 ? (
          <Button variant="primary" onClick={saveStepThree}>
            Guardar participación
          </Button>
        ) : null}
      </div>
    </div>
  );
};
