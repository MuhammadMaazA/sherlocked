import { useQuery } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { Link } from "react-router-dom"
import { api } from "../lib/api"
import type { Health } from "../types"

export function Layout({ children }: { children: ReactNode }) {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<Health>("/api/health"),
  })
  const synthetic = health.data?.synthetic
  const ok = health.data?.status === "ok" && !synthetic
  return (
    <div className="min-h-full bg-bg text-ink">
      <header className="flex h-[60px] items-center justify-between border-b border-line px-4">
        <Link to="/" className="flex items-baseline gap-3">
          <span className="font-[Syne] text-lg font-semibold tracking-tight text-amber">Sherlocked</span>
          <span className="hidden text-sm text-muted sm:inline">Safety Command</span>
        </Link>
        <Link to="/archive" className="text-xs uppercase tracking-[0.14em] text-muted">
          Archive
        </Link>
        <div className="flex items-center gap-3 text-xs text-muted">
          <span className={`h-2 w-2 rounded-full ${ok ? "bg-teal" : synthetic ? "bg-amber" : "bg-alert"}`} />
          <span>
            {health.isLoading && "Checking archive"}
            {health.isError && "Archive unreachable"}
            {health.data && (synthetic ? "Synthetic fixtures" : `Archive ${health.data.video?.username ?? "connected"}`)}
          </span>
        </div>
      </header>
      {synthetic && (
        <div className="border-b border-amber/40 bg-amber/10 px-4 py-2 text-sm text-amber">
          The mock provider is active. Every clip below is a synthetic fixture, not VAST footage.
        </div>
      )}
      {children}
    </div>
  )
}
