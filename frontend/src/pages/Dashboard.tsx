import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Player } from "../components/Player"
import { api } from "../lib/api"
import type { CaseRecord, Catalog, Evidence } from "../types"

const preset = {
  title: "Unusual activity near warehouse equipment",
  description:
    "Find footage of a person near a forklift. Reconstruct the observable sequence within each recording, and separate what is visible from what cannot be confirmed across clips.",
  location: "warehouse3",
  camera_ids: ["sdg_warehouse_cam-2"],
}

export function Dashboard() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [query, setQuery] = useState("person near a forklift in a warehouse aisle")
  const [camera, setCamera] = useState("sdg_warehouse_cam-2")
  const [selected, setSelected] = useState<Evidence | null>(null)
  const cases = useQuery({ queryKey: ["cases"], queryFn: () => api<{ cases: CaseRecord[] }>("/api/cases") })
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: () => api<Catalog>("/api/videos") })
  const search = useMutation({
    mutationFn: () =>
      api<{ results: Evidence[] }>("/api/videos/search", {
        method: "POST",
        body: JSON.stringify({ query, camera_id: camera || null, top_k: 6 }),
      }),
    onSuccess: (data) => setSelected(data.results[0] ?? null),
  })
  const createPreset = useMutation({
    mutationFn: () => api<CaseRecord>("/api/cases", { method: "POST", body: JSON.stringify(preset) }),
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ["cases"] })
      navigate(`/cases/${created.id}`)
    },
  })

  return (
    <div className="mx-auto grid max-w-6xl gap-6 px-4 py-6 lg:grid-cols-[1.1fr_0.9fr]">
      <section className="space-y-4">
        <div className="rounded-lg border border-line bg-panel p-5">
          <p className="text-xs uppercase tracking-[0.16em] text-teal">Investigation workspace</p>
          <h1 className="mt-2 text-2xl font-semibold">Evidence-backed video investigation</h1>
          <p className="mt-2 max-w-xl text-sm text-muted">
            Describe an incident. Sherlocked searches the indexed archive, keeps every finding tied to a clip, and
            refuses to invent a story the footage does not support.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link to="/cases/new" className="rounded bg-cyan px-3 py-2 text-sm font-medium text-bg">
              New investigation
            </Link>
            <button
              type="button"
              className="rounded border border-line px-3 py-2 text-sm"
              onClick={() => createPreset.mutate()}
              disabled={createPreset.isPending}
            >
              Open warehouse demo case
            </button>
          </div>
          {createPreset.isError && <p className="mt-2 text-sm text-alert">{(createPreset.error as Error).message}</p>}
        </div>
        <div className="rounded-lg border border-line bg-panel">
          <div className="border-b border-line px-4 py-3 text-sm font-medium">Cases</div>
          <div className="divide-y divide-line">
            {cases.isLoading && <p className="px-4 py-3 text-sm text-muted">Loading cases</p>}
            {cases.isError && <p className="px-4 py-3 text-sm text-alert">{(cases.error as Error).message}</p>}
            {cases.data?.cases.length === 0 && <p className="px-4 py-3 text-sm text-muted">No cases yet.</p>}
            {cases.data?.cases.map((item) => (
              <Link key={item.id} to={`/cases/${item.id}`} className="block px-4 py-3 hover:bg-panel-2">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium">{item.title}</span>
                  <span className="text-xs uppercase text-muted">{item.status}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-sm text-muted">{item.description}</p>
                <p className="mt-1 text-xs text-muted">{item.evidence_count} evidence items</p>
              </Link>
            ))}
          </div>
        </div>
      </section>
      <section className="space-y-4">
        <div className="rounded-lg border border-line bg-panel p-4">
          <div className="text-sm font-medium">Archive</div>
          {catalog.isLoading && <p className="mt-2 text-sm text-muted">Loading catalogue</p>}
          {catalog.isError && <p className="mt-2 text-sm text-alert">{(catalog.error as Error).message}</p>}
          {catalog.data && (
            <div className="mt-3 space-y-3 text-sm">
              <p className="text-muted">
                {catalog.data.overview.indexed_clips ?? "—"} indexed clips · {catalog.data.overview.unique_videos ?? "—"} videos
                {catalog.data.synthetic ? " · synthetic catalogue" : ""}
              </p>
              <div className="flex flex-wrap gap-1">
                {catalog.data.cameras.map((cam) => (
                  <button
                    key={cam.id}
                    type="button"
                    className={`rounded border px-2 py-1 text-xs ${camera === cam.id ? "border-cyan text-cyan" : "border-line text-muted"}`}
                    onClick={() => setCamera(cam.id)}
                  >
                    {cam.id}
                    {cam.count != null ? ` (${cam.count})` : ""}
                  </button>
                ))}
              </div>
            </div>
          )}
          <form
            className="mt-4 flex gap-2"
            onSubmit={(event) => {
              event.preventDefault()
              search.mutate()
            }}
          >
            <input
              className="min-w-0 flex-1 rounded border border-line bg-panel-2 px-3 py-2 text-sm outline-none focus:border-cyan"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <button type="submit" className="rounded bg-teal px-3 py-2 text-sm font-medium text-bg" disabled={search.isPending}>
              {search.isPending ? "Searching" : "Search"}
            </button>
          </form>
          {search.isError && <p className="mt-2 text-sm text-alert">{(search.error as Error).message}</p>}
          <div className="mt-3 max-h-48 space-y-2 overflow-auto">
            {search.data?.results.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setSelected(item)}
                className={`block w-full rounded border px-3 py-2 text-left text-sm ${selected?.id === item.id ? "border-cyan" : "border-line"}`}
              >
                <span className="text-xs text-muted">
                  {item.camera_id} · {item.start_seconds}–{item.end_seconds}s · {item.retrieval_score?.toFixed(3)}
                </span>
                <span className="mt-1 line-clamp-2 block">{item.observation}</span>
              </button>
            ))}
            {search.data?.results.length === 0 && <p className="text-sm text-muted">No segments matched.</p>}
          </div>
        </div>
        <div className="overflow-hidden rounded-lg border border-line bg-panel">
          <Player item={selected} />
        </div>
      </section>
    </div>
  )
}
