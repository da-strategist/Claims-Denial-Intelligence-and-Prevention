// Code lists and helpers for the 837 billing fields on the New Claim form

export const RELATIONSHIPS = [
  { value: 'self', label: 'Self' },
  { value: 'spouse', label: 'Spouse' },
  { value: 'child', label: 'Child' },
  { value: 'other', label: 'Other' },
]

export const SEXES = [
  { value: 'F', label: 'Female' },
  { value: 'M', label: 'Male' },
  { value: 'U', label: 'Unknown' },
]

// UB-04 codes most outpatient and ED claims here use; the API accepts any valid code
export const TYPES_OF_BILL = [
  { value: '131', label: '131 · Hospital outpatient' },
  { value: '111', label: '111 · Hospital inpatient' },
  { value: '141', label: '141 · Hospital referenced diagnostic' },
  { value: '831', label: '831 · Ambulatory surgery center' },
  { value: '851', label: '851 · Critical access hospital' },
]
export const ADMISSION_TYPES = [
  { value: '1', label: '1 · Emergency' },
  { value: '2', label: '2 · Urgent' },
  { value: '3', label: '3 · Elective' },
  { value: '4', label: '4 · Newborn' },
  { value: '5', label: '5 · Trauma' },
  { value: '9', label: '9 · Not available' },
]
export const ADMISSION_SOURCES = [
  { value: '1', label: '1 · Non-health-care point of origin' },
  { value: '2', label: '2 · Clinic or physician referral' },
  { value: '4', label: '4 · Transfer from a hospital' },
  { value: '5', label: '5 · Transfer from a nursing facility' },
  { value: '7', label: '7 · Emergency room' },
  { value: '9', label: '9 · Not available' },
]
export const PATIENT_STATUSES = [
  { value: '01', label: '01 · Discharged home' },
  { value: '02', label: '02 · Transferred to a hospital' },
  { value: '03', label: '03 · Transferred to a nursing facility' },
  { value: '06', label: '06 · Home health care' },
  { value: '07', label: '07 · Left against medical advice' },
  { value: '20', label: '20 · Expired' },
  { value: '30', label: '30 · Still a patient' },
]
export const REVENUE_CODES = [
  ['0250', 'Pharmacy'],
  ['0300', 'Laboratory'],
  ['0320', 'Radiology, diagnostic'],
  ['0360', 'Operating room'],
  ['0450', 'Emergency room'],
  ['0510', 'Clinic'],
  ['0636', 'Drugs, detailed coding'],
  ['0730', 'EKG/ECG'],
  ['0920', 'Other diagnostic services'],
]

export const emptyPolicy = () => ({
  member_id: '',
  group_number: '',
  relationship: 'self',
  first_name: '',
  last_name: '',
  birth_date: '',
  sex: '',
})
