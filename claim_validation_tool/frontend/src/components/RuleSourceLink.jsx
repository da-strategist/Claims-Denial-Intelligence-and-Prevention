import { payerDocumentFileUrl } from '../services/api'

/** "Source: Medicare provider manual, page 12", linking to the document. */
export default function RuleSourceLink({ source, className = '' }) {
  const page = source.page ? `, page ${source.page}` : ''
  return (
    <p className={`text-xs text-gray-500 ${className}`}>
      Source:{' '}
      <a className="font-medium text-accent hover:underline" href={payerDocumentFileUrl(source.document_id)} download>
        {source.document_title || source.document_id}
        {page}
      </a>
    </p>
  )
}
