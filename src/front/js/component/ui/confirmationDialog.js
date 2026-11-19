import React, { useEffect, useRef } from "react";

import { Button } from "./button";

export const ConfirmationDialog = ({
  busy = false,
  children,
  confirmLabel = "Confirmar",
  danger = false,
  descriptionId,
  onCancel,
  onConfirm,
  title,
  titleId,
}) => {
  const dialogRef = useRef(null);
  const cancelRef = useRef(null);
  const returnFocusRef = useRef(document.activeElement);

  useEffect(() => {
    cancelRef.current?.focus();

    const getFocusable = () => [
      ...(dialogRef.current?.querySelectorAll(
        "button:not([disabled]), [href], input:not([disabled]), " +
          "select:not([disabled]), textarea:not([disabled]), " +
          "[tabindex]:not([tabindex='-1'])",
      ) || []),
    ];

    const handleKeyDown = (event) => {
      if (event.key === "Escape" && !busy) {
        onCancel();
        return;
      }

      if (event.key !== "Tab") return;
      const controls = getFocusable();

      if (!controls.length) {
        event.preventDefault();
        dialogRef.current?.focus();
        return;
      }

      const first = controls[0];
      const last = controls[controls.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      returnFocusRef.current?.focus?.();
    };
  }, [busy, onCancel]);

  return (
    <div
      className="tournament-dialog-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onCancel();
      }}
    >
      <div
        ref={dialogRef}
        className="tournament-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        tabIndex="-1"
      >
        <h2 id={titleId}>{title}</h2>
        <div id={descriptionId}>{children}</div>
        <div className="tournament-dialog-actions">
          <button
            ref={cancelRef}
            type="button"
            className="button button-secondary"
            disabled={busy}
            onClick={onCancel}
          >
            Volver
          </button>
          <Button
            type="button"
            variant={danger ? "danger" : "primary"}
            disabled={busy}
            onClick={onConfirm}
          >
            {busy ? "Guardando..." : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
};
