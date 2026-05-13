import React, { useState, useContext } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Input } from "../../component/ui/input";
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

  const clearFieldError = (errorCode) => {
    if (!errors[errorCode]) return;

    setErrors((prev) => ({
      ...prev,
      [errorCode]: false,
    }));
  };

  const handleSubmit = async () => {
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
    });

    setLoading(false);

    if (!result.ok) {
      setErrors({ [result.code]: true });
      return;
    }

    navigate(`/teams/${team_id}/matches`);
  };
  return (
    <div className="page-container">
      <PageHeader
        variant="detail"
        eyebrow="Partido"
        title="Crear partido"
        subtitle="Prepara la información básica del partido."
        onBack={() => navigate(`/teams/${team_id}/matches`)}
      />
      <Card>
        <label className="form-label">Rival</label>
        <Input
          label="Rival"
          value={opponentName}
          className={errors.OPPONENT_NAME_REQUIRED ? "input-error" : ""}
          onChange={(e) => {
            setOpponentName(e.target.value);
            clearFieldError("OPPONENT_NAME_REQUIRED");
          }}
          placeholder="Club Atlético, Escuela de Vóley..."
        />
        {errors.OPPONENT_NAME_REQUIRED && (
          <p className="form-error">{errorMessages.OPPONENT_NAME_REQUIRED}</p>
        )}
        <label className="form-label">Fecha</label>
        <Input
          label="Fecha"
          type="date"
          value={date}
          className={errors.MATCH_DATE_REQUIRED ? "input-error" : ""}
          onChange={(e) => {
            setDate(e.target.value);
            clearFieldError("MATCH_DATE_REQUIRED");
          }}
        />
        {errors.MATCH_DATE_REQUIRED && (
          <p className="form-error">{errorMessages.MATCH_DATE_REQUIRED}</p>
        )}

        <label className="form-label">Tipo</label>

        <select
          className={`select ${errors.INVALID_MATCH_TYPE ? "input-error" : ""}`}
          value={matchType}
          onChange={(e) => {
            setMatchType(e.target.value);
            clearFieldError("INVALID_MATCH_TYPE");
          }}
        >
          <option value="official">Oficial</option>
          <option value="friendly">Amistoso</option>
          <option value="scrimmage">Entrenamiento</option>
        </select>

        {errors.INVALID_MATCH_TYPE && (
          <p className="form-error">{errorMessages.INVALID_MATCH_TYPE}</p>
        )}
        <label className="form-label">Ubicación</label>
        <Input
          label="Ubicación"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="Cancha principal"
        />
        <label className="form-label">Notas</label>
        <Input
          label="Notas"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Semifinal, torneo local..."
        />

        <div className="mt-4">
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? "Creando..." : "Crear partido"}
          </Button>
        </div>
      </Card>
    </div>
  );
};
