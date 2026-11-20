import { Link, Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import CrmShell from "./components/CrmShell";
import { CrmProvider } from "./crm/store";
import EntityListPage from "./crm/EntityListPage";
import GapPage from "./crm/GapPage";
import LeadFormPage from "./crm/LeadFormPage";
import LeadListPage from "./crm/LeadListPage";
import ActPage from "./pages/ActPage";
import LeadPage from "./pages/LeadPage";
import LeverPage from "./pages/LeverPage";
import PipelinePage from "./pages/PipelinePage";
import PortfolioPage from "./pages/PortfolioPage";
import { PipelineProvider } from "./state/PipelineProvider";

function NotFound() {
  return (
    <div className="mx-auto max-w-xl py-12">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">
        Pagina non trovata
      </p>
      <h1 className="mt-2 text-[26px] font-semibold tracking-tight text-ink">
        Questa schermata non è nella demo
      </h1>
      <p className="mt-3 text-[13px] leading-relaxed text-muted">
        La demo contiene la shell CRM, i lead e il modulo Previsioni.
      </p>
      <Link
        to="/"
        className="mt-6 inline-flex h-9 items-center rounded-md bg-[#176B3B] px-4 text-[13px] font-semibold text-white hover:bg-[#14562F]"
      >
        Torna ai lead
      </Link>
    </div>
  );
}

function RedirectLead() {
  const { leadId } = useParams<{ leadId: string }>();
  return <Navigate to={`/previsioni/leads/${leadId ?? ""}`} replace />;
}

function RedirectLever() {
  const { leadId } = useParams<{ leadId: string }>();
  return <Navigate to={`/previsioni/leads/${leadId ?? ""}/lever`} replace />;
}

function RedirectAct() {
  const { leadId } = useParams<{ leadId: string }>();
  return <Navigate to={`/previsioni/act/${leadId ?? ""}`} replace />;
}

export default function App() {
  const location = useLocation();
  return (
    <CrmProvider>
      <PipelineProvider>
        <CrmShell>
          {/* Keying by pathname gives every screen a fresh mount, so a record form
              never keeps the draft of the record it was opened from. */}
          <Routes key={location.pathname}>
            {/* CRM — the product shell (Q1) */}
            <Route path="/" element={<LeadListPage />} />
            <Route path="/lead/new" element={<LeadFormPage />} />
            <Route path="/lead/:leadId" element={<LeadFormPage />} />
            <Route path="/aziende" element={<EntityListPage entity="aziende" />} />
            <Route path="/contatti" element={<EntityListPage entity="contatti" />} />
            <Route path="/iniziative" element={<EntityListPage entity="iniziative" />} />
            <Route path="/non-incluso" element={<GapPage />} />

            {/* Previsioni — the ML module, moved under /previsioni (Q1) */}
            <Route path="/previsioni" element={<PipelinePage />} />
            <Route path="/previsioni/leads/:leadId" element={<LeadPage />} />
            <Route path="/previsioni/leads/:leadId/lever" element={<LeverPage />} />
            <Route path="/previsioni/act" element={<ActPage />} />
            <Route path="/previsioni/act/:leadId" element={<ActPage />} />
            <Route path="/previsioni/portfolio" element={<PortfolioPage />} />

            {/* Old ML links keep working. */}
            <Route path="/leads/:leadId" element={<RedirectLead />} />
            <Route path="/leads/:leadId/lever" element={<RedirectLever />} />
            <Route path="/act" element={<Navigate to="/previsioni/act" replace />} />
            <Route path="/act/:leadId" element={<RedirectAct />} />
            <Route path="/portfolio" element={<Navigate to="/previsioni/portfolio" replace />} />

            <Route path="*" element={<NotFound />} />
          </Routes>
        </CrmShell>
      </PipelineProvider>
    </CrmProvider>
  );
}
