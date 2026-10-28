export const MONEY_LOCALE = "es-ES";

const normalizeCurrencyCode = (currencyCode) => {
  if (typeof currencyCode !== "string") return "";

  const normalizedCode = currencyCode.trim().toUpperCase();

  return /^[A-Z]{3}$/.test(normalizedCode) ? normalizedCode : "";
};

const normalizeSpaces = (value) => value.replace(/[\u00a0\u202f]/g, " ");

export const formatMoney = (amount, currencyCode, options = {}) => {
  const {
    emptyValue = "—",
    locale = MONEY_LOCALE,
    minimumFractionDigits = 2,
    maximumFractionDigits = 2,
  } = options;

  if (amount === null || amount === undefined || amount === "") {
    return emptyValue;
  }

  const numericAmount = Number(amount);

  if (!Number.isFinite(numericAmount)) return emptyValue;

  const normalizedCode = normalizeCurrencyCode(currencyCode);
  const decimalOptions = {
    minimumFractionDigits,
    maximumFractionDigits,
  };

  if (normalizedCode) {
    try {
      return normalizeSpaces(
        new Intl.NumberFormat(locale, {
          ...decimalOptions,
          style: "currency",
          currency: normalizedCode,
          currencyDisplay: "code",
        }).format(numericAmount),
      );
    } catch (error) {
      const formattedAmount = new Intl.NumberFormat(
        locale,
        decimalOptions,
      ).format(numericAmount);

      return `${formattedAmount} ${normalizedCode}`;
    }
  }

  const formattedAmount = new Intl.NumberFormat(locale, decimalOptions).format(
    numericAmount,
  );

  return `${formattedAmount} —`;
};
