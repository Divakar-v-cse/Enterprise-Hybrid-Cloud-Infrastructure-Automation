import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { Loading } from "./ui";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, initialising } = useAuth();
  const location = useLocation();

  if (initialising) {
    return <Loading label="Restoring session" />;
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}
