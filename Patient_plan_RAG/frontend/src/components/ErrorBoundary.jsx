import React from "react";

/**
 * Catches render errors below it so one broken page doesn't blank the app.
 * Give it a `key` that changes on navigation to reset it between pages.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
    this.reset = this.reset.bind(this);
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("[ErrorBoundary]", error, info?.componentStack);
  }

  reset() {
    this.setState({ error: null });
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    if (this.props.fallback) return this.props.fallback({ error, reset: this.reset });

    return (
      <div role="alert" className="max-w-xl mx-auto mt-10 bg-white border border-red-200 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-red-700 mb-2">
          Something went wrong on this page
        </h2>
        <p className="text-sm text-gray-600 mb-4">
          The rest of the app still works. You can retry this page or go back
          to the dashboard.
        </p>
        {import.meta.env.DEV && (
          <pre className="text-xs bg-gray-50 border rounded p-2 mb-4 whitespace-pre-wrap text-gray-700">
            {String(error?.message || error)}
          </pre>
        )}
        <div className="flex gap-2">
          <button
            onClick={this.reset}
            className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700"
          >
            Try again
          </button>
          {this.props.onHome && (
            <button
              onClick={() => {
                this.reset();
                this.props.onHome();
              }}
              className="border px-4 py-1.5 rounded text-sm hover:bg-gray-50"
            >
              Go to Dashboard
            </button>
          )}
        </div>
      </div>
    );
  }
}
