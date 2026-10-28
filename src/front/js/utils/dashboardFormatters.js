const PAYMENT_METHOD_LABELS = {
  cash: "Efectivo",
  transfer: "Transferencia",
  zelle: "Zelle",
  mobile_payment: "Pago móvil",
  other: "Otro",
};

const PAYMENT_TYPE_LABELS = {
  enrollment: "Inscripción",
  monthly: "Mensualidad",
  uniform: "Uniforme",
  tournament: "Torneo",
  referee: "Arbitraje",
  extra: "Extra",
};

const PAYMENT_CONFIGURATION_LABELS = {
  missing_enrollment_date: "Falta fecha de ingreso",
  missing_payment_control_start_date: "Falta inicio del control de pagos",
  invalid_monthly_fee: "Cuota mensual requiere revisión",
  legacy_payment_history_requires_review:
    "Historial de pagos requiere revisión",
};

const MATCH_RESULT_LABELS = {
  win: "Victoria",
  loss: "Derrota",
  draw: "Empate",
};

export const formatDashboardDate = (dateValue, options = {}) => {
  if (!dateValue) return "Fecha no registrada";

  const date = new Date(`${dateValue}T00:00:00`);

  return date.toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "short",
    ...options,
  });
};

export const formatDashboardTime = (timeValue) => {
  if (!timeValue) return "Hora por definir";

  return timeValue.slice(0, 5);
};

export const getDashboardPaymentMethodLabel = (method) =>
  PAYMENT_METHOD_LABELS[method] || "Método no registrado";

export const getDashboardPaymentTypeLabel = (type) =>
  PAYMENT_TYPE_LABELS[type] || "Pago";

export const getPaymentConfigurationLabel = (reason) =>
  PAYMENT_CONFIGURATION_LABELS[reason] || "Configuración requiere revisión";

export const getMatchResultLabel = (result) =>
  MATCH_RESULT_LABELS[result] || "Resultado registrado";
