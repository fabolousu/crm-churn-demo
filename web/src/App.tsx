import { Link, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import { buttonPrimary, PageHeader } from "./components/ui";
import ActPage from "./pages/ActPage";
import LeadPage from "./pages/LeadPage";
import LeverPage from "./pages/LeverPage";
import PipelinePage from "./pages/PipelinePage";
import PortfolioPage from "./pages/PortfolioPage";
import { PipelineProvider } from "./state/PipelineProvider";

function NotFound() {
  return (
    <div>
      <PageHeader
        eyebrow="Not found"
        title="That screen is not in the demo"
        subtitle="The five screens are the queue, the Lead 360, the lever, the act loop and the portfolio."
      />
      <Link to="/" className={buttonPrimary}>
        Back to the queue
      </Link>
    </div>
  );
}

export default function App() {
  return (
    <PipelineProvider>
      <AppShell>
        <Routes>
          <Route path="/" element={<PipelinePage />} />
          <Route path="/leads/:leadId" element={<LeadPage />} />
          <Route path="/leads/:leadId/lever" element={<LeverPage />} />
          <Route path="/act" element={<ActPage />} />
          <Route path="/act/:leadId" element={<ActPage />} />
          <Route path="/portfolio" element={<PortfolioPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </AppShell>
    </PipelineProvider>
  );
}
