export const validateClient = ({ full_name, email, club_name }) => {
  const errors = {};

  if (!full_name.trim()) {
    errors.FULL_NAME_REQUIRED = true;
  }

  if (!email.trim()) {
    errors.EMAIL_REQUIRED = true;
  } else if (!/\S+@\S+\.\S+/.test(email)) {
    errors.INVALID_EMAIL = true;
  }

  if (!club_name.trim()) {
    errors.CLUB_NAME_REQUIRED = true;
  }

  return errors;
};

export const validateLogin = ({ email, password }) => {
  const errors = {};

  if (!email.trim()) {
    errors.EMAIL_REQUIRED = true;
  } else if (!/\S+@\S+\.\S+/.test(email)) {
    errors.INVALID_EMAIL = true;
  }

  if (!password.trim()) {
    errors.PASSWORD_REQUIRED = true;
  }

  return errors;
};

export const validatePassword = (password, confirmPassword = "") => {
  const errors = {};

  if (!password.trim()) {
    errors.PASSWORD_REQUIRED = true;
  } else if (password.trim().length < 8) {
    errors.PASSWORD_TOO_SHORT = true;
  }

  if (!confirmPassword.trim()) {
    errors.CONFIRM_PASSWORD_REQUIRED = true;
  } else if (password !== confirmPassword) {
    errors.PASSWORDS_NOT_MATCH = true;
  }

  return errors;
};

export const validateClubLocation = (location) => {
  const errors = {};

  if (!location.trim()) {
    errors.LOCATION_REQUIRED = true;
  }

  return errors;
};

export const validateTeam = ({ name, gender }) => {
  const errors = {};

  if (!name.trim()) {
    errors.TEAM_NAME_REQUIRED = true;
  }

  if (!gender) {
    errors.INVALID_TEAM_GENDER = true;
  }

  return errors;
};

export const validatePlayer = ({
  first_name,
  last_name,
  player_number,
  sex,
  team_id,
  birth_date,
}) => {
  const errors = {};

  if (!first_name.trim()) {
    errors.FIRST_NAME_REQUIRED = true;
  }

  if (!last_name.trim()) {
    errors.LAST_NAME_REQUIRED = true;
  }

  if (!player_number.toString().trim()) {
    errors.PLAYER_NUMBER_REQUIRED = true;
  } else {
    const parsedNumber = Number(player_number);

    if (
      !Number.isInteger(parsedNumber) ||
      parsedNumber < 1 ||
      parsedNumber > 99
    ) {
      errors.INVALID_PLAYER_NUMBER = true;
    }
  }

  if (!sex) {
    errors.SEX_REQUIRED = true;
  }

  if (!team_id) {
    errors.TEAM_ID_REQUIRED = true;
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

export const validateTraining = ({ team_id, date, location }) => {
  const errors = {};

  if (!team_id) {
    errors.TEAM_ID_REQUIRED = true;
  }

  if (!date.trim()) {
    errors.TRAINING_DATE_REQUIRED = true;
  }

  if (!location.trim()) {
    errors.TRAINING_LOCATION_REQUIRED = true;
  }

  return errors;
};
