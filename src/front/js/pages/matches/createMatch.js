import React, { useState, useContext } from "react";
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

  const clearFieldError = (errorCode) => {
    if (!errors[errorCode]) return;

    setErrors((prev) => ({
      ...prev,
      [errorCode]: false,
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
