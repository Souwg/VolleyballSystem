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
import "../../../styles/clubProfile.css";
import { Shield } from "lucide-react";

export const ClubProfile = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();

  const [location, setLocation] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [defaultEnrollmentFee, setDefaultEnrollmentFee] = useState("");
  const [defaultMonthlyFee, setDefaultMonthlyFee] = useState("");
  const [clubImageFile, setClubImageFile] = useState(null);
  const [clubImagePreview, setClubImagePreview] = useState("");
  const [name, setName] = useState("");
  const [state, setState] = useState("");

  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);

  const club = store.club || store.user?.club;

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
      setLocation(club.location?.trim() || "");
      setImageUrl(club.image_url?.trim() || "");
      setDefaultEnrollmentFee(club.default_enrollment_fee ?? "");
      setDefaultMonthlyFee(club.default_monthly_fee ?? "");
      setName(club.name?.trim() || "");
      setState(club.state?.trim() || "");
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

    if (saving || uploadingImage) return;

    setErrors({});

    const newErrors = validateClubProfile({
      name,
      location,
      state,
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
      location: location.trim(),
      state: state.trim(),
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
        eyebrow="Configuración"
        title="Mi club"
        subtitle="Actualiza la información principal, imagen y configuración de pagos del club."
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
              <p>{location || "Ubicación sin definir"}</p>
            </div>
          </div>

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
                Puedes subir un escudo o avatar desde tu galería. Formatos: PNG,
                JPG o WEBP.
              </small>
            </div>
          </FormField>
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
              placeholder="Ej: Los Halcones"
              value={name}
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
              errors.LOCATION_REQUIRED ? errorMessages.LOCATION_REQUIRED : null
            }
          >
            <Input
              type="text"
              className={errors.LOCATION_REQUIRED ? "input-error" : ""}
              placeholder="Ej: Cagua"
              value={location}
              onChange={(e) => {
                setLocation(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  LOCATION_REQUIRED: false,
                  SESSION_EXPIRED: false,
                  NETWORK_ERROR: false,
                  FORBIDDEN: false,
                  CLUB_NOT_FOUND: false,
                }));
              }}
            />
          </FormField>

          <FormField
            label="Estado"
            error={errors.STATE_REQUIRED ? errorMessages.STATE_REQUIRED : null}
          >
            <Input
              type="text"
              className={errors.STATE_REQUIRED ? "input-error" : ""}
              placeholder="Ej: Aragua"
              value={state}
              onChange={(e) => {
                setState(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  STATE_REQUIRED: false,
                  SESSION_EXPIRED: false,
                  NETWORK_ERROR: false,
                  FORBIDDEN: false,
                  CLUB_NOT_FOUND: false,
                }));
              }}
            />
          </FormField>

          <div className="club-profile-section">
            <div>
              <h3>Configuración de pagos</h3>
              <p>
                Define los montos base que se usarán al configurar pagos de
                nuevos deportistas.
              </p>
            </div>

            <FormField
              label="Inscripción por defecto"
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
                placeholder="Ej: 20"
                value={defaultEnrollmentFee}
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
              label="Mensualidad por defecto"
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
                placeholder="Ej: 25"
                value={defaultMonthlyFee}
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
            <Button type="submit" disabled={saving || uploadingImage}>
              {saving || uploadingImage ? "Guardando..." : "Guardar cambios"}
            </Button>

            <Button
              type="button"
              variant="secondary"
              onClick={() => navigate("/dashboard")}
            >
              Cancelar
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
};
