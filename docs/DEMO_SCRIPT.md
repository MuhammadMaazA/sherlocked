# Demo script (about three minutes)

Use the deployed App button, or `http://127.0.0.1:8000` on the VM. The provider badge must say the archive is connected, not synthetic fixtures.

**0:00** Investigators otherwise scrub hours of multi-camera footage by hand. Sherlocked turns the indexed archive into a case: search, a per-recording timeline, and answers that have to cite a clip.

**0:25** Click **Open warehouse demo case**. The title is "Unusual activity near warehouse equipment". The camera is `sdg_warehouse_cam-2`, location `warehouse3`. The question asks for a person near a forklift and for what cannot be confirmed across clips.

**0:50** Click **Investigate**. The stage list should show several searches, then segments expanded from the top parent recordings. Evidence cards are Cosmos captions with YOLO labels and a similarity score. Say the score is a rank, not a probability.

**1:25** Click the `ceiling_04` event at 5–10 seconds, then the 0–5 second event in the same band. The player opens the real segment. Point at the amber note: that band is not aligned with the `eye_00` band beside it. Inside `eye_00`, the 0–5 second caption says the forklift begins to move and the person runs. That claim stays attached to that file.

**2:05** Click the follow-up "What evidence supports this interpretation, and what remains uncertain?" The answer should name evidence ids. A hypothesis is `supported` only when two segments share a parent. Anything that looks like the same person on another render stays `unverified`.

**2:35** The archive search is VAST. Captions are Cosmos Reason, vectors are Cosmos Embed, boxes are YOLO, all already on the pipeline running on CoreWeave. Wording beyond those captions goes through Weights & Biases inference and is dropped if it cites an id we did not retrieve.

Close: Sherlocked does not ask you to trust an AI-generated story. It shows the clip behind the finding.

If live search stalls, play the segment already saved on the case. Do not switch to the mock provider during the demo.
