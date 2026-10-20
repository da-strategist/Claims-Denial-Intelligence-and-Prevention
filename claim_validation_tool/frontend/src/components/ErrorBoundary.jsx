import { Component } from 'react'

/**
 * Keeps a crash on one page from blanking the whole app: the nav stays usable and the
 * page offers a reload. Also catches a lazily loaded page whose code failed to download.
 */
export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Page crashed', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div role="alert" className="m-6 max-w-xl rounded-xl border border-red-200 bg-white p-5 shadow-sm">
        <h1 className="text-lg font-semibold text-gray-900">Something went wrong on this page</h1>
        <p className="mt-1 text-sm text-gray-600">
          The rest of the app still works — pick another page above, or reload this one.
        </p>
        <p className="mt-3 rounded-lg bg-gray-50 px-3 py-2 font-mono text-xs text-gray-600">
          {this.state.error.message}
        </p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="mt-4 btn-primary"
        >
          Reload page
        </button>
      </div>
    )
  }
}
