/** Provider categories (mirrors PROVIDER_CATEGORIES in backend/app/services/records.py). */
export const PROVIDER_CATEGORIES = [
  ["hospital", "Hospital"],
  ["clinic", "Clinic or physician practice"],
  ["pharmacy", "Pharmacy"],
  ["laboratory", "Laboratory"],
  ["imaging", "Imaging centre"],
  ["dental", "Dental practice"],
  ["other", "Other provider"],
];

export const categoryLabel = (value) =>
  (PROVIDER_CATEGORIES.find(([v]) => v === value) || [value, value])[1];
