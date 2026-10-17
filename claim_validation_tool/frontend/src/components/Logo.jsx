export default function Logo({ size = 'h-8 w-8 text-base' }) {
  return (
    <div
      aria-hidden="true"
      className={`flex shrink-0 items-center justify-center rounded-[10px] bg-gray-900 font-semibold text-white ${size}`}
    >
      C
    </div>
  )
}
