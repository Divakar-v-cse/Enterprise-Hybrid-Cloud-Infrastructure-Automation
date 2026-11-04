import { BrowserRouter, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AuthProvider } from "./context/AuthContext";
import { AuditPage } from "./pages/AuditPage";
import { CompliancePage } from "./pages/CompliancePage";
import { DashboardPage } from "./pages/DashboardPage";
import { DeploymentsPage } from "./pages/DeploymentsPage";
import { DriftPage } from "./pages/DriftPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ResourcesPage } from "./pages/ResourcesPage";
import { ServersPage } from "./pages/ServersPage";
import { UsersPage } from "./pages/UsersPage";

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="/resources" element={<ResourcesPage />} />
            <Route path="/servers" element={<ServersPage />} />
            <Route path="/deployments" element={<DeploymentsPage />} />
            <Route path="/compliance" element={<CompliancePage />} />
            <Route path="/drift" element={<DriftPage />} />
            <Route path="/audit" element={<AuditPage />} />
            <Route path="/users" element={<UsersPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
