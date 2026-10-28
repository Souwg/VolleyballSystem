export const getPublicLoginUrl = (origin = window.location.origin) =>
  new URL("/login", origin).toString();
