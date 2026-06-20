export const validateClient = ({ full_name, email, club_name, state }) => {
  const errors = {};

  const cleanFullName = full_name?.trim() || "";
  const cleanEmail = email?.trim() || "";
  const cleanClubName = club_name?.trim() || "";
  const cleanState = state?.trim() || "";

  if (!cleanFullName) {
    errors.FULL_NAME_REQUIRED = true;
  }

  if (!cleanEmail) {
    errors.EMAIL_REQUIRED = true;
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) {
    errors.INVALID_EMAIL = true;
  }

  if (!cleanClubName) {
    errors.CLUB_NAME_REQUIRED = true;
  }

  if (!cleanState) {
    errors.STATE_REQUIRED = true;
  }

  return errors;
};

export const validateClubProfile = ({
  name,
  location,
  state,
  defaultEnrollmentFee,
  defaultMonthlyFee,
}) => {
  const errors = {};

  const cleanName = name?.trim() || "";
  const cleanLocation = location?.trim() || "";
  const cleanState = state?.trim() || "";

  if (!cleanName) {
    errors.CLUB_NAME_REQUIRED = true;
  }

  if (!cleanLocation) {
    errors.LOCATION_REQUIRED = true;
  }

  if (!cleanState) {
    errors.STATE_REQUIRED = true;
  }

  if (defaultEnrollmentFee !== "" && Number(defaultEnrollmentFee) < 0) {
    errors.INVALID_DEFAULT_ENROLLMENT_FEE = true;
  }

  if (defaultMonthlyFee !== "" && Number(defaultMonthlyFee) < 0) {
    errors.INVALID_DEFAULT_MONTHLY_FEE = true;
  }

  return errors;
};

export const validateLogin = ({ email, password }) => {
  const errors = {};

  const cleanEmail = email?.trim() || "";
  const cleanPassword = password?.trim() || "";

  if (!cleanEmail) {
    errors.EMAIL_REQUIRED = true;
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) {
    errors.INVALID_EMAIL = true;
  }

  if (!cleanPassword) {
    errors.PASSWORD_REQUIRED = true;
  }

  return errors;
};

export const validatePassword = (password, confirmPassword = "") => {
  const errors = {};

  const cleanPassword = password?.trim() || "";
  const cleanConfirmPassword = confirmPassword?.trim() || "";

  if (!cleanPassword) {
    errors.PASSWORD_REQUIRED = true;
  } else if (cleanPassword.length < 8) {
    errors.PASSWORD_TOO_SHORT = true;
  }

  if (!cleanConfirmPassword) {
    errors.CONFIRM_PASSWORD_REQUIRED = true;
  } else if (cleanPassword !== cleanConfirmPassword) {
    errors.PASSWORDS_NOT_MATCH = true;
  }

  return errors;
};

export const validateCategory = ({ name }) => {
  const errors = {};

  const cleanName = name?.trim() || "";

  if (!cleanName) {
    errors.CATEGORY_NAME_REQUIRED = true;
  }

  return errors;
};

export const validateClubLocation = (location) => {
  const errors = {};

  if (!location?.trim()) {
    errors.LOCATION_REQUIRED = true;
  }

  return errors;
};

export const validateTeam = ({ name, gender }) => {
  const errors = {};

  const cleanName = name?.trim() || "";
  const cleanGender = gender?.trim() || "";

  if (!cleanName) {
    errors.TEAM_NAME_REQUIRED = true;
  }

  if (!cleanGender) {
    errors.INVALID_TEAM_GENDER = true;
  }

  return errors;
};

export const validatePlayerProfile = ({
  first_name,
  last_name,
  sex,
  birth_date,
}) => {
  const errors = {};

  if (!first_name?.trim()) {
    errors.FIRST_NAME_REQUIRED = true;
  }

  if (!last_name?.trim()) {
    errors.LAST_NAME_REQUIRED = true;
  }

  if (!sex) {
    errors.SEX_REQUIRED = true;
  }

  if (birth_date) {
    const selectedDate = new Date(birth_date);
    const today = new Date();

    if (selectedDate > today) {
      errors.INVALID_BIRTH_DATE = true;
    }
  }

  return errors;
};

export const validatePlayerAssignment = ({
  team_id,
  player_number,
  requiredTeam = true,
}) => {
  const errors = {};

  if (!team_id) {
    if (requiredTeam) {
      errors.TEAM_ID_REQUIRED = true;
    }

    return errors;
  }

  if (
    player_number === undefined ||
    player_number === null ||
    player_number === ""
  ) {
    errors.PLAYER_NUMBER_REQUIRED = true;
    return errors;
  }

  const parsedNumber = Number(player_number);

  if (
    !Number.isInteger(parsedNumber) ||
    parsedNumber < 1 ||
    parsedNumber > 99
  ) {
    errors.INVALID_PLAYER_NUMBER = true;
  }

  return errors;
};

export const validateTraining = ({ team_id, date, location }) => {
  const errors = {};

  if (!team_id) {
    errors.TEAM_ID_REQUIRED = true;
  }

  if (!date?.trim()) {
    errors.TRAINING_DATE_REQUIRED = true;
  }

  if (!location?.trim()) {
    errors.TRAINING_LOCATION_REQUIRED = true;
  }

  return errors;
};

export const validateMatch = ({ opponent_name, date, match_type }) => {
  const errors = {};

  if (!opponent_name?.trim()) {
    errors.OPPONENT_NAME_REQUIRED = true;
  }

  if (!date?.trim()) {
    errors.MATCH_DATE_REQUIRED = true;
  }

  const allowedTypes = ["official", "friendly", "scrimmage"];

  if (!allowedTypes.includes(match_type)) {
    errors.INVALID_MATCH_TYPE = true;
  }

  return errors;
};

export const validatePlayerPaymentSettings = ({
  enrollment_date,
  customEnrollmentFee,
  customMonthlyFee,
  enrollment_fee,
  monthly_fee,
  club,
}) => {
  const errors = {};

  if (!enrollment_date?.trim()) {
    errors.ENROLLMENT_DATE_REQUIRED = true;
  }

  const clubEnrollmentFee = Number(club?.default_enrollment_fee || 0);
  const clubMonthlyFee = Number(club?.default_monthly_fee || 0);

  if (!customEnrollmentFee && clubEnrollmentFee <= 0) {
    errors.CLUB_PAYMENT_DEFAULTS_REQUIRED = true;
  }

  if (!customMonthlyFee && clubMonthlyFee <= 0) {
    errors.CLUB_PAYMENT_DEFAULTS_REQUIRED = true;
  }

  if (customEnrollmentFee) {
    const parsedEnrollmentFee = Number(enrollment_fee);

    if (enrollment_fee === "" || enrollment_fee === null) {
      errors.ENROLLMENT_FEE_REQUIRED = true;
    } else if (Number.isNaN(parsedEnrollmentFee) || parsedEnrollmentFee <= 0) {
      errors.INVALID_ENROLLMENT_FEE = true;
    }
  }

  if (customMonthlyFee) {
    const parsedMonthlyFee = Number(monthly_fee);

    if (monthly_fee === "" || monthly_fee === null) {
      errors.MONTHLY_FEE_REQUIRED = true;
    } else if (Number.isNaN(parsedMonthlyFee) || parsedMonthlyFee <= 0) {
      errors.INVALID_MONTHLY_FEE = true;
    }
  }

  return errors;
};

export const validatePaymentRegistration = ({
  payment_date,
  payment_method,
}) => {
  const errors = {};

  const cleanPaymentDate = payment_date?.trim() || "";
  const cleanPaymentMethod = payment_method?.trim() || "";

  if (!cleanPaymentDate) {
    errors.PAYMENT_DATE_REQUIRED = true;
  } else {
    const selectedDate = new Date(`${cleanPaymentDate}T00:00:00`);
    const today = new Date();

    today.setHours(0, 0, 0, 0);

    if (selectedDate > today) {
      errors.INVALID_PAYMENT_DATE = true;
    }
  }

  if (!cleanPaymentMethod) {
    errors.PAYMENT_METHOD_REQUIRED = true;
  }

  return errors;
};

export const validateForgotPassword = ({ email }) => {
  const errors = {};

  const cleanEmail = email?.trim() || "";

  if (!cleanEmail) {
    errors.EMAIL_REQUIRED = true;
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) {
    errors.INVALID_EMAIL = true;
  }

  return errors;
};
