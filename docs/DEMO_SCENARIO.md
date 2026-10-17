# Demo scenario

Warehouse activity on `sdg_warehouse_cam-2` (location `warehouse3`, capture type `warehouse`, 60 indexed segments).

This is the clearest real evidence in the team-17 archive for a sequence: the same parent recording has two 5-second segments, and the captions describe a person and a forklift changing over those offsets. It is not a theft, and the app must not turn it into one.

## Queries that returned footage

- `person near a forklift`
- `person standing or walking near a forklift`
- `forklift moving in a warehouse aisle`
- Contradiction probe: `forklift stationary in an empty warehouse aisle` (still returned forklift segments; it did not produce an empty aisle)

Filters: `camera_id=sdg_warehouse_cam-2`, `location=warehouse3`.

## Confirmed caption examples

These are indexed Cosmos Reason captions, not a human narrative. Parent files are separate renders (ceiling and eye viewpoints, different seeds). They share a camera id and must not be merged onto one clock or one identity.

**Parent** `...run_7_seed_900334964.ceiling_04.rgb_chunk_0000.mp4`

- 0.0–5.0s: a person in a light shirt and dark pants stands near a blue and brown forklift.
- 5.0–10.0s: a person in a light shirt and dark pants walks away from a blue and black forklift. The caption says the forklift remains stationary. YOLO label on the matched segment: `person`. Retrieval score on the 5–10s search hit was about 0.59.

**Parent** `...run_7_seed_900334964.eye_00.rgb_chunk_0000.mp4`

- 0.0–5.0s: a person stands near a blue forklift, the forklift begins to move, and the person turns and runs.
- 5.0–10.0s: a person walks away from a light blue forklift labelled ATLAS.

**Parent** `...run_3_seed_1053328212.ceiling_03.rgb_chunk_0000.mp4`

- 0.0–5.0s: a person in a white shirt, gray pants, and white hard hat stands near a blue and black forklift.
- 5.0–10.0s: a person walks away from a stationary forklift with its forks extended.

A further segment caption says a person in a white uniform is operating an ATLAS forklift. That is one caption, not confirmation that the person in the ceiling clip is the same individual.

## What the demo must say

- What is visible is whatever is in the open clip and its caption.
- A sequence is only claimed inside one parent file.
- Cross-file resemblance is unverified.
- The system did not re-ingest these clips. The existing captions were sufficient.

## If search is slow

Open the case that was already investigated and play `ceiling_04` segment 5.0–10.0s, which streamed as `video/mp4` during the build.
