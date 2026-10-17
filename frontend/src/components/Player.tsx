import { useEffect, useState } from "react"
import { apiUrl } from "../lib/api"
import type { Evidence } from "../types"

export function Player({ item }: { item: Evidence | null }) {
  const [mode, setMode] = useState<"parent" | "segment">("parent")
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    setMode("parent")
    setFailed(false)
  }, [item?.id])

  if (!item) {
    return (
      <div className="flex h-full min-h-64 items-center justify-center text-sm text-muted">
        Select evidence to open its source clip.
      </div>
    )
  }

  const src = apiUrl(`/api/media/stream?item_id=${encodeURIComponent(item.id)}&which=${mode}`)
  const score = item.retrieval_score == null ? "—" : item.retrieval_score.toFixed(3)

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="relative min-h-0 flex-1 bg-black">
        {failed ? (
          <div className="flex h-full min-h-64 items-center justify-center px-6 text-center text-sm text-muted">
            This item has no playable media. Synthetic fixtures and missing source URIs cannot be shown as video.
          </div>
        ) : (
          <video
            key={src}
            className="h-full max-h-[52vh] w-full bg-black object-contain"
            controls
            playsInline
            src={src}
            onLoadedMetadata={(event) => {
              const video = event.currentTarget
              const start = item.start_seconds
              if (mode !== "parent" || start == null || !Number.isFinite(video.duration)) return
              if (start < video.duration - 0.2) {
                video.currentTime = start
              } else {
                setMode("segment")
              }
            }}
            onError={() => {
              if (mode === "parent") setMode("segment")
              else setFailed(true)
            }}
          />
        )}
      </div>
      <div className="space-y-2 border-t border-line px-4 py-3 text-sm">
        <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-wide text-muted">
          <span className="text-cyan">{item.camera_id || "Camera unknown"}</span>
          <span>{item.location || "Location unknown"}</span>
          <span>
            {item.start_seconds ?? "?"}–{item.end_seconds ?? "?"}s in parent
          </span>
          <span>score {score}</span>
        </div>
        <p className="text-ink">{item.observation}</p>
        <p className="text-xs text-muted">
          {mode === "parent"
            ? "Playing the parent recording and seeking to the segment offset when the file is long enough."
            : "Playing the segment file itself. It already starts at the matched moment, so the offset is not applied again."}
          {" "}Retrieval score is a similarity rank, not a probability.
          {item.evidence_type === "synthetic_fixture" ? " This record is synthetic." : " Caption source: indexed Cosmos Reason text."}
        </p>
        {item.object_labels.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {item.object_labels.map((label) => (
              <span key={label} className="rounded border border-line px-2 py-0.5 text-xs text-teal">
                {label}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
