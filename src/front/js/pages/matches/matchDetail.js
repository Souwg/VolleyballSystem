import React, { useEffect, useState, useContext, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { errorMessages } from "../../utils/errorMessages";

const STEPS = ["Convocadas", "Estado"];
const MATCH_STATUS_LABELS = {
  present: "Presente",
  late: "Llegó tarde",
  absent: "Ausente",
  injured: "Lesionada",
};
const PLAYABLE_STATUSES = ["present", "late"];

const POSITION_LABELS = {
  setter: "Armadora",
  outside: "Punta",
  middle: "Central",
  opposite: "Opuesto",
  libero: "Líbero",
};

const POSITION_OPTIONS = [
  { value: "setter", label: "Armadora" },
  { value: "outside", label: "Punta" },
  { value: "middle", label: "Central" },
  { value: "opposite", label: "Opuesto" },
  { value: "libero", label: "Líbero" },
];

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

  const [homeSets, setHomeSets] = useState(0);
  const [opponentSets, setOpponentSets] = useState(0);
  const [savingResult, setSavingResult] = useState(false);
  const [showResultEditor, setShowResultEditor] = useState(false);
  const [statusDirty, setStatusDirty] = useState(false);
  const [rosterError, setRosterError] = useState("");
  const [statusError, setStatusError] = useState("");
  const [savingRoster, setSavingRoster] = useState(false);
  const [savingStatus, setSavingStatus] = useState(false);

  const totalSets = homeSets + opponentSets;
  const disableHomeIncrease = homeSets >= 3 || totalSets >= 5;
  const disableOpponentIncrease = opponentSets >= 3 || totalSets >= 5;

  useEffect(() => {
    loadMatch();
  }, [match_id]);

  const loadMatch = async () => {
    setLoading(true);

    const matchResult = await actions.getMatchDetail(match_id);

    if (!matchResult.ok) {
      setStatusDirty(false);
      setLoading(false);
      return;
    }

    const matchData = matchResult.data.match;

    setMatch(matchData);
    setHomeSets(matchData.home_sets || 0);
    setOpponentSets(matchData.opponent_sets || 0);
    setCurrentStep(Math.min(matchData.match_step || 0, 1));

    const rosterResult = await actions.getMatchRoster(match_id);

    if (rosterResult.ok) {
      const rosterData = rosterResult.data || [];

      const normalizedRoster = rosterData.map((player) => ({
        ...player,
        position: player.position || player.main_position || "",
      }));

      setRoster(normalizedRoster);
      setTeamPlayers(normalizedRoster);
      setSelectedPlayers(
        rosterData.filter((p) => p.is_called).map((p) => p.player_id),
      );
    }

    setLoading(false);
  };

  const togglePlayerSelection = (player) => {
    setRosterError("");

    setSelectedPlayers((prev) => {
      const exists = prev.includes(player.player_id);

      if (exists) {
        return prev.filter((id) => id !== player.player_id);
      }

      return [...prev, player.player_id];
    });
  };

  const toggleMatchStatus = (matchPlayerId) => {
    setStatusDirty(true);
    setStatusError("");

    setRoster((prev) =>
      prev.map((player) => {
        if (player.match_player_id !== matchPlayerId) return player;

        const currentIndex = MATCH_STATES.indexOf(player.attendance_status);
        const nextStatus =
          MATCH_STATES[(currentIndex + 1) % MATCH_STATES.length];

        const isPlayable = nextStatus === "present" || nextStatus === "late";

        return {
          ...player,
          attendance_status: nextStatus,
          did_play: isPlayable ? player.did_play : false,
          position: player.position,
        };
      }),
    );
  };

  const updatePlayerPosition = (matchPlayerId, newPosition) => {
    setRoster((prev) =>
      prev.map((player) => {
        if (player.match_player_id !== matchPlayerId) return player;

        return {
          ...player,
          position: newPosition,
        };
      }),
    );
  };

  const saveStepOne = async () => {
    if (savingRoster) return;

    if (selectedPlayers.length === 0) {
      setRosterError(errorMessages.MATCH_ROSTER_REQUIRED);
      return;
    }

    setRosterError("");
    setSavingRoster(true);

    const playersPayload = teamPlayers
      .filter((p) => selectedPlayers.includes(p.player_id))
      .map((p) => ({
        player_id: p.player_id,
        player_number: p.player_number,
      }));

    const result = await actions.saveMatchRoster(match_id, playersPayload);

    setSavingRoster(false);

    if (!result?.ok) return;

    setCurrentStep(1);
    await loadMatch();
  };

  const saveStepTwo = async () => {
    if (savingStatus) return;

    const calledPlayers = roster.filter((p) => p.is_called);

    const hasMissingStatus = calledPlayers.some((p) => !p.attendance_status);

    if (hasMissingStatus) {
      setStatusError(errorMessages.MATCH_STATUS_REQUIRED);
      return;
    }

    setStatusError("");
    setSavingStatus(true);

    const playersPayload = calledPlayers.map((player) => ({
      match_player_id: player.match_player_id,
      attendance_status: player.attendance_status,
      position: player.position || player.main_position || null,
    }));

    const result = await actions.saveMatchStatus(match_id, playersPayload);

    setSavingStatus(false);

    if (!result?.ok) return;

    setMatch((prev) => ({
      ...prev,
      match_step: 2,
    }));

    setStatusDirty(false);
    setCurrentStep(1);
    await loadMatch();
  };

  const saveMatchResult = async () => {
    setSavingResult(true);

    const result = await actions.saveMatchResult(match_id, {
      home_sets: homeSets,
      opponent_sets: opponentSets,
    });

    setSavingResult(false);

    if (!result?.ok) return;

    setShowResultEditor(false);
    await loadMatch();
  };

  const filteredPlayers = useMemo(() => {
    if (currentStep === 0) return roster;

    if (currentStep === 1) {
      return roster.filter((p) => p.is_called);
    }

    return [];
  }, [roster, currentStep]);

  const hasUnsavedRosterChanges = useMemo(() => {
    const savedIds = roster
      .filter((p) => p.is_called)
      .map((p) => p.player_id)
      .sort();

    const selectedIds = [...selectedPlayers].sort();

    return JSON.stringify(savedIds) !== JSON.stringify(selectedIds);
  }, [roster, selectedPlayers]);

  const maxUnlockedStep = Math.min(match?.match_step ?? 0, 1);

  const canOpenLiveMode = (match?.match_step ?? 0) >= 2;

  const hasPlayersWhoPlayed = roster.some(
    (player) =>
      player.is_called &&
      PLAYABLE_STATUSES.includes(player.attendance_status) &&
      player.did_play,
  );

  const initialPlayersOnCourt = roster.filter(
    (player) =>
      player.is_called &&
      PLAYABLE_STATUSES.includes(player.attendance_status) &&
      player.did_play &&
      player.is_on_court,
  );

  const hasInitialSix = initialPlayersOnCourt.length === 6;

  const statusSaved = (match?.match_step ?? 0) >= 2;
  const isMatchCompleted = match?.is_completed;

  const getResultButtonText = () => {
    if (showResultEditor) return "Ocultar resultado";
    if (isMatchCompleted) return "Editar resultado";

    return "Cerrar partido";
  };

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
      <Card className="mb-4">
        <div className="d-flex justify-content-between align-items-center gap-3">
          <div>
            <small className="text-muted">Resultado</small>

            <h2 className="mb-1">
              {homeSets} - {opponentSets}
            </h2>

            <p className="mb-0">
              {match?.result === "win"
                ? "🏆 Victoria"
                : match?.result === "loss"
                ? "❌ Derrota"
                : "Pendiente"}
            </p>
          </div>

          <Button
            variant={isMatchCompleted ? "secondary" : "primary"}
            onClick={() => setShowResultEditor((prev) => !prev)}
          >
            {getResultButtonText()}
          </Button>
        </div>

        {(match?.match_step ?? 0) < 3 && (
          <small className="text-muted d-block mt-2">
            Puedes guardar solo el resultado. Para usar modo en vivo y
            estadísticas, completa la preparación del partido.
          </small>
        )}
      </Card>

      {showResultEditor && (
        <Card className="mb-4">
          <h3>{isMatchCompleted ? "Editar resultado" : "Cerrar partido"}</h3>

          <div className="d-flex justify-content-between align-items-center my-3">
            <div>
              <p className="mb-1">Tu equipo</p>
              <h2>{homeSets}</h2>
            </div>

            <div className="text-center">
              <small>SETS</small>
              <h2>-</h2>
            </div>

            <div className="text-end">
              <p className="mb-1">{match?.opponent_name}</p>
              <h2>{opponentSets}</h2>
            </div>
          </div>

          <div className="d-flex gap-2 flex-wrap">
            <Button
              onClick={() => setHomeSets((prev) => Math.max(0, prev - 1))}
            >
              - Tu equipo
            </Button>

            <Button
              onClick={() => setHomeSets((prev) => prev + 1)}
              disabled={disableHomeIncrease}
            >
              + Tu equipo
            </Button>

            <Button
              onClick={() => setOpponentSets((prev) => Math.max(0, prev - 1))}
            >
              - Rival
            </Button>

            <Button
              onClick={() => setOpponentSets((prev) => prev + 1)}
              disabled={disableOpponentIncrease}
            >
              + Rival
            </Button>

            <Button
              variant="primary"
              onClick={saveMatchResult}
              disabled={savingResult}
            >
              {savingResult ? "Guardando..." : "Guardar resultado"}
            </Button>
          </div>
        </Card>
      )}
      <Card className="mb-4">
        <h3>Estadísticas</h3>

        {canOpenLiveMode ? (
          <>
            <p className="text-muted">
              {hasInitialSix
                ? "El partido está listo para capturar acciones y registrar cambios en vivo."
                : "El partido está listo para iniciar el modo en vivo. Primero seleccionarás las 6 iniciales."}
            </p>

            <div className="d-flex flex-column gap-2">
              <Button
                variant="primary"
                onClick={() => navigate(`/matches/${match_id}/live`)}
              >
                Iniciar modo en vivo
              </Button>

              <Button
                variant="secondary"
                onClick={() => navigate(`/matches/${match_id}/stats`)}
                disabled={!hasPlayersWhoPlayed}
              >
                Ajustar estadísticas
              </Button>

              {!hasPlayersWhoPlayed && (
                <small className="text-muted">
                  Podrás ajustar estadísticas cuando guardes las 6 iniciales o
                  registres acciones en vivo.
                </small>
              )}
            </div>
          </>
        ) : (
          <p className="text-muted mb-0">
            🔒 Completa convocatoria y estado para activar el modo en vivo.
          </p>
        )}
      </Card>
      {/* Stepper */}
      <div className="stepper-mobile mb-4">
        {STEPS.map((step, index) => {
          const isLocked = index > maxUnlockedStep;
          const isBlockedByChanges =
            index > currentStep && hasUnsavedRosterChanges;

          return (
            <Button
              key={step}
              variant={currentStep === index ? "primary" : "secondary"}
              disabled={isLocked || isBlockedByChanges}
              onClick={() => {
                if (isLocked || isBlockedByChanges) return;
                setCurrentStep(index);
              }}
              className={`me-2 mb-2 ${isLocked ? "opacity-50" : ""}`}
            >
              {index + 1}. {step}
            </Button>
          );
        })}
      </div>
      {currentStep === 0 && (
        <p className="mb-3">
          Selecciona las jugadoras convocadas para este partido y guarda para
          continuar
        </p>
      )}
      {currentStep === 0 && rosterError && (
        <p className="form-error">{rosterError}</p>
      )}

      {currentStep === 0 && hasUnsavedRosterChanges && (
        <p className="text-warning mb-3">
          ⚠️ Tienes cambios sin guardar en la convocatoria
        </p>
      )}
      {currentStep === 1 && statusError && (
        <p className="form-error">{statusError}</p>
      )}
      {/* Players list */}
      {currentStep === 0
        ? teamPlayers.map((player) => {
            const isSelected = selectedPlayers.includes(player.player_id);

            return (
              <Card
                key={player.player_id}
                className={`mb-3 cursor-pointer ${
                  isSelected ? "border-primary" : ""
                }`}
                onClick={() => togglePlayerSelection(player)}
              >
                <h3>
                  #{player.player_number} {player.first_name} {player.last_name}
                </h3>

                <p className="text-muted mb-1">
                  Posición:{" "}
                  {POSITION_LABELS[player.position || player.main_position] ||
                    "Sin definir"}
                </p>

                <p>{isSelected ? "✅ Convocada" : "➕ Tap para convocar"}</p>
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
              }}
            >
              <h3>
                #{player.player_number} {player.first_name} {player.last_name}
              </h3>

              {PLAYABLE_STATUSES.includes(player.attendance_status) ? (
                <>
                  <p className="mb-1">Posición hoy:</p>

                  <select
                    value={player.position || player.main_position || ""}
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => {
                      e.stopPropagation();
                      updatePlayerPosition(
                        player.match_player_id,
                        e.target.value,
                      );
                    }}
                  >
                    <option value="">Sin definir</option>
                    {POSITION_OPTIONS.map((pos) => (
                      <option key={pos.value} value={pos.value}>
                        {pos.label}
                      </option>
                    ))}
                  </select>
                </>
              ) : (
                <p className="text-muted mb-1">
                  Posición:{" "}
                  {POSITION_LABELS[player.position || player.main_position] ||
                    "Sin definir"}
                </p>
              )}

              {currentStep >= 1 && (
                <>
                  <p className="mb-1">
                    Estado:{" "}
                    {MATCH_STATUS_LABELS[player.attendance_status] ||
                      "Sin estado"}
                  </p>
                  {currentStep === 1 && (
                    <small className="text-muted">
                      Toca para cambiar estado
                    </small>
                  )}
                </>
              )}
            </Card>
          ))}

      {/* Footer CTA */}
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
          <Button
            variant="primary"
            onClick={saveStepOne}
            disabled={savingRoster || !hasUnsavedRosterChanges}
          >
            {savingRoster ? "Guardando..." : "Guardar convocadas"}
          </Button>
        ) : currentStep === 1 ? (
          statusSaved && !statusDirty ? (
            <p className="text-success mb-0">✅ Estado guardado</p>
          ) : (
            <Button
              variant="primary"
              onClick={saveStepTwo}
              disabled={savingStatus}
            >
              {savingStatus
                ? "Guardando..."
                : statusSaved
                ? "Guardar cambios"
                : "Guardar estado"}
            </Button>
          )
        ) : null}
      </div>
    </div>
  );
};
