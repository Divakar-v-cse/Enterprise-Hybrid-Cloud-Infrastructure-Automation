import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="empty" style={{ padding: 60 }}>
      <h1 style={{ fontSize: 22 }}>Page not found</h1>
      <p className="muted" style={{ marginTop: 8 }}>
        The view you requested does not exist.
      </p>
      <p style={{ marginTop: 16 }}>
        <Link to="/">Return to the overview</Link>
      </p>
    </div>
  );
}
