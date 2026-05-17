import React from "react";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("InfinityGuard UI error", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <main className="grid min-h-screen place-items-center bg-panel px-4">
          <section className="max-w-xl rounded-lg border border-coral/30 bg-white p-6 shadow-soft">
            <h1 className="text-xl font-semibold text-coral">InfinityGuard UI failed to render</h1>
            <p className="mt-3 text-sm text-steel">The frontend loaded, but React hit a runtime error.</p>
            <pre className="mt-4 overflow-auto rounded-md bg-ink p-4 text-sm text-white">{String(this.state.error?.message || this.state.error)}</pre>
          </section>
        </main>
      );
    }
    return this.props.children;
  }
}
