import { Route, Routes } from "react-router-dom"
import { Layout } from "./components/Layout"
import { Command } from "./pages/Command"
import { Dashboard } from "./pages/Dashboard"
import { NewCase } from "./pages/NewCase"
import { ReportPage } from "./pages/Report"
import { Workspace } from "./pages/Workspace"

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Command />} />
        <Route path="/archive" element={<Dashboard />} />
        <Route path="/cases/new" element={<NewCase />} />
        <Route path="/cases/:caseId" element={<Workspace />} />
        <Route path="/cases/:caseId/report" element={<ReportPage />} />
      </Routes>
    </Layout>
  )
}
