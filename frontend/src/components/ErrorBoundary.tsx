import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log exception for diagnostics without exposing sensitive user telemetry
    console.error("CanineSense ErrorBoundary caught an error:", error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    if (window.location.hash !== "#/") {
      window.location.hash = "#/";
    } else {
      window.location.reload();
    }
  };

  handleClearSession = () => {
    try {
      localStorage.removeItem("cs_token");
      localStorage.removeItem("cs_user");
    } catch {
      /* ignore */
    }
    this.setState({ hasError: false, error: null });
    window.location.hash = "#/";
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          style={{
            minHeight: "60vh",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "32px 16px",
            background: "var(--bg, #F7F2E8)",
            color: "var(--ink, #382820)",
            fontFamily: "var(--font-sans, Outfit, -apple-system, sans-serif)",
          }}
        >
          <div
            style={{
              maxWidth: 540,
              width: "100%",
              background: "#FFFFFF",
              border: "1px solid var(--line, #E5D9C3)",
              borderRadius: 14,
              padding: "28px 24px",
              boxShadow: "0 6px 20px rgba(56, 40, 32, 0.06)",
              textAlign: "left",
            }}
          >
            <div
              style={{
                display: "inline-block",
                padding: "4px 10px",
                borderRadius: 999,
                fontSize: "0.75rem",
                fontWeight: 600,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                background: "#FBEAEB",
                color: "var(--accent, #762F3D)",
                marginBottom: 12,
              }}
            >
              Safeguard Notice · Isolated Error
            </div>
            <h2
              style={{
                margin: "0 0 8px",
                fontSize: "1.25rem",
                fontFamily: "var(--font-serif, Fraunces, serif)",
                color: "var(--ink, #382820)",
              }}
            >
              {this.props.fallbackTitle || "Unable to display this view"}
            </h2>
            <p style={{ margin: "0 0 16px", fontSize: "0.9rem", color: "var(--ink-2, #6E6256)", lineHeight: 1.5 }}>
              A client-side rendering exception was isolated by CanineSense AI to prevent an application failure. Your
              session and data remain secure.
            </p>
            {this.state.error?.message && (
              <pre
                style={{
                  background: "#F7F2E8",
                  padding: "10px 12px",
                  borderRadius: 8,
                  fontSize: "0.78rem",
                  color: "#762F3D",
                  overflowX: "auto",
                  margin: "0 0 20px",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {this.state.error.message}
              </pre>
            )}
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <button
                type="button"
                onClick={this.handleReset}
                className="btn accent"
                style={{
                  background: "var(--accent, #762F3D)",
                  color: "#FFFFFF",
                  border: "none",
                  padding: "8px 16px",
                  borderRadius: 8,
                  fontSize: "0.85rem",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Return to Overview
              </button>
              <button
                type="button"
                onClick={this.handleClearSession}
                className="btn ghost"
                style={{
                  background: "transparent",
                  border: "1px solid var(--line, #E5D9C3)",
                  color: "var(--ink, #382820)",
                  padding: "8px 16px",
                  borderRadius: 8,
                  fontSize: "0.85rem",
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                Reset Session &amp; Reload
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
