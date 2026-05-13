export const errorMessages = {
  NETWORK_ERROR: "Error de conexión. Intenta nuevamente.",

  FULL_NAME_REQUIRED: "El nombre es obligatorio",
  EMAIL_REQUIRED: "El email es obligatorio",
  INVALID_EMAIL: "Email inválido",
  CLIENT_ALREADY_EXISTS: "Ya existe un cliente con ese email",
  CLUB_NAME_REQUIRED: "El nombre del club es obligatorio",

  // LOGIN
  PASSWORD_REQUIRED: "La contraseña es obligatoria",
  PASSWORD_TOO_SHORT: "Debe tener al menos 8 caracteres",
  CONFIRM_PASSWORD_REQUIRED: "Confirma tu contraseña",
  PASSWORDS_NOT_MATCH: "Las contraseñas no coinciden",
  INVALID_CREDENTIALS: "Email o contraseña incorrectos",
  ACCOUNT_DISABLED: "Tu cuenta está desactivada. Contacta al administrador.",

  // ONBOARDING / TEAMS / PLAYERS
  LOCATION_REQUIRED: "La ubicación es obligatoria",
  TEAM_NAME_REQUIRED: "Ingresa un nombre para el equipo",
  TEAM_ALREADY_EXISTS: "Ya existe un equipo con ese nombre",
  INVALID_TEAM_GENDER: "Selecciona el género",
  FIRST_NAME_REQUIRED: "Ingresa el nombre",
  LAST_NAME_REQUIRED: "Ingresa el apellido",
  INVALID_BIRTH_DATE: "La fecha de nacimiento no puede ser futura",
  PLAYER_NUMBER_REQUIRED: "Ingresa el número del jugador",
  INVALID_PLAYER_NUMBER: "El número debe estar entre 1 y 99",
  PLAYER_NUMBER_DUPLICATED: "Ya existe un jugador con ese número",
  PLAYER_INACTIVE:
    "Esta deportista está desactivada y no puede asignarse a una categoría.",
  SEX_REQUIRED: "Selecciona un sexo",
  INVALID_SEX: "Sexo inválido",
  TEAM_ID_REQUIRED: "Selecciona un equipo",

  // TRAININGS
  TRAINING_DATE_REQUIRED: "Selecciona una fecha",
  TRAINING_LOCATION_REQUIRED: "La ubicación es obligatoria",
  TEAM_HAS_TRAININGS:
    "No puedes eliminar esta categoría porque tiene entrenamientos históricos.",

  // TEAMS
  TEAM_HAS_PLAYERS: "No puedes eliminar esta categoría porque tiene jugadores.",

  PLAYER_ALREADY_IN_TEAM: "Este jugador ya pertenece a la categoría.",

  PLAYER_MEMBERSHIP_NOT_FOUND: "El jugador no pertenece a esta categoría.",

  ATTENDANCE_REQUIRED: "Debes marcar al menos una asistencia.",
  // MATCHES
  OPPONENT_NAME_REQUIRED: "Ingresa el rival",
  MATCH_DATE_REQUIRED: "Selecciona la fecha",
  MATCH_STATUS_REQUIRED: "Debes registrar el estado de todas las convocadas",
  MATCH_PARTICIPATION_REQUIRED:
    "Debes registrar la participación de las jugadoras",
  MATCH_PLAYER_ID_REQUIRED: "Falta el registro de la jugadora en el partido.",
  MATCH_PLAYER_NOT_FOUND:
    "No se encontró el registro de la jugadora en el partido.",
  MATCH_PLAYER_INVALID: "La jugadora no pertenece a este partido.",
  PLAYER_NOT_CALLED: "La jugadora no está convocada para este partido.",
  PLAYER_NOT_ELIGIBLE_FOR_PARTICIPATION:
    "La jugadora no puede marcar participación con ese estado.",
  PLAYER_NOT_ELIGIBLE_FOR_STATS:
    "La jugadora no puede registrar estadísticas en este partido.",
  MATCH_ROSTER_REQUIRED: "Debes seleccionar al menos una jugadora.",
  INVALID_MATCH_STATUS: "Estado inválido",
  INVALID_MATCH_TYPE: "Tipo de partido inválido",
  INVALID_MATCH_RESULT:
    "Resultado inválido. Debe ser máximo 5 sets y uno de los equipos debe llegar a 3.",
  INVALID_ATTACK_STATS: "Los ataques no cuadran",
  INVALID_RECEPTION_STATS: "Las recepciones no cuadran",
  INVALID_SERVE_STATS: "Los saques no cuadran",
  INVALID_BLOCK_STATS: "Los bloqueos no cuadran",
  INVALID_POSITION: "Posición inválida",
  POSITION_REQUIRED: "Define la posición de las jugadoras que van a jugar",
};
