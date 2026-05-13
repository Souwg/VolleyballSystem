import React, { useEffect, useContext, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";

import { Container } from "../../component/ui/container";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Input } from "../../component/ui/input";
import { Button } from "../../component/ui/button";

import { validatePlayerProfile } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";

const POSITIONS = [
  { label: "Armadora", value: "setter" },
  { label: "Punta", value: "outside" },
  { label: "Central", value: "middle" },
  { label: "Opuesto", value: "opposite" },
  { label: "Líbero", value: "libero" },
];

export const EditPlayer = () => {
  const { actions } = useContext(Context);
  const { player_id } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState({});

  const [player, setPlayer] = useState(null);

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [sex, setSex] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [mainPosition, setMainPosition] = useState("");

  const loadPlayer = async () => {
    setLoading(true);

    const result = await actions.getPlayerAttendance(player_id);

    if (result.ok) {
      const currentPlayer = result.data.player;

      setPlayer(currentPlayer);
      setFirstName(currentPlayer.first_name || "");
      setLastName(currentPlayer.last_name || "");
      setSex(currentPlayer.sex || "");
      setBirthDate(currentPlayer.birth_date || "");
      setMainPosition(currentPlayer.main_position || "");
    }

    setLoading(false);
  };

  useEffect(() => {
    loadPlayer();
  }, [player_id]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (saving) return;

    const profileErrors = validatePlayerProfile({
      first_name: firstName,
      last_name: lastName,
      sex,
    });

    if (Object.keys(profileErrors).length > 0) {
      setErrors(profileErrors);
      return;
    }

    setErrors({});
    setSaving(true);

    const result = await actions.updatePlayer(player_id, {
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      sex,
      birth_date: birthDate || null,
      main_position: mainPosition || null,
    });

    if (!result.ok) {
      setErrors({ [result.code]: true });
      setSaving(false);
      return;
    }

    setSaving(false);
    navigate(`/players/${player_id}`);
  };

  if (loading) {
    return (
      <Container>
        <p>Cargando jugadora...</p>
      </Container>
    );
  }

  if (!player) {
    return (
      <Container>
        <p>No se pudo cargar la jugadora.</p>
      </Container>
    );
  }

  return (
    <Container>
      <PageHeader
        title="Editar perfil"
        subtitle={`${player.first_name} ${player.last_name}`}
      />

      <Card>
        <form onSubmit={handleSubmit} className="form">
          <label>Nombre</label>
          <Input
            value={firstName}
            placeholder="Nombre"
            className={errors.FIRST_NAME_REQUIRED ? "input-error" : ""}
            onChange={(e) => {
              setFirstName(e.target.value);
              setErrors((prev) => ({
                ...prev,
                FIRST_NAME_REQUIRED: false,
              }));
            }}
          />
          {errors.FIRST_NAME_REQUIRED && (
            <p className="form-error">{errorMessages.FIRST_NAME_REQUIRED}</p>
          )}

          <label>Apellido</label>
          <Input
            value={lastName}
            placeholder="Apellido"
            className={errors.LAST_NAME_REQUIRED ? "input-error" : ""}
            onChange={(e) => {
              setLastName(e.target.value);
              setErrors((prev) => ({
                ...prev,
                LAST_NAME_REQUIRED: false,
              }));
            }}
          />
          {errors.LAST_NAME_REQUIRED && (
            <p className="form-error">{errorMessages.LAST_NAME_REQUIRED}</p>
          )}

          <label>Sexo</label>
          <select
            value={sex}
            className={
              errors.SEX_REQUIRED || errors.INVALID_SEX ? "input-error" : ""
            }
            onChange={(e) => {
              setSex(e.target.value);
              setErrors((prev) => ({
                ...prev,
                SEX_REQUIRED: false,
                INVALID_SEX: false,
                PLAYER_GENDER_MISMATCH: false,
              }));
            }}
          >
            <option value="">Selecciona sexo</option>
            <option value="female">Femenino</option>
            <option value="male">Masculino</option>
          </select>

          {errors.SEX_REQUIRED && (
            <p className="form-error">{errorMessages.SEX_REQUIRED}</p>
          )}

          {errors.INVALID_SEX && (
            <p className="form-error">{errorMessages.INVALID_SEX}</p>
          )}

          {errors.PLAYER_GENDER_MISMATCH && (
            <p className="form-error">
              No puedes cambiar el sexo porque la jugadora pertenece a una
              categoría incompatible.
            </p>
          )}

          <label>Fecha de nacimiento</label>
          <Input
            type="date"
            value={birthDate}
            className={errors.INVALID_DATE_FORMAT ? "input-error" : ""}
            onChange={(e) => {
              setBirthDate(e.target.value);
              setErrors((prev) => ({
                ...prev,
                INVALID_DATE_FORMAT: false,
              }));
            }}
          />

          {errors.INVALID_DATE_FORMAT && (
            <p className="form-error">Formato de fecha inválido</p>
          )}

          <label>Posición principal</label>
          <select
            value={mainPosition}
            className={errors.INVALID_POSITION ? "input-error" : ""}
            onChange={(e) => {
              setMainPosition(e.target.value);
              setErrors((prev) => ({
                ...prev,
                INVALID_POSITION: false,
              }));
            }}
          >
            <option value="">Sin posición definida</option>
            {POSITIONS.map((position) => (
              <option key={position.value} value={position.value}>
                {position.label}
              </option>
            ))}
          </select>

          {errors.INVALID_POSITION && (
            <p className="form-error">Posición inválida</p>
          )}

          <div className="form-actions">
            <Button
              type="button"
              className="button-secondary"
              onClick={() => navigate(`/players/${player_id}`)}
            >
              Cancelar
            </Button>

            <Button type="submit" className="button-primary" disabled={saving}>
              {saving ? "Guardando..." : "Guardar cambios"}
            </Button>
          </div>
        </form>
      </Card>
    </Container>
  );
};
