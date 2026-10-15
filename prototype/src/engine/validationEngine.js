function evaluateCondition(claim, condition) {
  const { field, operator, value } = condition
  const claimValue = claim[field]

  switch (operator) {
    case 'isEmpty':
      return claimValue === null || claimValue === undefined || claimValue === ''
    case 'isNotEmpty':
      return claimValue !== null && claimValue !== undefined && claimValue !== ''
    case 'equals':
      return String(claimValue) === String(value)
    case 'notEquals':
      return String(claimValue) !== String(value)
    case 'greaterThan':
      return Number(claimValue) > Number(value)
    case 'lessThan':
      return Number(claimValue) < Number(value)
    case 'contains':
      return String(claimValue || '').toLowerCase().includes(String(value).toLowerCase())
    default:
      return false
  }
}

function matchesScope(claim, scope) {
  if (!scope || scope.type === 'all') return true
  if (scope.type === 'payer') return claim.payerName === scope.value
  if (scope.type === 'claimType') return claim.claimType === scope.value
  if (scope.type === 'department') return claim.departmentName === scope.value
  return true
}

function calculateRiskScore(claim, failures) {
  let score = 0

  // Base score from failures
  const errorCount = failures.filter(f => f.severity === 'error').length
  const warningCount = failures.filter(f => f.severity === 'warning').length
  score += errorCount * 25
  score += warningCount * 10

  // Denial history
  if (claim.denial) {
    score += 20
    if (claim.denial.isPreventable) score += 5
  }

  // Days in AR factor
  if (claim.daysInAr > 90) score += 15
  else if (claim.daysInAr > 60) score += 10
  else if (claim.daysInAr > 30) score += 5

  // PA required but not obtained
  if (claim.paRequired && !claim.paObtained) score += 15

  // Missing diagnosis
  if (!claim.primaryIcd10 || claim.primaryIcd10 === '') score += 10

  // Not a clean claim
  if (!claim.isCleanClaim) score += 5

  return Math.min(score, 100)
}

export function validateClaims(claims, rules) {
  const activeRules = rules.filter(r => r.status === 'active')

  return claims.map(claim => {
    const failures = []

    for (const rule of activeRules) {
      if (!matchesScope(claim, rule.scope)) continue

      let ruleTriggered = false
      if (rule.conditionLogic === 'OR') {
        ruleTriggered = rule.conditions.some(cond => evaluateCondition(claim, cond))
      } else {
        ruleTriggered = rule.conditions.every(cond => evaluateCondition(claim, cond))
      }

      if (ruleTriggered) {
        failures.push({
          ruleId: rule.id,
          ruleName: rule.name,
          severity: rule.severity,
          category: rule.category,
          message: rule.description,
          recommendedAction: rule.recommendedAction,
        })
      }
    }

    const riskScore = calculateRiskScore(claim, failures)

    let status = 'pass'
    const hasError = failures.some(f => f.severity === 'error')
    const hasWarning = failures.some(f => f.severity === 'warning')

    if (hasError && riskScore >= 60) {
      status = 'aifix'
    } else if (hasError) {
      status = 'error'
    } else if (hasWarning) {
      status = 'warning'
    }

    return {
      claimId: claim.claimId,
      status,
      failures,
      riskScore,
    }
  })
}

export function testRule(claims, rule) {
  const matched = []
  const unaffected = []

  for (const claim of claims) {
    if (!matchesScope(claim, rule.scope)) {
      unaffected.push(claim.claimId)
      continue
    }

    let ruleTriggered = false
    if (rule.conditionLogic === 'OR') {
      ruleTriggered = rule.conditions.some(cond => evaluateCondition(claim, cond))
    } else {
      ruleTriggered = rule.conditions.every(cond => evaluateCondition(claim, cond))
    }

    if (ruleTriggered) {
      matched.push(claim.claimId)
    } else {
      unaffected.push(claim.claimId)
    }
  }

  return { matched, unaffected, total: claims.length }
}
