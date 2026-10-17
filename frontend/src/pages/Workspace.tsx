import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useMemo, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { Player } from "../components/Player"
import { api } from "../lib/api"
import type { CaseRecord, Evidence, Hypothesis, Investigation, Message, Timeline } from "../types"

const followups = [
  "What evidence supports this interpretation, and what remains uncertain?",
  "Which clips show movement, and which describe something stationary?",
  "Can these recordings be placed on one clock?",
]

export function Workspace() {
  const { caseId = "" } = useParams()
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [filter, setFilter] = useState("")
  const [question, setQuestion] = useState("")
  const caseQuery = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => api<CaseRecord>(`/api/cases/${caseId}`),
  })
  const evidenceQuery = useQuery({
    queryKey: ["evidence", caseId],
    queryFn: () => api<{ evidence: Evidence[] }>(`/api/cases/${caseId}/evidence`),
  })
  const timelineQuery = useQuery({
    queryKey: ["timeline", caseId],
    queryFn: () => api<Timeline>(`/api/cases/${caseId}/timeline`),
  })
  const hypothesisQuery = useQuery({
    queryKey: ["hypotheses", caseId],
    queryFn: () => api<{ hypotheses: Hypothesis[] }>(`/api/cases/${caseId}/hypotheses`),
  })
  const messageQuery = useQuery({
    queryKey: ["messages", caseId],
    queryFn: () => api<{ messages: Message[] }>(`/api/cases/${caseId}/messages`),
  })

  const investigate = useMutation({
    mutationFn: () => api<Investigation>(`/api/cases/${caseId}/investigate`, { method: "POST", body: "{}" }),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["case", caseId] })
      queryClient.setQueryData(["evidence", caseId], { evidence: result.evidence })
      queryClient.setQueryData(["timeline", caseId], result.timeline)
      queryClient.setQueryData(["hypotheses", caseId], { hypotheses: result.hypotheses })
      queryClient.setQueryData(["messages", caseId], { messages: result.messages })
      setSelectedId(result.evidence[0]?.id ?? null)
    },
  })
  const ask = useMutation({
    mutationFn: (text: string) =>
      api<{ messages: Message[] }>(`/api/cases/${caseId}/ask`, {
        method: "POST",
        body: JSON.stringify({ question: text }),
      }),
    onSuccess: (result) => {
      queryClient.setQueryData(["messages", caseId], { messages: result.messages })
      setQuestion("")
    },
  })

  const evidence = evidenceQuery.data?.evidence ?? []
  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase()
    if (!needle) return evidence
    return evidence.filter((item) =>
      `${item.camera_id} ${item.observation} ${item.object_labels.join(" ")}`.toLowerCase().includes(needle),
    )
  }, [evidence, filter])
  const selected = evidence.find((item) => item.id === selectedId) ?? visible[0] ?? null
  const stages = investigate.data?.stages

  function focusEvidence(id: string) {
    setSelectedId(id)
  }

  return (
    <div className="workspace">
      <aside className="flex min-h-0 flex-col border-r border-line bg-panel-2">
        <div className="border-b border-line px-3 py-3">
          <p className="text-xs uppercase tracking-wide text-muted">Evidence</p>
          <h1 className="truncate text-sm font-medium">{caseQuery.data?.title || "Investigation"}</h1>
          <input
            className="mt-2 w-full rounded border border-line bg-panel px-2 py-1 text-sm"
            placeholder="Filter captions"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          />
        </div>
        <div className="min-h-0 flex-1 overflow-auto">
          {evidenceQuery.isLoading && <p className="p-3 text-sm text-muted">Loading evidence</p>}
          {visible.length === 0 && !evidenceQuery.isLoading && (
            <p className="p-3 text-sm text-muted">No evidence yet. Launch the investigation to search the archive.</p>
          )}
          {visible.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => focusEvidence(item.id)}
              className={`block w-full border-b border-line px-3 py-3 text-left ${selected?.id === item.id ? "bg-panel" : ""}`}
            >
              <span className="text-xs text-cyan">
                {item.camera_id} · {item.start_seconds}–{item.end_seconds}s
              </span>
              <span className="mt-1 line-clamp-3 block text-sm">{item.observation}</span>
              <span className="mt-1 block text-xs text-muted">
                {item.object_labels.join(", ") || "no detections"} · score {item.retrieval_score?.toFixed(3) ?? "—"}
              </span>
            </button>
          ))}
        </div>
      </aside>
      <section className="min-h-0 bg-bg">
        <div className="flex items-center justify-between gap-2 border-b border-line px-3 py-2">
          <p className="truncate text-xs text-muted">{caseQuery.data?.description}</p>
          <div className="flex shrink-0 gap-2">
            <button
              type="button"
              className="rounded bg-cyan px-3 py-1.5 text-sm font-medium text-bg disabled:opacity-60"
              disabled={investigate.isPending}
              onClick={() => investigate.mutate()}
            >
              {investigate.isPending ? "Investigating" : "Investigate"}
            </button>
            <Link to={`/cases/${caseId}/report`} className="rounded border border-line px-3 py-1.5 text-sm">
              Report
            </Link>
          </div>
        </div>
        {investigate.isError && <p className="px-3 py-2 text-sm text-alert">{(investigate.error as Error).message}</p>}
        <Player item={selected} />
      </section>
      <aside className="flex min-h-0 flex-col border-l border-line bg-panel">
        <div className="border-b border-line px-3 py-3 text-sm font-medium">Investigator</div>
        <div className="min-h-0 flex-1 space-y-3 overflow-auto px-3 py-3">
          {investigate.isPending && <p className="text-sm text-muted">Searching the archive and checking citations.</p>}
          {stages && (
            <ol className="space-y-1 text-xs text-muted">
              {stages.map((stage) => (
                <li key={stage.id}>
                  <span className="text-teal">{stage.label}.</span> {stage.detail}
                </li>
              ))}
            </ol>
          )}
          {hypothesisQuery.data?.hypotheses.map((item) => (
            <article key={item.id} className="rounded border border-line p-2 text-sm">
              <p className={`text-xs uppercase ${item.status === "contradicted" ? "text-alert" : item.status === "supported" ? "text-teal" : "text-amber"}`}>
                {item.status}
              </p>
              <p className="mt-1">{item.statement}</p>
              <div className="mt-2 flex flex-wrap gap-1">
                {item.supporting_evidence_ids.map((id) => (
                  <button key={id} type="button" className="rounded bg-teal/15 px-1.5 py-0.5 text-xs text-teal" onClick={() => focusEvidence(id)}>
                    {id}
                  </button>
                ))}
                {item.contradicting_evidence_ids.map((id) => (
                  <button key={id} type="button" className="rounded bg-alert/15 px-1.5 py-0.5 text-xs text-alert" onClick={() => focusEvidence(id)}>
                    {id}
                  </button>
                ))}
              </div>
            </article>
          ))}
          {messageQuery.data?.messages.map((message) => (
            <article key={message.id} className="text-sm">
              <p className="text-xs uppercase text-muted">{message.role}</p>
              <p className="whitespace-pre-wrap text-ink">{message.content}</p>
              {message.evidence_ids.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {message.evidence_ids.slice(0, 8).map((id) => (
                    <button key={`${message.id}-${id}`} type="button" className="text-xs text-cyan" onClick={() => focusEvidence(id)}>
                      {id}
                    </button>
                  ))}
                </div>
              )}
            </article>
          ))}
          <p className="text-xs text-muted">
            Sherlocked assists review. It does not determine guilt, infer intent, or identify a person.
          </p>
        </div>
        <form
          className="border-t border-line p-3"
          onSubmit={(event) => {
            event.preventDefault()
            if (question.trim()) ask.mutate(question.trim())
          }}
        >
          <div className="mb-2 flex flex-wrap gap-1">
            {followups.map((prompt) => (
              <button key={prompt} type="button" className="rounded border border-line px-2 py-1 text-left text-xs text-muted" onClick={() => ask.mutate(prompt)}>
                {prompt}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              className="min-w-0 flex-1 rounded border border-line bg-panel-2 px-2 py-1 text-sm"
              value={question}
              placeholder="Ask about retrieved evidence"
              onChange={(event) => setQuestion(event.target.value)}
            />
            <button type="submit" className="rounded bg-teal px-2 text-sm text-bg" disabled={ask.isPending}>
              Ask
            </button>
          </div>
          {ask.isError && <p className="mt-1 text-xs text-alert">{(ask.error as Error).message}</p>}
        </form>
      </aside>
      <section className="span-bottom overflow-auto border-t border-line bg-panel-2">
        <div className="px-3 py-2 text-xs text-muted">{timelineQuery.data?.note || "Timeline"}</div>
        <div className="flex gap-3 px-3 pb-3">
          {(timelineQuery.data?.groups ?? []).map((group) => (
            <div key={group.group_id} className="min-w-72 rounded border border-line bg-panel p-2">
              <p className="truncate text-xs text-cyan">{group.camera_id}</p>
              <p className="truncate text-xs text-muted">{group.label}</p>
              <p className="mt-1 text-xs text-amber">{group.clock_note}</p>
              <div className="mt-2 space-y-1">
                {group.events.map((event) => (
                  <button
                    key={event.id}
                    type="button"
                    className="block w-full rounded bg-panel-2 px-2 py-1 text-left text-xs"
                    onClick={() => focusEvidence(event.evidence_ids[0])}
                  >
                    <span className="text-teal">
                      {event.relative_time}–{event.end_seconds}s · {event.verification_status}
                    </span>
                    <span className="line-clamp-2 block">{event.description}</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
          {(timelineQuery.data?.groups.length ?? 0) === 0 && (
            <p className="text-sm text-muted">Events appear here after an investigation, grouped by parent recording.</p>
          )}
        </div>
      </section>
    </div>
  )
}
