export const errorMessages = {
  NETWORK_ERROR: "Error de conexión. Intenta nuevamente.",
  SESSION_EXPIRED: "Tu sesión expiró. Inicia sesión nuevamente.",

  // CLIENTS / GENERAL FORM
  FULL_NAME_REQUIRED: "El nombre es obligatorio",
  EMAIL_REQUIRED: "El email es obligatorio",
  INVALID_EMAIL: "Email inválido",
  CLIENT_ALREADY_EXISTS: "Ya existe un cliente con ese email",
  CLIENT_CREATION_FAILED:
    "No pudimos crear el cliente. Intenta nuevamente.",
  EMAIL_ALREADY_EXISTS: "Ya existe un usuario con ese email",
  INVALID_ROLE: "Selecciona un rol válido",
  CLUB_NAME_REQUIRED: "El nombre del club es obligatorio",
  STATE_REQUIRED: "El estado es obligatorio",
  SPORT_REQUIRED: "Selecciona un deporte",
  INVALID_SPORT: "El deporte seleccionado no es válido",
  SPORT_NOT_AVAILABLE:
    "El deporte seleccionado no está disponible para nuevas altas",
  COUNTRY_REQUIRED: "Selecciona un país",
  INVALID_COUNTRY: "El país seleccionado no es válido",
  COUNTRY_NOT_AVAILABLE:
    "El país seleccionado no está disponible para nuevas altas",
  ADMINISTRATIVE_AREA_REQUIRED:
    "Selecciona un estado, provincia o región",
  INVALID_ADMINISTRATIVE_AREA:
    "El estado, provincia o región seleccionado no es válido",
  ADMINISTRATIVE_AREA_NOT_AVAILABLE:
    "El estado, provincia o región seleccionado no está disponible",
  AREA_COUNTRY_MISMATCH:
    "La región seleccionada no pertenece al país indicado",
  CITY_REQUIRED: "La ciudad es obligatoria",
  CITY_TOO_LONG: "La ciudad no puede superar los 120 caracteres",
  TIMEZONE_REQUIRED: "Selecciona una zona horaria",
  CURRENCY_REQUIRED: "Selecciona una moneda",
  INVALID_CURRENCY: "La moneda seleccionada no es válida",
  INVALID_TIMEZONE: "La zona horaria seleccionada no es válida",

  // LOGIN / PASSWORD
  PASSWORD_REQUIRED: "La contraseña es obligatoria",
  PASSWORD_TOO_SHORT: "Debe tener al menos 8 caracteres",
  CONFIRM_PASSWORD_REQUIRED: "Confirma tu contraseña",
  PASSWORDS_NOT_MATCH: "Las contraseñas no coinciden",
  FIRST_LOGIN_ALREADY_COMPLETED:
    "La contraseña inicial ya fue configurada.",
  FIRST_LOGIN_REQUIRED:
    "Debes establecer tu nueva contraseña antes de continuar.",
  INVALID_CREDENTIALS: "Email o contraseña incorrectos",
  ACCOUNT_DISABLED: "Tu cuenta está desactivada. Contacta al administrador.",
  CLUB_SUSPENDED: "El acceso a este club se encuentra suspendido.",
  RESET_TOKEN_REQUIRED: "El enlace de recuperación no es válido",
  RESET_TOKEN_INVALID: "El enlace no es válido o ya fue usado",
  RESET_TOKEN_EXPIRED: "El enlace expiró. Solicita uno nuevo.",
  USER_NOT_FOUND: "Usuario no encontrado",
  PASSWORD_RESET_EMAIL_FAILED:
    "No pudimos enviar el correo. Intenta nuevamente más tarde.",

  // CLUB
  LOCATION_REQUIRED: "La ciudad es obligatoria",
  CLUB_NOT_FOUND: "Club no encontrado",
  CLUB_REQUIRED: "El usuario no pertenece a ningún club",
  CLUB_SETUP_PENDING:
    "El dueño del club debe completar la configuración inicial.",
  FORBIDDEN: "No tienes permisos para realizar esta acción",
  INVALID_DEFAULT_ENROLLMENT_FEE:
    "El monto de inscripción debe ser un número válido",
  INVALID_DEFAULT_MONTHLY_FEE:
    "El monto de mensualidad debe ser un número válido",

  // CATEGORIES
  CATEGORY_NAME_REQUIRED: "Ingresa un nombre para la categoría",
  CATEGORY_ALREADY_EXISTS: "Ya existe una categoría con ese nombre",
  CATEGORY_ID_REQUIRED: "Selecciona una categoría",
  CATEGORY_NOT_FOUND: "Categoría no encontrada",
  CATEGORY_HAS_TEAMS: "No puedes eliminar una categoría que tiene equipos.",

  // TEAMS
  TEAM_NAME_REQUIRED: "Ingresa un nombre para el equipo",
  TEAM_ALREADY_EXISTS: "Ya existe un equipo con ese nombre",
  INVALID_TEAM_GENDER: "Selecciona el género",
  TEAM_ID_REQUIRED: "Selecciona un equipo",
  TEAM_NOT_FOUND: "Equipo no encontrado",
  TEAM_HAS_PLAYERS: "No puedes eliminar este equipo porque tiene jugadores.",
  TEAM_HAS_TRAININGS:
    "No puedes eliminar este equipo porque tiene entrenamientos históricos.",
  TEAM_GENDER_HAS_PLAYERS:
    "No puedes cambiar el género del equipo porque tiene deportistas incompatibles.",

  // PLAYERS
  FIRST_NAME_REQUIRED: "Ingresa el nombre",
  LAST_NAME_REQUIRED: "Ingresa el apellido",
  INVALID_BIRTH_DATE: "La fecha de nacimiento no puede ser futura",
  PLAYER_NUMBER_REQUIRED: "Ingresa el número del jugador",
  INVALID_PLAYER_NUMBER: "El número debe estar entre 1 y 99",
  PLAYER_NUMBER_DUPLICATED: "Ya existe un jugador con ese número",
  PLAYER_INACTIVE:
    "Esta deportista está desactivada y no puede asignarse a un equipo.",
  SEX_REQUIRED: "Selecciona un sexo",
  INVALID_SEX: "Sexo inválido",
  PLAYER_ALREADY_IN_TEAM: "Este jugador ya pertenece al equipo.",
  PLAYER_MEMBERSHIP_NOT_FOUND: "El jugador no pertenece a este equipo.",
  PLAYER_GENDER_MISMATCH:
    "El sexo del deportista no coincide con la rama del equipo.",
  PLAYER_NOT_FOUND: "Deportista no encontrado",
  INVALID_PLAYER_STATUS: "Estado del deportista inválido",
  INVALID_PLAYER_ACTIVE_STATUS: "Estado inválido",
  PLAYER_HAS_HISTORY:
    "No se puede eliminar esta jugadora porque posee historial registrado. Puedes desactivarla en su lugar.",

  // TRAININGS / ATTENDANCE
  TRAINING_DATE_REQUIRED: "Selecciona una fecha",
  TRAINING_START_TIME_REQUIRED: "Selecciona la hora de inicio",
  TRAINING_END_TIME_REQUIRED: "Selecciona la hora de finalización",
  INVALID_TIME_FORMAT: "El formato de la hora no es válido",
  INVALID_TRAINING_TIME_RANGE:
    "La hora de finalización debe ser posterior a la hora de inicio",
  TRAINING_LOCATION_REQUIRED: "La ubicación es obligatoria",
  ATTENDANCE_REQUIRED: "Debes marcar al menos una asistencia.",
  TRAINING_NOT_FOUND: "Entrenamiento no encontrado",
  INVALID_TRAINING_STATUS:
    "El estado actual del entrenamiento no permite realizar esta acción.",
  TRAINING_CANCELLED:
    "No puedes registrar asistencia en un entrenamiento cancelado.",
  TRAINING_ROSTER_FROZEN:
    "Los participantes de este entrenamiento ya no pueden modificarse.",
  TRAINING_LOCKED:
    "Este entrenamiento está cerrado. Usa una corrección histórica para modificarlo.",
  CORRECTION_REASON_REQUIRED:
    "El motivo de la corrección es obligatorio.",
  CORRECTION_REASON_TOO_LONG:
    "El motivo no puede superar los 500 caracteres.",
  CORRECTION_NO_CHANGES:
    "La corrección no contiene cambios reales.",
  INVALID_TRAINING_CORRECTION_FIELDS:
    "La corrección contiene información no permitida.",
  TRAINING_CORRECTION_FAILED:
    "No se pudo guardar la corrección. Intenta nuevamente.",
  TRAINING_REACTIVATION_FAILED:
    "No se pudo reactivar el entrenamiento. Intenta nuevamente.",
  INVALID_ATTENDANCE_STATUS: "Estado de asistencia inválido",
  TEAM_HAS_NO_PLAYERS:
    "Agrega al menos un deportista al equipo antes de crear un entrenamiento.",

  // TOURNAMENTS
  TOURNAMENT_NAME_REQUIRED: "Ingresa el nombre del torneo",
  TOURNAMENT_START_DATE_REQUIRED: "Selecciona la fecha de inicio",
  TOURNAMENT_ALREADY_EXISTS:
    "Ya existe un torneo con ese nombre y fecha de inicio",
  TOURNAMENT_NOT_FOUND: "Torneo no encontrado",
  INVALID_TOURNAMENT_DATE_RANGE:
    "La fecha de finalización no puede ser anterior a la fecha de inicio",
  INVALID_TOURNAMENT_STATUS: "Estado de torneo inválido",
  INVALID_AMOUNT: "Ingresa un monto válido",
  TOURNAMENT_TEAM_NOT_FOUND: "Participación de torneo no encontrada",
  TEAM_ALREADY_IN_TOURNAMENT: "Este equipo ya está inscrito en el torneo",
  TOURNAMENT_NOT_ACTIVE: "El torneo no está activo",
  TOURNAMENT_TEAM_NOT_ACTIVE: "La participación del equipo no está activa",
  PLAYER_NOT_IN_TEAM: "Una o más deportistas no pertenecen a este equipo",
  INVALID_TOURNAMENT_PLAYERS: "La selección de deportistas no es válida",
  TOURNAMENT_PLAYERS_REQUIRED: "Debes inscribir al menos una deportista",
  INVALID_TOURNAMENT_REGISTRATION_FEE:
    "El costo de inscripción debe ser mayor que cero",
  TOURNAMENT_REGISTRATION_CHARGES_LOCKED:
    "No puedes modificar los cargos porque alguno ya fue pagado o tiene recibo",
  TOURNAMENT_PLAYERS_FINANCIALLY_LOCKED:
    "No puedes cambiar las deportistas porque existen pagos registrados",

  // MATCHES
  MATCH_NOT_FOUND: "Partido no encontrado",
  OPPONENT_NAME_REQUIRED: "Ingresa el rival",
  MATCH_DATE_REQUIRED: "Selecciona la fecha",
  MATCH_STATUS_REQUIRED: "Debes registrar el estado de todas las convocadas",
  MATCH_PARTICIPATION_REQUIRED:
    "Debes registrar la participación de las jugadoras",
  INVALID_MATCH_PARTICIPATION:
    "La lista de participación contiene datos inválidos.",
  DUPLICATE_MATCH_PARTICIPANT:
    "Una jugadora aparece más de una vez en la participación.",
  MATCH_PARTICIPATION_MANAGED_BY_LIVE:
    "La participación de este partido se determina desde LiveMatch.",
  MATCH_PLAYER_ID_REQUIRED: "Falta el registro de la jugadora en el partido.",
  MATCH_PLAYER_NOT_FOUND:
    "No se encontró el registro de la jugadora en el partido.",
  MATCH_PLAYER_INVALID: "La jugadora no pertenece a este partido.",
  MATCH_ROSTER_REQUIRED: "Debes seleccionar al menos una jugadora.",
  INVALID_MATCH_ROSTER:
    "Uno o más participantes no pertenecen a este partido.",
  MATCH_COMPLETED:
    "El partido ya está finalizado y no permite realizar este cambio.",
  MATCH_HISTORY_LOCKED:
    "El cambio no puede realizarse porque existe historial deportivo registrado.",
  INVALID_MATCH_STATUS: "Estado inválido",
  INVALID_MATCH_TYPE: "Tipo de partido inválido",
  INVALID_MATCH_RESULT:
    "Resultado inválido. Debe ser máximo 5 sets y uno de los equipos debe llegar a 3.",
  MATCH_RESULT_INCOMPLETE:
    "Debes guardar un resultado válido antes de finalizar el partido.",
  MATCH_RESULT_NOT_SUPPORTED:
    "El deporte del club no tiene una validación de resultado configurada.",
  MATCH_FINALIZED:
    "El partido ya fue finalizado y no puede modificarse.",
  INVALID_MATCH_CAPTURE_MODE: "Selecciona un modo de captura válido.",
  MATCH_CAPTURE_MODE_REQUIRED:
    "Elige cómo registrarás las estadísticas de este partido.",
  MATCH_CAPTURE_MODE_LOCKED:
    "El modo de captura ya no puede cambiarse porque el partido tiene información estadística o fue finalizado.",
  MATCH_CAPTURE_MODE_LEGACY_LOCKED:
    "Este partido tiene estadísticas históricas cuyo origen debe revisarse antes de permitir cambios.",
  MATCH_STATS_MANAGED_BY_LIVE:
    "Las estadísticas de este partido se generan desde LiveMatch.",
  MATCH_EVENTS_NOT_AVAILABLE:
    "Los eventos no están disponibles en el modo resumen.",
  MATCH_EVENT_RULES_NOT_SUPPORTED:
    "El deporte del club no tiene eventos válidos configurados.",
  MATCH_LINEUP_NOT_SUPPORTED:
    "El deporte del club no tiene una alineación válida configurada.",
  MATCH_PERIODS_NOT_SUPPORTED:
    "El deporte del club no tiene períodos válidos configurados.",

  PLAYER_NOT_CALLED: "La jugadora no está convocada para este partido.",
  PLAYER_NOT_ELIGIBLE_FOR_PARTICIPATION:
    "La jugadora no puede marcar participación con ese estado.",
  PLAYER_NOT_ELIGIBLE_FOR_STATS:
    "La jugadora no puede registrar estadísticas en este partido.",
  PLAYER_NOT_ELIGIBLE_FOR_LINEUP:
    "Todas las jugadoras iniciales deben estar presentes o haber llegado tarde",
  PLAYER_NOT_ELIGIBLE_FOR_SUBSTITUTION:
    "La jugadora que entra debe estar presente o haber llegado tarde",
  PLAYER_NOT_ON_COURT: "Solo puedes registrar acciones a jugadoras en cancha",

  STARTING_LINEUP_REQUIRED: "Debes seleccionar las jugadoras iniciales",
  STARTING_LINEUP_MUST_HAVE_6:
    "Debes seleccionar exactamente 6 jugadoras en cancha",
  INVALID_STARTING_LINEUP: "Una o más jugadoras no pertenecen a este partido",

  INVALID_SET_NUMBER: "Set inválido",
  SUBSTITUTION_PLAYERS_REQUIRED: "Debes indicar quién sale y quién entra",
  INVALID_SUBSTITUTION: "Cambio inválido",
  PLAYER_OUT_NOT_ELIGIBLE: "La jugadora que sale no está disponible para jugar",
  PLAYER_OUT_NOT_ON_COURT: "La jugadora que sale debe estar en cancha",
  PLAYER_IN_ALREADY_ON_COURT: "La jugadora que entra ya está en cancha",

  MATCH_EVENT_REQUIRED: "Faltan datos del evento",
  INVALID_EVENT_ACTION: "Acción inválida",
  INVALID_EVENT_RESULT: "Resultado inválido para esta acción",
  MATCH_EVENT_NOT_FOUND: "Evento no encontrado",

  INVALID_ATTACK_STATS: "Los ataques no cuadran",
  INVALID_RECEPTION_STATS: "Las recepciones no cuadran",
  INVALID_SERVE_STATS: "Los saques no cuadran",
  INVALID_BLOCK_STATS: "Los bloqueos no cuadran",
  INVALID_POSITION: "Posición inválida",
  POSITION_REQUIRED: "Define la posición de las jugadoras que van a jugar",

  REFEREE_FEE_NOT_CONFIGURED:
    "Este partido no tiene costo de arbitraje configurado",
  INVALID_REFEREE_FEE: "El costo de arbitraje debe ser mayor que cero",
  REFEREE_CHARGES_LOCKED:
    "No puedes recalcular el arbitraje porque existen pagos registrados",
  MATCH_ROSTER_FINANCIALLY_LOCKED:
    "No puedes cambiar la convocatoria porque existen pagos de arbitraje registrados",
  TOURNAMENT_TEAM_MISMATCH:
    "El torneo seleccionado no corresponde al equipo del partido",

  // IMAGES
  IMAGE_TOO_LARGE: "La imagen es demasiado pesada",
  IMAGE_REQUIRED: "Debes seleccionar una imagen",
  INVALID_IMAGE_FORMAT: "Formato inválido. Usa PNG, JPG o WEBP",

  // PAYMENTS
  ENROLLMENT_DATE_REQUIRED: "Selecciona la fecha de inscripción",
  CLUB_PAYMENT_DEFAULTS_REQUIRED:
    "Primero configura los montos de inscripción y mensualidad en el perfil del club",
  ENROLLMENT_FEE_REQUIRED: "Ingresa el monto de inscripción",
  MONTHLY_FEE_REQUIRED: "Ingresa el monto de la mensualidad",
  INVALID_ENROLLMENT_FEE: "La inscripción debe ser mayor a 0",
  INVALID_MONTHLY_FEE: "La mensualidad debe ser mayor a 0",
  PAYMENT_DATE_REQUIRED: "Selecciona la fecha de pago",
  PAYMENT_METHOD_REQUIRED: "Selecciona el método de pago",
  INVALID_PAYMENT_METHOD: "Método de pago inválido",
  INVALID_PAYMENT_AMOUNT: "Monto inválido",
  INVALID_DATE_FORMAT: "Formato de fecha inválido",
  INVALID_PAYMENT_STATUS: "Estado de pago inválido",
  INVALID_PAYMENT_TYPE: "Tipo de pago inválido",
  PAYMENT_NOT_FOUND: "Pago no encontrado",
  PAYMENT_SYNC_FAILED:
    "No pudimos sincronizar los pagos. Intenta nuevamente.",
  INVALID_DUE_DATE_FORMAT: "Formato de fecha límite inválido",
  INVALID_ENROLLMENT_DATE_FORMAT: "Formato de fecha de inscripción inválido",
  INITIAL_PAYMENT_MODE_REQUIRED:
    "Selecciona cómo quieres iniciar el historial de mensualidades",
  INITIAL_ENROLLMENT_STATUS_REQUIRED:
    "Selecciona el estado inicial de la inscripción",
  INVALID_HISTORY_ENROLLMENT_DATE:
    "No puedes traer historial de mensualidades para una inscripción futura",
  INVALID_LAST_PAID_MONTH_FORMAT:
    "El último mes pagado no tiene un formato válido",
  LAST_PAID_MONTH_BEFORE_ENROLLMENT:
    "El último mes pagado no puede ser anterior a la inscripción",
  LAST_PAID_MONTH_NOT_REACHED: "Ese ciclo mensual todavía no ha comenzado",
  ENROLLMENT_DATE_LOCKED:
    "La fecha de inscripción ya no puede modificarse porque el control de pagos ya fue iniciado",
  LEGACY_PAYMENT_HISTORY_REQUIRES_REVIEW:
    "Este deportista tiene pagos creados con la configuración anterior y requiere revisión antes de iniciar el nuevo control",
  MIGRATED_PAYMENT_LOCKED:
    "Los pagos anteriores a SportFlow forman parte del historial y no pueden modificarse",
  MIGRATED_PAYMENT_RECEIPT_NOT_ALLOWED:
    "Los pagos realizados antes de SportFlow no generan recibo",
  // RECEIPTS
  PAYMENT_NOT_PAID: "Solo puedes generar recibos de pagos registrados",
  RECEIPT_NUMBER_CONFLICT:
    "No se pudo asignar un número único al recibo. Contacta al administrador.",
  RECEIPT_PDF_GENERATION_FAILED:
    "No se pudo generar el PDF del recibo. Intenta nuevamente.",
  RECEIPT_PDF_REPAIR_FAILED:
    "No se pudo reparar el PDF del recibo. Intenta nuevamente.",
  RECEIPT_PDF_INVALID_PATH:
    "La ubicación del PDF del recibo no es válida.",
  RECEIPT_NOT_FOUND: "Recibo no encontrado",
  RECEIPT_INVALIDATED:
    "El recibo fue invalidado y no puede compartirse nuevamente.",
  INVALID_RECEIPT_CHANNEL: "Canal de envío inválido",
  INVALID_RECEIPT_DESTINATION: "El destino de WhatsApp es inválido",
  INVALID_PAYMENT_DATE: "La fecha de pago no puede ser futura",
};
