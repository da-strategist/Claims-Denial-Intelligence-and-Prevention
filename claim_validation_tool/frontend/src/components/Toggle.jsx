/** Accessible on/off switch. */
export default function Toggle({ checked, onChange, label, disabled = false }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-red-300 disabled:cursor-not-allowed disabled:opacity-50 ${checked ? 'bg-red-600' : 'bg-gray-300'}`}
    >
      <span
        className="inline-block h-4 w-4 rounded-full bg-white shadow transition-transform"
        style={{ transform: `translateX(${checked ? 18 : 2}px)` }}
      />
    </button>
  )
}
