import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { api } from "../lib/api"
import type { CaseRecord, Catalog } from "../types"

export function NewCase() {
  const navigate = useNavigate()
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: () => api<Catalog>("/api/videos") })
  const [title, setTitle] = useState("Unusual activity near warehouse equipment")
  const [description, setDescription] = useState(
    "Find footage of a person near a forklift. Reconstruct the observable sequence within each recording, and separate what is visible from what cannot be confirmed across clips.",
  )
  const [location, setLocation] = useState("warehouse3")
  const [cameras, setCameras] = useState<string[]>(["sdg_warehouse_cam-2"])
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  function toggle(id: string) {
    setCameras((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]))
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setPending(true)
    setError(null)
    try {
      const created = await api<CaseRecord>("/api/cases", {
        method: "POST",
        body: JSON.stringify({
          title,
          description,
          location: location || null,
          camera_ids: cameras,
        }),
      })
      navigate(`/cases/${created.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the case")
    } finally {
      setPending(false)
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-2xl space-y-4 px-4 py-6">
      <h1 className="text-xl font-semibold">New investigation</h1>
      <label className="block text-sm">
        Title
        <input className="mt-1 w-full rounded border border-line bg-panel px-3 py-2" value={title} onChange={(event) => setTitle(event.target.value)} required />
      </label>
      <label className="block text-sm">
        What should be investigated
        <textarea className="mt-1 min-h-32 w-full rounded border border-line bg-panel px-3 py-2" value={description} onChange={(event) => setDescription(event.target.value)} required />
      </label>
      <label className="block text-sm">
        Location filter
        <select className="mt-1 w-full rounded border border-line bg-panel px-3 py-2" value={location} onChange={(event) => setLocation(event.target.value)}>
          <option value="">Any location</option>
          {catalog.data?.locations.map((item) => (
            <option key={item.id} value={item.id}>
              {item.id}
            </option>
          ))}
        </select>
      </label>
      <fieldset>
        <legend className="text-sm">Cameras</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {catalog.data?.cameras.map((item) => (
            <label key={item.id} className={`rounded border px-2 py-1 text-xs ${cameras.includes(item.id) ? "border-cyan text-cyan" : "border-line text-muted"}`}>
              <input className="mr-1" type="checkbox" checked={cameras.includes(item.id)} onChange={() => toggle(item.id)} />
              {item.id}
            </label>
          ))}
          {catalog.isLoading && <span className="text-sm text-muted">Loading cameras</span>}
        </div>
      </fieldset>
      {error && <p className="text-sm text-alert">{error}</p>}
      <button type="submit" disabled={pending} className="rounded bg-cyan px-4 py-2 text-sm font-medium text-bg">
        {pending ? "Creating" : "Create and open"}
      </button>
    </form>
  )
}
