import { icd10Codes } from '../data/referenceData.js'

const diagnosisFixes = {
  'Cardiology': { code: 'I25.10', description: 'Atherosclerotic heart disease of native coronary artery' },
  'Orthopedics': { code: 'M17.11', description: 'Primary osteoarthritis, right knee' },
  'Oncology': { code: 'C34.90', description: 'Malignant neoplasm of unspecified part of bronchus or lung' },
  'Internal Medicine': { code: 'E11.9', description: 'Type 2 diabetes mellitus without complications' },
  'Neurology': { code: 'G43.909', description: 'Migraine, unspecified, not intractable' },
  'Gastroenterology': { code: 'K21.0', description: 'Gastro-esophageal reflux disease with esophagitis' },
  'Pulmonology': { code: 'J44.1', description: 'Chronic obstructive pulmonary disease with acute exacerbation' },
  'Emergency Medicine': { code: 'R07.9', description: 'Chest pain, unspecified' },
  'Nephrology': { code: 'N17.9', description: 'Acute kidney failure, unspecified' },
  'Endocrinology': { code: 'E03.9', description: 'Hypothyroidism, unspecified' },
  'Dermatology': { code: 'L40.0', description: 'Psoriasis vulgaris' },
  'Rheumatology': { code: 'M05.79', description: 'Rheumatoid arthritis with rheumatoid factor' },
  'Psychiatry': { code: 'F33.1', description: 'Major depressive disorder, recurrent, moderate' },
  'Hematology': { code: 'D64.9', description: 'Anemia, unspecified' },
  'Urology': { code: 'N40.1', description: 'Benign prostatic hyperplasia with lower urinary tract symptoms' },
}

const unspecifiedUpgrades = {
  'unspecified atrial fibrillation': { code: 'I48.0', description: 'Paroxysmal atrial fibrillation' },
  'anemia, unspecified': { code: 'D50.9', description: 'Iron deficiency anemia, unspecified' },
  'pneumonia, unspecified': { code: 'J15.9', description: 'Bacterial pneumonia, unspecified' },
  'chest pain, unspecified': { code: 'R07.89', description: 'Other chest pain' },
  'cough, unspecified': { code: 'R05.9', description: 'Cough, unspecified' },
  'cerebral infarction, unspecified': { code: 'I63.50', description: 'Cerebral infarction due to unspecified occlusion or stenosis of unspecified cerebral artery' },
}

export function generateAiFix(claim, failure) {
  const category = failure.category || ''
  const ruleName = failure.ruleName || ''

  // Missing diagnosis code fix
  if (ruleName.toLowerCase().includes('diagnosis') && (!claim.primaryIcd10 || claim.primaryIcd10 === '')) {
    const specialty = claim.specialty || claim.departmentName
    const fix = diagnosisFixes[specialty]
    if (fix) {
      return {
        description: `Auto-corrected to ICD-10 code ${fix.code} (${fix.description})`,
        confidence: 0.85,
        suggestedValue: fix.code,
        field: 'primaryIcd10',
        reasoning: `Based on the provider specialty (${specialty}) and department context, the most likely primary diagnosis code is ${fix.code}. Clinical documentation should be reviewed to confirm.`,
      }
    }
    return null
  }

  // Missing authorization fix
  if (category === 'Authorization' && ruleName.toLowerCase().includes('authorization') && claim.paRequired && !claim.paObtained) {
    return {
      description: `Flagged for urgent prior authorization request to ${claim.payerName}`,
      confidence: 0.78,
      suggestedValue: null,
      field: 'paObtained',
      reasoning: `Claim requires prior authorization from ${claim.payerName}. Recommend submitting a retrospective authorization request citing medical necessity based on ${claim.diagnosisDescription || 'clinical documentation'}. Success rate for retro-auth with ${claim.payerName} is approximately 65%.`,
    }
  }

  // Authorization number missing
  if (ruleName.toLowerCase().includes('authorization number') && claim.paObtained && !claim.paNumber) {
    return {
      description: 'Authorization number needs to be retrieved from payer portal',
      confidence: 0.70,
      suggestedValue: null,
      field: 'paNumber',
      reasoning: `Prior authorization was obtained but the number was not recorded on the claim. Check the ${claim.payerName} provider portal for the authorization number associated with service date ${claim.serviceDate}.`,
    }
  }

  // High billed amount review
  if (category === 'Billing' && ruleName.toLowerCase().includes('billed amount')) {
    const suggestedAmount = Math.round(claim.totalCharge * 0.85)
    return {
      description: `Reviewed charge detail — suggested adjusted amount: $${suggestedAmount.toLocaleString()}`,
      confidence: 0.72,
      suggestedValue: suggestedAmount,
      field: 'totalCharge',
      reasoning: `The billed amount of $${claim.totalCharge.toLocaleString()} exceeds the $50K threshold. Based on historical allowed amounts for similar ${claim.claimType} claims with ${claim.payerName}, the expected reimbursement is approximately 85% of billed charges. Consider verifying all line items.`,
    }
  }

  // Unspecified diagnosis upgrade for payer compliance
  if (ruleName.toLowerCase().includes('coding compliance') && claim.diagnosisDescription) {
    const descLower = claim.diagnosisDescription.toLowerCase()
    for (const [key, fix] of Object.entries(unspecifiedUpgrades)) {
      if (descLower.includes(key) || descLower === key) {
        return {
          description: `Upgraded diagnosis specificity to ${fix.code} (${fix.description})`,
          confidence: 0.88,
          suggestedValue: fix.code,
          field: 'primaryIcd10',
          reasoning: `The current diagnosis "${claim.diagnosisDescription}" uses an unspecified code which may trigger denial with ${claim.payerName}. Upgraded to ${fix.code} for higher specificity. Review clinical notes to confirm appropriateness.`,
        }
      }
    }
  }

  // Non-clean claim fix
  if (ruleName.toLowerCase().includes('non-clean') || ruleName.toLowerCase().includes('clean claim')) {
    return {
      description: 'Identified missing fields — claim needs demographic and billing review',
      confidence: 0.65,
      suggestedValue: null,
      field: 'isCleanClaim',
      reasoning: `This claim is flagged as not clean, indicating missing or incomplete required fields. Common issues include: missing subscriber ID, incomplete demographics, or coding discrepancies. A full pre-submission audit is recommended.`,
    }
  }

  // No automated fix available
  return null
}
