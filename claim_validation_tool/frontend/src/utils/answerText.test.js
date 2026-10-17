import { describe, expect, it } from 'vitest'
import { answerBlocks, inlineSegments } from './answerText'

describe('answer text', () => {
  it('groups paragraphs, lists, and headings', () => {
    const text = [
      '## Answer',
      'CPT 93000 is bundled into the cath [S1].',
      'It can be billed with modifier 59.',
      '',
      '- Separate session required [S1]',
      '* Document the distinct indication',
      '1. Add modifier 59',
      '2. Resubmit',
    ].join('\n')
    expect(answerBlocks(text)).toEqual([
      { type: 'h', text: 'Answer' },
      { type: 'p', text: 'CPT 93000 is bundled into the cath [S1]. It can be billed with modifier 59.' },
      { type: 'ul', items: ['Separate session required [S1]', 'Document the distinct indication'] },
      { type: 'ol', items: ['Add modifier 59', 'Resubmit'] },
    ])
  })

  it('finds bold text and grouped citations', () => {
    expect(inlineSegments('**Not covered** for I10 [S2, S3]; see [S1].')).toEqual([
      { bold: 'Not covered' },
      { text: ' for I10 ' },
      { citations: ['S2', 'S3'] },
      { text: '; see ' },
      { citations: ['S1'] },
      { text: '.' },
    ])
  })
})
