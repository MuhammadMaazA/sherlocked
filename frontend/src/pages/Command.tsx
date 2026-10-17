import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useLayoutEffect, useRef, useState, type PointerEvent } from "react"
import { api, apiUrl } from "../lib/api"
import type { DetectionFrame, SafetyAction, SafetyView, SafetyWall, WallCamera, WallSegment } from "../types"

type Mode = "investigate" | "prevent" | "report"
type TileState = "normal" | "incident" | "concern" | "watch"

const PILL: Record<string, string> = {
  routine: "Clear",
  watch: "Watch",
  potential_near_miss: "Near miss",
  other_safety_concern: "Climb",
  contact: "Contact",
}

const ZONE = { x: 0.08, y: 0.58, w: 0.34, h: 0.28 }

function segmentAt(camera: WallCamera, time: number): WallSegment | undefined {
  return camera.segments.find((segment) => time >= segment.start && time < segment.end) ?? camera.segments.at(-1)
}

function tileState(camera: WallCamera, time: number, locked: boolean): TileState {
  if (locked && camera.takeover) return "incident"
  const segment = segmentAt(camera, time)
  if (segment?.category === "contact") return "incident"
  if (segment?.category === "other_safety_concern") return "concern"
  if (segment?.category === "potential_near_miss") return "watch"
  return "normal"
}

function beep() {
  const context = new AudioContext()
  const oscillator = context.createOscillator()
  const gain = context.createGain()
  oscillator.type = "square"
  oscillator.frequency.value = 740
  gain.gain.value = 0.04
  oscillator.connect(gain)
  gain.connect(context.destination)
  oscillator.start()
  oscillator.stop(context.currentTime + 0.16)
  oscillator.onended = () => void context.close()
}

export function Command() {
  const queryClient = useQueryClient()
  const wall = useQuery({ queryKey: ["safety-wall"], queryFn: () => api<SafetyWall>("/api/safety/wall") })
  const videos = useRef<Record<string, HTMLVideoElement | null>>({})
  const tileRefs = useRef<Record<string, HTMLElement | null>>({})
  const clock = useRef<Record<string, number>>({})
  const fired = useRef<Set<string>>(new Set())
  const [tick, setTick] = useState(0)
  const [paused, setPaused] = useState(true)
  const [live, setLive] = useState(false)
  const [audioOn, setAudioOn] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [zoomCode, setZoomCode] = useState<string | null>(null)
  const [stageTime, setStageTime] = useState(0)
  const [banner, setBanner] = useState<WallCamera | null>(null)
  const zoomTimer = useRef<number | null>(null)
  const zoomFrom = useRef<DOMRect | null>(null)

  useLayoutEffect(() => {
    if (!zoomCode || !zoomFrom.current) return
    const tile = tileRefs.current[zoomCode]
    const first = zoomFrom.current
    zoomFrom.current = null
    if (!tile) return
    const last = tile.getBoundingClientRect()
    if (!last.width || !last.height) return
    const dx = first.left - last.left
    const dy = first.top - last.top
    tile.animate(
      [
        { transform: `translate(${dx}px, ${dy}px) scale(${first.width / last.width}, ${first.height / last.height})` },
        { transform: "translate(0px, 0px) scale(1, 1)" },
      ],
      { duration: 760, easing: "cubic-bezier(.22,1,.36,1)" },
    )
  }, [zoomCode])

  useEffect(() => {
    const id = window.setInterval(() => setTick((value) => value + 1), 250)
    return () => window.clearInterval(id)
  }, [])

  function pauseOthers(keep: string) {
    for (const [code, video] of Object.entries(videos.current)) {
      if (code !== keep) video?.pause()
    }
    setPaused(true)
  }

  function present(code: string) {
    zoomFrom.current = tileRefs.current[code]?.getBoundingClientRect() ?? null
    setZoomCode(code)
  }

  function onProgress(camera: WallCamera, time: number) {
    const previous = clock.current[camera.code] ?? 0
    clock.current[camera.code] = time
    if (!live || !camera.takeover || fired.current.has(camera.code)) return
    const start = camera.takeover.start
    const end = camera.takeover.end
    if (!(previous < start && time >= start && time < end)) return
    fired.current.add(camera.code)
    setBanner(camera)
    setStageTime(time)
    present(camera.code)
    pauseOthers(camera.code)
    if (audioOn) beep()
    if (zoomTimer.current) window.clearTimeout(zoomTimer.current)
    zoomTimer.current = window.setTimeout(() => setExpanded(camera.code), 880)
  }

  function begin(fromStart: boolean) {
    fired.current = new Set()
    setBanner(null)
    setExpanded(null)
    setZoomCode(null)
    if (zoomTimer.current) window.clearTimeout(zoomTimer.current)
    setLive(true)
    setPaused(false)
    for (const video of Object.values(videos.current)) {
      if (!video) continue
      if (fromStart) video.currentTime = 0
      video.playbackRate = 1
      void video.play().catch(() => undefined)
    }
  }

  useEffect(() => {
    if (!live || expanded) return
    const id = window.setInterval(() => {
      const master = videos.current["WH-01"]
      if (!master || master.paused) return
      for (const [code, video] of Object.entries(videos.current)) {
        if (!video || code === "WH-01") continue
        if (Math.abs(video.currentTime - master.currentTime) > 0.4) video.currentTime = master.currentTime
      }
    }, 700)
    return () => window.clearInterval(id)
  }, [live, expanded])

  function togglePause() {
    const next = !paused
    setPaused(next)
    for (const video of Object.values(videos.current)) {
      if (!video) continue
      if (next) video.pause()
      else void video.play().catch(() => undefined)
    }
  }

  function openCamera(camera: WallCamera) {
    const video = videos.current[camera.code]
    let time = clock.current[camera.code] ?? 0
    const takeover = camera.takeover
    if (video && takeover && (time < takeover.start || time >= takeover.end)) {
      time = takeover.start + 0.15
      video.currentTime = time
      clock.current[camera.code] = time
      setTick((value) => value + 1)
    }
    setStageTime(time)
    present(camera.code)
    pauseOthers(camera.code)
    if (zoomTimer.current) window.clearTimeout(zoomTimer.current)
    zoomTimer.current = window.setTimeout(() => setExpanded(camera.code), 420)
  }

  const cameras = wall.data?.cameras ?? []
  void tick

  return (
    <div className="command">
      <div className="command-bar">
        <div>
          <p className="eyebrow">Indexed footage replay</p>
          <h1>Monitoring replay</h1>
        </div>
        <Stat label="Camera feeds" value={wall.data?.feeds ?? "—"} />
        <Stat label="Events flagged" value={wall.data?.events_flagged ?? "—"} />
        <Stat label="Awaiting review" value={wall.data?.awaiting_review ?? "—"} tone={wall.data && wall.data.awaiting_review > 0 ? "alert" : "ok"} />
        <div className="engines">
          {(wall.data?.engines ?? []).map((engine) => (
            <span key={engine.name} title={engine.role}>
              {engine.name}
            </span>
          ))}
        </div>
        <div className="command-controls">
          <button type="button" className="primary" onClick={() => begin(true)}>
            {live ? "Restart replay" : "Start monitoring replay"}
          </button>
          <button type="button" onClick={togglePause} disabled={!live}>
            {paused ? "Resume" : "Pause"}
          </button>
          <label className="audio-toggle">
            <input type="checkbox" checked={audioOn} onChange={(event) => setAudioOn(event.target.checked)} />
            Alert audio
          </label>
        </div>
      </div>
      {wall.isError && <p className="command-error">{(wall.error as Error).message}</p>}
      {wall.isLoading && <p className="command-note">Loading indexed warehouse recordings…</p>}
      <div className={`wall ${zoomCode ? "has-zoom" : ""}`}>
        {cameras.map((camera) => {
          const time = clock.current[camera.code] ?? 0
          const status = tileState(camera, time, fired.current.has(camera.code))
          const segment = segmentAt(camera, time)
          return (
            <div className="slot" key={camera.code}>
            <article
              ref={(node) => {
                tileRefs.current[camera.code] = node
              }}
              className={`tile state-${status} ${zoomCode === camera.code ? "is-zoom" : ""}`}
              onClick={() => openCamera(camera)}
              role="button"
              tabIndex={0}
            >
              <video
                ref={(node) => {
                  videos.current[camera.code] = node
                }}
                src={apiUrl(`/api/safety/stream?camera=${camera.code}`)}
                muted
                playsInline
                loop
                preload="auto"
                onTimeUpdate={(event) => onProgress(camera, event.currentTarget.currentTime)}
              />
              <div className="hud">
                <i className="live-dot" />
                <span>{camera.code}</span>
                <span className="pill">{PILL[segment?.category ?? "routine"] ?? status}</span>
              </div>
              {zoomCode === camera.code && <FeedOverlay code={camera.code} time={time} />}
              <div className="tile-labels">{(segment?.display_labels ?? []).join(" · ") || "indexed"}</div>
              <div className="ticker">
                <span>
                  {segment?.ticker} · {segment?.ticker}
                </span>
              </div>
            </article>
            </div>
          )
        })}
      </div>
      {banner && !expanded && (
        <AlertBanner camera={banner} onReview={() => openCamera(banner)} onDismiss={() => setBanner(null)} />
      )}
      {expanded && (
        <Stage
          code={expanded}
          startTime={stageTime}
          onClose={() => {
            setExpanded(null)
            setZoomCode(null)
          }}
          onSaved={() => void queryClient.invalidateQueries({ queryKey: ["safety-wall"] })}
        />
      )}
      <p className="command-foot">{wall.data?.disclaimer}</p>
    </div>
  )
}

function Stat({ label, value, tone }: { label: string; value: number | string; tone?: "alert" | "ok" }) {
  return (
    <div className={`stat ${tone ?? ""}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  )
}

function AlertBanner({ camera, onReview, onDismiss }: { camera: WallCamera; onReview: () => void; onDismiss: () => void }) {
  const takeover = camera.takeover
  return (
    <div className="alert-banner">
      <div>
        <p className="eyebrow">Safety event detected</p>
        <h2>
          {camera.code} · {takeover?.headline}
        </h2>
        <p>
          Indexed window {takeover?.start}–{takeover?.end}s. Playback reached that segment. This is not a new live detection.
        </p>
      </div>
      <button type="button" className="primary" onClick={onReview}>
        Review
      </button>
      <button type="button" onClick={onDismiss}>
        Hold
      </button>
    </div>
  )
}

function Stage({ code, startTime, onClose, onSaved }: { code: string; startTime: number; onClose: () => void; onSaved: () => void }) {
  const view = useQuery({
    queryKey: ["safety-camera", code],
    queryFn: () => api<SafetyView>(`/api/safety/cameras/${code}`),
  })
  const detections = useQuery({
    queryKey: ["safety-detections", code],
    queryFn: () => api<{ frames: DetectionFrame[]; note?: string }>(`/api/safety/cameras/${code}/detections`),
  })
  const actions = useQuery({
    queryKey: ["safety-actions"],
    queryFn: () => api<{ actions: SafetyAction[] }>("/api/safety/actions"),
  })
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const frameRef = useRef<HTMLDivElement | null>(null)
  const [time, setTime] = useState(startTime)
  const [slow, setSlow] = useState(false)
  const [mode, setMode] = useState<Mode>("investigate")
  const [draft, setDraft] = useState<SafetyAction | null>(null)
  const [zone, setZone] = useState(ZONE)
  const [snap, setSnap] = useState<string | null>(null)
  const drag = useRef<{ dx: number; dy: number; mode: "move" | "resize" } | null>(null)

  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    const seek = () => {
      video.currentTime = startTime
      video.playbackRate = slow ? 0.5 : 1
      void video.play().catch(() => undefined)
    }
    if (video.readyState >= 1) seek()
    else video.addEventListener("loadedmetadata", seek, { once: true })
  }, [code, startTime, slow])

  function capture() {
    const video = videoRef.current
    if (!video || video.readyState < 2) return
    const canvas = document.createElement("canvas")
    canvas.width = 320
    canvas.height = 180
    const context = canvas.getContext("2d")
    if (!context) return
    try {
      context.drawImage(video, 0, 0, 320, 180)
      setSnap(canvas.toDataURL("image/jpeg", 0.72))
    } catch {
      setSnap(null)
    }
  }

  const frames = detections.data?.frames ?? []
  const boxes = nearestBoxes(frames, time)
  const mine = (actions.data?.actions ?? []).filter((item) => item.camera_code === code)

  const act = useMutation({
    mutationFn: (body: { kind: SafetyAction["kind"]; payload?: SafetyAction["payload"]; body?: string }) =>
      api<SafetyAction>("/api/safety/actions", { method: "POST", body: JSON.stringify({ camera: code, ...body }) }),
    onSuccess: async (action) => {
      if (action.kind === "risk") {
        setDraft(action)
        setMode("report")
      }
      await actions.refetch()
      onSaved()
    },
  })

  const saveDraft = useMutation({
    mutationFn: () =>
      api<SafetyAction>(`/api/safety/actions/${draft?.id}`, {
        method: "PATCH",
        body: JSON.stringify({ body: draft?.body ?? "" }),
      }),
    onSuccess: async () => {
      await actions.refetch()
      onSaved()
    },
  })

  function onPointerDown(event: PointerEvent<HTMLElement>, pointerMode: "move" | "resize") {
    const bounds = frameRef.current?.getBoundingClientRect()
    if (!bounds) return
    drag.current = {
      mode: pointerMode,
      dx: event.clientX / bounds.width - zone.x,
      dy: event.clientY / bounds.height - zone.y,
    }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!drag.current) return
    const bounds = frameRef.current?.getBoundingClientRect()
    if (!bounds) return
    const px = event.clientX / bounds.width
    const py = event.clientY / bounds.height
    if (drag.current.mode === "move") {
      setZone((current) => ({
        ...current,
        x: clamp(px - drag.current!.dx, 0, 1 - current.w),
        y: clamp(py - drag.current!.dy, 0, 1 - current.h),
      }))
    } else {
      setZone((current) => ({
        ...current,
        w: clamp(px - current.x, 0.08, 1 - current.x),
        h: clamp(py - current.y, 0.08, 1 - current.y),
      }))
    }
  }

  const focus = view.data

  return (
    <div className="stage">
        <div className="stage-video">
        {focus?.category === "contact" && (
          <p className="stage-alert">
            Safety event · {code} · {focus.headline} · indexed window {focus.window.start}–{focus.window.end}s
          </p>
        )}
        <div
          className="frame"
          ref={frameRef}
          onPointerMove={onPointerMove}
          onPointerUp={() => {
            drag.current = null
          }}
        >
          <video
            ref={videoRef}
            src={apiUrl(`/api/safety/stream?camera=${code}`)}
            muted
            playsInline
            onTimeUpdate={(event) => setTime(event.currentTarget.currentTime)}
            onSeeked={capture}
          />
          {mode === "prevent" && <SeparationSketch box={boxes[0]} />}
          {boxes.map((box, index) => (
            <div
              key={`${box.label}-${index}`}
              className="detect-box"
              style={{ left: `${box.x * 100}%`, top: `${box.y * 100}%`, width: `${box.w * 100}%`, height: `${box.h * 100}%` }}
            >
              <span>
                {box.label} {box.confidence.toFixed(2)}
              </span>
            </div>
          ))}
          {mode === "prevent" && (
            <div
              className="zone"
              role="button"
              aria-label="Proposed pedestrian boundary"
              style={{ left: `${zone.x * 100}%`, top: `${zone.y * 100}%`, width: `${zone.w * 100}%`, height: `${zone.h * 100}%` }}
              onPointerDown={(event) => onPointerDown(event, "move")}
            >
              Proposed pedestrian boundary
              <i onPointerDown={(event) => { event.stopPropagation(); onPointerDown(event, "resize") }} />
            </div>
          )}
        </div>
        <div className="transport">
          <button type="button" onClick={() => videoRef.current?.paused ? void videoRef.current.play() : videoRef.current?.pause()}>
            Play / pause
          </button>
          <button
            type="button"
            onClick={() => {
              const next = !slow
              setSlow(next)
              if (videoRef.current) videoRef.current.playbackRate = next ? 0.5 : 1
            }}
          >
            {slow ? "Normal speed" : "Slow motion"}
          </button>
          <span>
            {time.toFixed(1)}s · window {focus?.window.start ?? "—"}–{focus?.window.end ?? "—"}s
          </span>
          <div className="windows">
            {focus?.segments.map((segment) => (
              <button
                key={segment.start}
                type="button"
                className={segment.category !== "routine" ? "marked" : ""}
                onClick={() => {
                  if (videoRef.current) videoRef.current.currentTime = segment.start
                }}
              >
                {segment.start}–{segment.end}s {segment.category.replaceAll("_", " ")}
              </button>
            ))}
          </div>
        </div>
      </div>
      <aside className="stage-panel">
        <div className="panel-head">
          <p className="eyebrow">{code} · {focus?.category.replaceAll("_", " ") ?? "loading"}</p>
          <button type="button" onClick={onClose}>
            Back to wall
          </button>
        </div>
        {view.isLoading && <p>Opening the indexed note…</p>}
        {view.isError && <p className="command-error">{(view.error as Error).message}</p>}
        {focus && mode === "investigate" && (
          <>
            <h2>{focus.headline}</h2>
            <p className="observed">{focus.observed}</p>
            <h3>Why this window</h3>
            <ul>
              {(focus.signals ?? []).map((signal) => (
                <li key={signal}>{signal}</li>
              ))}
            </ul>
            <p className="meta">
              {focus.parent_name}
              <br />
              {focus.filename}
            </p>
            <h3>In view</h3>
            <p>{focus.display_labels.join(" · ") || "No caption-supported class"}</p>
            <p className="meta">Detector classes stored on the clip: {focus.detector_labels.join(", ") || "none"}. Only person boxes are drawn.</p>
            <div className="worker">
              {snap && <img src={snap} alt="Frame from this clip" />}
              <div>
                <strong>Worker A — unidentified</strong>
                <p>{focus.person_annotation}</p>
              </div>
            </div>
            <h3>Contributing factors</h3>
            <ul>
              {focus.hypotheses.map((item) => (
                <li key={item.text}>
                  {item.text} <em>{item.status.replaceAll("_", " ")}</em>
                </li>
              ))}
              {focus.hypotheses.length === 0 && <li>No extra factor is proposed for this routine clip.</li>}
            </ul>
            <h3>Unresolved</h3>
            <ul>
              {focus.uncertain.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            {detections.data?.note && <p className="meta">{detections.data.note}</p>}
          </>
        )}
        {focus && mode === "prevent" && (
          <>
            <h2>Prevent this</h2>
            <p>
              The lane, ring, and barrier draw from the YOLO11 person box and the Cosmos caption. Drag the yellow
              boundary to adjust it. This is a proposed control, not a physics simulation.
            </p>
            <ul>
              {focus.controls.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <button
              type="button"
              className="primary"
              disabled={act.isPending}
              onClick={() =>
                act.mutate({
                  kind: "prevent",
                  payload: zone,
                  body: `Proposed pedestrian boundary at x ${zone.x.toFixed(2)}, y ${zone.y.toFixed(2)}, w ${zone.w.toFixed(2)}, h ${zone.h.toFixed(2)}. Not a physical simulation.`,
                })
              }
            >
              Add to action plan
            </button>
          </>
        )}
        {focus && mode === "report" && (
          <>
            <h2>Risk note</h2>
            <textarea value={draft?.body ?? ""} onChange={(event) => setDraft((current) => (current ? { ...current, body: event.target.value } : current))} />
            <div className="row">
              <button type="button" className="primary" disabled={!draft || saveDraft.isPending} onClick={() => saveDraft.mutate()}>
                Save edits
              </button>
              <a href={apiUrl(`/api/safety/cameras/${code}/report.html`)} target="_blank" rel="noreferrer">
                Open HTML report
              </a>
            </div>
          </>
        )}
        <div className="actions">
          <button type="button" disabled={act.isPending} onClick={() => act.mutate({ kind: "risk" })}>
            Generate risk assessment
          </button>
          <button type="button" onClick={() => { videoRef.current?.pause(); setMode("prevent") }}>
            Prevent this
          </button>
          <button type="button" disabled={act.isPending} onClick={() => act.mutate({ kind: "training" })}>
            Recommend training
          </button>
          <button type="button" disabled={act.isPending} onClick={() => act.mutate({ kind: "escalate" })}>
            Escalate incident
          </button>
        </div>
        {act.isError && <p className="command-error">{(act.error as Error).message}</p>}
        <h3>Response queue</h3>
        <ul className="queue">
          {mine.map((item) => (
            <li key={item.id}>
              <strong>{item.kind}</strong> · {item.status}
              <span>{item.title}</span>
            </li>
          ))}
          {mine.length === 0 && <li>Nothing saved for this camera yet.</li>}
        </ul>
      </aside>
    </div>
  )
}

function FeedOverlay({ code, time }: { code: string; time: number }) {
  const detections = useQuery({
    queryKey: ["safety-detections", code],
    queryFn: () => api<{ frames: DetectionFrame[] }>(`/api/safety/cameras/${code}/detections`),
  })
  const boxes = nearestBoxes(detections.data?.frames ?? [], time)
  return (
    <>
      {boxes.map((box, index) => (
        <div
          key={`${box.label}-${index}`}
          className="detect-box"
          style={{ left: `${box.x * 100}%`, top: `${box.y * 100}%`, width: `${box.w * 100}%`, height: `${box.h * 100}%` }}
        >
          <span>
            {box.label} {box.confidence.toFixed(2)}
          </span>
        </div>
      ))}
    </>
  )
}

function SeparationSketch({
  box,
}: {
  box?: { x: number; y: number; w: number; h: number }
}) {
  const cx = box ? (box.x + box.w / 2) * 100 : 50
  const cy = box ? (box.y + box.h * 0.72) * 100 : 70
  const laneEnd = Math.max(12, cx - 4)
  return (
    <svg className="plan" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <circle className="ring" cx={cx} cy={cy - 8} r="9" />
      <path className="lane" d={`M 3 ${Math.min(92, cy + 10)} H ${laneEnd}`} />
      <path className="barrier" d={`M ${Math.min(96, cx + 8)} ${Math.max(18, cy - 18)} H 97`} />
      <text className="plan-label" x="4" y="96">
        Proposed lane
      </text>
    </svg>
  )
}

function nearestBoxes(frames: DetectionFrame[], time: number) {
  let best: DetectionFrame | null = null
  let gap = 0.35
  for (const frame of frames) {
    const delta = Math.abs(frame.time_sec - time)
    if (delta < gap) {
      gap = delta
      best = frame
    }
  }
  return best?.boxes ?? []
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}
