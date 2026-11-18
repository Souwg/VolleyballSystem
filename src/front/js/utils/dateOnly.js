const DATE_ONLY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

export const parseDateOnly = (value) => {
  const match = DATE_ONLY_PATTERN.exec(String(value || ""));

  if (!match) return null;

  const [, year, month, day] = match;
  const parsed = new Date(Number(year), Number(month) - 1, Number(day));

  if (
    parsed.getFullYear() !== Number(year) ||
    parsed.getMonth() !== Number(month) - 1 ||
    parsed.getDate() !== Number(day)
  ) {
    return null;
  }

  return parsed;
};

export const formatDateOnly = (value, options = {}) => {
  const parsed = parseDateOnly(value);

  if (!parsed) return "Fecha no disponible";

  return parsed.toLocaleDateString("es-ES", options);
};

export const getLocalDateOnlyValue = (date = new Date()) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
};
