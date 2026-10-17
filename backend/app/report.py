"""HTML investigation report. Evidence statements stay tied to ids."""

from __future__ import annotations

import html
from typing import Any


def render_report(case: dict[str, Any], investigation: dict[str, Any] | None) -> str:
    title = html.escape(case["title"])
    description = html.escape(case["description"])
    if not investigation:
        body = "<p>No investigation has been run for this case.</p>"
    else:
        findings = investigation.get("findings") or {}
        evidence = investigation.get("evidence") or []
        timeline = investigation.get("timeline") or {}
        hypotheses = investigation.get("hypotheses") or []

        def items(lines: list[str]) -> str:
            if not lines:
                return "<p>None recorded.</p>"
            return "<ul>" + "".join(f"<li>{html.escape(line)}</li>" for line in lines) + "</ul>"

        evidence_rows = []
        for item in evidence:
            evidence_rows.append(
                "<tr>"
                f"<td>{html.escape(item.get('id') or '')}</td>"
                f"<td>{html.escape(str(item.get('camera_id') or ''))}</td>"
                f"<td>{html.escape(str(item.get('start_seconds')))}–{html.escape(str(item.get('end_seconds')))}s</td>"
                f"<td>{html.escape(', '.join(item.get('object_labels') or []))}</td>"
                f"<td>{html.escape(item.get('observation') or '')}</td>"
                "</tr>"
            )
        group_blocks = []
        for group in timeline.get("groups") or []:
            events = "".join(
                f"<li>{html.escape(str(event.get('relative_time')))}s — {html.escape(event.get('description') or '')} "
                f"({html.escape(', '.join(event.get('evidence_ids') or []))})</li>"
                for event in group.get("events") or []
            )
            group_blocks.append(
                f"<h3>{html.escape(group.get('label') or 'Recording')}</h3>"
                f"<p>{html.escape(group.get('clock_note') or '')}</p><ol>{events}</ol>"
            )
        hypothesis_blocks = []
        for hypothesis in hypotheses:
            hypothesis_blocks.append(
                f"<article><p><strong>{html.escape(hypothesis.get('status') or '')}</strong> — "
                f"{html.escape(hypothesis.get('statement') or '')}</p>"
                f"<p>Supports: {html.escape(', '.join(hypothesis.get('supporting_evidence_ids') or []))}</p>"
                f"<p>Conflicts: {html.escape(', '.join(hypothesis.get('contradicting_evidence_ids') or []) or 'none')}</p>"
                "</article>"
            )
        note = findings.get("synthesis_note")
        synthesis = f"<h2>Index synthesis</h2><p>{html.escape(note)}</p>" if note else ""
        body = f"""
        <h2>What was observed</h2>
        {items(findings.get("observed") or [])}
        <h2>What was inferred</h2>
        {items(findings.get("inferred") or [])}
        <h2>What remains uncertain</h2>
        {items(findings.get("uncertain") or [])}
        <h2>Evidence</h2>
        <table>
          <thead><tr><th>Id</th><th>Camera</th><th>Offset</th><th>Detections</th><th>Caption</th></tr></thead>
          <tbody>{''.join(evidence_rows) or '<tr><td colspan="5">No evidence.</td></tr>'}</tbody>
        </table>
        <h2>Timeline</h2>
        <p>{html.escape(timeline.get('note') or '')}</p>
        {''.join(group_blocks) or '<p>No events.</p>'}
        <h2>Hypotheses</h2>
        {''.join(hypothesis_blocks) or '<p>No hypotheses.</p>'}
        <h2>Recommended next steps</h2>
        {items(findings.get("next_steps") or [])}
        {synthesis}
        <p class="meta">Reasoner: {html.escape(str(investigation.get('reasoner')))}.
        Retrieval calls: {html.escape(str(investigation.get('retrieval_calls')))}.
        Elapsed: {html.escape(str(investigation.get('elapsed_ms')))} ms.</p>
        """
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Sherlocked report — {title}</title>
  <style>
    body {{ font-family: Georgia, serif; margin: 2rem auto; max-width: 900px; color: #1b1f24; line-height: 1.45; }}
    h1 {{ font-family: "IBM Plex Sans", sans-serif; font-size: 1.6rem; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 0.92rem; }}
    td, th {{ border: 1px solid #d5dbe3; padding: 0.4rem; vertical-align: top; }}
    .banner {{ background: #f4f1e8; padding: 0.8rem 1rem; }}
    .meta {{ color: #526070; }}
  </style>
</head>
<body>
  <p class="banner">Sherlocked assists a human review. This report does not determine guilt, infer intent, or identify a person. Captions are model output from the indexed archive.</p>
  <h1>{title}</h1>
  <p>{description}</p>
  <p>Location: {html.escape(case.get('location') or 'not set')} · Cameras: {html.escape(', '.join(case.get('camera_ids') or []) or 'not filtered')}</p>
  {body}
</body>
</html>"""
