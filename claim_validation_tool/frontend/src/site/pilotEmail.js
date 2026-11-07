import { pilotContactEmail } from './content'

/** What the email says: the visitor sees and sends it from their own email app. */
export function pilotEmail(form) {
  const subject = `Pilot interest: ${form.organization}`
  const body = [
    `Name: ${form.name}`,
    `Work email: ${form.email}`,
    `Organization: ${form.organization}`,
    `Job title: ${form.title}`,
    `Organization type: ${form.orgType}`,
    '',
    form.message,
  ].join('\n')
  return `mailto:${pilotContactEmail()}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body.trim())}`
}
