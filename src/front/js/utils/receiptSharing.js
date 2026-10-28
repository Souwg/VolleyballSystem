import { getAssetUrl } from "./getAssetUrl";
import { formatMoney } from "./money";

const PAYMENT_METHOD_LABELS = {
  cash: "Efectivo",
  transfer: "Transferencia",
  zelle: "Zelle",
  mobile_payment: "Pago móvil",
  other: "Otro",
};

const formatSnapshotDate = (date) => {
  if (!date) return "No registrada";

  return new Date(`${date}T00:00:00`).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
};

export const buildReceiptWhatsappMessage = (receipt) => {
  const receiptUrl = receipt.share_url
    ? getAssetUrl(receipt.share_url)
    : "";

  const playerName = receipt.player_name_snapshot || "el deportista";
  const concept = receipt.concept_snapshot || "Pago";
  const method =
    PAYMENT_METHOD_LABELS[receipt.payment_method_snapshot] || "No registrado";

  return encodeURIComponent(
    `Hola, te compartimos el recibo de pago de ${playerName}.\n\n` +
      `Recibo: ${receipt.receipt_number}\n` +
      `Concepto: ${concept}\n` +
      `Monto: ${formatMoney(
        receipt.amount_snapshot,
        receipt.currency_code_snapshot,
        { emptyValue: "No registrado" },
      )}\n` +
      `Fecha: ${formatSnapshotDate(receipt.payment_date_snapshot)}\n` +
      `Método: ${method}\n` +
      `Referencia: ${receipt.reference_snapshot || "Sin referencia"}` +
      `${receiptUrl ? `\n\nVer PDF: ${receiptUrl}` : ""}`,
  );
};

export const openReceiptWhatsappWindow = () => {
  const whatsappWindow = window.open("about:blank", "_blank");

  if (!whatsappWindow) return null;

  try {
    whatsappWindow.opener = null;
  } catch (error) {
    whatsappWindow.close();
    return null;
  }

  return whatsappWindow;
};

export const navigateReceiptWhatsapp = (
  whatsappWindow,
  phone,
  encodedMessage,
) => {
  try {
    if (!whatsappWindow || whatsappWindow.closed) return false;

    const link = whatsappWindow.document.createElement("a");
    link.href = `https://wa.me/${phone}?text=${encodedMessage}`;
    link.target = "_self";
    link.rel = "noopener noreferrer";
    whatsappWindow.document.body.appendChild(link);
    link.click();
  } catch (error) {
    whatsappWindow.close();
    return false;
  }

  return true;
};
