/** Page frame: one title, one line of context, and the page's actions on the right. */
export function Page({ children, wide = false, narrow = false }) {
  const width = wide ? 'max-w-[1600px]' : narrow ? 'max-w-3xl' : 'max-w-6xl'
  return (
    <div className={`mx-auto space-y-6 px-4 py-6 sm:px-8 sm:py-10 ${width}`}>
      {children}
    </div>
  )
}

export default function PageHeader({ title, subtitle, children }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-3xl font-semibold tracking-tight text-gray-900">{title}</h1>
        {subtitle && <p className="mt-1 text-[15px] text-gray-500">{subtitle}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </header>
  )
}

/** Inline problem message, e.g. "Could not load claims". */
export function Notice({ tone = 'error', children }) {
  const style = {
    error: 'bg-red-50 text-red-800',
    warning: 'bg-amber-50 text-amber-900',
    info: 'bg-accent-soft text-gray-800',
  }[tone]
  return (
    <div role={tone === 'error' ? 'alert' : 'status'} className={`rounded-xl px-4 py-3 text-sm ${style}`}>
      {children}
    </div>
  )
}
