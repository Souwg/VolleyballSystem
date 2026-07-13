import React, { useState, useContext, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Context } from "../../store/appContext";

import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Input } from "../../component/ui/input";
import { Select } from "../../component/ui/select";
import { Textarea } from "../../component/ui/textarea";
import { FormField } from "../../component/ui/formField";
import { Button } from "../../component/ui/button";

import { errorMessages } from "../../utils/errorMessages";
import { validateMatch } from "../../utils/validators";

export const CreateMatch = () => {
  const { actions } = useContext(Context);
  const { team_id } = useParams();
  const navigate = useNavigate();

  const [opponentName, setOpponentName] = useState("");
  const [date, setDate] = useState("");
  const [matchType, setMatchType] = useState("official");
  const [location, setLocation] = useState("");
  const [notes, setNotes] = useState("");
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  const [tournamentEntries, setTournamentEntries] = useState([]);
  const [tournamentTeamId, setTournamentTeamId] = useState("");
  const [refereeFee, setRefereeFee] = useState("");
  const [loadingTournaments, setLoadingTournaments] = useState(true);

  useEffect(() => {
    const loadTournamentEntries = async () => {
      setLoadingTournaments(true);

      const result = await actions.getTeamTournamentEntries(team_id);

      if (result.ok) {
        setTournamentEntries(result.data.tournament_entries || []);
      } else {
        setTournamentEntries([]);
      }

      setLoadingTournaments(false);
    };

    loadTournamentEntries();
  }, [team_id]);

  const selectedTournamentEntry = tournamentEntries.find(
    (entry) => entry.id === tournamentTeamId,
  );

  const clearFieldError = (errorCode) => {
    setErrors((prev) => ({
      ...prev,
      [errorCode]: false,
      TEAM_ID_REQUIRED: false,
      TEAM_NOT_FOUND: false,
      FORBIDDEN: false,
      CLUB_REQUIRED: false,
      SESSION_EXPIRED: false,
      NETWORK_ERROR: false,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (loading) return;

    const validationErrors = validateMatch({
      opponent_name: opponentName,
      date,
      match_type: matchType,
    });

    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setErrors({});
    setLoading(true);

    const result = await actions.createMatch({
      team_id,
      opponent_name: opponentName.trim(),
      date,
      match_type: matchType,
      location: location.trim(),
      notes: notes.trim(),
      tournament_team_id: tournamentTeamId || null,
      referee_fee: refereeFee === "" ? null : refereeFee,
    });

    setLoading(false);

    if (!result.ok) {
      setErrors({ [result.code]: true });
      return;
    }

    navigate(`/teams/${team_id}/matches`);
  };

  return (
    <>
      <PageHeader
        variant="detail"
        eyebrow="Partido"
        title="Crear partido"
        subtitle="Prepara la información básica del partido."
        onBack={() => navigate(`/teams/${team_id}/matches`)}
      />

      <Card>
        <form className="form" onSubmit={handleSubmit}>
          <FormField
            label="Rival"
            error={
              errors.OPPONENT_NAME_REQUIRED
                ? errorMessages.OPPONENT_NAME_REQUIRED
                : null
            }
          >
            <Input
              value={opponentName}
              className={errors.OPPONENT_NAME_REQUIRED ? "input-error" : ""}
              onChange={(e) => {
                setOpponentName(e.target.value);
                clearFieldError("OPPONENT_NAME_REQUIRED");
              }}
              placeholder="Club Atlético, Escuela de vóley..."
            />
          </FormField>

          <FormField
            label="Fecha"
            error={
              errors.MATCH_DATE_REQUIRED
                ? errorMessages.MATCH_DATE_REQUIRED
                : null
            }
          >
            <Input
              type="date"
              value={date}
              className={errors.MATCH_DATE_REQUIRED ? "input-error" : ""}
              onChange={(e) => {
                setDate(e.target.value);
                clearFieldError("MATCH_DATE_REQUIRED");
              }}
            />
          </FormField>

          <FormField
            label="Tipo de partido"
            error={
              errors.INVALID_MATCH_TYPE
                ? errorMessages.INVALID_MATCH_TYPE
                : null
            }
          >
            <Select
              value={matchType}
              className={errors.INVALID_MATCH_TYPE ? "input-error" : ""}
              onChange={(e) => {
                setMatchType(e.target.value);
                clearFieldError("INVALID_MATCH_TYPE");
              }}
            >
              <option value="official">Oficial</option>
              <option value="friendly">Amistoso</option>
              <option value="scrimmage">Scrimmage</option>
            </Select>
          </FormField>

          <FormField
            label="Competencia"
            helper="Opcional. Selecciona un torneo activo o deja el partido como independiente."
            error={
              errors.TOURNAMENT_TEAM_MISMATCH
                ? errorMessages.TOURNAMENT_TEAM_MISMATCH
                : errors.TOURNAMENT_TEAM_NOT_FOUND
                ? errorMessages.TOURNAMENT_TEAM_NOT_FOUND
                : null
            }
          >
            <Select
              value={tournamentTeamId}
              disabled={loadingTournaments}
              className={
                errors.TOURNAMENT_TEAM_MISMATCH ||
                errors.TOURNAMENT_TEAM_NOT_FOUND
                  ? "input-error"
                  : ""
              }
              onChange={(e) => {
                const selectedId = e.target.value;

                setTournamentTeamId(selectedId);

                const selectedEntry = tournamentEntries.find(
                  (entry) => entry.id === selectedId,
                );

                setRefereeFee(
                  selectedEntry
                    ? String(
                        selectedEntry.tournament?.default_referee_fee ?? "",
                      )
                    : "",
                );

                clearFieldError("TOURNAMENT_TEAM_MISMATCH");
                clearFieldError("TOURNAMENT_TEAM_NOT_FOUND");
              }}
            >
              <option value="">Partido independiente</option>

              {tournamentEntries.map((entry) => (
                <option key={entry.id} value={entry.id}>
                  {entry.tournament?.name || "Torneo"}
                </option>
              ))}
            </Select>
          </FormField>

          <FormField
            label="Costo de arbitraje"
            helper={
              tournamentTeamId
                ? "Se tomó el monto predeterminado del torneo. Puedes modificarlo para este partido."
                : "Opcional. Si lo defines, luego podrás dividirlo entre las convocadas."
            }
            error={
              errors.INVALID_AMOUNT
                ? errorMessages.INVALID_AMOUNT
                : errors.INVALID_REFEREE_FEE
                ? errorMessages.INVALID_REFEREE_FEE
                : null
            }
          >
            <Input
              type="number"
              min="0"
              step="0.01"
              value={refereeFee}
              className={
                errors.INVALID_AMOUNT || errors.INVALID_REFEREE_FEE
                  ? "input-error"
                  : ""
              }
              onChange={(e) => {
                setRefereeFee(e.target.value);
                clearFieldError("INVALID_AMOUNT");
                clearFieldError("INVALID_REFEREE_FEE");
              }}
              placeholder="Ej: 25.00"
            />
          </FormField>

          <FormField
            label="Ubicación"
            helper="Opcional. Puedes escribir la cancha, gimnasio o sede."
          >
            <Input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="Cancha principal"
            />
          </FormField>

          <FormField
            label="Notas"
            helper="Opcional. Agrega contexto del partido."
          >
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Semifinal, torneo local, indicaciones para el equipo..."
            />
          </FormField>
          {(errors.TEAM_ID_REQUIRED ||
            errors.TEAM_NOT_FOUND ||
            errors.FORBIDDEN ||
            errors.CLUB_REQUIRED ||
            errors.SESSION_EXPIRED ||
            errors.NETWORK_ERROR) && (
            <p className="form-error">
              {errors.TEAM_ID_REQUIRED
                ? errorMessages.TEAM_ID_REQUIRED
                : errors.TEAM_NOT_FOUND
                ? errorMessages.TEAM_NOT_FOUND
                : errors.FORBIDDEN
                ? errorMessages.FORBIDDEN
                : errors.CLUB_REQUIRED
                ? errorMessages.CLUB_REQUIRED
                : errors.SESSION_EXPIRED
                ? errorMessages.SESSION_EXPIRED
                : errorMessages.NETWORK_ERROR}
            </p>
          )}
          <div className="form-actions">
            <Button type="submit" disabled={loading}>
              {loading ? "Creando..." : "Crear partido"}
            </Button>
          </div>
        </form>
      </Card>
    </>
  );
};
