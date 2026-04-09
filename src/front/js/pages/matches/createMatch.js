import React, { useState, useContext } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Input } from "../../component/ui/input";
import { Button } from "../../component/ui/button";
import { errorMessages } from "../../utils/errorMessages";

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

  const clearFieldError = (field) => {
    if (!errors[field]) return;

    setErrors((prev) => ({
      ...prev,
      [field]: null,
    }));
  };

  const handleSubmit = async () => {
    const nextErrors = {};

    if (!date) {
      nextErrors.date =
        errorMessages.MATCH_DATE_REQUIRED || "La fecha es obligatoria";
    }

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      return;
    }

    setLoading(true);

    const result = await actions.createMatch({
      team_id,
      opponent_name: opponentName,
      date,
      match_type: matchType,
      location,
      notes,
    });

    setLoading(false);

    if (!result.ok) {
      setErrors({
        general: errorMessages[result.code] || result.message,
      });
      return;
    }

    navigate(`/teams/${team_id}/matches`);
  };

  return (
    <div className="page-container">
      <PageHeader
        title="Crear partido"
        subtitle="Prepara el contexto del match"
      />

      <Card>
        <Input
          label="Rival"
          value={opponentName}
          onChange={(e) => {
            setOpponentName(e.target.value);
            clearFieldError("opponent_name");
          }}
          placeholder="Ej: Eagles"
        />

        <Input
          label="Fecha"
          type="date"
          value={date}
          onChange={(e) => {
            setDate(e.target.value);
            clearFieldError("date");
          }}
          error={errors.date}
        />

        <label className="form-label">Tipo</label>
        <select
          className="form-input"
          value={matchType}
          onChange={(e) => setMatchType(e.target.value)}
        >
          <option value="official">Official</option>
          <option value="friendly">Friendly</option>
          <option value="scrimmage">Scrimmage</option>
        </select>

        <Input
          label="Ubicación"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="Cancha principal"
        />

        <Input
          label="Notas"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Semifinal, torneo local..."
        />

        {errors.general && <p className="text-danger mt-2">{errors.general}</p>}

        <div className="mt-4">
          <Button variant="primary" onClick={handleSubmit} disabled={loading}>
            {loading ? "Creando..." : "Crear partido"}
          </Button>
        </div>
      </Card>
    </div>
  );
};
