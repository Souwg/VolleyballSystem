import React, { useContext, useEffect, useMemo, useState } from "react";
import { getAssetUrl } from "../../utils/getAssetUrl";
import { useLocation, useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { Input } from "../../component/ui/input";
import { Select } from "../../component/ui/select";
import { FormField } from "../../component/ui/formField";
import { validatePaymentRegistration } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";
import "../../../styles/payments.css";
import { ReceiptText } from "lucide-react";

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

export const Payments = () => {
  const { store, actions } = useContext(Context);
  const location = useLocation();
  const navigate = useNavigate();

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
  const [visiblePayments, setVisiblePayments] = useState(5);
  const [registeringPaymentId, setRegisteringPaymentId] = useState(null);
  const [expandedPaymentId, setExpandedPaymentId] = useState(null);
  const [paymentRegisterForm, setPaymentRegisterForm] = useState({
    payment_date: new Date().toISOString().slice(0, 10),
    payment_method: "",
    reference: "",
    notes: "",
  });
  const [paymentRegisterErrors, setPaymentRegisterErrors] = useState({});
  const [receiptLoadingId, setReceiptLoadingId] = useState(null);
  const [receiptErrors, setReceiptErrors] = useState({});

  const payments = store.payments || [];

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

  useEffect(() => {
    loadPayments();
  }, [statusFilter, typeFilter]);

  useEffect(() => {
    setVisiblePayments(6);
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
      payment_date: new Date().toISOString().slice(0, 10),
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
    const errors = validatePaymentRegistration(paymentRegisterForm);

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

  const getPlayerFullName = (payment) => {
    const firstName = payment.player?.first_name || "";
    const lastName = payment.player?.last_name || "";

    return `${firstName} ${lastName}`.trim() || "el deportista";
  };

  const getWhatsappPhone = (payment) => {
    const phone = payment.player?.representative_phone;

    if (!phone) return null;

    return phone.replace(/\D/g, "");
  };

  const buildWhatsappMessage = (payment, receipt) => {
    const playerName = getPlayerFullName(payment);

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

    const phone = getWhatsappPhone(payment);

    if (!phone) {
      setReceiptErrors({
        [payment.id]: "Este deportista no tiene teléfono de representante.",
      });

      return;
    }

    setReceiptLoadingId(payment.id);

    const receiptResult = await actions.createPaymentReceipt(payment.id);

    if (!receiptResult.ok) {
      setReceiptLoadingId(null);

      setReceiptErrors({
        [payment.id]: receiptResult.message || "No se pudo generar el recibo.",
      });

      return;
    }

    const receipt = receiptResult.data.receipt;
    const message = buildWhatsappMessage(payment, receipt);

    const sharedResult = await actions.markPaymentReceiptShared(receipt.id, {
      sent_channel: "whatsapp",
      sent_to: phone,
    });

    setReceiptLoadingId(null);

    if (!sharedResult.ok) {
      setReceiptErrors({
        [payment.id]:
          sharedResult.message ||
          "Se generó el recibo, pero no se pudo registrar el envío.",
      });

      return;
    }

    await loadPayments();

    window.open(
      `https://wa.me/${phone}?text=${message}`,
      "_blank",
      "noopener,noreferrer",
    );
  };

  return (
    <div className="payments-page">
      <PageHeader
        tone="payments"
        icon={ReceiptText}
        eyebrow="Control financiero"
        title="Pagos del club"
        subtitle="Revisa pagos pendientes, atrasados, registrados y recibos generados."
      />

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
          <Card className="payment-summary-card">
            <span>Atrasado</span>
            <strong>${formatMoney(summary?.overdue_amount)}</strong>
            <small>{summary?.overdue || 0} pagos fuera de fecha</small>
          </Card>

          <Card className="payment-summary-card">
            <span>Por cobrar</span>
            <strong>${formatMoney(summary?.expected_amount)}</strong>
            <small>{summary?.pending || 0} pendientes</small>
          </Card>

          <Card className="payment-summary-card">
            <span>Cobrado</span>
            <strong>${formatMoney(summary?.paid_amount)}</strong>
            <small>{summary?.paid || 0} pagos registrados</small>
          </Card>
        </div>
      )}
      {!isContextView && (
        <Card className="filter-card">
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

      <Card>
        <div className="payments-list-header">
          <h3>
            {requestedTournamentTeamId
              ? "Cobros de inscripción"
              : requestedMatchId
              ? "Cobros de arbitraje"
              : "Cobros registrados"}
          </h3>
          <span>
            {isContextView
              ? `${filteredPayments.length} ${
                  filteredPayments.length === 1 ? "cobro" : "cobros"
                }`
              : `Mostrando ${Math.min(
                  visiblePayments,
                  filteredPayments.length,
                )} de ${filteredPayments.length}`}
          </span>
        </div>

        {loading ? (
          <p className="empty-state">Cargando pagos...</p>
        ) : filteredPayments.length === 0 ? (
          <p className="empty-state">
            No hay cobros que coincidan con esta búsqueda o filtros.
          </p>
        ) : (
          <>
            <div className="payments-list">
              {filteredPayments.slice(0, visiblePayments).map((payment) => (
                <div key={payment.id} className="payment-row">
                  <div>
                    <h4>
                      {payment.player?.first_name} {payment.player?.last_name}
                    </h4>

                    <div className="payment-concept-row">
                      <span
                        className={`payment-type-badge ${payment.payment_type}`}
                      >
                        {PAYMENT_TYPE_LABELS[payment.payment_type] || "Pago"}
                      </span>

                      <strong>${formatMoney(payment.amount)}</strong>
                    </div>

                    <p className="payment-origin">
                      {getPaymentDescription(payment)}
                    </p>

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
                    ) : (
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
                            paymentRegisterErrors.PAYMENT_DATE_REQUIRED &&
                            errorMessages.PAYMENT_DATE_REQUIRED
                          }
                        >
                          <Input
                            type="date"
                            name="payment_date"
                            value={paymentRegisterForm.payment_date}
                            className={
                              paymentRegisterErrors.PAYMENT_DATE_REQUIRED
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
              ))}
            </div>
            {visiblePayments < filteredPayments.length && (
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
