import React, { useContext, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";
import { ReceiptShareHistory } from "../../component/receiptShareHistory";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { Input } from "../../component/ui/input";
import { Select } from "../../component/ui/select";
import { FormField } from "../../component/ui/formField";
import { validatePaymentRegistration } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";
import { getClubToday } from "../../utils/clubDate";
import { formatMoney } from "../../utils/money";
import {
  buildReceiptWhatsappMessage,
  navigateReceiptWhatsapp,
  openReceiptWhatsappWindow,
} from "../../utils/receiptSharing";
import "../../../styles/paymentShared.css";
import "../../../styles/payments.css";
import {
  ReceiptText,
  AlertTriangle,
  Clock3,
  CircleCheckBig,
} from "lucide-react";

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
  enrollment: "Inscripción al club",
  monthly: "Mensualidad",
  uniform: "Uniforme",
  tournament: "Inscripción de torneo",
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

const getPaymentDescription = (payment) => {
  if (payment.payment_type === "monthly") {
    return `${formatDate(payment.period_start)} - ${formatDate(
      payment.period_end,
    )}`;
  }

  if (payment.payment_type === "enrollment") {
    return "Pago único de inscripción al club";
  }

  if (payment.payment_type === "tournament") {
    const tournamentName =
      payment.tournament_team?.tournament?.name || payment.tournament?.name;

    const teamName = payment.tournament_team?.team?.name || payment.team?.name;

    if (tournamentName && teamName) {
      return `${tournamentName} · ${teamName}`;
    }

    if (tournamentName) {
      return tournamentName;
    }

    return payment.notes || "Inscripción de torneo";
  }

  if (payment.payment_type === "referee") {
    const opponentName = payment.match?.opponent_name || payment.opponent_name;

    const matchDate = payment.match?.date || payment.match_date;

    if (opponentName && matchDate) {
      return `Partido vs. ${opponentName} · ${formatDate(matchDate)}`;
    }

    if (opponentName) {
      return `Partido vs. ${opponentName}`;
    }

    return payment.notes || "Arbitraje del partido";
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

export const Payments = () => {
  const { store, actions } = useContext(Context);
  const location = useLocation();
  const navigate = useNavigate();
  const club = store.club || store.user?.club;
  const todayDate = getClubToday(club);

  const searchParams = useMemo(
    () => new URLSearchParams(location.search),
    [location.search],
  );

  const requestedPaymentType = searchParams.get("payment_type") || "";

  const requestedTournamentTeamId =
    searchParams.get("tournament_team_id") || "";

  const requestedMatchId = searchParams.get("match_id") || "";
  const isContextView = Boolean(requestedTournamentTeamId || requestedMatchId);

  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState(requestedPaymentType);
  const [searchTerm, setSearchTerm] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [visibleOpenPayments, setVisibleOpenPayments] = useState(3);
  const [visibleHistoryPayments, setVisibleHistoryPayments] = useState(5);
  const [registeringPaymentId, setRegisteringPaymentId] = useState(null);
  const [expandedPaymentId, setExpandedPaymentId] = useState(null);
  const [paymentRegisterForm, setPaymentRegisterForm] = useState({
    payment_date: todayDate,
    payment_method: "",
    reference: "",
    notes: "",
  });
  const [paymentRegisterErrors, setPaymentRegisterErrors] = useState({});
  const [receiptLoadingId, setReceiptLoadingId] = useState(null);
  const [receiptErrors, setReceiptErrors] = useState({});
  const [receiptNotices, setReceiptNotices] = useState({});
  const [receiptShareEvents, setReceiptShareEvents] = useState({});
  const [shareHistoryLoadingId, setShareHistoryLoadingId] = useState(null);
  const [shareHistoryErrors, setShareHistoryErrors] = useState({});
  const [syncPanelOpen, setSyncPanelOpen] = useState(false);
  const [syncPreview, setSyncPreview] = useState(null);
  const [syncResult, setSyncResult] = useState(null);
  const [syncError, setSyncError] = useState("");
  const [syncPreviewLoading, setSyncPreviewLoading] = useState(false);
  const [syncApplying, setSyncApplying] = useState(false);
  const [syncConfirmationOpen, setSyncConfirmationOpen] = useState(false);

  const payments = store.payments || [];
  const canManagePayments = ["club_owner", "staff"].includes(
    store.user?.role,
  );

  const filteredPayments = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();

    return payments.filter((payment) => {
      const playerName = `${payment.player?.first_name || ""} ${
        payment.player?.last_name || ""
      }`.toLowerCase();

      const matchesSearch =
        !normalizedSearch || playerName.includes(normalizedSearch);

      const matchesTournamentEntry =
        !requestedTournamentTeamId ||
        payment.tournament_team_id === requestedTournamentTeamId;

      const matchesMatch =
        !requestedMatchId || payment.match_id === requestedMatchId;

      return matchesSearch && matchesTournamentEntry && matchesMatch;
    });
  }, [payments, searchTerm, requestedTournamentTeamId, requestedMatchId]);

  const openPayments = useMemo(
    () =>
      filteredPayments.filter((payment) =>
        ["overdue", "pending"].includes(payment.status),
      ),
    [filteredPayments],
  );

  const historyPayments = useMemo(
    () =>
      filteredPayments.filter((payment) =>
        ["paid", "cancelled"].includes(payment.status),
      ),
    [filteredPayments],
  );

  const visibleOpenPaymentRows = openPayments.slice(0, visibleOpenPayments);

  const visibleHistoryPaymentRows = historyPayments.slice(
    0,
    visibleHistoryPayments,
  );

  const summary = store.paymentSummary;

  const currentFilters = {
    ...(statusFilter ? { status: statusFilter } : {}),
    ...(typeFilter ? { payment_type: typeFilter } : {}),
  };

  useEffect(() => {
    setTypeFilter(requestedPaymentType);
  }, [requestedPaymentType]);

  const loadPayments = async () => {
    setLoading(true);
    await actions.getPayments(currentFilters);
    setLoading(false);
  };

  const loadSyncPreview = async () => {
    setSyncPreviewLoading(true);
    setSyncError("");

    const result = await actions.getPaymentsSyncPreview();

    if (result.ok) {
      setSyncPreview(result.data);
    } else {
      setSyncPreview(null);
      setSyncError(
        result.message ||
          errorMessages[result.code] ||
          "No pudimos cargar la vista previa.",
      );
    }

    setSyncPreviewLoading(false);
  };

  const openSyncPanel = async () => {
    setSyncPanelOpen(true);
    setSyncResult(null);
    setSyncConfirmationOpen(false);
    await loadSyncPreview();
  };

  const closeSyncPanel = () => {
    if (syncApplying) return;

    setSyncPanelOpen(false);
    setSyncPreview(null);
    setSyncResult(null);
    setSyncError("");
    setSyncConfirmationOpen(false);
  };

  const handlePaymentsSync = async () => {
    if (syncApplying) return;

    setSyncApplying(true);
    setSyncError("");

    const result = await actions.syncPayments();

    if (!result.ok) {
      setSyncError(
        result.message ||
          errorMessages[result.code] ||
          "No pudimos sincronizar los pagos.",
      );
      setSyncApplying(false);
      return;
    }

    setSyncResult(result.data);
    setSyncConfirmationOpen(false);
    await loadPayments();
    await loadSyncPreview();
    setSyncApplying(false);
  };

  useEffect(() => {
    loadPayments();
  }, [statusFilter, typeFilter]);

  useEffect(() => {
    setVisibleOpenPayments(3);
    setVisibleHistoryPayments(5);
  }, [
    searchTerm,
    statusFilter,
    typeFilter,
    requestedTournamentTeamId,
    requestedMatchId,
  ]);

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

  const loadReceiptShareHistory = async (payment) => {
    const receiptId = payment.receipt?.id;

    if (!receiptId) {
      setReceiptShareEvents((current) => ({
        ...current,
        [payment.id]: [],
      }));
      return;
    }

    setShareHistoryLoadingId(payment.id);
    setShareHistoryErrors((current) => ({
      ...current,
      [payment.id]: "",
    }));

    const result = await actions.getPaymentReceiptShareEvents(receiptId);

    if (result.ok) {
      setReceiptShareEvents((current) => ({
        ...current,
        [payment.id]: result.data.share_events || [],
      }));
    } else {
      setShareHistoryErrors((current) => ({
        ...current,
        [payment.id]:
          result.message || "No pudimos cargar el historial de compartidos.",
      }));
    }

    setShareHistoryLoadingId(null);
  };

  const togglePaymentDetails = (payment) => {
    setRegisteringPaymentId(null);

    const isOpening = expandedPaymentId !== payment.id;

    setExpandedPaymentId((currentId) =>
      currentId === payment.id ? null : payment.id,
    );

    if (isOpening && payment.receipt?.id) {
      loadReceiptShareHistory(payment);
    }
  };

  const handlePaymentRegisterChange = (event) => {
    const { name, value } = event.target;

    setPaymentRegisterForm((prev) => ({
      ...prev,
      [name]: value,
    }));

    setPaymentRegisterErrors((prev) => ({
      ...prev,
      [name]: false,
      PAYMENT_DATE_REQUIRED: false,
      PAYMENT_METHOD_REQUIRED: false,
      INVALID_PAYMENT_METHOD: false,
      INVALID_PAYMENT_AMOUNT: false,
      INVALID_PAYMENT_STATUS: false,
      PAYMENT_NOT_FOUND: false,
      INVALID_DATE_FORMAT: false,
      FORBIDDEN: false,
      CLUB_REQUIRED: false,
      SESSION_EXPIRED: false,
      NETWORK_ERROR: false,
    }));
  };

  const handleRegisterPayment = async (payment) => {
    const errors = validatePaymentRegistration({
      ...paymentRegisterForm,
      todayDate,
    });

    setPaymentRegisterErrors(errors);

    if (Object.keys(errors).length > 0) return;

    const result = await actions.updatePayment(
      payment.id,
      {
        status: "paid",
        payment_date: paymentRegisterForm.payment_date,
        payment_method: paymentRegisterForm.payment_method,
        reference: paymentRegisterForm.reference,
        notes: paymentRegisterForm.notes,
      },
      currentFilters,
    );

    if (result.ok) {
      closeRegisterPayment();
    } else if (result.code) {
      setPaymentRegisterErrors({ [result.code]: true });
    }
  };

  const handleMarkAsPending = async (payment) => {
    const confirmed = window.confirm(
      "¿Seguro que quieres revertir este pago? Se eliminará la fecha de pago registrada.",
    );

    if (!confirmed) return;

    const result = await actions.updatePayment(
      payment.id,
      {
        status: "pending",
      },
      currentFilters,
    );

    if (!result?.ok && result?.code) {
      setPaymentRegisterErrors({ [result.code]: true });
    }
  };

  const getWhatsappPhone = (payment) => {
    const phone = payment.player?.representative_phone;

    if (!phone) return null;

    return phone.replace(/\D/g, "");
  };

  const handleSendReceiptWhatsapp = async (payment) => {
    if (receiptLoadingId === payment.id) return;

    setReceiptErrors({});
    setReceiptNotices({});

    const phone = getWhatsappPhone(payment);

    if (!phone) {
      setReceiptErrors({
        [payment.id]: "Este deportista no tiene teléfono de representante.",
      });

      return;
    }

    const whatsappWindow = openReceiptWhatsappWindow();

    if (!whatsappWindow) {
      setReceiptErrors({
        [payment.id]:
          "No se pudo abrir WhatsApp. Revisa el bloqueo de ventanas emergentes.",
      });
      return;
    }

    setReceiptLoadingId(payment.id);

    const receiptResult = await actions.createPaymentReceipt(payment.id);

    if (!receiptResult.ok) {
      whatsappWindow.close();
      setReceiptLoadingId(null);

      setReceiptErrors({
        [payment.id]: receiptResult.message || "No se pudo generar el recibo.",
      });

      return;
    }

    const receipt = receiptResult.data.receipt;
    const message = buildReceiptWhatsappMessage(receipt);
    const whatsappOpened = navigateReceiptWhatsapp(
      whatsappWindow,
      phone,
      message,
    );

    if (!whatsappOpened) {
      setReceiptLoadingId(null);
      setReceiptErrors({
        [payment.id]:
          "No se pudo abrir WhatsApp. Revisa el bloqueo de ventanas emergentes.",
      });
      return;
    }

    const sharedResult = await actions.createPaymentReceiptShareEvent(
      receipt.id,
      {
        channel: "whatsapp",
        destination: phone,
      },
    );

    setReceiptLoadingId(null);

    if (!sharedResult.ok) {
      setReceiptNotices({
        [payment.id]:
          "WhatsApp se abrió, pero no pudimos registrar la acción en el historial.",
      });
      return;
    }

    setReceiptShareEvents((current) => ({
      ...current,
      [payment.id]: [
        sharedResult.data.share_event,
        ...(current[payment.id] || []),
      ],
    }));
    setReceiptNotices({
      [payment.id]: "WhatsApp se abrió y la acción quedó registrada.",
    });
    await loadPayments();
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
                  {payment.player?.first_name} {payment.player?.last_name}
                </strong>

                <span>
                  {PAYMENT_TYPE_LABELS[payment.payment_type] || "Pago"} ·{" "}
                  {getPaymentDescription(payment)}
                </span>

                <small>Pagado antes de SportFlow</small>
              </div>
            </div>

            <strong className="payment-history-amount">
              {formatMoney(payment.amount, payment.currency_code)}
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
                  {payment.player?.first_name} {payment.player?.last_name}
                </strong>

                <span>
                  {PAYMENT_TYPE_LABELS[payment.payment_type] || "Pago"} ·{" "}
                  {getPaymentDescription(payment)}
                </span>

                {getPaymentMetaText(payment) && (
                  <small>{getPaymentMetaText(payment)}</small>
                )}
              </div>
            </div>

            <strong className="payment-history-amount">
              {formatMoney(payment.amount, payment.currency_code)}
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
                : "Compartir por WhatsApp"}
            </Button>

            <div className="payment-secondary-actions">
              <button
                type="button"
                className="payment-details-toggle"
                onClick={() => togglePaymentDetails(payment)}
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

          {receiptNotices[payment.id] && (
            <p className="receipt-share-notice">
              {receiptNotices[payment.id]}
            </p>
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

              {payment.receipt?.id && (
                <ReceiptShareHistory
                  events={receiptShareEvents[payment.id] || []}
                  loading={shareHistoryLoadingId === payment.id}
                  error={shareHistoryErrors[payment.id] || ""}
                />
              )}
            </div>
          )}
        </div>
      );
    }
    return (
      <div
        key={payment.id}
        className={`payment-row ${
          isOpenPayment ? "club-payment-open-row" : "club-payment-history-row"
        }`}
      >
        <div>
          <h4>
            {payment.player?.first_name} {payment.player?.last_name}
          </h4>

          <div className="payment-concept-row">
            <span className={`payment-type-badge ${payment.payment_type}`}>
              {PAYMENT_TYPE_LABELS[payment.payment_type] || "Pago"}
            </span>

            <strong>{formatMoney(payment.amount, payment.currency_code)}</strong>
          </div>

          <p className="payment-origin">{getPaymentDescription(payment)}</p>

          {getPaymentMetaText(payment) && <p>{getPaymentMetaText(payment)}</p>}
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

        {isOpenPayment && registeringPaymentId === payment.id && (
          <div className="payment-register-panel">
            <div className="payment-register-header">
              <strong>Registrar pago</strong>
              <span>
                {PAYMENT_TYPE_LABELS[payment.payment_type] || "Pago"} ·{" "}
                {formatMoney(payment.amount, payment.currency_code)}
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

            {(paymentRegisterErrors.INVALID_PAYMENT_METHOD ||
              paymentRegisterErrors.INVALID_PAYMENT_AMOUNT ||
              paymentRegisterErrors.INVALID_PAYMENT_STATUS ||
              paymentRegisterErrors.PAYMENT_NOT_FOUND ||
              paymentRegisterErrors.INVALID_DATE_FORMAT ||
              paymentRegisterErrors.FORBIDDEN ||
              paymentRegisterErrors.CLUB_REQUIRED ||
              paymentRegisterErrors.SESSION_EXPIRED ||
              paymentRegisterErrors.NETWORK_ERROR) && (
              <p className="form-error">
                {paymentRegisterErrors.INVALID_PAYMENT_METHOD
                  ? errorMessages.INVALID_PAYMENT_METHOD
                  : paymentRegisterErrors.INVALID_PAYMENT_AMOUNT
                  ? errorMessages.INVALID_PAYMENT_AMOUNT
                  : paymentRegisterErrors.INVALID_PAYMENT_STATUS
                  ? errorMessages.INVALID_PAYMENT_STATUS
                  : paymentRegisterErrors.PAYMENT_NOT_FOUND
                  ? errorMessages.PAYMENT_NOT_FOUND
                  : paymentRegisterErrors.INVALID_DATE_FORMAT
                  ? errorMessages.INVALID_DATE_FORMAT
                  : paymentRegisterErrors.FORBIDDEN
                  ? errorMessages.FORBIDDEN
                  : paymentRegisterErrors.CLUB_REQUIRED
                  ? errorMessages.CLUB_REQUIRED
                  : paymentRegisterErrors.SESSION_EXPIRED
                  ? errorMessages.SESSION_EXPIRED
                  : errorMessages.NETWORK_ERROR}
              </p>
            )}

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

  return (
    <>
      <PageHeader
        tone="payments"
        icon={ReceiptText}
        eyebrow="Control financiero"
        title="Pagos del club"
        subtitle="Revisa pagos pendientes, atrasados, registrados y recibos generados."
        actions={
          canManagePayments && (
            <div className="payments-header-actions">
              <Button
                type="button"
                onClick={openSyncPanel}
                disabled={syncPreviewLoading || syncApplying}
              >
                {syncPreviewLoading ? "Consultando..." : "Sincronizar pagos"}
              </Button>

              <Button
                type="button"
                variant="secondary"
                onClick={() => navigate("/payments/tournament-charges")}
              >
                Cargos de torneos
              </Button>
            </div>
          )
        }
      />
      <div className="payments-page">
        {syncPanelOpen && (
          <Card className="payments-sync-card">
            <div className="payments-sync-header">
              <div>
                <span>Sincronización manual</span>
                <h3>Antes de sincronizar</h3>
                <p>
                  Revisa los cambios calculados con la configuración actual del
                  club.
                </p>
              </div>

              <Button
                type="button"
                variant="secondary"
                onClick={closeSyncPanel}
                disabled={syncApplying}
              >
                Cerrar
              </Button>
            </div>

            {syncPreviewLoading && !syncPreview ? (
              <p className="empty-state">Calculando vista previa...</p>
            ) : syncPreview ? (
              <>
                <div className="payments-sync-summary">
                  <div>
                    <span>Mensualidades que se crearán</span>
                    <strong>
                      {syncPreview.summary?.payments_to_create || 0}
                    </strong>
                  </div>

                  <div>
                    <span>Pagos que pasarán a vencidos</span>
                    <strong>
                      {syncPreview.summary?.payments_to_mark_overdue || 0}
                    </strong>
                  </div>

                  <div>
                    <span>Jugadoras inactivas omitidas</span>
                    <strong>
                      {syncPreview.summary?.players_skipped_inactive || 0}
                    </strong>
                  </div>

                  <div>
                    <span>Configuraciones por revisar</span>
                    <strong>{syncPreview.warnings?.length || 0}</strong>
                  </div>
                </div>

                {syncPreview.warnings?.length > 0 && (
                  <div className="payments-sync-warnings">
                    <strong>Requieren revisión</strong>
                    <ul>
                      {syncPreview.warnings.slice(0, 3).map((warning) => (
                        <li key={`${warning.player_id}-${warning.reason}`}>
                          {warning.player_name}: {warning.message}
                        </li>
                      ))}
                    </ul>

                    {syncPreview.warnings.length > 3 && (
                      <small>
                        Hay {syncPreview.warnings.length - 3} configuraciones
                        adicionales por revisar.
                      </small>
                    )}
                  </div>
                )}

                {syncResult && (
                  <div className="payments-sync-result" role="status">
                    <strong>
                      {syncResult.applied?.payments_created === 0 &&
                      syncResult.applied?.payments_marked_overdue === 0
                        ? "Los pagos ya estaban actualizados."
                        : "Sincronización completada."}
                    </strong>
                    <p>
                      {syncResult.applied?.payments_created || 0} mensualidades
                      creadas. {syncResult.applied?.payments_marked_overdue || 0}{" "}
                      pagos marcados como vencidos.
                    </p>
                  </div>
                )}

                {syncError && <p className="form-error">{syncError}</p>}

                {syncConfirmationOpen ? (
                  <div className="payments-sync-confirmation">
                    <strong>¿Sincronizar pagos?</strong>
                    <p>
                      SportFlow creará las mensualidades pendientes que
                      correspondan y actualizará los pagos vencidos según la
                      configuración actual.
                    </p>

                    <div className="payments-sync-actions">
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() => setSyncConfirmationOpen(false)}
                        disabled={syncApplying}
                      >
                        Cancelar
                      </Button>

                      <Button
                        type="button"
                        onClick={handlePaymentsSync}
                        disabled={syncApplying}
                      >
                        {syncApplying ? "Sincronizando..." : "Sincronizar"}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="payments-sync-actions">
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={closeSyncPanel}
                    >
                      Cancelar
                    </Button>

                    <Button
                      type="button"
                      onClick={() => setSyncConfirmationOpen(true)}
                      disabled={syncPreviewLoading}
                    >
                      Confirmar sincronización
                    </Button>
                  </div>
                )}
              </>
            ) : (
              <>
                {syncError && <p className="form-error">{syncError}</p>}
                <div className="payments-sync-actions">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={closeSyncPanel}
                  >
                    Cerrar
                  </Button>
                  <Button type="button" onClick={loadSyncPreview}>
                    Volver a intentar
                  </Button>
                </div>
              </>
            )}
          </Card>
        )}

        {(requestedTournamentTeamId || requestedMatchId) && (
          <Card className="payments-context-card">
            <div className="payments-context-copy">
              <span>Vista filtrada</span>

              <strong>
                {requestedTournamentTeamId
                  ? "Cargos de inscripción del torneo"
                  : "Cargos de arbitraje del partido"}
              </strong>

              <p>
                Estás viendo únicamente los cargos generados desde el proceso
                anterior.
              </p>
            </div>

            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setTypeFilter("");
                setStatusFilter("");
                setSearchTerm("");
                navigate("/payments");
              }}
            >
              Ver todos los pagos
            </Button>
          </Card>
        )}

        {!isContextView && (
          <div className="payments-summary-grid">
            <Card className="payment-summary-card club-payment-summary overdue">
              <div className="club-payment-stat-header">
                <AlertTriangle size={15} />
                <span>Atrasado</span>
              </div>

              <strong>
                {formatMoney(summary?.overdue_amount, club?.currency_code)}
              </strong>
              <small>{summary?.overdue || 0} pagos fuera de fecha</small>
            </Card>

            <Card className="payment-summary-card club-payment-summary pending">
              <div className="club-payment-stat-header">
                <Clock3 size={15} />
                <span>Por cobrar</span>
              </div>

              <strong>
                {formatMoney(summary?.pending_amount, club?.currency_code)}
              </strong>
              <small>{summary?.pending || 0} pendientes</small>
            </Card>

            <Card className="payment-summary-card club-payment-summary paid">
              <div className="club-payment-stat-header">
                <CircleCheckBig size={15} />
                <span>Cobrado</span>
              </div>

              <strong>
                {formatMoney(
                  summary?.registered_paid_amount,
                  club?.currency_code,
                )}
              </strong>
              <small>{summary?.registered_paid || 0} pagos registrados</small>
            </Card>
          </div>
        )}
        {!isContextView && (
          <Card className="filter-card payments-filter-card">
            <div className="filter-header">
              <div className="filter-header-content">
                <h3>Filtros</h3>
                <p>Busca por deportista, estado o tipo de pago.</p>
              </div>

              <Button
                type="button"
                variant="secondary"
                className="filter-toggle"
                onClick={() => setFiltersOpen((prev) => !prev)}
              >
                {filtersOpen ? "Ocultar" : "Filtrar"}
              </Button>
            </div>

            <div className={`filter-content ${filtersOpen ? "open" : ""}`}>
              <div className="filter-grid">
                <label className="field-group">
                  <span>Buscar deportista</span>
                  <input
                    className="input"
                    type="text"
                    placeholder="Ej: Juan Pérez"
                    value={searchTerm}
                    onChange={(event) => setSearchTerm(event.target.value)}
                  />
                </label>

                <label className="field-group">
                  <span>Estado</span>
                  <select
                    className="input"
                    value={statusFilter}
                    onChange={(event) => setStatusFilter(event.target.value)}
                  >
                    <option value="">Todos</option>
                    <option value="pending">Pendientes</option>
                    <option value="paid">Pagados</option>
                    <option value="overdue">Atrasados</option>
                    <option value="cancelled">Cancelados</option>
                  </select>
                </label>

                <label className="field-group">
                  <span>Tipo de pago</span>
                  <select
                    className="input"
                    value={typeFilter}
                    onChange={(event) => setTypeFilter(event.target.value)}
                  >
                    <option value="">Todos</option>
                    <option value="enrollment">Inscripción al club</option>
                    <option value="monthly">Mensualidad</option>
                    <option value="tournament">Inscripción de torneo</option>
                    <option value="referee">Arbitraje</option>
                    <option value="uniform">Uniforme</option>
                    <option value="extra">Extra</option>
                  </select>
                </label>
              </div>

              {(searchTerm ||
                statusFilter ||
                typeFilter ||
                requestedTournamentTeamId ||
                requestedMatchId) && (
                <div className="filter-actions">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => {
                      setSearchTerm("");
                      setStatusFilter("");
                      setTypeFilter("");
                      navigate("/payments");
                    }}
                  >
                    Limpiar filtros
                  </Button>
                </div>
              )}
            </div>
          </Card>
        )}

        {loading ? (
          <Card>
            <p className="empty-state">Cargando pagos...</p>
          </Card>
        ) : filteredPayments.length === 0 ? (
          <Card>
            <p className="empty-state">
              No hay cobros que coincidan con esta búsqueda o filtros.
            </p>
          </Card>
        ) : (
          <>
            {openPayments.length > 0 && (
              <Card
                className={`club-payment-open-card ${
                  openPayments.some((payment) => payment.status === "overdue")
                    ? "has-overdue"
                    : "has-pending"
                }`}
              >
                <div className="payments-list-header">
                  <h3>Cobros</h3>

                  <span className="club-payment-section-count">
                    {openPayments.length}{" "}
                    {openPayments.length === 1 ? "cobro" : "cobros"}
                  </span>
                </div>

                <div className="payments-list club-payment-open-list">
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

            {historyPayments.length > 0 && (
              <Card className="club-payment-history-card">
                <div className="payments-list-header">
                  <h3>Historial</h3>

                  <span className="club-payment-section-count">
                    {historyPayments.length}{" "}
                    {historyPayments.length === 1 ? "pago" : "pagos"}
                  </span>
                </div>

                <div className="payments-list club-payment-history-list">
                  {visibleHistoryPaymentRows.map(renderPaymentRow)}
                </div>

                {visibleHistoryPayments < historyPayments.length && (
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() =>
                      setVisibleHistoryPayments((prev) => prev + 5)
                    }
                  >
                    Mostrar más
                  </Button>
                )}
              </Card>
            )}
          </>
        )}
      </div>
    </>
  );
};
