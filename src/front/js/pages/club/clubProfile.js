import React, { useContext, useEffect, useState } from "react";
import { Context } from "../../store/appContext";
import { useNavigate } from "react-router-dom";

import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { Input } from "../../component/ui/input";
import { FormField } from "../../component/ui/formField";
import { validateClubProfile } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";
import { getAssetUrl } from "../../utils/getAssetUrl";
import "../../../styles/clubShared.css";
import "../../../styles/clubProfile.css";
import { Shield } from "lucide-react";

export const ClubProfile = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();

  const [city, setCity] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [defaultEnrollmentFee, setDefaultEnrollmentFee] = useState("");
  const [defaultMonthlyFee, setDefaultMonthlyFee] = useState("");
  const [clubImageFile, setClubImageFile] = useState(null);
  const [clubImagePreview, setClubImagePreview] = useState("");
  const [name, setName] = useState("");

  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);

  const club = store.club || store.user?.club;
  const canEditClubProfile = store.user?.role === "club_owner";
  const isReadOnly = !canEditClubProfile;

  const getInitials = (value = "") => {
    return value
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((word) => word.charAt(0))
      .join("")
      .toUpperCase();
  };

  useEffect(() => {
    if (club) {
      setCity((club.city || club.location || "").trim());
      setImageUrl(club.image_url?.trim() || "");
      setDefaultEnrollmentFee(club.default_enrollment_fee ?? "");
      setDefaultMonthlyFee(club.default_monthly_fee ?? "");
      setName(club.name?.trim() || "");
    }
  }, [club]);

  useEffect(() => {
    return () => {
      if (clubImagePreview) {
        URL.revokeObjectURL(clubImagePreview);
      }
    };
  }, [clubImagePreview]);

  const handleSave = async (e) => {
    e.preventDefault();

    if (!canEditClubProfile) return;

    if (saving || uploadingImage) return;

    setErrors({});

    const newErrors = validateClubProfile({
      name,
      city,
      defaultEnrollmentFee,
      defaultMonthlyFee,
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setSaving(true);

    let finalImageUrl = imageUrl.trim();

    if (clubImageFile) {
      setUploadingImage(true);

      const uploadResult = await actions.uploadClubImage(clubImageFile);

      setUploadingImage(false);

      if (!uploadResult?.ok) {
        setErrors({ [uploadResult.code]: true });
        setSaving(false);
        return;
      }

      finalImageUrl = uploadResult.data.image_url;
    }

    const result = await actions.updateClub({
      name: name.trim(),
      city: city.trim(),
      image_url: finalImageUrl,
      default_enrollment_fee: defaultEnrollmentFee || 0,
      default_monthly_fee: defaultMonthlyFee || 0,
    });

    if (!result?.ok) {
      setErrors({ [result.code]: true });
      setSaving(false);
      return;
    }

    setSaving(false);
    navigate("/dashboard");
  };

  return (
    <div className="club-profile-page">
      <PageHeader
        tone="dashboard"
        icon={Shield}
        eyebrow={isReadOnly ? "Información" : "Configuración"}
        title="Mi club"
        subtitle={
          isReadOnly
            ? "Consulta la información principal y la configuración de pagos del club."
            : "Actualiza la información principal, imagen y configuración de pagos del club."
        }
      />

      <Card>
        <form className="form" onSubmit={handleSave}>
          <div className="club-profile-preview">
            <div className="club-profile-avatar">
              {clubImagePreview || imageUrl ? (
                <img
                  src={clubImagePreview || getAssetUrl(imageUrl)}
                  alt="Escudo del club"
                />
              ) : (
                <span>{getInitials(club?.name || "Club")}</span>
              )}
            </div>

            <div>
              <h3>{club?.name}</h3>
              <p>{city || "Ubicación sin definir"}</p>
            </div>
          </div>

          {canEditClubProfile && (
            <FormField label="Escudo o avatar del club">
              <div className="club-image-picker">
                <label className="button button-secondary club-image-button">
                  Cambiar imagen
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/jpg,image/webp"
                    hidden
                    onChange={(e) => {
                      const file = e.target.files?.[0];

                      if (!file) return;

                      const previewUrl = URL.createObjectURL(file);

                      setClubImageFile(file);
                      setClubImagePreview(previewUrl);
                      setErrors((prev) => ({
                        ...prev,
                        IMAGE_TOO_LARGE: false,
                        INVALID_IMAGE_FORMAT: false,
                        IMAGE_REQUIRED: false,
                        SESSION_EXPIRED: false,
                        NETWORK_ERROR: false,
                        FORBIDDEN: false,
                        CLUB_NOT_FOUND: false,
                      }));
                    }}
                  />
                </label>

                <small className="form-helper">
                  Puedes subir un escudo o avatar desde tu galería. Formatos:
                  PNG, JPG o WEBP.
                </small>
              </div>
            </FormField>
          )}
          <FormField
            label="Nombre del club"
            error={
              errors.CLUB_NAME_REQUIRED
                ? errorMessages.CLUB_NAME_REQUIRED
                : null
            }
          >
            <Input
              type="text"
              className={errors.CLUB_NAME_REQUIRED ? "input-error" : ""}
              placeholder={isReadOnly ? "No registrado" : "Ej: Los Halcones"}
              value={name}
              disabled={isReadOnly}
              onChange={(e) => {
                setName(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  CLUB_NAME_REQUIRED: false,
                  SESSION_EXPIRED: false,
                  NETWORK_ERROR: false,
                  FORBIDDEN: false,
                  CLUB_NOT_FOUND: false,
                }));
              }}
            />
          </FormField>

          <FormField
            label="Ciudad"
            error={
              errors.CITY_REQUIRED
                ? errorMessages.CITY_REQUIRED
                : errors.CITY_TOO_LONG
                ? errorMessages.CITY_TOO_LONG
                : null
            }
          >
            <Input
              type="text"
              className={
                errors.CITY_REQUIRED || errors.CITY_TOO_LONG
                  ? "input-error"
                  : ""
              }
              placeholder={isReadOnly ? "No registrado" : "Ej: Cagua"}
              value={city}
              maxLength={120}
              disabled={isReadOnly}
              onChange={(e) => {
                setCity(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  CITY_REQUIRED: false,
                  CITY_TOO_LONG: false,
                  SESSION_EXPIRED: false,
                  NETWORK_ERROR: false,
                  FORBIDDEN: false,
                  CLUB_NOT_FOUND: false,
                }));
              }}
            />
          </FormField>

          <FormField
            label="País"
          >
            <Input
              type="text"
              value={club?.country?.name || "No clasificado"}
              disabled
              className="input-readonly"
            />
          </FormField>

          <FormField label="Estado / Provincia / Región">
            <Input
              type="text"
              value={
                club?.administrative_area?.name ||
                club?.state ||
                "No clasificado"
              }
              disabled
              className="input-readonly"
            />
          </FormField>

          <FormField label="Zona horaria">
            <Input
              type="text"
              value={club?.timezone || "No configurada"}
              disabled
              className="input-readonly"
            />
          </FormField>

          <FormField label="Moneda">
            <Input
              type="text"
              value={
                club?.currency
                  ? `${club.currency.code} — ${club.currency.name}`
                  : club?.currency_code || "No configurada"
              }
              disabled
              className="input-readonly"
            />
          </FormField>

          <div className="club-profile-section">
            <div>
              <h3>Configuración de pagos</h3>
              <p>
                Define los montos base que se usarán al configurar pagos de las
                jugadoras. Cada jugadora puede tener un monto personalizado sin
                cambiar estos valores del club.
              </p>
            </div>

            <FormField
              label={`Inscripción por defecto (${
                club?.currency_code || "moneda no configurada"
              })`}
              error={
                errors.INVALID_DEFAULT_ENROLLMENT_FEE
                  ? errorMessages.INVALID_DEFAULT_ENROLLMENT_FEE
                  : null
              }
            >
              <Input
                type="number"
                className={
                  errors.INVALID_DEFAULT_ENROLLMENT_FEE ? "input-error" : ""
                }
                placeholder={isReadOnly ? "No registrado" : "Ej: 20"}
                value={defaultEnrollmentFee}
                disabled={isReadOnly}
                onChange={(e) => {
                  setDefaultEnrollmentFee(e.target.value);
                  setErrors((prev) => ({
                    ...prev,
                    INVALID_DEFAULT_ENROLLMENT_FEE: false,
                    SESSION_EXPIRED: false,
                    NETWORK_ERROR: false,
                    FORBIDDEN: false,
                    CLUB_NOT_FOUND: false,
                  }));
                }}
              />
            </FormField>

            <FormField
              label={`Mensualidad por defecto (${
                club?.currency_code || "moneda no configurada"
              })`}
              error={
                errors.INVALID_DEFAULT_MONTHLY_FEE
                  ? errorMessages.INVALID_DEFAULT_MONTHLY_FEE
                  : null
              }
            >
              <Input
                type="number"
                className={
                  errors.INVALID_DEFAULT_MONTHLY_FEE ? "input-error" : ""
                }
                placeholder={isReadOnly ? "No registrado" : "Ej: 25"}
                value={defaultMonthlyFee}
                disabled={isReadOnly}
                onChange={(e) => {
                  setDefaultMonthlyFee(e.target.value);
                  setErrors((prev) => ({
                    ...prev,
                    INVALID_DEFAULT_MONTHLY_FEE: false,
                    SESSION_EXPIRED: false,
                    NETWORK_ERROR: false,
                    FORBIDDEN: false,
                    CLUB_NOT_FOUND: false,
                  }));
                }}
              />
            </FormField>
          </div>

          {errors.IMAGE_TOO_LARGE && (
            <p className="form-error">{errorMessages.IMAGE_TOO_LARGE}</p>
          )}

          {errors.INVALID_IMAGE_FORMAT && (
            <p className="form-error">{errorMessages.INVALID_IMAGE_FORMAT}</p>
          )}

          {errors.IMAGE_REQUIRED && (
            <p className="form-error">{errorMessages.IMAGE_REQUIRED}</p>
          )}

          {(errors.SESSION_EXPIRED ||
            errors.NETWORK_ERROR ||
            errors.FORBIDDEN ||
            errors.CLUB_NOT_FOUND) && (
            <p className="form-error">
              {errors.SESSION_EXPIRED
                ? errorMessages.SESSION_EXPIRED
                : errors.NETWORK_ERROR
                ? errorMessages.NETWORK_ERROR
                : errors.FORBIDDEN
                ? errorMessages.FORBIDDEN
                : errorMessages.CLUB_NOT_FOUND}
            </p>
          )}

          <div className="form-actions">
            {canEditClubProfile && (
              <Button type="submit" disabled={saving || uploadingImage}>
                {saving || uploadingImage ? "Guardando..." : "Guardar cambios"}
              </Button>
            )}

            <Button
              type="button"
              variant="secondary"
              onClick={() => navigate("/dashboard")}
            >
              {isReadOnly ? "Volver al panel" : "Cancelar"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
};
