import { navigate } from './router'

/** An internal link: a real <a href> (works without JavaScript, opens in a new tab) that
 * navigates in place on a plain click. */
export function Link({ href, onClick, ...props }) {
  const handle = (event) => {
    onClick?.(event)
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return
    }
    event.preventDefault()
    navigate(href)
  }
  return <a href={href} onClick={handle} {...props} />
}
