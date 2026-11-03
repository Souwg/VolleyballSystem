import React, { useContext, useEffect, useState } from "react";

import { Context } from "../../store/appContext";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";
import { errorMessages } from "../../utils/errorMessages";

const MODES = [
  {
    value: "team_assigned",
    title: "Acceso por equipos",
    description:
      "Los entrenadores solo pueden operar los equipos que tengan asignados.",
  },
  {
    value: "club_wide",
    title: "Acceso general",
    description:
      "Los entrenadores pueden operar todos los equipos deportivos del club.",
  },
];

const ACTIVATION_WARNING =
  "Los entrenadores solo podrán gestionar los equipos que tengan asignados. Los equipos sin entrenador asignado seguirán disponibles para el dueño del club.\n\n¿Quieres activar el acceso por equipos?";

const READINESS_LABELS = [
  ["active_coaches", "Entrenadores activos"],
  ["coaches_without_team", "Entrenadores sin equipo asignado"],
  ["active_teams_without_coach", "Equipos activos sin entrenador"],
  ["planned_teams_without_coach", "Equipos planificados sin entrenador"],
];

export const CoachAccessSection = () => {
  const { store, actions } = useContext(Context);
  const club = store.club || store.user?.club;
  const currentMode = club?.coach_access_mode;

  const [selectedMode, setSelectedMode] = useState(currentMode);
  const [readiness, setReadiness] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      const result = await actions.getClubCoachAccess();

      if (mounted && result.ok) {
        setSelectedMode(result.data.coach_access_mode);
        setReadiness(result.data.readiness);
      }
    };

    load();

    return () => {
      mounted = false;
    };
  }, []);

  const handleSave = async (event) => {
    event.preventDefault();

    if (saving || selectedMode === currentMode) return;

    if (
      selectedMode === "team_assigned" &&
      !window.confirm(ACTIVATION_WARNING)
    ) {
      return;
    }

    setSaving(true);
    setError("");

    const result = await actions.updateClubCoachAccess(selectedMode);

    setSaving(false);

    if (!result.ok) {
      setError(
        errorMessages[result.code] ||
          result.message ||
          errorMessages.NETWORK_ERROR,
      );
      return;
    }

    setReadiness(result.data.readiness);
  };

  return (
    <Card className="coach-access-card">
      <form className="form" onSubmit={handleSave}>
        <div className="club-profile-section coach-access-section">
          <div>
            <h3>Acceso de entrenadores</h3>
            <p>
              Elige qué equipos puede operar cada entrenador. Las asignaciones
              se conservan aunque cambies esta opción.
            </p>
          </div>

          <div className="coach-access-options">
            {MODES.map((mode) => (
              <label
                key={mode.value}
                className={`coach-access-option ${
                  selectedMode === mode.value ? "selected" : ""
                }`}
              >
                <input
                  type="radio"
                  name="coach-access-mode"
                  value={mode.value}
                  checked={selectedMode === mode.value}
                  onChange={() => setSelectedMode(mode.value)}
                />

                <span className="coach-access-option-copy">
                  <strong>
                    {mode.title}
                    {currentMode === mode.value && (
                      <span className="status-badge status-info">
                        Modo actual
                      </span>
                    )}
                  </strong>
                  <span>{mode.description}</span>
                </span>
              </label>
            ))}
          </div>

          {selectedMode === "team_assigned" && readiness && (
            <ul className="coach-access-readiness">
              {READINESS_LABELS.map(([key, label]) => (
                <li key={key}>
                  <span>{label}</span>
                  <strong>{readiness[key]}</strong>
                </li>
              ))}
            </ul>
          )}

          {error && <p className="form-error">{error}</p>}

          <div className="form-actions">
            <Button
              type="submit"
              disabled={saving || selectedMode === currentMode}
            >
              {saving ? "Guardando..." : "Guardar acceso"}
            </Button>
          </div>
        </div>
      </form>
    </Card>
  );
};
