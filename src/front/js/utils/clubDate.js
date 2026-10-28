export const getDateInTimeZone = (timeZone, instant = new Date()) => {
  if (!timeZone) return "";

  try {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(instant);

    const values = Object.fromEntries(
      parts.map(({ type, value }) => [type, value]),
    );

    return `${values.year}-${values.month}-${values.day}`;
  } catch (error) {
    return "";
  }
};

export const getClubToday = (club, instant = new Date()) =>
  getDateInTimeZone(club?.timezone, instant);
