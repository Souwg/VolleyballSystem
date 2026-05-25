import React, { useEffect, useState, useContext } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";
import { Button } from "../../component/ui/button";
import "../../../styles/liveMatch.css";

const ACTIONS = [
  { value: "attack", label: "Ataque" },
  { value: "reception", label: "Recepción" },
  { value: "serve", label: "Saque" },
  { value: "block", label: "Bloqueo" },
  { value: "set", label: "Armado" },
  { value: "defense", label: "Defensa" },
];

const RESULTS_BY_ACTION = {
  attack: [
    { value: "positive", label: "Punto" },
    { value: "neutral", label: "Sigue" },
    { value: "error", label: "Error" },
  ],

  reception: [
    { value: "positive", label: "Buena" },
    { value: "neutral", label: "Regular" },
    { value: "negative", label: "Mala" },
  ],

  serve: [
    { value: "ace", label: "Ace" },
    { value: "in", label: "Adentro" },
    { value: "error", label: "Error" },
  ],

  block: [
    { value: "point", label: "Punto" },
    { value: "neutral", label: "Sigue" },
    { value: "error", label: "Error" },
  ],

  set: [
    { value: "positive", label: "Bueno" },
    { value: "neutral", label: "Regular" },
    { value: "error", label: "Error" },
  ],

  defense: [
    { value: "positive", label: "Buena" },
    { value: "neutral", label: "Regular" },
    { value: "negative", label: "Mala" },
  ],
};

const POSITION_LABELS = {
  setter: "Armadora",
  outside: "Punta",
  middle: "Central",
  opposite: "Opuesto",
  libero: "Líbero",
};
export const LiveMatch = () => {
  const { actions } = useContext(Context);
  const { match_id } = useParams();
  const navigate = useNavigate();

  const [roster, setRoster] = useState([]);
  const [showSubstitutionPanel, setShowSubstitutionPanel] = useState(false);
  const [selectedOutPlayer, setSelectedOutPlayer] = useState(null);
  const [savingParticipation, setSavingParticipation] = useState(false);
  const [selectedPlayer, setSelectedPlayer] = useState(null);
  const [selectedAction, setSelectedAction] = useState(null);
  const [lastAction, setLastAction] = useState(null);
  const [saving, setSaving] = useState(false);
  const [undoing, setUndoing] = useState(false);
  const [currentSet, setCurrentSet] = useState(1);
  const [setMessage, setSetMessage] = useState("");
  const [showSetPicker, setShowSetPicker] = useState(false);
  const [selectedStartingPlayers, setSelectedStartingPlayers] = useState([]);
  const [savingLineup, setSavingLineup] = useState(false);
  const [lineupError, setLineupError] = useState("");

  const loadRoster = async () => {
    const result = await actions.getMatchRoster(match_id);

    if (!result.ok) return;

    const rosterData = result.data || [];
    setRoster(rosterData);
  };

  const toggleStartingPlayer = (player) => {
    setSelectedStartingPlayers((prev) => {
      const exists = prev.includes(player.match_player_id);

      setLineupError("");

      if (exists) {
        return prev.filter((id) => id !== player.match_player_id);
      }

      if (prev.length >= 6) {
        setLineupError("Solo puedes seleccionar 6 jugadoras iniciales");
        return prev;
      }

      return [...prev, player.match_player_id];
    });
  };

  const saveStartingLineup = async () => {
    if (selectedStartingPlayers.length !== 6 || savingLineup) return;

    setSavingLineup(true);

    const result = await actions.saveStartingLineup(
      match_id,
      selectedStartingPlayers,
    );

    setSavingLineup(false);

    if (!result?.ok) return;

    setSelectedStartingPlayers([]);
    setLineupError("");
    await loadRoster();
  };

  useEffect(() => {
    loadRoster();
  }, [match_id]);

  const getActionLabel = (value) => {
    return ACTIONS.find((action) => action.value === value)?.label || value;
  };

  const playableRoster = roster.filter(
    (p) => p.is_called && ["present", "late"].includes(p.attendance_status),
  );

  const courtPlayers = playableRoster.filter((p) => p.is_on_court);

  const benchPlayers = playableRoster.filter((p) => !p.is_on_court);

  const selectedStartingPlayersData = playableRoster.filter((player) =>
    selectedStartingPlayers.includes(player.match_player_id),
  );

  const availableStartingPlayers = playableRoster.filter(
    (player) => !selectedStartingPlayers.includes(player.match_player_id),
  );

  const hasStartingLineup = courtPlayers.length === 6;

  const handleSubstitution = async (incomingPlayer) => {
    if (!selectedOutPlayer || savingParticipation) return;

    setSavingParticipation(true);

    const result = await actions.createMatchSubstitution(match_id, {
      player_out_id: selectedOutPlayer.match_player_id,
      player_in_id: incomingPlayer.match_player_id,
      set_number: currentSet,
    });

    setSavingParticipation(false);

    if (!result?.ok) return;

    navigator.vibrate?.(50);

    setLastAction({
      id: null,
      player_number: incomingPlayer.player_number,
      player_name: incomingPlayer.first_name,
      action_type: "Cambio",
      result: "Entra",
      result_label: `entra por #${selectedOutPlayer.player_number} ${selectedOutPlayer.first_name} · Set ${currentSet}`,
    });

    setSelectedOutPlayer(null);
    setShowSubstitutionPanel(false);
    setSelectedPlayer(null);
    setSelectedAction(null);

    await loadRoster();
  };

  const handleRegister = async (result) => {
    if (!selectedPlayer || !selectedAction || saving) return;

    setSaving(true);

    const res = await actions.createMatchEvent({
      match_id,
      match_player_id: selectedPlayer.match_player_id,
      action_type: selectedAction,
      result,
      set_number: currentSet,
    });

    setSaving(false);

    if (!res?.ok) return;

    const resultLabel =
      RESULTS_BY_ACTION[selectedAction]?.find((item) => item.value === result)
        ?.label || result;

    navigator.vibrate?.(50);

    setLastAction({
      id: res.data.event?.id,
      player_number: selectedPlayer.player_number,
      player_name: selectedPlayer.first_name,
      action_type: selectedAction,
      result,
      result_label: `${resultLabel} · Set ${currentSet}`,
    });

    setSelectedAction(null);
    setSelectedPlayer(null);
  };

  const handleUndo = async () => {
    if (!lastAction?.id || undoing) return;

    setUndoing(true);

    const res = await actions.deleteMatchEvent(lastAction.id);

    setUndoing(false);

    if (!res?.ok) return;

    navigator.vibrate?.(30);
    setLastAction(null);
  };

  const handleSetChange = (set) => {
    setCurrentSet(set);

    setSelectedPlayer(null);
    setSelectedAction(null);
    setSelectedOutPlayer(null);
    setShowSubstitutionPanel(false);

    setSetMessage(`Ahora estás capturando acciones del Set ${set}`);

    setTimeout(() => {
      setSetMessage("");
    }, 2500);
  };

  return (
    <div className="live-match-page">
      <div className="live-topbar">
        <button
          type="button"
          className="live-back-button"
          onClick={() => navigate(`/matches/${match_id}`)}
        >
          ← Volver
        </button>

        <span className="live-topbar-label">Partido en vivo</span>
      </div>

      {!hasStartingLineup && (
        <section className="live-lineup-card">
          <div className="live-section">
            <div>
              <h3 className="live-section-title">Selecciona 6 iniciales</h3>
              <p className="live-section-helper">
                Antes de iniciar el modo en vivo, selecciona las 6 deportistas
                que están en cancha.
              </p>
            </div>

            <span className="live-lineup-counter">
              {selectedStartingPlayers.length}/6 seleccionadas
            </span>

            {lineupError && <p className="form-error">{lineupError}</p>}
          </div>

          <div className="live-section mt-3">
            <h4>Seleccionadas</h4>

            {selectedStartingPlayersData.length === 0 ? (
              <p className="live-section-helper">
                Todavía no has seleccionado deportistas.
              </p>
            ) : (
              <div className="live-grid">
                {selectedStartingPlayersData.map((player) => (
                  <button
                    key={player.match_player_id}
                    type="button"
                    className="live-chip active"
                    onClick={() => toggleStartingPlayer(player)}
                  >
                    #{player.player_number} {player.first_name}
                    {player.position && (
                      <small>{POSITION_LABELS[player.position]}</small>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="live-section mt-3">
            <h4>Disponibles</h4>

            <div className="live-grid">
              {availableStartingPlayers.map((player) => (
                <button
                  key={player.match_player_id}
                  type="button"
                  className="live-chip"
                  onClick={() => toggleStartingPlayer(player)}
                  disabled={selectedStartingPlayers.length >= 6}
                >
                  #{player.player_number} {player.first_name}
                  {player.position && (
                    <small>{POSITION_LABELS[player.position]}</small>
                  )}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-3">
            <Button
              variant="primary"
              onClick={saveStartingLineup}
              disabled={selectedStartingPlayers.length !== 6 || savingLineup}
            >
              {savingLineup ? "Guardando..." : "Guardar 6 iniciales"}
            </Button>
          </div>
        </section>
      )}
      {hasStartingLineup && (
        <section className="live-capture-bar">
          <div className="live-capture-main">
            <span className="live-capture-label">Capturando</span>
            <strong>Set {currentSet}</strong>
          </div>

          <div className="live-capture-actions">
            <button
              type="button"
              className="live-mini-button"
              onClick={() => setShowSetPicker((prev) => !prev)}
            >
              {showSetPicker ? "Cerrar" : "Cambiar Set"}
            </button>

            <button
              type="button"
              className="live-mini-button"
              onClick={() => setShowSubstitutionPanel((prev) => !prev)}
            >
              {showSubstitutionPanel ? "Cerrar" : "Cambio de Jugador"}
            </button>
          </div>

          {showSetPicker && (
            <div className="live-set-picker">
              {[1, 2, 3, 4, 5].map((set) => (
                <button
                  key={set}
                  type="button"
                  className={`live-set-pill ${
                    currentSet === set ? "active" : ""
                  }`}
                  onClick={() => {
                    handleSetChange(set);
                    setShowSetPicker(false);
                  }}
                >
                  {set}
                </button>
              ))}
            </div>
          )}

          {setMessage && <p className="live-set-message">✅ {setMessage}</p>}
        </section>
      )}

      {hasStartingLineup && showSubstitutionPanel && (
        <section className="live-substitution-card">
          <h3 className="mb-3">Cambio en vivo</h3>

          <p className="mb-2">1. Selecciona quién sale</p>

          <div className="live-grid">
            {courtPlayers.map((player) => (
              <button
                key={player.match_player_id}
                type="button"
                className={`live-chip ${
                  selectedOutPlayer?.match_player_id === player.match_player_id
                    ? "active"
                    : ""
                }`}
                onClick={() => setSelectedOutPlayer(player)}
              >
                Sale #{player.player_number} {player.first_name}
                {player.position && (
                  <small>{POSITION_LABELS[player.position]}</small>
                )}
              </button>
            ))}
          </div>

          <p className="mb-2 mt-3">2. Selecciona quién entra</p>

          {benchPlayers.length === 0 ? (
            <p className="text-muted mb-0">
              No hay jugadoras disponibles en banca.
            </p>
          ) : (
            <div className="live-grid">
              {benchPlayers.map((player) => (
                <button
                  key={player.match_player_id}
                  type="button"
                  className="live-chip"
                  disabled={savingParticipation}
                  onClick={() => {
                    if (!selectedOutPlayer) return;
                    handleSubstitution(player);
                  }}
                >
                  Entra #{player.player_number} {player.first_name}
                  {player.position && (
                    <small>{POSITION_LABELS[player.position]}</small>
                  )}
                </button>
              ))}
            </div>
          )}

          {!selectedOutPlayer && benchPlayers.length > 0 && (
            <small className="text-muted d-block mt-3">
              Primero selecciona quién sale y luego quién entra.
            </small>
          )}
        </section>
      )}

      {hasStartingLineup && (
        <section className="live-section">
          <h3 className="live-section-title">Jugadoras en cancha</h3>

          <div className="live-grid">
            {courtPlayers.map((p) => (
              <button
                key={p.match_player_id}
                type="button"
                className={`live-chip ${
                  selectedPlayer?.match_player_id === p.match_player_id
                    ? "active"
                    : ""
                }`}
                onClick={() => setSelectedPlayer(p)}
              >
                #{p.player_number} {p.first_name}
                {p.position && <small>{POSITION_LABELS[p.position]}</small>}
              </button>
            ))}
          </div>
        </section>
      )}

      {(selectedPlayer || selectedAction) && (
        <section className="live-current-selection">
          {selectedPlayer && (
            <p>
              Deportista:{" "}
              <strong>
                #{selectedPlayer.player_number} {selectedPlayer.first_name}
              </strong>
            </p>
          )}

          {selectedAction && (
            <p>
              Acción: <strong>{getActionLabel(selectedAction)}</strong>
            </p>
          )}
        </section>
      )}
      {hasStartingLineup && (
        <>
          <section className="live-section">
            <h3 className="live-section-title">Acción</h3>

            <div className="live-actions-grid">
              {ACTIONS.map((action) => (
                <Button
                  key={action.value}
                  className="live-action-button"
                  variant={
                    selectedAction === action.value ? "primary" : "secondary"
                  }
                  onClick={() => setSelectedAction(action.value)}
                >
                  {action.label}
                </Button>
              ))}
            </div>
          </section>

          <section className="live-section">
            <h3 className="live-section-title">Resultado</h3>

            {!selectedAction ? (
              <p className="live-section-helper">
                Primero selecciona una acción para ver sus resultados.
              </p>
            ) : (
              <div className="live-results-grid">
                {(RESULTS_BY_ACTION[selectedAction] || []).map((result) => (
                  <Button
                    key={result.value}
                    className={`live-result-button live-result-${result.value}`}
                    disabled={!selectedPlayer || !selectedAction || saving}
                    onClick={() => handleRegister(result.value)}
                  >
                    {result.label}
                  </Button>
                ))}
              </div>
            )}
          </section>

          {lastAction && (
            <section className="live-last-action">
              <p>
                Última acción:{" "}
                <strong>
                  #{lastAction.player_number} {lastAction.player_name} ·{" "}
                  {getActionLabel(lastAction.action_type)} ·{" "}
                  {lastAction.result_label}
                </strong>
              </p>

              <Button
                variant="secondary"
                onClick={handleUndo}
                disabled={undoing}
              >
                {undoing ? "Deshaciendo..." : "Deshacer"}
              </Button>
            </section>
          )}
        </>
      )}
    </div>
  );
};
