from app.providers.vast import normalize_search_hit, parse_labels
from app.services.timeline import build_timeline
from app.services.validation import validate_hypotheses


def test_parse_labels():
    assert parse_labels("person, forklift") == ["person", "forklift"]
    assert parse_labels(["car"]) == ["car"]
    assert parse_labels(None) == []


def test_normalize_keeps_source_offsets():
    hit = normalize_search_hit(
        {
            "source": "s3://segments/clip.mp4",
            "original_video": "s3://chunks/parent.mp4",
            "reasoning_content": "A person walks away from a forklift.",
            "camera_id": "sdg_warehouse_cam-2",
            "location": "warehouse3",
            "segment_start_sec": 5.0,
            "segment_end_sec": 10.0,
            "similarity_score": 0.55,
            "object_classes": "person",
            "filename": "clip.mp4",
            "upload_timestamp": "2026-10-01T07:45:12",
            "cosmos_model": "nvidia/cosmos3-nano-reasoner",
        }
    )
    assert hit["source_segment_id"] == "s3://segments/clip.mp4"
    assert hit["source_video_id"] == "s3://chunks/parent.mp4"
    assert hit["start_seconds"] == 5.0
    assert hit["metadata"]["score_meaning"] == "hybrid_similarity"
    assert "probability" not in hit["metadata"]["score_meaning"]


def test_next_steps_drop_identity_and_non_strings():
    from app.services.investigation import _plain_steps

    assert _plain_steps(
        [
            {"description": "Verify the identity of the person."},
            "Verify the identity of the person.",
            "Determine the purpose of the departure.",
            "Open each cited segment.",
        ]
    ) == ["Open each cited segment."]


def test_dict_bullets_are_rewritten_and_raw_objects_are_dropped():
    from app.services.validation import bullets_citing

    known = {"ev_a"}
    lines = bullets_citing(
        [
            {"id": "ev_a", "description": "A person stands near a forklift."},
            {"id": "ev_missing", "description": "Not retrieved."},
            "no id here",
            "ev_a is a caption",
        ],
        known,
    )
    assert lines == [
        "ev_a: A person stands near a forklift.",
        "ev_a is a caption",
    ]


def test_unknown_evidence_ids_are_removed_and_support_is_downgraded():
    evidence = [
        {"id": "ev_a", "source_video_id": "parent-1"},
        {"id": "ev_b", "source_video_id": "parent-2"},
    ]
    cleaned = validate_hypotheses(
        [
            {
                "statement": "A vehicle left by the north exit.",
                "supporting_evidence_ids": ["ev_a", "ev_missing"],
                "contradicting_evidence_ids": ["ev_ghost"],
                "unresolved_questions": ["Which exit?"],
                "status": "supported",
            }
        ],
        evidence,
    )
    assert cleaned[0]["supporting_evidence_ids"] == ["ev_a"]
    assert cleaned[0]["contradicting_evidence_ids"] == []
    assert cleaned[0]["status"] == "unverified"


def test_timeline_does_not_interleave_parents():
    evidence = [
        {
            "id": "ev_late",
            "source_video_id": "parent-a",
            "camera_id": "cam",
            "filename": "a2.mp4",
            "metadata": {"parent_filename": "parent-a.mp4"},
            "start_seconds": 10,
            "end_seconds": 15,
            "observation": "second",
        },
        {
            "id": "ev_other",
            "source_video_id": "parent-b",
            "camera_id": "cam",
            "filename": "b.mp4",
            "metadata": {},
            "start_seconds": 1,
            "end_seconds": 2,
            "observation": "other recording",
        },
        {
            "id": "ev_early",
            "source_video_id": "parent-a",
            "camera_id": "cam",
            "filename": "a1.mp4",
            "metadata": {"parent_filename": "parent-a.mp4"},
            "start_seconds": 0,
            "end_seconds": 5,
            "observation": "first",
        },
    ]
    timeline = build_timeline("case_1", evidence)
    groups = {group["group_id"]: group for group in timeline["groups"]}
    assert list(groups) == ["parent-a", "parent-b"] or set(groups) == {"parent-a", "parent-b"}
    assert [event["relative_time"] for event in groups["parent-a"]["events"]] == [0, 10]
    assert groups["parent-a"]["events"][0]["evidence_ids"] == ["ev_early"]
    assert all(event["absolute_time"] is None for group in timeline["groups"] for event in group["events"])
