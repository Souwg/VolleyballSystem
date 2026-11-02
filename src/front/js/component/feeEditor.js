import React, { useState } from "react";

import { Button } from "./ui/button";
import { FormField } from "./ui/formField";
import { Input } from "./ui/input";
import { errorMessages } from "../utils/errorMessages";
import { formatMoney } from "../utils/money";

import "../../styles/feeEditor.css";

export const FeeEditor = ({ label, value, currencyCode, helper, onSave }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [amount, setAmount] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const hasValue = Number(value) > 0;

  const openEditor = () => {
    setAmount(hasValue ? String(value) : "");
    setError("");
    setIsEditing(true);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (saving) return;

    if (amount === "" || Number.isNaN(Number(amount)) || Number(amount) < 0) {
      setError(errorMessages.INVALID_AMOUNT);
      return;
    }

    setError("");
    setSaving(true);

    const result = await onSave(amount);

    setSaving(false);

    if (!result.ok) {
      setError(
        errorMessages[result.code] ||
          result.message ||
          errorMessages.NETWORK_ERROR,
      );
      return;
    }

    setIsEditing(false);
  };

  return (
    <div className="fee-editor">
      <div className="fee-editor-summary">
        <div>
          <span>{label}</span>
          <strong>
            {hasValue ? formatMoney(value, currencyCode) : "Sin definir"}
          </strong>
        </div>

        {!isEditing && (
          <Button type="button" variant="secondary" onClick={openEditor}>
            {hasValue ? "Cambiar monto" : "Definir monto"}
          </Button>
        )}
      </div>

      {isEditing && (
        <form className="form fee-editor-form" onSubmit={handleSubmit}>
          <FormField
            label={`${label} (${currencyCode || "moneda no configurada"})`}
            helper={helper}
            error={error || null}
          >
            <Input
              type="number"
              min="0"
              step="0.01"
              value={amount}
              className={error ? "input-error" : ""}
              onChange={(event) => {
                setAmount(event.target.value);
                setError("");
              }}
              placeholder="Ej: 25.00"
            />
          </FormField>

          <div className="form-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setIsEditing(false)}
              disabled={saving}
            >
              Cancelar
            </Button>

            <Button type="submit" disabled={saving}>
              {saving ? "Guardando..." : "Guardar monto"}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
};
