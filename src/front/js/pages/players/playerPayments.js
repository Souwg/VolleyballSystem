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
import "../../../styles/paymentShared.css";
import "../../../styles/playerPayments.css";
import { AlertTriangle, Clock3, CircleCheckBig } from "lucide-react";

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
  referee: "Arbitraje",
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

const getAnchoredCycleStart = (enrollmentDate, offset) => {
  if (!enrollmentDate) return null;

  const [year, month, day] = enrollmentDate.split("-").map(Number);

  const absoluteMonth = month - 1 + offset;

  const targetYear = year + Math.floor(absoluteMonth / 12);

  const targetMonthIndex = ((absoluteMonth % 12) + 12) % 12;

  const lastDay = new Date(targetYear, targetMonthIndex + 1, 0).getDate();

  return new Date(targetYear, targetMonthIndex, Math.min(day, lastDay));
};

const getValidLastPaidMonths = (enrollmentDate, todayDate) => {
  if (!enrollmentDate || !todayDate) {
    return [];
  }

  const [todayYear, todayMonth, todayDay] = todayDate.split("-").map(Number);

  const today = new Date(todayYear, todayMonth - 1, todayDay);

  const [enrollmentYear, enrollmentMonth] = enrollmentDate
    .split("-")
    .map(Number);

  const monthsDifference =
    (todayYear - enrollmentYear) * 12 + todayMonth - enrollmentMonth;

  if (monthsDifference < 0) {
    return [];
  }

  const options = [];

  for (let offset = 0; offset <= monthsDifference; offset += 1) {
    const cycleStart = getAnchoredCycleStart(enrollmentDate, offset);

    if (!cycleStart || cycleStart > today) {
      continue;
    }

    const year = cycleStart.getFullYear();

    const month = String(cycleStart.getMonth() + 1).padStart(2, "0");

    const rawLabel = cycleStart.toLocaleDateString("es-ES", {
      month: "long",
      year: "numeric",
    });

    const label = rawLabel.charAt(0).toUpperCase() + rawLabel.slice(1);

    options.push({
      value: `${year}-${month}`,
      label,
    });
  }

  return options;
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
  if (payment.status === "paid" && payment.settlement_source === "migration") {
    return "Pagado antes de SportFlow";
  }

  if (payment.status === "paid") {
    return payment.payment_date
      ? `Pagado el ${formatDate(payment.payment_date)}`
      : "Pagado";
  }

  if (payment.status === "overdue" && payment.due_date) {
    return `Debía pagarse el ${formatDate(payment.due_date)}`;
  }

  if (payment.status === "pending" && payment.due_date) {
    return `Pago esperado el ${formatDate(payment.due_date)}`;
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
  const [showCustomAmounts, setShowCustomAmounts] = useState(false);
  const [setupStep, setSetupStep] = useState(1);
  const [visiblePayments, setVisiblePayments] = useState(5);
  const [visibleOpenPayments, setVisibleOpenPayments] = useState(3);
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

    initial_payment_mode: "import_history",
    initial_enrollment_status: "",
    last_paid_month: "",
  });

  const validLastPaidMonths = getValidLastPaidMonths(
    paymentForm.enrollment_date,
    todayDate,
  );

  const pendingCount = payments.filter(
    (payment) => payment.status === "pending",
  ).length;
  const paidCount = payments.filter(
    (payment) => payment.status === "paid",
  ).length;
  const overdueCount = payments.filter(
    (payment) => payment.status === "overdue",
  ).length;

  const openPayments = payments.filter((payment) =>
    ["overdue", "pending"].includes(payment.status),
  );

  const visibleOpenPaymentRows = openPayments.slice(0, visibleOpenPayments);

  const historyPayments = payments.filter(
    (payment) => !["overdue", "pending"].includes(payment.status),
  );

  const visibleHistoryPayments = historyPayments.slice(0, visiblePayments);

  const enrollmentPayment = payments.find(
    (payment) => payment.payment_type === "enrollment",
  );

  const hasLegacyPaymentHistory = Boolean(
    player &&
      !player.payment_control_start_date &&
      payments.some((payment) =>
        ["enrollment", "monthly"].includes(payment.payment_type),
      ),
  );

  const isInitialPaymentSetup = Boolean(
    player && !player.payment_control_start_date && !hasLegacyPaymentHistory,
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
      const loadedPayments = data.payments || [];

      setPlayer(data.player);

      setPaymentForm({
        enrollment_date: data.player.enrollment_date || "",
        enrollment_fee: data.player.enrollment_fee ?? "",
        monthly_fee: data.player.monthly_fee ?? "",

        initial_payment_mode: "import_history",
        initial_enrollment_status: "",
        last_paid_month: "",
      });

      setCustomEnrollmentFee(data.player.enrollment_fee !== null);

      setCustomMonthlyFee(data.player.monthly_fee !== null);

      setShowCustomAmounts(
        data.player.enrollment_fee !== null || data.player.monthly_fee !== null,
      );

      const hasLegacyBasePayments =
        !data.player.payment_control_start_date &&
        loadedPayments.some((payment) =>
          ["enrollment", "monthly"].includes(payment.payment_type),
        );

      const shouldOpenInitialSetup =
        !data.player.payment_control_start_date && !hasLegacyBasePayments;

      setShowPaymentSettings(shouldOpenInitialSetup);

      if (shouldOpenInitialSetup) {
        setSetupStep(1);
      }
    }

    setLoading(false);
  };

  useEffect(() => {
    loadPlayerPayments();
  }, [player_id]);

  const handlePaymentFormChange = (event) => {
    const { name, value } = event.target;

    if (name === "initial_enrollment_status" && value === "not_applicable") {
      setCustomEnrollmentFee(false);
    }

    setPaymentForm((prev) => ({
      ...prev,
      [name]: value,

      // Si cambia la fecha de inscripción,
      // cambian también los ciclos mensuales válidos.
      ...(name === "enrollment_date"
        ? {
            last_paid_month: "",
          }
        : {}),

      ...(name === "initial_payment_mode" && value === "start_now"
        ? {
            last_paid_month: "",
          }
        : {}),

      ...(name === "initial_enrollment_status" && value === "not_applicable"
        ? {
            enrollment_fee: "",
          }
        : {}),
    }));

    setFormErrors({});
  };

  const handleContinueSetup = () => {
    const errors = {};

    if (!paymentForm.enrollment_date?.trim()) {
      errors.ENROLLMENT_DATE_REQUIRED = true;
    }

    const clubMonthlyFee = Number(club?.default_monthly_fee || 0);

    if (!customMonthlyFee && clubMonthlyFee <= 0) {
      errors.CLUB_PAYMENT_DEFAULTS_REQUIRED = true;
    }

    if (customMonthlyFee) {
      const monthlyFee = Number(paymentForm.monthly_fee);

      if (paymentForm.monthly_fee === "" || paymentForm.monthly_fee === null) {
        errors.MONTHLY_FEE_REQUIRED = true;
      } else if (Number.isNaN(monthlyFee) || monthlyFee <= 0) {
        errors.INVALID_MONTHLY_FEE = true;
      }
    }

    setFormErrors(errors);

    if (Object.keys(errors).length > 0) {
      return;
    }

    setSetupStep(2);

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  const handleSavePaymentSettings = async () => {
    const errors = validatePlayerPaymentSettings({
      enrollment_date: paymentForm.enrollment_date,
      customEnrollmentFee,
      customMonthlyFee,
      enrollment_fee: paymentForm.enrollment_fee,
      monthly_fee: paymentForm.monthly_fee,
      club,

      isInitialSetup: isInitialPaymentSetup,
      initial_payment_mode: paymentForm.initial_payment_mode,
      initial_enrollment_status: paymentForm.initial_enrollment_status,
      last_paid_month: paymentForm.last_paid_month,
    });

    setFormErrors(errors);

    if (Object.keys(errors).length > 0) {
      return;
    }

    setSavingSettings(true);

    const paymentSettings = {
      enrollment_date: paymentForm.enrollment_date,
    };

    // ==========================================
    // MONTOS PERSONALIZADOS
    // ==========================================

    if (customEnrollmentFee) {
      paymentSettings.enrollment_fee = Number(paymentForm.enrollment_fee);
    }

    if (customMonthlyFee) {
      paymentSettings.monthly_fee = Number(paymentForm.monthly_fee);
    }

    // ==========================================
    // CONFIGURACIÓN INICIAL
    // ==========================================

    if (isInitialPaymentSetup) {
      paymentSettings.initial_payment_mode = paymentForm.initial_payment_mode;

      paymentSettings.initial_enrollment_status =
        paymentForm.initial_enrollment_status;

      paymentSettings.last_paid_month =
        paymentForm.initial_payment_mode === "import_history" &&
        paymentForm.last_paid_month
          ? paymentForm.last_paid_month
          : null;
    }

    const result = await actions.updatePlayerPaymentSettings(
      player_id,
      paymentSettings,
    );

    if (result.ok) {
      await loadPlayerPayments();
      setShowPaymentSettings(false);
    } else if (result.code) {
      setFormErrors({
        [result.code]: true,
      });
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

  const renderPaymentRow = (payment) => {
    const isMigrationPayment =
      payment.status === "paid" && payment.settlement_source === "migration";
    const isOpenPayment = ["overdue", "pending"].includes(payment.status);

    if (isMigrationPayment) {
      return (
        <div key={payment.id} className="payment-history-entry">
          <div className="payment-history-summary">
            <div className="payment-history-main">
              <span className="payment-history-icon">
                <CircleCheckBig size={16} />
              </span>

              <div className="payment-history-copy">
                <strong>
                  {PAYMENT_TYPE_LABELS[payment.payment_type] || "Pago"}
                </strong>

                <span>{getPaymentDescription(payment)}</span>

                <small>Pagado antes de SportFlow</small>
              </div>
            </div>

            <strong className="payment-history-amount">
              ${formatMoney(payment.amount)}
            </strong>
          </div>
        </div>
      );
    }

    if (payment.status === "paid") {
      return (
        <div key={payment.id} className="payment-history-entry">
          <div className="payment-history-summary">
            <div className="payment-history-main">
              <span className="payment-history-icon">
                <CircleCheckBig size={16} />
              </span>

              <div className="payment-history-copy">
                <strong>
                  {PAYMENT_TYPE_LABELS[payment.payment_type] || "Pago"}
                </strong>

                <span>{getPaymentDescription(payment)}</span>

                {getPaymentMetaText(payment) && (
                  <small>{getPaymentMetaText(payment)}</small>
                )}
              </div>
            </div>

            <strong className="payment-history-amount">
              ${formatMoney(payment.amount)}
            </strong>
          </div>

          <div className="payment-history-actions">
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
          </div>

          {receiptErrors[payment.id] && (
            <p className="form-error">{receiptErrors[payment.id]}</p>
          )}

          {expandedPaymentId === payment.id && (
            <div className="payment-details-panel">
              <div className="payment-details-grid">
                <div>
                  <span>Fecha de pago</span>
                  <strong>
                    {formatDate(payment.payment_date) || "No registrada"}
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
                  <strong>{payment.reference || "Sin referencia"}</strong>
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
        </div>
      );
    }

    return (
      <div
        key={payment.id}
        className={isOpenPayment ? "player-payment-open-row" : "payment-row"}
      >
        <div className={isOpenPayment ? "player-payment-open-main" : undefined}>
          <div
            className={isOpenPayment ? "player-payment-open-copy" : undefined}
          >
            <h4>
              {PAYMENT_TYPE_LABELS[payment.payment_type] || "Pago"}
              {!isOpenPayment && ` · $${formatMoney(payment.amount)}`}
            </h4>

            <p>{getPaymentDescription(payment)}</p>

            {getPaymentMetaText(payment) && (
              <p>{getPaymentMetaText(payment)}</p>
            )}
          </div>

          {isOpenPayment && (
            <strong className="player-payment-open-amount">
              ${formatMoney(payment.amount)}
            </strong>
          )}
        </div>

        <div className="payment-row-actions">
          <span className={STATUS_CLASSES[payment.status]}>
            {STATUS_LABELS[payment.status]}
          </span>

          {isOpenPayment && registeringPaymentId !== payment.id && (
            <Button type="button" onClick={() => openRegisterPayment(payment)}>
              Registrar pago
            </Button>
          )}
        </div>

        {registeringPaymentId === payment.id && (
          <div className="payment-register-panel">
            <div className="payment-register-header">
              <strong>Registrar pago</strong>
              <span>
                {PAYMENT_TYPE_LABELS[payment.payment_type] || "Pago"} · $
                {formatMoney(payment.amount)}
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
    );
  };

  if (loading) return null;

  return (
    <>
      <PageHeader
        variant="detail"
        eyebrow={
          isInitialPaymentSetup
            ? "Configuración de cobro"
            : "Pagos del deportista"
        }
        title={
          player
            ? `${player.first_name} ${player.last_name}`
            : "Pagos del deportista"
        }
        subtitle={
          isInitialPaymentSetup
            ? "Define qué se cobra y desde qué momento SportFlow comenzará a llevar el control."
            : "Consulta el estado de pagos, ajusta la configuración y revisa el historial completo."
        }
        onBack={() => navigate(`/players/${player_id}`)}
      />
      <div className="payments-page">
        {!isInitialPaymentSetup && (
          <div className="payments-summary-grid">
            <Card className="payment-summary-card player-payment-stat overdue">
              <div className="player-payment-stat-header">
                <AlertTriangle size={15} />
                <span>Atrasados</span>
              </div>

              <strong>{overdueCount}</strong>
            </Card>

            <Card className="payment-summary-card player-payment-stat pending">
              <div className="player-payment-stat-header">
                <Clock3 size={15} />
                <span>Pendientes</span>
              </div>

              <strong>{pendingCount}</strong>
            </Card>

            <Card className="payment-summary-card player-payment-stat paid">
              <div className="player-payment-stat-header">
                <CircleCheckBig size={15} />
                <span>Pagados</span>
              </div>

              <strong>{paidCount}</strong>
            </Card>
          </div>
        )}

        <Card
          className={`player-payment-settings-card ${
            !isInitialPaymentSetup && !showPaymentSettings ? "is-compact" : ""
          }`}
        >
          {isInitialPaymentSetup && (
            <div
              className="player-payment-stepper"
              aria-label="Progreso de configuración"
            >
              <div
                className={`player-payment-step ${
                  setupStep === 1 ? "active" : "completed"
                }`}
              >
                <span className="player-payment-step-number">
                  {setupStep > 1 ? "✓" : "1"}
                </span>

                <span>Datos del cobro</span>
              </div>

              <div
                className={`player-payment-step-line ${
                  setupStep === 2 ? "active" : ""
                }`}
              />

              <div
                className={`player-payment-step ${
                  setupStep === 2 ? "active" : ""
                }`}
              >
                <span className="player-payment-step-number">2</span>

                <span>Estado actual</span>
              </div>
            </div>
          )}
          <div className="player-payments-section-header">
            <div>
              <span className="player-payments-card-label">
                {isInitialPaymentSetup
                  ? `Paso ${setupStep} de 2`
                  : "Cobro mensual"}
              </span>

              <h3>
                {isInitialPaymentSetup
                  ? setupStep === 1
                    ? "Datos del cobro"
                    : "Estado actual"
                  : "Ajustes de cobro"}
              </h3>
            </div>

            {!isInitialPaymentSetup && !hasLegacyPaymentHistory && (
              <Button
                type="button"
                variant="secondary"
                onClick={() => setShowPaymentSettings((prev) => !prev)}
              >
                {showPaymentSettings ? "Ocultar" : "Editar"}
              </Button>
            )}
          </div>
          {hasLegacyPaymentHistory && (
            <div className="player-payment-legacy-warning">
              <strong>Configuración anterior detectada</strong>

              <p>
                Este deportista ya tiene pagos creados con la configuración
                anterior de SportFlow.
              </p>

              <p>
                Su historial debe revisarse antes de iniciar el nuevo control
                mensual para evitar pagos duplicados.
              </p>
            </div>
          )}
          {!hasLegacyPaymentHistory &&
            (showPaymentSettings ? (
              <>
                {(!isInitialPaymentSetup || setupStep === 1) && (
                  <>
                    <div className="player-payment-settings-grid">
                      {isInitialPaymentSetup ? (
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

                          {formErrors.INVALID_HISTORY_ENROLLMENT_DATE && (
                            <p className="form-error">
                              {errorMessages.INVALID_HISTORY_ENROLLMENT_DATE}
                            </p>
                          )}
                        </label>
                      ) : (
                        <div className="player-payment-readonly-field">
                          <span>Fecha de inscripción</span>

                          <strong>
                            {formatDate(paymentForm.enrollment_date) ||
                              "Sin definir"}
                          </strong>

                          <small>
                            Esta fecha define el ciclo histórico de pagos y ya
                            no puede modificarse.
                          </small>
                        </div>
                      )}
                    </div>

                    <div className="player-payment-defaults">
                      <span>Montos</span>

                      <div className="player-payment-defaults-grid">
                        <div>
                          <small>Inscripción</small>
                          <strong>
                            {isInitialPaymentSetup &&
                            paymentForm.initial_enrollment_status ===
                              "not_applicable"
                              ? "No aplica"
                              : `$${formatMoney(
                                  customEnrollmentFee
                                    ? paymentForm.enrollment_fee
                                    : club?.default_enrollment_fee,
                                )}`}
                          </strong>
                        </div>

                        <div>
                          <small>Mensualidad</small>
                          <strong>
                            $
                            {formatMoney(
                              customMonthlyFee
                                ? paymentForm.monthly_fee
                                : club?.default_monthly_fee,
                            )}
                          </strong>
                        </div>
                      </div>
                      {formErrors.CLUB_PAYMENT_DEFAULTS_REQUIRED && (
                        <p className="form-error">
                          {errorMessages.CLUB_PAYMENT_DEFAULTS_REQUIRED}
                        </p>
                      )}
                    </div>

                    <div className="player-payment-custom-amounts">
                      <button
                        type="button"
                        className="player-payment-custom-trigger"
                        onClick={() => setShowCustomAmounts((prev) => !prev)}
                      >
                        <span>
                          {showCustomAmounts
                            ? "Ocultar personalización"
                            : "Personalizar montos"}
                        </span>

                        <span aria-hidden="true">
                          {showCustomAmounts ? "−" : "+"}
                        </span>
                      </button>

                      {showCustomAmounts && (
                        <div className="player-payment-custom-panel">
                          {!(
                            isInitialPaymentSetup &&
                            paymentForm.initial_enrollment_status ===
                              "not_applicable"
                          ) &&
                            !enrollmentIsPaid && (
                              <div className="player-payment-custom-item">
                                <label className="player-payment-custom-toggle">
                                  <input
                                    type="checkbox"
                                    checked={customEnrollmentFee}
                                    onChange={(event) => {
                                      const checked = event.target.checked;

                                      setCustomEnrollmentFee(checked);
                                      setFormErrors({});

                                      setPaymentForm((prev) => ({
                                        ...prev,
                                        enrollment_fee: checked
                                          ? prev.enrollment_fee ||
                                            club?.default_enrollment_fee ||
                                            ""
                                          : "",
                                      }));
                                    }}
                                  />

                                  <span>Personalizar inscripción</span>
                                </label>

                                {customEnrollmentFee && (
                                  <FormField
                                    label="Monto de inscripción"
                                    error={
                                      formErrors.ENROLLMENT_FEE_REQUIRED
                                        ? errorMessages.ENROLLMENT_FEE_REQUIRED
                                        : formErrors.INVALID_ENROLLMENT_FEE
                                        ? errorMessages.INVALID_ENROLLMENT_FEE
                                        : null
                                    }
                                  >
                                    <Input
                                      type="number"
                                      name="enrollment_fee"
                                      value={paymentForm.enrollment_fee}
                                      onChange={handlePaymentFormChange}
                                      placeholder="Ej: 20"
                                    />
                                  </FormField>
                                )}
                              </div>
                            )}

                          {isInitialPaymentSetup &&
                            paymentForm.initial_enrollment_status ===
                              "not_applicable" && (
                              <div className="player-payment-locked-box">
                                <strong>Sin cobro de inscripción</strong>
                                <span>Solo se configurará la mensualidad.</span>
                              </div>
                            )}

                          {enrollmentIsPaid && (
                            <div className="player-payment-locked-box">
                              <strong>Inscripción pagada</strong>
                              <span>
                                El monto de inscripción ya forma parte del
                                historial y no puede modificarse.
                              </span>
                            </div>
                          )}

                          <div className="player-payment-custom-item">
                            <label className="player-payment-custom-toggle">
                              <input
                                type="checkbox"
                                checked={customMonthlyFee}
                                onChange={(event) => {
                                  const checked = event.target.checked;

                                  setCustomMonthlyFee(checked);
                                  setFormErrors({});

                                  setPaymentForm((prev) => ({
                                    ...prev,
                                    monthly_fee: checked
                                      ? prev.monthly_fee ||
                                        club?.default_monthly_fee ||
                                        ""
                                      : "",
                                  }));
                                }}
                              />

                              <span>Personalizar mensualidad</span>
                            </label>

                            {customMonthlyFee && (
                              <FormField
                                label="Monto mensual"
                                error={
                                  formErrors.MONTHLY_FEE_REQUIRED
                                    ? errorMessages.MONTHLY_FEE_REQUIRED
                                    : formErrors.INVALID_MONTHLY_FEE
                                    ? errorMessages.INVALID_MONTHLY_FEE
                                    : null
                                }
                              >
                                <Input
                                  type="number"
                                  name="monthly_fee"
                                  value={paymentForm.monthly_fee}
                                  onChange={handlePaymentFormChange}
                                  placeholder="Ej: 25"
                                />
                              </FormField>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </>
                )}
                {isInitialPaymentSetup && setupStep === 2 && (
                  <div className="player-payment-initial-state">
                    <p className="player-payment-step-description">
                      Cuéntanos cómo están sus pagos actualmente.
                    </p>

                    <div className="player-payment-initial-section">
                      <div className="player-payment-initial-title">
                        <strong>Inscripción</strong>
                        <span>
                          Indica cuál era el estado de la inscripción.
                        </span>
                      </div>

                      <div className="player-payment-options">
                        <label className="player-payment-option">
                          <input
                            type="radio"
                            name="initial_enrollment_status"
                            value="pending"
                            checked={
                              paymentForm.initial_enrollment_status ===
                              "pending"
                            }
                            onChange={handlePaymentFormChange}
                          />

                          <span>
                            <strong>Pendiente</strong>
                            <small>La inscripción todavía debe cobrarse.</small>
                          </span>
                        </label>

                        <label className="player-payment-option">
                          <input
                            type="radio"
                            name="initial_enrollment_status"
                            value="paid_before_sportflow"
                            checked={
                              paymentForm.initial_enrollment_status ===
                              "paid_before_sportflow"
                            }
                            onChange={handlePaymentFormChange}
                          />

                          <span>
                            <strong>Pagada antes de SportFlow</strong>
                            <small>
                              Se conservará como historial y no generará recibo
                              ni notificaciones.
                            </small>
                          </span>
                        </label>

                        <label className="player-payment-option">
                          <input
                            type="radio"
                            name="initial_enrollment_status"
                            value="not_applicable"
                            checked={
                              paymentForm.initial_enrollment_status ===
                              "not_applicable"
                            }
                            onChange={handlePaymentFormChange}
                          />

                          <span>
                            <strong>No aplica</strong>
                            <small>
                              Este deportista no tiene cobro de inscripción.
                            </small>
                          </span>
                        </label>
                      </div>

                      {formErrors.INITIAL_ENROLLMENT_STATUS_REQUIRED && (
                        <p className="form-error">
                          {errorMessages.INITIAL_ENROLLMENT_STATUS_REQUIRED}
                        </p>
                      )}
                    </div>

                    <div className="player-payment-initial-section">
                      <div className="player-payment-initial-title">
                        <strong>Mensualidades</strong>

                        <span>
                          Decide desde qué momento SportFlow llevará el control
                          mensual.
                        </span>
                      </div>

                      <div className="player-payment-options">
                        <label className="player-payment-option">
                          <input
                            type="radio"
                            name="initial_payment_mode"
                            value="import_history"
                            checked={
                              paymentForm.initial_payment_mode ===
                              "import_history"
                            }
                            onChange={handlePaymentFormChange}
                          />

                          <span>
                            <strong>Ya tiene historial de pagos</strong>
                            <small>
                              Indica hasta qué mes estaba al día antes de usar
                              SportFlow.
                            </small>
                          </span>
                        </label>

                        <label className="player-payment-option">
                          <input
                            type="radio"
                            name="initial_payment_mode"
                            value="start_now"
                            checked={
                              paymentForm.initial_payment_mode === "start_now"
                            }
                            onChange={handlePaymentFormChange}
                          />

                          <span>
                            <strong>Empezar a controlar desde ahora</strong>
                            <small>
                              Se incluirá el ciclo actual, pero no los
                              anteriores.
                            </small>
                          </span>
                        </label>
                      </div>

                      {formErrors.INITIAL_PAYMENT_MODE_REQUIRED && (
                        <p className="form-error">
                          {errorMessages.INITIAL_PAYMENT_MODE_REQUIRED}
                        </p>
                      )}

                      {paymentForm.initial_payment_mode ===
                        "import_history" && (
                        <div className="player-payment-last-month">
                          <FormField
                            label="Último mes pagado"
                            helper={
                              paymentForm.enrollment_date
                                ? "Solo aparecen los ciclos que ya han comenzado."
                                : "Primero selecciona la fecha de inscripción."
                            }
                            error={
                              formErrors.INVALID_LAST_PAID_MONTH_FORMAT
                                ? errorMessages.INVALID_LAST_PAID_MONTH_FORMAT
                                : formErrors.LAST_PAID_MONTH_BEFORE_ENROLLMENT
                                ? errorMessages.LAST_PAID_MONTH_BEFORE_ENROLLMENT
                                : formErrors.LAST_PAID_MONTH_NOT_REACHED
                                ? errorMessages.LAST_PAID_MONTH_NOT_REACHED
                                : null
                            }
                          >
                            <Select
                              name="last_paid_month"
                              value={paymentForm.last_paid_month}
                              onChange={handlePaymentFormChange}
                              disabled={!paymentForm.enrollment_date}
                            >
                              <option value="">
                                Sin mensualidades pagadas
                              </option>

                              {validLastPaidMonths.map((option) => (
                                <option key={option.value} value={option.value}>
                                  {option.label}
                                </option>
                              ))}
                            </Select>
                          </FormField>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {isInitialPaymentSetup ? (
                  setupStep === 1 ? (
                    <div className="player-payment-setup-actions">
                      <Button type="button" onClick={handleContinueSetup}>
                        Continuar
                      </Button>
                    </div>
                  ) : (
                    <>
                      <p className="player-payment-settings-help">
                        Revisa el estado actual antes de guardar. Esta
                        información se utilizará una sola vez para crear el
                        historial inicial.
                      </p>

                      <div className="player-payment-setup-actions two-actions">
                        <Button
                          type="button"
                          variant="secondary"
                          onClick={() => {
                            setSetupStep(1);

                            window.scrollTo({
                              top: 0,
                              behavior: "smooth",
                            });
                          }}
                        >
                          ← Atrás
                        </Button>

                        <Button
                          type="button"
                          onClick={handleSavePaymentSettings}
                          disabled={savingSettings}
                        >
                          {savingSettings
                            ? "Guardando..."
                            : "Guardar configuración"}
                        </Button>
                      </div>
                    </>
                  )
                ) : (
                  <>
                    <p className="player-payment-settings-help">
                      Los cambios de monto se aplicarán a los nuevos cobros. El
                      historial existente se conserva.
                    </p>

                    <Button
                      type="button"
                      onClick={handleSavePaymentSettings}
                      disabled={savingSettings}
                    >
                      {savingSettings
                        ? "Guardando..."
                        : "Guardar configuración"}
                    </Button>
                  </>
                )}
              </>
            ) : (
              <p className="player-payment-settings-help">
                $
                {formatMoney(
                  customMonthlyFee
                    ? paymentForm.monthly_fee
                    : club?.default_monthly_fee,
                )}{" "}
                mensual · Desde{" "}
                {formatDate(paymentForm.enrollment_date) || "sin fecha"}
              </p>
            ))}
        </Card>
        {!isInitialPaymentSetup && (
          <>
            {openPayments.length > 0 && (
              <Card
                className={`player-payment-open-card ${
                  overdueCount > 0 ? "has-overdue" : "has-pending"
                }`}
              >
                <div className="payments-list-header">
                  <h3>Cobros</h3>

                  <span className="player-payment-section-count">
                    {openPayments.length}{" "}
                    {openPayments.length === 1 ? "cobro" : "cobros"}
                  </span>
                </div>

                <div className="payments-list">
                  {visibleOpenPaymentRows.map(renderPaymentRow)}
                </div>

                {visibleOpenPayments < openPayments.length && (
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => setVisibleOpenPayments((prev) => prev + 3)}
                  >
                    Mostrar más
                  </Button>
                )}
              </Card>
            )}

            <Card className="player-payment-history-card">
              <div className="payments-list-header">
                <h3>Historial</h3>

                <span className="player-payment-section-count">
                  {historyPayments.length}{" "}
                  {historyPayments.length === 1 ? "pago" : "pagos"}
                </span>
              </div>

              {historyPayments.length === 0 ? (
                <p className="empty-state">
                  Todavía no hay pagos en el historial de este deportista.
                </p>
              ) : (
                <>
                  <div className="payments-list player-payment-history-list">
                    {visibleHistoryPayments.map(renderPaymentRow)}
                  </div>

                  {visiblePayments < historyPayments.length && (
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
          </>
        )}
      </div>
    </>
  );
};
