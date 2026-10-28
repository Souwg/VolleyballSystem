const TRAINING_STATUS = {
  scheduled: {
    label: "Programado",
    className: "status-info",
  },
  completed: {
    label: "Completado",
    className: "status-success",
  },
  cancelled: {
    label: "Cancelado",
    className: "status-muted",
  },
};

export const getTrainingStatus = (status) =>
  TRAINING_STATUS[status] || {
    label: "Estado desconocido",
    className: "status-muted",
  };
