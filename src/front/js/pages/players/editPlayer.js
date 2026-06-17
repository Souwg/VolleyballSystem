import React, { useEffect, useContext, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";

import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { FormField } from "../../component/ui/formField";
import { Input } from "../../component/ui/input";
import { Select } from "../../component/ui/select";

import { validatePlayerProfile } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";
import { getAssetUrl } from "../../utils/getAssetUrl";
import "../../../styles/editPlayer.css";
const POSITIONS = [
  { label: "Armador", value: "setter" },
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
  const [imageUrl, setImageUrl] = useState("");
  const [playerImageFile, setPlayerImageFile] = useState(null);
  const [playerImagePreview, setPlayerImagePreview] = useState("");
  const [uploadingImage, setUploadingImage] = useState(false);

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
      setImageUrl(currentPlayer.image_url || "");
      setPlayerImagePreview("");
      setPlayerImageFile(null);
    }

    setLoading(false);
  };

  useEffect(() => {
    loadPlayer();
  }, [player_id]);

  const handlePlayerImageChange = (e) => {
    const file = e.target.files?.[0];

    if (!file) return;

    setPlayerImageFile(file);
    setPlayerImagePreview(URL.createObjectURL(file));

    setErrors((prev) => ({
      ...prev,
      IMAGE_TOO_LARGE: false,
      INVALID_IMAGE_FORMAT: false,
      IMAGE_REQUIRED: false,
    }));
  };
  const handleSubmit = async (e) => {
    e.preventDefault();

    if (saving) return;

    const profileErrors = validatePlayerProfile({
      first_name: firstName,
      last_name: lastName,
      sex,
      birth_date: birthDate,
    });

    if (Object.keys(profileErrors).length > 0) {
      setErrors(profileErrors);
      return;
    }

    setErrors({});
    setSaving(true);

    let finalImageUrl = imageUrl;

    if (playerImageFile) {
      setUploadingImage(true);

      const uploadResult = await actions.uploadPlayerImage(
        player_id,
        playerImageFile,
      );

      setUploadingImage(false);

      if (!uploadResult?.ok) {
        setErrors({ [uploadResult.code]: true });
        setSaving(false);
        return;
      }

      finalImageUrl = uploadResult.data.image_url;
    }

    const result = await actions.updatePlayer(player_id, {
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      sex,
      birth_date: birthDate || null,
      main_position: mainPosition || null,
      image_url: finalImageUrl || null,
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
    return <p>Cargando jugadora...</p>;
  }

  if (!player) {
    return <p>No se pudo cargar la jugadora.</p>;
  }

  return (
    <div className="edit-player-page">
      <PageHeader
        variant="detail"
        eyebrow="Perfil de deportista"
        title="Editar perfil"
        subtitle={`${player.first_name} ${player.last_name}`}
        onBack={() => navigate(`/players/${player_id}`)}
      />

      <Card>
        <form onSubmit={handleSubmit} className="form">
          <div className="player-photo-field">
            <div className="player-photo-preview">
              {playerImagePreview || imageUrl ? (
                <img
                  src={playerImagePreview || getAssetUrl(imageUrl)}
                  alt="Foto del deportista"
                />
              ) : (
                <span>
                  {firstName?.charAt(0) || ""}
                  {lastName?.charAt(0) || ""}
                </span>
              )}
            </div>

            <div className="player-photo-content">
              <strong>Foto del deportista</strong>
              <p>Opcional. Se mostrará en el perfil del deportista.</p>

              <label className="button button-secondary player-photo-button">
                Cambiar foto
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/jpg,image/webp"
                  onChange={handlePlayerImageChange}
                  hidden
                />
              </label>
            </div>
          </div>
          <FormField
            label="Nombre"
            error={
              errors.FIRST_NAME_REQUIRED && errorMessages.FIRST_NAME_REQUIRED
            }
          >
            <Input
              name="first_name"
              value={firstName}
              onChange={(e) => {
                setFirstName(e.target.value);

                setErrors((prev) => ({
                  ...prev,
                  FIRST_NAME_REQUIRED: false,
                }));
              }}
              className={errors.FIRST_NAME_REQUIRED ? "input-error" : ""}
            />
          </FormField>

          <FormField
            label="Apellido"
            error={
              errors.LAST_NAME_REQUIRED && errorMessages.LAST_NAME_REQUIRED
            }
          >
            <Input
              name="last_name"
              value={lastName}
              onChange={(e) => {
                setLastName(e.target.value);

                setErrors((prev) => ({
                  ...prev,
                  LAST_NAME_REQUIRED: false,
                }));
              }}
              className={errors.LAST_NAME_REQUIRED ? "input-error" : ""}
            />
          </FormField>
          <FormField
            label="Sexo"
            error={
              errors.SEX_REQUIRED
                ? errorMessages.SEX_REQUIRED
                : errors.INVALID_SEX
                ? errorMessages.INVALID_SEX
                : errors.PLAYER_GENDER_MISMATCH
                ? "No puedes cambiar el sexo porque la jugadora pertenece a una categoría incompatible."
                : ""
            }
          >
            <Select
              value={sex}
              className={
                errors.SEX_REQUIRED ||
                errors.INVALID_SEX ||
                errors.PLAYER_GENDER_MISMATCH
                  ? "input-error"
                  : ""
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
            </Select>
          </FormField>
          <FormField
            label="Fecha de nacimiento"
            error={
              errors.INVALID_DATE_FORMAT
                ? "Formato de fecha inválido"
                : errors.INVALID_BIRTH_DATE
                ? errorMessages.INVALID_BIRTH_DATE
                : ""
            }
          >
            <Input
              type="date"
              value={birthDate}
              className={
                errors.INVALID_DATE_FORMAT || errors.INVALID_BIRTH_DATE
                  ? "input-error"
                  : ""
              }
              onChange={(e) => {
                setBirthDate(e.target.value);

                setErrors((prev) => ({
                  ...prev,
                  INVALID_DATE_FORMAT: false,
                  INVALID_BIRTH_DATE: false,
                }));
              }}
            />
          </FormField>

          <FormField
            label="Posición principal"
            error={errors.INVALID_POSITION ? "Posición inválida" : ""}
          >
            <Select
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
            </Select>
          </FormField>

          <div className="form-actions">
            <Button
              type="button"
              className="button-secondary"
              onClick={() => navigate(`/players/${player_id}`)}
            >
              Cancelar
            </Button>

            <Button
              type="submit"
              className="button-primary"
              disabled={saving || uploadingImage}
            >
              {saving || uploadingImage ? "Guardando..." : "Guardar cambios"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
};
