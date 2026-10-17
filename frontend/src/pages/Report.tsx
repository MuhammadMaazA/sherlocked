import { useQuery } from "@tanstack/react-query"
import { Link, useParams } from "react-router-dom"
import { api, apiUrl } from "../lib/api"
import type { CaseRecord, Investigation } from "../types"

export function ReportPage() {
  const { caseId = "" } = useParams()
  const report = useQuery({
    queryKey: ["report", caseId],
    queryFn: () => api<{ case: CaseRecord; investigation: Investigation | null }>(`/api/cases/${caseId}/report`),
  })
  const data = report.data
  const findings = data?.investigation?.findings
  return (
    <div className="mx-auto max-w-3xl space-y-4 px-4 py-6">
      <div className="flex items-center justify-between">
        <Link to={`/cases/${caseId}`} className="text-sm text-cyan">
          Back to workspace
        </Link>
        <a className="text-sm text-teal" href={apiUrl(`/api/cases/${caseId}/report.html`)} target="_blank" rel="noreferrer">
          Printable report
        </a>
      </div>
      {report.isLoading && <p className="text-sm text-muted">Loading report</p>}
      {report.isError && <p className="text-sm text-alert">{(report.error as Error).message}</p>}
      {data && (
        <>
          <h1 className="text-2xl font-semibold">{data.case.title}</h1>
          <p className="text-sm text-muted">{data.case.description}</p>
          <p className="rounded border border-amber/40 bg-amber/10 px-3 py-2 text-sm text-amber">
            Human review is required. This report does not determine guilt, infer intent, or identify a person.
          </p>
          {!data.investigation && <p>No investigation has been run.</p>}
          {findings && (
            <div className="space-y-4 text-sm">
              <Section title="Observed" lines={findings.observed} />
              <Section title="Inferred" lines={findings.inferred} />
              <Section title="Uncertain" lines={findings.uncertain} />
              <Section title="Next steps" lines={findings.next_steps} />
              {findings.synthesis_note && (
                <section>
                  <h2 className="font-medium text-cyan">Index synthesis</h2>
                  <p className="mt-1 whitespace-pre-wrap text-muted">{findings.synthesis_note}</p>
                </section>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function Section({ title, lines }: { title: string; lines: string[] }) {
  return (
    <section>
      <h2 className="font-medium text-cyan">{title}</h2>
      {lines.length === 0 ? <p className="mt-1 text-muted">None.</p> : <ul className="mt-1 list-disc space-y-1 pl-5">{lines.map((line) => <li key={line}>{line}</li>)}</ul>}
    </section>
  )
}
