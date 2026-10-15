export const claims = [
  {
    claimId: 'CLM-2026-0001', patientId: 'PAT-1001', providerName: 'Dr. Sarah Mitchell', specialty: 'Cardiology',
    payerId: 'PAY-001', payerName: 'Aetna', departmentName: 'Cardiology', serviceDate: '2026-09-15',
    submissionDate: '2026-09-18', totalCharge: 4500.00, totalAllowed: 3800.00, totalPaid: 3800.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'I25.10', diagnosisDescription: 'Atherosclerotic heart disease of native coronary artery',
    daysInAr: 12, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0002', patientId: 'PAT-1002', providerName: 'Dr. James Anderson', specialty: 'Orthopedics',
    payerId: 'PAY-002', payerName: 'UnitedHealthcare', departmentName: 'Orthopedics', serviceDate: '2026-09-10',
    submissionDate: '2026-09-12', totalCharge: 12500.00, totalAllowed: 10200.00, totalPaid: 0,
    status: 'denied', claimType: 'Professional', primaryIcd10: 'M17.11', diagnosisDescription: 'Primary osteoarthritis, right knee',
    daysInAr: 45, isCleanClaim: false, paRequired: true, paObtained: false, paNumber: null,
    denial: { denialId: 'DEN-001', rootCauseCategory: 'Authorization', carcCode: '197', carcDescription: 'Precertification/authorization/notification absent', rarcCode: 'N386', rarcDescription: 'Missing authorization', denialAmount: 12500.00, workflowFailurePoint: 'Pre-Service', isPreventable: true, denialReasonText: 'Prior authorization was not obtained before the procedure' }
  },
  {
    claimId: 'CLM-2026-0003', patientId: 'PAT-1003', providerName: 'Dr. Lisa Chen', specialty: 'Internal Medicine',
    payerId: 'PAY-003', payerName: 'Blue Cross Blue Shield', departmentName: 'Internal Medicine', serviceDate: '2026-09-20',
    submissionDate: '2026-09-22', totalCharge: 850.00, totalAllowed: 720.00, totalPaid: 720.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'E11.9', diagnosisDescription: 'Type 2 diabetes mellitus without complications',
    daysInAr: 8, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0004', patientId: 'PAT-1004', providerName: 'Dr. Robert Williams', specialty: 'Oncology',
    payerId: 'PAY-004', payerName: 'Cigna', departmentName: 'Oncology', serviceDate: '2026-08-25',
    submissionDate: '2026-08-28', totalCharge: 55000.00, totalAllowed: 48000.00, totalPaid: 48000.00,
    status: 'approved', claimType: 'Institutional', primaryIcd10: 'C34.90', diagnosisDescription: 'Malignant neoplasm of unspecified part of bronchus or lung',
    daysInAr: 35, isCleanClaim: true, paRequired: true, paObtained: true, paNumber: 'PA-2026-4401', denial: null
  },
  {
    claimId: 'CLM-2026-0005', patientId: 'PAT-1005', providerName: 'Dr. Maria Garcia', specialty: 'Neurology',
    payerId: 'PAY-005', payerName: 'Medicare', departmentName: 'Neurology', serviceDate: '2026-09-05',
    submissionDate: '2026-09-08', totalCharge: 3200.00, totalAllowed: 2800.00, totalPaid: 2800.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'G43.909', diagnosisDescription: 'Migraine, unspecified, not intractable',
    daysInAr: 15, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0006', patientId: 'PAT-1006', providerName: 'Dr. Kevin Thompson', specialty: 'Gastroenterology',
    payerId: 'PAY-001', payerName: 'Aetna', departmentName: 'Gastroenterology', serviceDate: '2026-09-12',
    submissionDate: '2026-09-15', totalCharge: 6800.00, totalAllowed: 5500.00, totalPaid: 0,
    status: 'denied', claimType: 'Professional', primaryIcd10: '', diagnosisDescription: '',
    daysInAr: 52, isCleanClaim: false, paRequired: false, paObtained: false, paNumber: null,
    denial: { denialId: 'DEN-002', rootCauseCategory: 'Coding', carcCode: '16', carcDescription: 'Claim/service lacks information needed for adjudication', rarcCode: 'M76', rarcDescription: 'Missing diagnosis code', denialAmount: 6800.00, workflowFailurePoint: 'Coding', isPreventable: true, denialReasonText: 'Missing primary diagnosis code on claim submission' }
  },
  {
    claimId: 'CLM-2026-0007', patientId: 'PAT-1007', providerName: 'Dr. Angela Davis', specialty: 'Pulmonology',
    payerId: 'PAY-002', payerName: 'UnitedHealthcare', departmentName: 'Pulmonology', serviceDate: '2026-09-18',
    submissionDate: '2026-09-20', totalCharge: 2100.00, totalAllowed: 1800.00, totalPaid: 1800.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'J44.1', diagnosisDescription: 'Chronic obstructive pulmonary disease with acute exacerbation',
    daysInAr: 10, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0008', patientId: 'PAT-1008', providerName: 'Dr. Thomas Brown', specialty: 'Cardiology',
    payerId: 'PAY-003', payerName: 'Blue Cross Blue Shield', departmentName: 'Cardiology', serviceDate: '2026-08-30',
    submissionDate: '2026-09-02', totalCharge: 78000.00, totalAllowed: 65000.00, totalPaid: 58000.00,
    status: 'approved', claimType: 'Institutional', primaryIcd10: 'I21.09', diagnosisDescription: 'ST elevation myocardial infarction involving other coronary artery of anterior wall',
    daysInAr: 42, isCleanClaim: false, paRequired: true, paObtained: true, paNumber: 'PA-2026-8801', denial: null
  },
  {
    claimId: 'CLM-2026-0009', patientId: 'PAT-1009', providerName: 'Dr. Jennifer Lee', specialty: 'Dermatology',
    payerId: 'PAY-004', payerName: 'Cigna', departmentName: 'Dermatology', serviceDate: '2026-09-22',
    submissionDate: '2026-09-24', totalCharge: 450.00, totalAllowed: 380.00, totalPaid: 380.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'L40.0', diagnosisDescription: 'Psoriasis vulgaris',
    daysInAr: 6, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0010', patientId: 'PAT-1010', providerName: 'Dr. Michael Roberts', specialty: 'Emergency Medicine',
    payerId: 'PAY-006', payerName: 'Humana', departmentName: 'Emergency', serviceDate: '2026-09-25',
    submissionDate: '2026-09-27', totalCharge: 8900.00, totalAllowed: 7200.00, totalPaid: 0,
    status: 'denied', claimType: 'Institutional', primaryIcd10: 'S72.001A', diagnosisDescription: 'Fracture of unspecified part of neck of right femur, initial encounter',
    daysInAr: 68, isCleanClaim: false, paRequired: true, paObtained: false, paNumber: null,
    denial: { denialId: 'DEN-003', rootCauseCategory: 'Authorization', carcCode: '197', carcDescription: 'Precertification/authorization/notification absent', rarcCode: 'N386', rarcDescription: 'Missing authorization', denialAmount: 8900.00, workflowFailurePoint: 'Pre-Service', isPreventable: true, denialReasonText: 'Admission authorization was not obtained within required timeframe' }
  },
  {
    claimId: 'CLM-2026-0011', patientId: 'PAT-1011', providerName: 'Dr. Patricia Moore', specialty: 'Endocrinology',
    payerId: 'PAY-005', payerName: 'Medicare', departmentName: 'Endocrinology', serviceDate: '2026-09-08',
    submissionDate: '2026-09-10', totalCharge: 1200.00, totalAllowed: 980.00, totalPaid: 980.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'E05.90', diagnosisDescription: 'Thyrotoxicosis, unspecified',
    daysInAr: 14, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0012', patientId: 'PAT-1012', providerName: 'Dr. David Wilson', specialty: 'Orthopedics',
    payerId: 'PAY-001', payerName: 'Aetna', departmentName: 'Orthopedics', serviceDate: '2026-09-01',
    submissionDate: '2026-09-03', totalCharge: 35000.00, totalAllowed: 28000.00, totalPaid: 28000.00,
    status: 'approved', claimType: 'Institutional', primaryIcd10: 'M16.11', diagnosisDescription: 'Primary osteoarthritis, right hip',
    daysInAr: 30, isCleanClaim: true, paRequired: true, paObtained: true, paNumber: 'PA-2026-1201', denial: null
  },
  {
    claimId: 'CLM-2026-0013', patientId: 'PAT-1013', providerName: 'Dr. Susan Taylor', specialty: 'Rheumatology',
    payerId: 'PAY-002', payerName: 'UnitedHealthcare', departmentName: 'Rheumatology', serviceDate: '2026-09-14',
    submissionDate: '2026-09-16', totalCharge: 1600.00, totalAllowed: 1350.00, totalPaid: 1350.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'M05.79', diagnosisDescription: 'Rheumatoid arthritis with rheumatoid factor',
    daysInAr: 11, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0014', patientId: 'PAT-1014', providerName: 'Dr. Richard Martinez', specialty: 'Urology',
    payerId: 'PAY-003', payerName: 'Blue Cross Blue Shield', departmentName: 'Urology', serviceDate: '2026-08-28',
    submissionDate: '2026-08-30', totalCharge: 18500.00, totalAllowed: 15000.00, totalPaid: 0,
    status: 'denied', claimType: 'Institutional', primaryIcd10: 'N40.1', diagnosisDescription: 'Benign prostatic hyperplasia with lower urinary tract symptoms',
    daysInAr: 72, isCleanClaim: false, paRequired: true, paObtained: true, paNumber: 'PA-2026-1401',
    denial: { denialId: 'DEN-004', rootCauseCategory: 'Billing', carcCode: '4', carcDescription: 'The procedure code is inconsistent with the modifier used', rarcCode: 'N519', rarcDescription: 'Invalid modifier', denialAmount: 18500.00, workflowFailurePoint: 'Billing', isPreventable: true, denialReasonText: 'Modifier used does not match procedure code for facility billing' }
  },
  {
    claimId: 'CLM-2026-0015', patientId: 'PAT-1015', providerName: 'Dr. Nancy Clark', specialty: 'Psychiatry',
    payerId: 'PAY-004', payerName: 'Cigna', departmentName: 'Behavioral Health', serviceDate: '2026-09-19',
    submissionDate: '2026-09-21', totalCharge: 350.00, totalAllowed: 300.00, totalPaid: 300.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'F33.1', diagnosisDescription: 'Major depressive disorder, recurrent, moderate',
    daysInAr: 9, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0016', patientId: 'PAT-1016', providerName: 'Dr. Steven Harris', specialty: 'General Surgery',
    payerId: 'PAY-006', payerName: 'Humana', departmentName: 'Surgery', serviceDate: '2026-09-05',
    submissionDate: '2026-09-08', totalCharge: 42000.00, totalAllowed: 35000.00, totalPaid: 35000.00,
    status: 'approved', claimType: 'Institutional', primaryIcd10: 'K80.20', diagnosisDescription: 'Calculus of gallbladder without cholecystitis',
    daysInAr: 28, isCleanClaim: true, paRequired: true, paObtained: true, paNumber: 'PA-2026-1601', denial: null
  },
  {
    claimId: 'CLM-2026-0017', patientId: 'PAT-1017', providerName: 'Dr. Karen White', specialty: 'Obstetrics',
    payerId: 'PAY-005', payerName: 'Medicare', departmentName: 'OB/GYN', serviceDate: '2026-09-10',
    submissionDate: '2026-09-12', totalCharge: 15000.00, totalAllowed: 12500.00, totalPaid: 0,
    status: 'pending', claimType: 'Institutional', primaryIcd10: 'O80', diagnosisDescription: 'Encounter for full-term uncomplicated delivery',
    daysInAr: 55, isCleanClaim: false, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0018', patientId: 'PAT-1018', providerName: 'Dr. Charles Jackson', specialty: 'Ophthalmology',
    payerId: 'PAY-001', payerName: 'Aetna', departmentName: 'Ophthalmology', serviceDate: '2026-09-22',
    submissionDate: '2026-09-24', totalCharge: 5200.00, totalAllowed: 4400.00, totalPaid: 4400.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'H25.11', diagnosisDescription: 'Age-related nuclear cataract, right eye',
    daysInAr: 7, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0019', patientId: 'PAT-1019', providerName: 'Dr. Elizabeth King', specialty: 'Nephrology',
    payerId: 'PAY-002', payerName: 'UnitedHealthcare', departmentName: 'Nephrology', serviceDate: '2026-09-16',
    submissionDate: '2026-09-18', totalCharge: 9800.00, totalAllowed: 8200.00, totalPaid: 0,
    status: 'denied', claimType: 'Professional', primaryIcd10: 'N18.6', diagnosisDescription: 'End stage renal disease',
    daysInAr: 85, isCleanClaim: false, paRequired: true, paObtained: false, paNumber: null,
    denial: { denialId: 'DEN-005', rootCauseCategory: 'Eligibility', carcCode: '27', carcDescription: 'Expenses incurred after coverage terminated', rarcCode: 'N30', rarcDescription: 'Patient not eligible', denialAmount: 9800.00, workflowFailurePoint: 'Registration', isPreventable: true, denialReasonText: 'Patient eligibility was not verified prior to service' }
  },
  {
    claimId: 'CLM-2026-0020', patientId: 'PAT-1020', providerName: 'Dr. George Wright', specialty: 'Hematology',
    payerId: 'PAY-003', payerName: 'Blue Cross Blue Shield', departmentName: 'Hematology/Oncology', serviceDate: '2026-09-08',
    submissionDate: '2026-09-10', totalCharge: 22000.00, totalAllowed: 18500.00, totalPaid: 18500.00,
    status: 'approved', claimType: 'Institutional', primaryIcd10: 'C91.10', diagnosisDescription: 'Chronic lymphocytic leukemia of B-cell type not having achieved remission',
    daysInAr: 22, isCleanClaim: true, paRequired: true, paObtained: true, paNumber: 'PA-2026-2001', denial: null
  },
  {
    claimId: 'CLM-2026-0021', patientId: 'PAT-1021', providerName: 'Dr. Barbara Allen', specialty: 'Allergy/Immunology',
    payerId: 'PAY-004', payerName: 'Cigna', departmentName: 'Allergy', serviceDate: '2026-09-25',
    submissionDate: '2026-09-27', totalCharge: 680.00, totalAllowed: 560.00, totalPaid: 560.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'J30.1', diagnosisDescription: 'Allergic rhinitis due to pollen',
    daysInAr: 5, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0022', patientId: 'PAT-1022', providerName: 'Dr. Donald Scott', specialty: 'Cardiology',
    payerId: 'PAY-006', payerName: 'Humana', departmentName: 'Cardiology', serviceDate: '2026-09-02',
    submissionDate: '2026-09-05', totalCharge: 28000.00, totalAllowed: 23000.00, totalPaid: 0,
    status: 'denied', claimType: 'Institutional', primaryIcd10: 'I48.91', diagnosisDescription: 'Unspecified atrial fibrillation',
    daysInAr: 62, isCleanClaim: false, paRequired: true, paObtained: true, paNumber: 'PA-2026-2201',
    denial: { denialId: 'DEN-006', rootCauseCategory: 'Coding', carcCode: '11', carcDescription: 'Diagnosis inconsistent with procedure', rarcCode: 'N657', rarcDescription: 'Diagnosis/procedure code mismatch', denialAmount: 28000.00, workflowFailurePoint: 'Coding', isPreventable: true, denialReasonText: 'Primary diagnosis code does not support medical necessity for the procedure performed' }
  },
  {
    claimId: 'CLM-2026-0023', patientId: 'PAT-1023', providerName: 'Dr. Sandra Green', specialty: 'Physical Medicine',
    payerId: 'PAY-005', payerName: 'Medicare', departmentName: 'Rehabilitation', serviceDate: '2026-09-20',
    submissionDate: '2026-09-22', totalCharge: 1800.00, totalAllowed: 1500.00, totalPaid: 1500.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'M54.5', diagnosisDescription: 'Low back pain',
    daysInAr: 10, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0024', patientId: 'PAT-1024', providerName: 'Dr. Paul Adams', specialty: 'ENT',
    payerId: 'PAY-001', payerName: 'Aetna', departmentName: 'Otolaryngology', serviceDate: '2026-09-15',
    submissionDate: '2026-09-17', totalCharge: 7200.00, totalAllowed: 6000.00, totalPaid: 6000.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'J32.0', diagnosisDescription: 'Chronic maxillary sinusitis',
    daysInAr: 13, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0025', patientId: 'PAT-1025', providerName: 'Dr. Laura Nelson', specialty: 'Pediatrics',
    payerId: 'PAY-002', payerName: 'UnitedHealthcare', departmentName: 'Pediatrics', serviceDate: '2026-09-18',
    submissionDate: '2026-09-20', totalCharge: 320.00, totalAllowed: 280.00, totalPaid: 280.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'J06.9', diagnosisDescription: 'Acute upper respiratory infection, unspecified',
    daysInAr: 7, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0026', patientId: 'PAT-1026', providerName: 'Dr. Mark Campbell', specialty: 'Neurosurgery',
    payerId: 'PAY-003', payerName: 'Blue Cross Blue Shield', departmentName: 'Neurosurgery', serviceDate: '2026-08-20',
    submissionDate: '2026-08-22', totalCharge: 125000.00, totalAllowed: 105000.00, totalPaid: 0,
    status: 'pending', claimType: 'Institutional', primaryIcd10: 'G91.1', diagnosisDescription: 'Obstructive hydrocephalus',
    daysInAr: 90, isCleanClaim: false, paRequired: true, paObtained: true, paNumber: 'PA-2026-2601', denial: null
  },
  {
    claimId: 'CLM-2026-0027', patientId: 'PAT-1027', providerName: 'Dr. Dorothy Baker', specialty: 'Internal Medicine',
    payerId: 'PAY-004', payerName: 'Cigna', departmentName: 'Internal Medicine', serviceDate: '2026-09-24',
    submissionDate: '2026-09-26', totalCharge: 950.00, totalAllowed: 800.00, totalPaid: 800.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'I10', diagnosisDescription: 'Essential (primary) hypertension',
    daysInAr: 4, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0028', patientId: 'PAT-1028', providerName: 'Dr. Joseph Hill', specialty: 'Oncology',
    payerId: 'PAY-006', payerName: 'Humana', departmentName: 'Oncology', serviceDate: '2026-09-12',
    submissionDate: '2026-09-15', totalCharge: 68000.00, totalAllowed: 58000.00, totalPaid: 0,
    status: 'denied', claimType: 'Institutional', primaryIcd10: 'C50.911', diagnosisDescription: 'Malignant neoplasm of unspecified site of right female breast',
    daysInAr: 48, isCleanClaim: false, paRequired: true, paObtained: false, paNumber: null,
    denial: { denialId: 'DEN-007', rootCauseCategory: 'Authorization', carcCode: '197', carcDescription: 'Precertification/authorization/notification absent', rarcCode: 'N386', rarcDescription: 'Missing authorization', denialAmount: 68000.00, workflowFailurePoint: 'Pre-Service', isPreventable: true, denialReasonText: 'Chemotherapy regimen requires prior authorization which was not obtained' }
  },
  {
    claimId: 'CLM-2026-0029', patientId: 'PAT-1029', providerName: 'Dr. Helen Rivera', specialty: 'Gastroenterology',
    payerId: 'PAY-005', payerName: 'Medicare', departmentName: 'Gastroenterology', serviceDate: '2026-09-06',
    submissionDate: '2026-09-09', totalCharge: 3500.00, totalAllowed: 2900.00, totalPaid: 2900.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'K21.0', diagnosisDescription: 'Gastro-esophageal reflux disease with esophagitis',
    daysInAr: 16, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0030', patientId: 'PAT-1030', providerName: 'Dr. Frank Cooper', specialty: 'Cardiology',
    payerId: 'PAY-001', payerName: 'Aetna', departmentName: 'Cardiology', serviceDate: '2026-09-11',
    submissionDate: '2026-09-14', totalCharge: 15800.00, totalAllowed: 13200.00, totalPaid: 13200.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'I50.9', diagnosisDescription: 'Heart failure, unspecified',
    daysInAr: 18, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0031', patientId: 'PAT-1031', providerName: 'Dr. Carol Phillips', specialty: 'Dermatology',
    payerId: 'PAY-002', payerName: 'UnitedHealthcare', departmentName: 'Dermatology', serviceDate: '2026-09-23',
    submissionDate: '2026-09-25', totalCharge: 2800.00, totalAllowed: 2300.00, totalPaid: 0,
    status: 'in_review', claimType: 'Professional', primaryIcd10: 'C43.9', diagnosisDescription: 'Malignant melanoma of skin, unspecified',
    daysInAr: 25, isCleanClaim: false, paRequired: true, paObtained: true, paNumber: 'PA-2026-3101', denial: null
  },
  {
    claimId: 'CLM-2026-0032', patientId: 'PAT-1032', providerName: 'Dr. Raymond Evans', specialty: 'Pulmonology',
    payerId: 'PAY-003', payerName: 'Blue Cross Blue Shield', departmentName: 'Pulmonology', serviceDate: '2026-09-09',
    submissionDate: '2026-09-11', totalCharge: 4100.00, totalAllowed: 3400.00, totalPaid: 0,
    status: 'denied', claimType: 'Professional', primaryIcd10: 'J18.9', diagnosisDescription: 'Pneumonia, unspecified organism',
    daysInAr: 78, isCleanClaim: false, paRequired: false, paObtained: false, paNumber: null,
    denial: { denialId: 'DEN-008', rootCauseCategory: 'Demographics', carcCode: '15', carcDescription: 'Missing subscriber/insured ID', rarcCode: 'N61', rarcDescription: 'Subscriber ID missing or invalid', denialAmount: 4100.00, workflowFailurePoint: 'Registration', isPreventable: true, denialReasonText: 'Subscriber identification number was missing from the claim' }
  },
  {
    claimId: 'CLM-2026-0033', patientId: 'PAT-1033', providerName: 'Dr. Janet Reed', specialty: 'Endocrinology',
    payerId: 'PAY-004', payerName: 'Cigna', departmentName: 'Endocrinology', serviceDate: '2026-09-17',
    submissionDate: '2026-09-19', totalCharge: 1100.00, totalAllowed: 920.00, totalPaid: 920.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'E03.9', diagnosisDescription: 'Hypothyroidism, unspecified',
    daysInAr: 8, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0034', patientId: 'PAT-1034', providerName: 'Dr. Wayne Morris', specialty: 'Vascular Surgery',
    payerId: 'PAY-006', payerName: 'Humana', departmentName: 'Surgery', serviceDate: '2026-08-15',
    submissionDate: '2026-08-18', totalCharge: 52000.00, totalAllowed: 44000.00, totalPaid: 44000.00,
    status: 'approved', claimType: 'Institutional', primaryIcd10: 'I71.4', diagnosisDescription: 'Abdominal aortic aneurysm, without rupture',
    daysInAr: 38, isCleanClaim: true, paRequired: true, paObtained: true, paNumber: 'PA-2026-3401', denial: null
  },
  {
    claimId: 'CLM-2026-0035', patientId: 'PAT-1035', providerName: 'Dr. Christine Rogers', specialty: 'Internal Medicine',
    payerId: 'PAY-005', payerName: 'Medicare', departmentName: 'Internal Medicine', serviceDate: '2026-09-21',
    submissionDate: '2026-09-23', totalCharge: 780.00, totalAllowed: 650.00, totalPaid: 650.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'J20.9', diagnosisDescription: 'Acute bronchitis, unspecified',
    daysInAr: 6, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0036', patientId: 'PAT-1036', providerName: 'Dr. Peter Stewart', specialty: 'Orthopedics',
    payerId: 'PAY-001', payerName: 'Aetna', departmentName: 'Orthopedics', serviceDate: '2026-09-03',
    submissionDate: '2026-09-06', totalCharge: 28500.00, totalAllowed: 24000.00, totalPaid: 0,
    status: 'denied', claimType: 'Institutional', primaryIcd10: 'M23.611', diagnosisDescription: 'Other spontaneous disruption of anterior cruciate ligament of right knee',
    daysInAr: 58, isCleanClaim: false, paRequired: true, paObtained: false, paNumber: null,
    denial: { denialId: 'DEN-009', rootCauseCategory: 'Authorization', carcCode: '197', carcDescription: 'Precertification/authorization/notification absent', rarcCode: 'N386', rarcDescription: 'Missing authorization', denialAmount: 28500.00, workflowFailurePoint: 'Pre-Service', isPreventable: true, denialReasonText: 'Prior authorization required for ACL reconstruction was not obtained' }
  },
  {
    claimId: 'CLM-2026-0037', patientId: 'PAT-1037', providerName: 'Dr. Deborah Sanchez', specialty: 'Psychiatry',
    payerId: 'PAY-002', payerName: 'UnitedHealthcare', departmentName: 'Behavioral Health', serviceDate: '2026-09-19',
    submissionDate: '2026-09-21', totalCharge: 420.00, totalAllowed: 360.00, totalPaid: 360.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'F41.1', diagnosisDescription: 'Generalized anxiety disorder',
    daysInAr: 9, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0038', patientId: 'PAT-1038', providerName: 'Dr. Gregory Price', specialty: 'Neurology',
    payerId: 'PAY-003', payerName: 'Blue Cross Blue Shield', departmentName: 'Neurology', serviceDate: '2026-09-14',
    submissionDate: '2026-09-16', totalCharge: 7500.00, totalAllowed: 6200.00, totalPaid: 6200.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'G40.909', diagnosisDescription: 'Epilepsy, unspecified, not intractable',
    daysInAr: 14, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0039', patientId: 'PAT-1039', providerName: 'Dr. Stephanie Ward', specialty: 'OB/GYN',
    payerId: 'PAY-004', payerName: 'Cigna', departmentName: 'OB/GYN', serviceDate: '2026-09-07',
    submissionDate: '2026-09-10', totalCharge: 2400.00, totalAllowed: 2000.00, totalPaid: 0,
    status: 'pending', claimType: 'Professional', primaryIcd10: 'N92.0', diagnosisDescription: 'Excessive and frequent menstruation with regular cycle',
    daysInAr: 42, isCleanClaim: false, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0040', patientId: 'PAT-1040', providerName: 'Dr. Bryan Cox', specialty: 'Infectious Disease',
    payerId: 'PAY-006', payerName: 'Humana', departmentName: 'Internal Medicine', serviceDate: '2026-09-13',
    submissionDate: '2026-09-15', totalCharge: 3800.00, totalAllowed: 3200.00, totalPaid: 3200.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'A41.9', diagnosisDescription: 'Sepsis, unspecified organism',
    daysInAr: 16, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0041', patientId: 'PAT-1041', providerName: 'Dr. Alice Turner', specialty: 'Cardiology',
    payerId: 'PAY-005', payerName: 'Medicare', departmentName: 'Cardiology', serviceDate: '2026-09-04',
    submissionDate: '2026-09-07', totalCharge: 19500.00, totalAllowed: 16000.00, totalPaid: 0,
    status: 'denied', claimType: 'Professional', primaryIcd10: '', diagnosisDescription: '',
    daysInAr: 65, isCleanClaim: false, paRequired: true, paObtained: false, paNumber: null,
    denial: { denialId: 'DEN-010', rootCauseCategory: 'Coding', carcCode: '16', carcDescription: 'Claim/service lacks information needed for adjudication', rarcCode: 'M76', rarcDescription: 'Missing diagnosis code', denialAmount: 19500.00, workflowFailurePoint: 'Coding', isPreventable: true, denialReasonText: 'Claim submitted without primary diagnosis code and missing prior authorization' }
  },
  {
    claimId: 'CLM-2026-0042', patientId: 'PAT-1042', providerName: 'Dr. Harold Brooks', specialty: 'Gastroenterology',
    payerId: 'PAY-001', payerName: 'Aetna', departmentName: 'Gastroenterology', serviceDate: '2026-09-16',
    submissionDate: '2026-09-18', totalCharge: 4800.00, totalAllowed: 4000.00, totalPaid: 4000.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'K57.30', diagnosisDescription: 'Diverticulosis of large intestine without perforation or abscess',
    daysInAr: 12, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0043', patientId: 'PAT-1043', providerName: 'Dr. Virginia Coleman', specialty: 'Rheumatology',
    payerId: 'PAY-002', payerName: 'UnitedHealthcare', departmentName: 'Rheumatology', serviceDate: '2026-09-21',
    submissionDate: '2026-09-23', totalCharge: 2200.00, totalAllowed: 1850.00, totalPaid: 1850.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'M32.9', diagnosisDescription: 'Systemic lupus erythematosus, unspecified',
    daysInAr: 7, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0044', patientId: 'PAT-1044', providerName: 'Dr. Eugene Howard', specialty: 'Emergency Medicine',
    payerId: 'PAY-003', payerName: 'Blue Cross Blue Shield', departmentName: 'Emergency', serviceDate: '2026-09-26',
    submissionDate: '2026-09-28', totalCharge: 12000.00, totalAllowed: 10000.00, totalPaid: 0,
    status: 'in_review', claimType: 'Institutional', primaryIcd10: 'I63.9', diagnosisDescription: 'Cerebral infarction, unspecified',
    daysInAr: 20, isCleanClaim: false, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0045', patientId: 'PAT-1045', providerName: 'Dr. Marilyn Barnes', specialty: 'Nephrology',
    payerId: 'PAY-004', payerName: 'Cigna', departmentName: 'Nephrology', serviceDate: '2026-09-10',
    submissionDate: '2026-09-12', totalCharge: 8400.00, totalAllowed: 7000.00, totalPaid: 7000.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'N17.9', diagnosisDescription: 'Acute kidney failure, unspecified',
    daysInAr: 18, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0046', patientId: 'PAT-1046', providerName: 'Dr. Russell Peterson', specialty: 'General Surgery',
    payerId: 'PAY-006', payerName: 'Humana', departmentName: 'Surgery', serviceDate: '2026-08-28',
    submissionDate: '2026-08-30', totalCharge: 34000.00, totalAllowed: 28000.00, totalPaid: 0,
    status: 'denied', claimType: 'Institutional', primaryIcd10: 'K35.80', diagnosisDescription: 'Unspecified acute appendicitis',
    daysInAr: 75, isCleanClaim: false, paRequired: false, paObtained: false, paNumber: null,
    denial: { denialId: 'DEN-011', rootCauseCategory: 'Billing', carcCode: '97', carcDescription: 'The benefit for this service is included in the payment/allowance for another service/procedure', rarcCode: 'N362', rarcDescription: 'Bundled service', denialAmount: 34000.00, workflowFailurePoint: 'Billing', isPreventable: true, denialReasonText: 'Service was bundled with another procedure and should not have been billed separately' }
  },
  {
    claimId: 'CLM-2026-0047', patientId: 'PAT-1047', providerName: 'Dr. Cynthia Foster', specialty: 'Ophthalmology',
    payerId: 'PAY-005', payerName: 'Medicare', departmentName: 'Ophthalmology', serviceDate: '2026-09-18',
    submissionDate: '2026-09-20', totalCharge: 6100.00, totalAllowed: 5200.00, totalPaid: 5200.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'H40.11', diagnosisDescription: 'Primary open-angle glaucoma, right eye',
    daysInAr: 10, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0048', patientId: 'PAT-1048', providerName: 'Dr. Jack Simmons', specialty: 'Urology',
    payerId: 'PAY-001', payerName: 'Aetna', departmentName: 'Urology', serviceDate: '2026-09-08',
    submissionDate: '2026-09-10', totalCharge: 16500.00, totalAllowed: 13800.00, totalPaid: 13800.00,
    status: 'approved', claimType: 'Institutional', primaryIcd10: 'N20.0', diagnosisDescription: 'Calculus of kidney',
    daysInAr: 22, isCleanClaim: true, paRequired: true, paObtained: true, paNumber: 'PA-2026-4801', denial: null
  },
  {
    claimId: 'CLM-2026-0049', patientId: 'PAT-1049', providerName: 'Dr. Diane Perry', specialty: 'Pulmonology',
    payerId: 'PAY-002', payerName: 'UnitedHealthcare', departmentName: 'Pulmonology', serviceDate: '2026-09-15',
    submissionDate: '2026-09-17', totalCharge: 5600.00, totalAllowed: 4700.00, totalPaid: 0,
    status: 'denied', claimType: 'Professional', primaryIcd10: 'J96.00', diagnosisDescription: 'Acute respiratory failure, unspecified whether with hypoxia or hypercapnia',
    daysInAr: 55, isCleanClaim: false, paRequired: true, paObtained: false, paNumber: null,
    denial: { denialId: 'DEN-012', rootCauseCategory: 'Authorization', carcCode: '197', carcDescription: 'Precertification/authorization/notification absent', rarcCode: 'N386', rarcDescription: 'Missing authorization', denialAmount: 5600.00, workflowFailurePoint: 'Pre-Service', isPreventable: true, denialReasonText: 'Treatment requires prior authorization per payer policy' }
  },
  {
    claimId: 'CLM-2026-0050', patientId: 'PAT-1050', providerName: 'Dr. Terry Long', specialty: 'Internal Medicine',
    payerId: 'PAY-003', payerName: 'Blue Cross Blue Shield', departmentName: 'Internal Medicine', serviceDate: '2026-09-24',
    submissionDate: '2026-09-26', totalCharge: 650.00, totalAllowed: 540.00, totalPaid: 540.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'R05.9', diagnosisDescription: 'Cough, unspecified',
    daysInAr: 4, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0051', patientId: 'PAT-1051', providerName: 'Dr. Ruth Hughes', specialty: 'Cardiology',
    payerId: 'PAY-004', payerName: 'Cigna', departmentName: 'Cardiology', serviceDate: '2026-09-06',
    submissionDate: '2026-09-09', totalCharge: 92000.00, totalAllowed: 78000.00, totalPaid: 78000.00,
    status: 'approved', claimType: 'Institutional', primaryIcd10: 'I25.10', diagnosisDescription: 'Atherosclerotic heart disease of native coronary artery',
    daysInAr: 32, isCleanClaim: true, paRequired: true, paObtained: true, paNumber: 'PA-2026-5101', denial: null
  },
  {
    claimId: 'CLM-2026-0052', patientId: 'PAT-1052', providerName: 'Dr. Phillip Gray', specialty: 'Hematology',
    payerId: 'PAY-006', payerName: 'Humana', departmentName: 'Hematology/Oncology', serviceDate: '2026-09-11',
    submissionDate: '2026-09-13', totalCharge: 18000.00, totalAllowed: 15200.00, totalPaid: 0,
    status: 'denied', claimType: 'Professional', primaryIcd10: 'D64.9', diagnosisDescription: 'Anemia, unspecified',
    daysInAr: 82, isCleanClaim: false, paRequired: false, paObtained: false, paNumber: null,
    denial: { denialId: 'DEN-013', rootCauseCategory: 'Coding', carcCode: '11', carcDescription: 'Diagnosis inconsistent with procedure', rarcCode: 'N657', rarcDescription: 'Diagnosis/procedure code mismatch', denialAmount: 18000.00, workflowFailurePoint: 'Coding', isPreventable: true, denialReasonText: 'Unspecified diagnosis code insufficient to support medical necessity for treatment' }
  },
  {
    claimId: 'CLM-2026-0053', patientId: 'PAT-1053', providerName: 'Dr. Sharon Watson', specialty: 'Dermatology',
    payerId: 'PAY-005', payerName: 'Medicare', departmentName: 'Dermatology', serviceDate: '2026-09-20',
    submissionDate: '2026-09-22', totalCharge: 1500.00, totalAllowed: 1250.00, totalPaid: 1250.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'L70.0', diagnosisDescription: 'Acne vulgaris',
    daysInAr: 8, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0054', patientId: 'PAT-1054', providerName: 'Dr. Albert Bell', specialty: 'Orthopedics',
    payerId: 'PAY-001', payerName: 'Aetna', departmentName: 'Orthopedics', serviceDate: '2026-09-13',
    submissionDate: '2026-09-15', totalCharge: 9200.00, totalAllowed: 7800.00, totalPaid: 7800.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'M75.10', diagnosisDescription: 'Rotator cuff tear or rupture, not specified as incomplete or complete',
    daysInAr: 15, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0055', patientId: 'PAT-1055', providerName: 'Dr. Judith Murphy', specialty: 'Oncology',
    payerId: 'PAY-002', payerName: 'UnitedHealthcare', departmentName: 'Oncology', serviceDate: '2026-09-02',
    submissionDate: '2026-09-05', totalCharge: 45000.00, totalAllowed: 38000.00, totalPaid: 0,
    status: 'pending', claimType: 'Institutional', primaryIcd10: 'C18.9', diagnosisDescription: 'Malignant neoplasm of colon, unspecified',
    daysInAr: 48, isCleanClaim: false, paRequired: true, paObtained: true, paNumber: 'PA-2026-5501', denial: null
  },
  {
    claimId: 'CLM-2026-0056', patientId: 'PAT-1056', providerName: 'Dr. Lawrence Richardson', specialty: 'Physical Medicine',
    payerId: 'PAY-003', payerName: 'Blue Cross Blue Shield', departmentName: 'Rehabilitation', serviceDate: '2026-09-17',
    submissionDate: '2026-09-19', totalCharge: 2100.00, totalAllowed: 1750.00, totalPaid: 1750.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'S83.511A', diagnosisDescription: 'Sprain of anterior cruciate ligament of right knee, initial encounter',
    daysInAr: 11, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0057', patientId: 'PAT-1057', providerName: 'Dr. Catherine Wood', specialty: 'Allergy/Immunology',
    payerId: 'PAY-004', payerName: 'Cigna', departmentName: 'Allergy', serviceDate: '2026-09-22',
    submissionDate: '2026-09-24', totalCharge: 920.00, totalAllowed: 780.00, totalPaid: 780.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'T78.40XA', diagnosisDescription: 'Allergy, unspecified, initial encounter',
    daysInAr: 6, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0058', patientId: 'PAT-1058', providerName: 'Dr. Howard James', specialty: 'Neurosurgery',
    payerId: 'PAY-006', payerName: 'Humana', departmentName: 'Neurosurgery', serviceDate: '2026-08-22',
    submissionDate: '2026-08-25', totalCharge: 88000.00, totalAllowed: 74000.00, totalPaid: 0,
    status: 'denied', claimType: 'Institutional', primaryIcd10: 'M50.20', diagnosisDescription: 'Other cervical disc displacement, unspecified cervical region',
    daysInAr: 95, isCleanClaim: false, paRequired: true, paObtained: true, paNumber: 'PA-2026-5801',
    denial: { denialId: 'DEN-014', rootCauseCategory: 'Billing', carcCode: '4', carcDescription: 'The procedure code is inconsistent with the modifier used', rarcCode: 'N519', rarcDescription: 'Invalid modifier', denialAmount: 88000.00, workflowFailurePoint: 'Billing', isPreventable: true, denialReasonText: 'Incorrect modifier used on surgical procedure code' }
  },
  {
    claimId: 'CLM-2026-0059', patientId: 'PAT-1059', providerName: 'Dr. Teresa Sanders', specialty: 'Internal Medicine',
    payerId: 'PAY-005', payerName: 'Medicare', departmentName: 'Internal Medicine', serviceDate: '2026-09-25',
    submissionDate: '2026-09-27', totalCharge: 480.00, totalAllowed: 400.00, totalPaid: 400.00,
    status: 'approved', claimType: 'Professional', primaryIcd10: 'K21.9', diagnosisDescription: 'Gastro-esophageal reflux disease without esophagitis',
    daysInAr: 3, isCleanClaim: true, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
  {
    claimId: 'CLM-2026-0060', patientId: 'PAT-1060', providerName: 'Dr. Roy Patterson', specialty: 'Emergency Medicine',
    payerId: 'PAY-001', payerName: 'Aetna', departmentName: 'Emergency', serviceDate: '2026-09-27',
    submissionDate: '2026-09-29', totalCharge: 15200.00, totalAllowed: 12800.00, totalPaid: 0,
    status: 'in_review', claimType: 'Institutional', primaryIcd10: 'R07.9', diagnosisDescription: 'Chest pain, unspecified',
    daysInAr: 18, isCleanClaim: false, paRequired: false, paObtained: false, paNumber: null, denial: null
  },
]
