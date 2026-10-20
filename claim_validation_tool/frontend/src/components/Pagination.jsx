const BUTTON_CLASS = 'btn-secondary btn-sm'

export default function Pagination({ page, pages, total, pageSize, onPageChange, disabled }) {
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1
  const last = Math.min(page * pageSize, total)

  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="text-sm text-gray-500">
        Showing {first.toLocaleString()}–{last.toLocaleString()} of {total.toLocaleString()}
      </div>
      <div className="flex items-center gap-2">
        <button
          className={BUTTON_CLASS}
          onClick={() => onPageChange(page - 1)}
          disabled={disabled || page <= 1}
        >
          Previous
        </button>
        <span className="text-sm text-gray-600">
          Page {page.toLocaleString()} of {Math.max(pages, 1).toLocaleString()}
        </span>
        <button
          className={BUTTON_CLASS}
          onClick={() => onPageChange(page + 1)}
          disabled={disabled || page >= pages}
        >
          Next
        </button>
      </div>
    </div>
  )
}
