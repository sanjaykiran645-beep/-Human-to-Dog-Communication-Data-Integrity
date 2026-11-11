import { useEffect } from "react";
import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
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
import NotFound from "./pages/NotFound";
import CookieBanner from "./components/CookieBanner";

function Private({ children }: { children: ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

const ROUTE_TITLES: Record<string, { title: string; desc: string }> = {
  "/": {
    title: "CanineSense AI · Bioacoustic Canine Intelligence",
    desc: "Acoustic intelligence and spectrogram analysis for canine vocalizations. Private, experimental, and scientifically grounded.",
  },
  "/login": {
    title: "Sign In · CanineSense AI Acoustic Lab",
    desc: "Access your private canine vocalization recordings, spectrograms, and bioacoustic telemetry.",
  },
  "/register": {
    title: "Create Account · CanineSense AI Acoustic Lab",
    desc: "Register a private bioacoustic workspace for canine vocalization analysis and reference synthesis.",
  },
  "/app": {
    title: "Dashboard · CanineSense AI Acoustic Lab",
    desc: "Overview of private canine recordings, acoustic corpus distribution, and dual-engine metrics.",
  },
  "/app/analyze": {
    title: "Engine A · Acoustic Vocalization Analysis · CanineSense AI",
    desc: "Upload or record dog vocalizations for STFT spectrogram generation, YIN F0 extraction, and classification.",
  },
  "/app/communicate": {
    title: "Engine B · Canine Vocalization Lab · CanineSense AI",
    desc: "Explore authentic canine vocalization reference retrieval and controlled bioacoustic synthesis.",
  },
  "/app/dogs": {
    title: "Canine Profiles · CanineSense AI",
    desc: "Manage dog profiles to provide anatomical and vocalization context for F0 estimation.",
  },
  "/app/history": {
    title: "Recording Archive · CanineSense AI",
    desc: "Review past canine vocalization recordings, spectrograms, waveforms, and acoustic features.",
  },
  "/app/analytics": {
    title: "Corpus Analytics & Model Card · CanineSense AI",
    desc: "Inspect vocalization frequency distributions, model cards, and transparent evaluation metrics.",
  },
  "/app/settings": {
    title: "Settings & Privacy · CanineSense AI",
    desc: "Manage credentials, export complete JSON research archives, or trigger instant account deletion.",
  },
  "/privacy-policy": {
    title: "Privacy Policy · CanineSense AI",
    desc: "Comprehensive privacy policy detailing local DSP audio processing, data retention, and user rights.",
  },
  "/terms-of-service": {
    title: "Terms of Service · CanineSense AI",
    desc: "Terms governing use of the CanineSense AI bioacoustic research platform and veterinary disclaimers.",
  },
  "/refund-policy": {
    title: "Refund Policy · CanineSense AI",
    desc: "Billing and refund transparency policy for CanineSense AI open-access tools.",
  },
  "/cookie-policy": {
    title: "Cookie Policy · CanineSense AI",
    desc: "Detailed inventory of browser storage and cookies used by CanineSense AI.",
  },
  "/cookie-settings": {
    title: "Cookie Settings · CanineSense AI",
    desc: "Customize your browser storage and privacy preferences for CanineSense AI.",
  },
  "/contact": {
    title: "Contact & Support · CanineSense AI",
    desc: "Direct communication channels for bioacoustic inquiries, support, and privacy requests.",
  },
  "/data-deletion": {
    title: "Data Deletion · CanineSense AI",
    desc: "Step-by-step instructions for permanent self-service account and audio data erasure.",
  },
};

export default function App() {
  const loc = useLocation();

  useEffect(() => {
    const meta = ROUTE_TITLES[loc.pathname] || {
      title: "404 · Page Not Found · CanineSense AI",
      desc: "Page not found. Return to CanineSense AI bioacoustic canine intelligence platform.",
    };
    document.title = meta.title;
    let metaDesc = document.querySelector('meta[name="description"]');
    if (!metaDesc) {
      metaDesc = document.createElement("meta");
      metaDesc.setAttribute("name", "description");
      document.head.appendChild(metaDesc);
    }
    metaDesc.setAttribute("content", meta.desc);
    window.scrollTo(0, 0);
  }, [loc.pathname]);
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
        <Route path="*" element={<NotFound />} />
      </Routes>
      <CookieBanner />
    </>
  );
}
