/** The file's bytes as base64, for JSON uploads. */
export function readBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '')
    reader.onerror = () => reject(new Error('Could not read the file'))
    reader.readAsDataURL(file)
  })
}

/** "12 pages" for a PDF, "3 parts" for a text file. */
export function pageCount(document) {
  const unit = document.media_type === 'application/pdf' ? 'page' : 'part'
  return `${document.pages} ${unit}${document.pages === 1 ? '' : 's'}`
}

/** Payers that can have documents: every one but self-pay. */
export const documentPayers = (payers) => Object.values(payers ?? {}).filter((payer) => payer.payer_type !== 'Self-Pay')
