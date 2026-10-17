// The assistant's answers are plain text with light Markdown and [S1]-style citations

const BULLET = /^\s*[-*•]\s+/
const NUMBERED = /^\s*\d+[.)]\s+/
const HEADING = /^\s*#{1,4}\s+/

/** Split an answer into blocks: { type: 'p' | 'h', text } or { type: 'ul' | 'ol', items }. */
export function answerBlocks(text) {
  const blocks = []
  const push = (type, line) => {
    const last = blocks.at(-1)
    if (last?.type === type) last.items.push(line)
    else blocks.push({ type, items: [line] })
  }
  for (const raw of text.split('\n')) {
    const line = raw.trimEnd()
    if (!line.trim()) {
      blocks.push({ type: 'break' })
    } else if (BULLET.test(line)) {
      push('ul', line.replace(BULLET, ''))
    } else if (NUMBERED.test(line)) {
      push('ol', line.replace(NUMBERED, ''))
    } else if (HEADING.test(line)) {
      blocks.push({ type: 'h', text: line.replace(HEADING, '') })
    } else {
      const last = blocks.at(-1)
      // Consecutive lines form one paragraph
      if (last?.type === 'p') last.text += ` ${line.trim()}`
      else blocks.push({ type: 'p', text: line.trim() })
    }
  }
  return blocks.filter((block) => block.type !== 'break')
}

const INLINE = /(\*\*[^*]+\*\*|\[S\d+(?:\s*[,;]\s*S\d+)*\])/

/** Inline pieces: { text }, { bold }, or { citations: ['S1', 'S2'] }. */
export function inlineSegments(text) {
  return text
    .split(INLINE)
    .filter(Boolean)
    .map((part) => {
      if (part.startsWith('**')) return { bold: part.slice(2, -2) }
      if (/^\[S\d/.test(part)) {
        return { citations: part.slice(1, -1).split(/[,;]/).map((label) => label.trim()) }
      }
      return { text: part }
    })
}
