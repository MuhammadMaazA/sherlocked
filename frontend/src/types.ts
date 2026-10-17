export type Health = {
  status: string
  provider: string
  synthetic: boolean
  reasoner: string
  video?: {
    authenticated?: boolean
    username?: string | null
    detail?: string
  }
}

export type CameraOption = { id: string; count?: number }

export type Catalog = {
  provider: string
  synthetic: boolean
  overview: Record<string, number | boolean | null>
  cameras: CameraOption[]
  locations: CameraOption[]
  capture_types: CameraOption[]
  objects?: { label: string; segment_count: number }[]
  videos: VideoSource[]
}

export type VideoSource = {
  id: string
  provider: string
  camera_id?: string | null
  location?: string | null
  title: string
  duration_seconds?: number | null
  capture_start_time?: string | null
  metadata: Record<string, unknown>
}

export type CaseRecord = {
  id: string
  title: string
  description: string
  location?: string | null
  incident_start?: string | null
  incident_end?: string | null
  status: string
  camera_ids: string[]
  created_at: string
  updated_at: string
  evidence_count: number
}

export type Evidence = {
  id: string
  case_id?: string | null
  camera_id?: string | null
  location?: string | null
  start_seconds?: number | null
  end_seconds?: number | null
  observation: string
  object_labels: string[]
  source_description: string
  retrieval_score?: number | null
  evidence_type: string
  filename?: string | null
  metadata: Record<string, unknown>
}

export type TimelineEvent = {
  id: string
  description: string
  event_type: string
  absolute_time?: string | null
  relative_time?: number | null
  end_seconds?: number | null
  evidence_ids: string[]
  verification_status: string
}

export type TimelineGroup = {
  group_id: string
  camera_id?: string | null
  location?: string | null
  label: string
  clock: string
  clock_note: string
  events: TimelineEvent[]
}

export type Timeline = {
  groups: TimelineGroup[]
  note: string
}

export type Hypothesis = {
  id: string
  statement: string
  supporting_evidence_ids: string[]
  contradicting_evidence_ids: string[]
  unresolved_questions: string[]
  status: string
}

export type Findings = {
  observed: string[]
  inferred: string[]
  uncertain: string[]
  next_steps: string[]
  synthesis_note?: string | null
}

export type Stage = { id: string; label: string; detail: string }

export type Message = {
  id: string
  case_id: string
  role: string
  content: string
  evidence_ids: string[]
  created_at: string
}

export type WallSegment = {
  start: number
  end: number
  category: string
  headline: string | null
  ticker: string
  observation: string
  labels: string[]
  display_labels: string[]
  filename: string
  takeover: boolean
  signals?: string[]
}

export type WallCamera = {
  code: string
  camera_id?: string | null
  location?: string | null
  parent_name: string
  segments: WallSegment[]
  takeover: { start: number; end: number; headline: string; category: string; filename: string } | null
}

export type SafetyAction = {
  id: string
  camera_code: string
  kind: string
  title: string
  body: string
  status: string
  payload: Record<string, number | string | boolean | null>
  created_at: string
}

export type SafetyWall = {
  mode: string
  disclaimer: string
  feeds: number
  events_flagged: number
  awaiting_review: number
  flagged_cameras: string[]
  cameras: WallCamera[]
  actions: SafetyAction[]
  engines?: { name: string; role: string }[]
}

export type SafetyView = {
  camera: string
  category: string
  headline: string
  window: { start: number; end: number; precision: string }
  observed: string
  filename: string
  parent_name: string
  display_labels: string[]
  signals?: string[]
  detector_labels: string[]
  person_annotation: string
  hypotheses: { text: string; status: string }[]
  uncertain: string[]
  review: string[]
  controls: string[]
  segments: WallSegment[]
}

export type DetectionFrame = {
  time_sec: number
  boxes: { label: string; confidence: number; x: number; y: number; w: number; h: number }[]
}

export type Investigation = {
  case_id: string
  question: string
  stages: Stage[]
  evidence: Evidence[]
  timeline: Timeline
  hypotheses: Hypothesis[]
  findings: Findings
  messages: Message[]
  reasoner: string
  retrieval_calls: number
  elapsed_ms: number
}
