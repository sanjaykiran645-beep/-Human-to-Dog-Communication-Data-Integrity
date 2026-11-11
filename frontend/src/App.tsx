import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./Layout";
import { getToken } from "./api";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Analyze from "./pages/Analyze";
import Communicate from "./pages/Communicate";
import Dogs from "./pages/Dogs";
import History from "./pages/History";
import Analytics from "./pages/Analytics";
import Settings from "./pages/Settings";
import PrivacyPolicy from "./pages/PrivacyPolicy";
import TermsOfService from "./pages/TermsOfService";
import RefundPolicy from "./pages/RefundPolicy";
import CookiePolicy from "./pages/CookiePolicy";
import CookieSettings from "./pages/CookieSettings";
import Contact from "./pages/Contact";
import DataDeletion from "./pages/DataDeletion";
import CookieBanner from "./components/CookieBanner";

function Private({ children }: { children: ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Login />} />

        {/* Legal, Privacy & Compliance Public Routes */}
        <Route path="/privacy-policy" element={<PrivacyPolicy />} />
        <Route path="/terms-of-service" element={<TermsOfService />} />
        <Route path="/refund-policy" element={<RefundPolicy />} />
        <Route path="/cookie-policy" element={<CookiePolicy />} />
        <Route path="/cookie-settings" element={<CookieSettings />} />
        <Route path="/contact" element={<Contact />} />
        <Route path="/data-deletion" element={<DataDeletion />} />

        {/* Authenticated Workspace */}
        <Route
          path="/app"
          element={
            <Private>
              <Layout />
            </Private>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="analyze" element={<Analyze />} />
          <Route path="communicate" element={<Communicate />} />
          <Route path="dogs" element={<Dogs />} />
          <Route path="history" element={<History />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <CookieBanner />
    </>
  );
}
