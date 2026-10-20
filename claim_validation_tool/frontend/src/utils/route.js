// Hash routes may carry a query string: #/claims?search=CLM0120001

/** The route part of the hash, without its query: "#/claims". */
export const hashPath = (hash) => hash.split('?')[0]

/** Query parameters from the current hash. */
export const hashParams = () => new URLSearchParams(window.location.hash.split('?')[1] ?? '')

/** Link to a route with query parameters. */
export function routeHref(path, params) {
  const query = new URLSearchParams(params).toString()
  return query ? `${path}?${query}` : path
}
