import React, { useContext, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getAssetUrl } from "../../utils/getAssetUrl";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { Input } from "../../component/ui/input";
import { Select } from "../../component/ui/select";
import { FormField } from "../../component/ui/formField";
import {
  validatePlayerPaymentSettings,
  validatePaymentRegistration,
} from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";
import "../../../styles/payments.css";
import "../../../styles/playerDetails.css";

const STATUS_LABELS = {
  pending: "Pendiente",
  paid: "Pagado",
  overdue: "Atrasado",
  cancelled: "Cancelado",
};

const STATUS_CLASSES = {
  pending: "payment-status pending",
  paid: "payment-status paid",
  overdue: "payment-status overdue",
  cancelled: "payment-status cancelled",
};

const PAYMENT_TYPE_LABELS = {
  enrollment: "Inscripción",
  monthly: "Mensualidad",
  uniform: "Uniforme",
  tournament: "Torneo",
  extra: "Extra",
};

const PAYMENT_METHOD_LABELS = {
  cash: "Efectivo",
  transfer: "Transferencia",
  zelle: "Zelle",
  mobile_payment: "Pago móvil",
  other: "Otro",
};

const formatDate = (date) => {
  if (!date) return null;

  return new Date(`${date}T00:00:00`).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
};
const formatMoney = (amount) => {
  const value = Number(amount || 0);

  return value.toLocaleString("es-ES", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

const getPaymentDescription = (payment) => {
  if (payment.payment_type === "monthly") {
    return `${formatDate(payment.period_start)} - ${formatDate(
      payment.period_end,
    )}`;
  }

  if (payment.payment_type === "enrollment") {
    return "Pago único de inscripción";
  }

  return payment.notes || "Pago del deportista";
};

const getPaymentMetaText = (payment) => {
  if (payment.status === "paid") {
    return payment.payment_date
      ? `Pagado el ${formatDate(payment.payment_date)}`
      : "Pagado";
  }

  if (payment.status === "overdue" && payment.due_date) {
    return `Atrasado · Debía pagarse el ${formatDate(payment.due_date)}`;
  }

  if (payment.status === "pending" && payment.due_date) {
    return `Pendiente · Pago esperado el ${formatDate(payment.due_date)}`;
  }

  if (payment.status === "cancelled") {
    return "Pago cancelado";
  }

  return null;
};

export const PlayerPayments = () => {
  const { player_id } = useParams();
  const navigate = useNavigate();
  const { store, actions } = useContext(Context);

  const club = store.club || store.user?.club;
  const payments = store.playerPayments || [];

  const [player, setPlayer] = useState(null);
  const [loading, setLoading] = useState(true);
  const [savingSettings, setSavingSettings] = useState(false);
  const [customEnrollmentFee, setCustomEnrollmentFee] = useState(false);
  const [customMonthlyFee, setCustomMonthlyFee] = useState(false);
  const [visiblePayments, setVisiblePayments] = useState(5);
  const [formErrors, setFormErrors] = useState({});
  const [showPaymentSettings, setShowPaymentSettings] = useState(false);
  const [registeringPaymentId, setRegisteringPaymentId] = useState(null);
  const [expandedPaymentId, setExpandedPaymentId] = useState(null);
  const [receiptLoadingId, setReceiptLoadingId] = useState(null);
  const [receiptErrors, setReceiptErrors] = useState({});
  const todayDate = new Date().toISOString().slice(0, 10);
  const [paymentRegisterForm, setPaymentRegisterForm] = useState({
    payment_date: new Date().toISOString().slice(0, 10),
    payment_method: "",
    reference: "",
    notes: "",
  });
  const [paymentRegisterErrors, setPaymentRegisterErrors] = useState({});

  const [paymentForm, setPaymentForm] = useState({
    enrollment_date: "",
    enrollment_fee: "",
    monthly_fee: "",
  });

  const pendingCount = payments.filter(
    (payment) => payment.status === "pending",
  ).length;
  const paidCount = payments.filter(
    (payment) => payment.status === "paid",
  ).length;
  const overdueCount = payments.filter(
    (payment) => payment.status === "overdue",
  ).length;

  const enrollmentPayment = payments.find(
    (payment) => payment.payment_type === "enrollment",
  );

  const hasEnrollmentDate = Boolean(player?.enrollment_date);
  const enrollmentIsPaid = enrollmentPayment?.status === "paid";

  const currentMonthlyPayment = [...payments]
    .filter(
      (payment) =>
        payment.payment_type === "monthly" &&
        ["pending", "overdue"].includes(payment.status),
    )
    .sort((a, b) => new Date(a.due_date) - new Date(b.due_date))[0];

  const getPlayerFullName = () => {
    if (!player) return "el deportista";

    return `${player.first_name} ${player.last_name}`;
  };

  const getWhatsappPhone = () => {
    if (!player?.representative_phone) return null;

    return player.representative_phone.replace(/\D/g, "");
  };

  const buildWhatsappMessage = (payment, receipt) => {
    const playerName = getPlayerFullName();

    const receiptUrl = receipt.pdf_url ? getAssetUrl(receipt.pdf_url) : "";

    return encodeURIComponent(
      `Hola, te compartimos el recibo de pago de ${playerName}.\n\n` +
        `Recibo: ${receipt.receipt_number}\n` +
        `Concepto: ${PAYMENT_TYPE_LABELS[payment.payment_type] || "Pago"}\n` +
        `Monto: $${formatMoney(payment.amount)}\n` +
        `Fecha: ${formatDate(payment.payment_date) || "No registrada"}\n` +
        `Método: ${
          PAYMENT_METHOD_LABELS[payment.payment_method] || "No registrado"
        }\n` +
        `Referencia: ${payment.reference || "Sin referencia"}` +
        `${receiptUrl ? `\n\nVer PDF: ${receiptUrl}` : ""}`,
    );
  };

  const handleSendReceiptWhatsapp = async (payment) => {
    setReceiptErrors({});

    const phone = getWhatsappPhone();

    if (!phone) {
      setReceiptErrors({
        [payment.id]: "Este deportista no tiene teléfono de representante.",
      });
      return;
    }

    setReceiptLoadingId(payment.id);

    const receiptResult = await actions.createPaymentReceipt(payment.id);

    setReceiptLoadingId(null);

    if (!receiptResult.ok) {
      setReceiptErrors({
        [payment.id]: receiptResult.message || "No se pudo generar el recibo.",
      });
      return;
    }

    const receipt = receiptResult.data.receipt;
    const message = buildWhatsappMessage(payment, receipt);

    await actions.markPaymentReceiptShared(receipt.id, {
      sent_channel: "whatsapp",
      sent_to: phone,
    });

    await loadPlayerPayments();

    window.open(`https://wa.me/${phone}?text=${message}`, "_blank");
  };

  const loadPlayerPayments = async () => {
    setLoading(true);

    const result = await actions.getPlayerPayments(player_id);

    if (result.ok) {
      const data = result.data;

      setPlayer(data.player);

      setPaymentForm({
        enrollment_date: data.player.enrollment_date || "",
        enrollment_fee: data.player.enrollment_fee ?? "",
        monthly_fee: data.player.monthly_fee ?? "",
      });

      setCustomEnrollmentFee(data.player.enrollment_fee !== null);
      setCustomMonthlyFee(data.player.monthly_fee !== null);
    }

    setLoading(false);
  };

  useEffect(() => {
    loadPlayerPayments();
  }, [player_id]);

  const handlePaymentFormChange = (event) => {
    const { name, value } = event.target;

    setPaymentForm((prev) => ({
      ...prev,
      [name]: value,
    }));

    setFormErrors({});
  };

  const handleSavePaymentSettings = async () => {
    const errors = validatePlayerPaymentSettings({
      enrollment_date: paymentForm.enrollment_date,
      customEnrollmentFee,
      customMonthlyFee,
      enrollment_fee: paymentForm.enrollment_fee,
      monthly_fee: paymentForm.monthly_fee,
      club,
    });

    setFormErrors(errors);

    if (Object.keys(errors).length > 0) return;

    setSavingSettings(true);

    const paymentSettings = {
      enrollment_date: paymentForm.enrollment_date,
    };

    if (customEnrollmentFee) {
      paymentSettings.enrollment_fee = Number(paymentForm.enrollment_fee);
    }

    if (customMonthlyFee) {
      paymentSettings.monthly_fee = Number(paymentForm.monthly_fee);
    }

    const result = await actions.updatePlayerPaymentSettings(
      player_id,
      paymentSettings,
    );

    if (result.ok) {
      await loadPlayerPayments();
      setShowPaymentSettings(false);
    } else if (result.code) {
      setFormErrors({ [result.code]: true });
    }

    setSavingSettings(false);
  };

  const openRegisterPayment = (payment) => {
    setRegisteringPaymentId(payment.id);
    setExpandedPaymentId(null);

    setPaymentRegisterForm({
      payment_date: todayDate,
      payment_method: "",
      reference: "",
      notes: "",
    });

    setPaymentRegisterErrors({});
  };

  const closeRegisterPayment = () => {
    setRegisteringPaymentId(null);
    setPaymentRegisterErrors({});
  };

  const togglePaymentDetails = (paymentId) => {
    setRegisteringPaymentId(null);

    setExpandedPaymentId((currentId) =>
      currentId === paymentId ? null : paymentId,
    );
  };

  const handlePaymentRegisterChange = (event) => {
    const { name, value } = event.target;

    setPaymentRegisterForm((prev) => ({
      ...prev,
      [name]: value,
    }));

    setPaymentRegisterErrors((prev) => ({
      ...prev,
      PAYMENT_DATE_REQUIRED: false,
      PAYMENT_METHOD_REQUIRED: false,
      INVALID_PAYMENT_METHOD: false,
      INVALID_DATE_FORMAT: false,
      INVALID_PAYMENT_DATE: false,
    }));
  };

  const handleRegisterPayment = async (payment) => {
    const errors = validatePaymentRegistration(paymentRegisterForm);

    setPaymentRegisterErrors(errors);

    if (Object.keys(errors).length > 0) return;

    const result = await actions.updatePayment(payment.id, {
      status: "paid",
      payment_date: paymentRegisterForm.payment_date,
      payment_method: paymentRegisterForm.payment_method,
      reference: paymentRegisterForm.reference,
      notes: paymentRegisterForm.notes,
    });

    if (result.ok) {
      closeRegisterPayment();
      await loadPlayerPayments();
    } else if (result.code) {
      setPaymentRegisterErrors({ [result.code]: true });
    }
  };

  const handleMarkAsPending = async (payment) => {
    const confirmed = window.confirm(
      "¿Seguro que quieres revertir este pago? Se eliminará la fecha de pago registrada.",
    );

    if (!confirmed) return;

    await actions.updatePayment(payment.id, {
      status: "pending",
    });

    await loadPlayerPayments();
  };

  if (loading) return null;

  return (
    <div className="payments-page">
      <button
        type="button"
        className="page-back-button"
        onClick={() => navigate(`/players/${player_id}`)}
      >
        ← Volver al perfil
      </button>

      <PageHeader
        variant="detail"
        eyebrow="Pagos del deportista"
        title={
          player
            ? `${player.first_name} ${player.last_name}`
            : "Pagos del deportista"
        }
        subtitle="Consulta el estado de pagos, ajusta la configuración y revisa el historial completo."
      />

      <div className="payments-summary-grid">
        <Card className="payment-summary-card">
          <span>Pendientes</span>
          <strong>{pendingCount}</strong>
        </Card>

        <Card className="payment-summary-card">
          <span>Pagados</span>
          <strong>{paidCount}</strong>
        </Card>

        <Card className="payment-summary-card">
          <span>Atrasados</span>
          <strong>{overdueCount}</strong>
        </Card>
      </div>

      <Card className="player-payment-settings-card">
        <div className="player-section-header">
          <div>
            <span className="player-card-label">Cobro mensual</span>
            <h3>Ajustes de cobro</h3>
          </div>

          <Button
            type="button"
            variant="secondary"
            onClick={() => setShowPaymentSettings((prev) => !prev)}
          >
            {showPaymentSettings ? "Ocultar" : "Editar"}
          </Button>
        </div>

        {showPaymentSettings ? (
          <>
            <div className="player-payment-settings-grid">
              <label className="field-group">
                <span>Fecha de inscripción</span>
                <Input
                  type="date"
                  name="enrollment_date"
                  value={paymentForm.enrollment_date}
                  onChange={handlePaymentFormChange}
                />

                {formErrors.ENROLLMENT_DATE_REQUIRED && (
                  <p className="form-error">
                    {errorMessages.ENROLLMENT_DATE_REQUIRED}
                  </p>
                )}
              </label>
            </div>

            <div className="player-payment-defaults">
              <span>Montos del club</span>

              <div className="player-payment-defaults-grid">
                <div>
                  <small>Inscripción</small>
                  <strong>${formatMoney(club?.default_enrollment_fee)}</strong>
                </div>

                <div>
                  <small>Mensualidad</small>
                  <strong>${formatMoney(club?.default_monthly_fee)}</strong>
                </div>
              </div>
              {formErrors.CLUB_PAYMENT_DEFAULTS_REQUIRED && (
                <p className="form-error">
                  {errorMessages.CLUB_PAYMENT_DEFAULTS_REQUIRED}
                </p>
              )}
            </div>

            {enrollmentIsPaid ? (
              <div className="player-payment-locked-box">
                <strong>Inscripción pagada</strong>
                <span>
                  Este monto ya fue registrado como pagado. Para modificarlo,
                  primero revierte el pago desde el historial.
                </span>
              </div>
            ) : (
              <>
                <label className="player-payment-custom-toggle">
                  <input
                    type="checkbox"
                    checked={customEnrollmentFee}
                    onChange={(event) => {
                      const checked = event.target.checked;

                      setCustomEnrollmentFee(checked);
                      setFormErrors({});

                      if (!checked) {
                        setPaymentForm((prev) => ({
                          ...prev,
                          enrollment_fee: "",
                        }));
                      }
                    }}
                  />
                  <span>Personalizar inscripción</span>
                </label>

                {customEnrollmentFee && (
                  <div className="player-payment-settings-grid">
                    <label className="field-group">
                      <span>Pago de inscripción personalizado</span>
                      <Input
                        type="number"
                        name="enrollment_fee"
                        placeholder="Ej: 20"
                        value={paymentForm.enrollment_fee}
                        onChange={handlePaymentFormChange}
                      />

                      {formErrors.ENROLLMENT_FEE_REQUIRED && (
                        <p className="form-error">
                          {errorMessages.ENROLLMENT_FEE_REQUIRED}
                        </p>
                      )}

                      {formErrors.INVALID_ENROLLMENT_FEE && (
                        <p className="form-error">
                          {errorMessages.INVALID_ENROLLMENT_FEE}
                        </p>
                      )}
                    </label>
                  </div>
                )}
              </>
            )}

            <label className="player-payment-custom-toggle">
              <input
                type="checkbox"
                checked={customMonthlyFee}
                onChange={(event) => {
                  const checked = event.target.checked;

                  setCustomMonthlyFee(checked);
                  setFormErrors({});

                  if (!checked) {
                    setPaymentForm((prev) => ({
                      ...prev,
                      monthly_fee: "",
                    }));
                  }
                }}
              />
              <span>Personalizar mensualidad para este deportista</span>
            </label>

            {customMonthlyFee && (
              <div className="player-payment-settings-grid">
                <label className="field-group">
                  <span>Mensualidad personalizada</span>
                  <Input
                    type="number"
                    name="monthly_fee"
                    placeholder="Ej: 25"
                    value={paymentForm.monthly_fee}
                    onChange={handlePaymentFormChange}
                  />

                  {formErrors.MONTHLY_FEE_REQUIRED && (
                    <p className="form-error">
                      {errorMessages.MONTHLY_FEE_REQUIRED}
                    </p>
                  )}

                  {formErrors.INVALID_MONTHLY_FEE && (
                    <p className="form-error">
                      {errorMessages.INVALID_MONTHLY_FEE}
                    </p>
                  )}
                </label>
              </div>
            )}

            <p className="player-payment-settings-help">
              La fecha de inscripción inicia el ciclo de pagos. Puedes usar los
              montos del club o personalizar solo la inscripción o solo la
              mensualidad de este deportista.
            </p>

            <Button
              type="button"
              onClick={handleSavePaymentSettings}
              disabled={savingSettings}
            >
              {savingSettings ? "Guardando..." : "Guardar configuración"}
            </Button>
          </>
        ) : (
          <div className="player-payment-settings-preview">
            <div>
              <span>Fecha de inscripción</span>
              <strong>
                {formatDate(paymentForm.enrollment_date) || "Sin definir"}
              </strong>
            </div>

            <div>
              <span>Montos</span>
              <strong>
                {customEnrollmentFee || customMonthlyFee
                  ? "Tiene montos personalizados"
                  : "Usa montos del club"}
              </strong>
            </div>
          </div>
        )}
      </Card>

      <Card>
        <div className="payments-list-header">
          <h3>Historial completo</h3>
          <span>
            Mostrando {Math.min(visiblePayments, payments.length)} de{" "}
            {payments.length}
          </span>
        </div>

        {payments.length === 0 ? (
          <p className="empty-state">
            Todavía no hay pagos registrados para este deportista.
          </p>
        ) : (
          <>
            <div className="payments-list">
              {payments.slice(0, visiblePayments).map((payment) => (
                <div key={payment.id} className="payment-row">
                  <div>
                    <h4>
                      {PAYMENT_TYPE_LABELS[payment.payment_type] || "Pago"} · $
                      {formatMoney(payment.amount)}
                    </h4>

                    <p>{getPaymentDescription(payment)}</p>

                    {getPaymentMetaText(payment) && (
                      <p>{getPaymentMetaText(payment)}</p>
                    )}
                  </div>

                  <div className="payment-row-actions">
                    <span className={STATUS_CLASSES[payment.status]}>
                      {STATUS_LABELS[payment.status]}
                    </span>

                    {payment.status === "paid" ? (
                      <>
                        <Button
                          type="button"
                          variant="secondary"
                          className="payment-receipt-button"
                          onClick={() => handleSendReceiptWhatsapp(payment)}
                          disabled={receiptLoadingId === payment.id}
                        >
                          {receiptLoadingId === payment.id
                            ? "Preparando..."
                            : payment.receipt?.sent_at
                            ? "Reenviar recibo"
                            : "Enviar recibo"}
                        </Button>

                        <div className="payment-secondary-actions">
                          <button
                            type="button"
                            className="payment-details-toggle"
                            onClick={() => togglePaymentDetails(payment.id)}
                          >
                            {expandedPaymentId === payment.id
                              ? "Ocultar detalles"
                              : "Ver detalles"}
                          </button>

                          <button
                            type="button"
                            className="payment-revert-link"
                            onClick={() => handleMarkAsPending(payment)}
                          >
                            Revertir pago
                          </button>
                        </div>

                        {receiptErrors[payment.id] && (
                          <p className="form-error">
                            {receiptErrors[payment.id]}
                          </p>
                        )}
                      </>
                    ) : registeringPaymentId === payment.id ? null : (
                      <Button
                        type="button"
                        onClick={() => openRegisterPayment(payment)}
                      >
                        Registrar pago
                      </Button>
                    )}
                  </div>
                  {expandedPaymentId === payment.id && (
                    <div className="payment-details-panel">
                      <div className="payment-details-grid">
                        <div>
                          <span>Fecha de pago</span>
                          <strong>
                            {formatDate(payment.payment_date) ||
                              "No registrada"}
                          </strong>
                        </div>

                        <div>
                          <span>Método</span>
                          <strong>
                            {PAYMENT_METHOD_LABELS[payment.payment_method] ||
                              "No registrado"}
                          </strong>
                        </div>

                        <div>
                          <span>Referencia</span>
                          <strong>
                            {payment.reference || "Sin referencia"}
                          </strong>
                        </div>

                        <div>
                          <span>Fecha esperada</span>
                          <strong>
                            {formatDate(payment.due_date) || "No definida"}
                          </strong>
                        </div>

                        {payment.notes && (
                          <div className="payment-details-note">
                            <span>Notas</span>
                            <strong>{payment.notes}</strong>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  {registeringPaymentId === payment.id && (
                    <div className="payment-register-panel">
                      <div className="payment-register-header">
                        <strong>Registrar pago</strong>
                        <span>
                          {PAYMENT_TYPE_LABELS[payment.payment_type] || "Pago"}{" "}
                          · ${formatMoney(payment.amount)}
                        </span>
                      </div>

                      <div className="payment-register-grid">
                        <FormField
                          label="Fecha de pago"
                          error={
                            paymentRegisterErrors.PAYMENT_DATE_REQUIRED
                              ? errorMessages.PAYMENT_DATE_REQUIRED
                              : paymentRegisterErrors.INVALID_PAYMENT_DATE
                              ? errorMessages.INVALID_PAYMENT_DATE
                              : paymentRegisterErrors.INVALID_DATE_FORMAT
                              ? errorMessages.INVALID_DATE_FORMAT
                              : null
                          }
                        >
                          <Input
                            type="date"
                            name="payment_date"
                            value={paymentRegisterForm.payment_date}
                            max={todayDate}
                            className={
                              paymentRegisterErrors.PAYMENT_DATE_REQUIRED ||
                              paymentRegisterErrors.INVALID_PAYMENT_DATE ||
                              paymentRegisterErrors.INVALID_DATE_FORMAT
                                ? "input-error"
                                : ""
                            }
                            onChange={handlePaymentRegisterChange}
                          />
                        </FormField>

                        <FormField
                          label="Método de pago"
                          error={
                            paymentRegisterErrors.PAYMENT_METHOD_REQUIRED &&
                            errorMessages.PAYMENT_METHOD_REQUIRED
                          }
                        >
                          <Select
                            name="payment_method"
                            value={paymentRegisterForm.payment_method}
                            className={
                              paymentRegisterErrors.PAYMENT_METHOD_REQUIRED
                                ? "input-error"
                                : ""
                            }
                            onChange={handlePaymentRegisterChange}
                          >
                            <option value="">Selecciona método</option>
                            <option value="cash">Efectivo</option>
                            <option value="transfer">Transferencia</option>
                            <option value="zelle">Zelle</option>
                            <option value="mobile_payment">Pago móvil</option>
                            <option value="other">Otro</option>
                          </Select>
                        </FormField>

                        <FormField label="Referencia" helper="Opcional">
                          <Input
                            name="reference"
                            placeholder="Ej: 839201"
                            value={paymentRegisterForm.reference}
                            onChange={handlePaymentRegisterChange}
                          />
                        </FormField>

                        <FormField label="Notas" helper="Opcional">
                          <Input
                            name="notes"
                            placeholder="Ej: Pagó junto con mensualidad anterior"
                            value={paymentRegisterForm.notes}
                            onChange={handlePaymentRegisterChange}
                          />
                        </FormField>
                      </div>

                      <div className="payment-register-actions">
                        <Button
                          type="button"
                          variant="secondary"
                          onClick={closeRegisterPayment}
                        >
                          Cancelar
                        </Button>

                        <Button
                          type="button"
                          onClick={() => handleRegisterPayment(payment)}
                        >
                          Guardar pago
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {visiblePayments < payments.length && (
              <Button
                type="button"
                variant="secondary"
                onClick={() => setVisiblePayments((prev) => prev + 5)}
              >
                Ver más pagos
              </Button>
            )}
          </>
        )}
      </Card>
    </div>
  );
};
