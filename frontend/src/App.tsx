import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import ChallengePage from "./pages/ChallengePage";
import HomePage from "./pages/HomePage";

const EngineLab = lazy(() => import("./lab/EngineLab"));

export default function App() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-neutral-500">Loading…</div>}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/c/:slug" element={<ChallengePage />} />
        <Route path="/lab" element={<EngineLab />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
