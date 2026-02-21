import React, { Suspense, lazy } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { MainLayout } from "./components/layout/MainLayout";
import { Toaster } from "./components/ui/sonner";

// Eager load authentication pages
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { AdminLogin } from "./pages/AdminLogin";
import { PendingApproval } from "./pages/PendingApproval";

// Lazy load heavy pages for code splitting
const Dashboard = lazy(() => import("./pages/Dashboard").then(module => ({ default: module.Dashboard })));
const Company = lazy(() => import("./pages/Company").then(module => ({ default: module.Company })));
const Jobs = lazy(() => import("./pages/Jobs").then(module => ({ default: module.Jobs })));
const JobEdit = lazy(() => import("./pages/JobEdit").then(module => ({ default: module.JobEdit })));
const Candidates = lazy(() => import("./pages/Candidates").then(module => ({ default: module.Candidates })));
const Analysis = lazy(() => import("./pages/Analysis").then(module => ({ default: module.Analysis })));
const Settings = lazy(() => import("./pages/Settings").then(module => ({ default: module.Settings })));
const SuperAdmin = lazy(() => import("./pages/SuperAdmin").then(module => ({ default: module.SuperAdmin })));

// Loading component
const PageLoader = () => (
  <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-indigo-50">
    <div className="text-center">
      <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mx-auto mb-4"></div>
      <p className="text-slate-600">Loading...</p>
    </div>
  </div>
);

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            {/* Public Routes */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/pending-approval" element={<PendingApproval />} />
            
            {/* Admin Routes */}
            <Route path="/admin-login" element={<AdminLogin />} />
            <Route path="/super-admin" element={<SuperAdmin />} />
            
            {/* Protected Routes */}
            <Route element={<MainLayout />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/company" element={<Company />} />
              <Route path="/jobs" element={<Jobs />} />
              <Route path="/jobs/:id" element={<JobEdit />} />
              <Route path="/candidates" element={<Candidates />} />
              <Route path="/analysis" element={<Analysis />} />
              <Route path="/settings" element={<Settings />} />
            </Route>
            
            {/* Redirect root to dashboard */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </AuthProvider>
  );
}

export default App;
