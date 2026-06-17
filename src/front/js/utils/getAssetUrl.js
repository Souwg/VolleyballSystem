export const getAssetUrl = (url) => {
  if (!url) return "";

  if (url.startsWith("http://") || url.startsWith("https://")) {
    return url;
  }

  const backendUrl = process.env.REACT_APP_BACKEND_URL?.trim();

  if (!backendUrl) return url;

  return `${backendUrl}${url}`;
};
