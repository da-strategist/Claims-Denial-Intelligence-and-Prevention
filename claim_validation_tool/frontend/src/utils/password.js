// The server's policy, checked as they type so the reasons show before submitting
export function passwordProblems(password, confirm) {
  const problems = []
  if (password.length < 12) problems.push('At least 12 characters')
  if (password.toLowerCase() === password || password.toUpperCase() === password)
    problems.push('Upper- and lower-case letters')
  if (/^[a-zA-Z]*$/.test(password)) problems.push('A digit or symbol')
  if (confirm !== password) problems.push('Both passwords match')
  return problems
}
