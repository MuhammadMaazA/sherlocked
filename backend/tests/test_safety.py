from app.services.safety import classify_text, investigation, load_wall


def test_contact_requires_caption_language():
    assert classify_text("The person makes contact with the forklift and runs away.") == "contact"
    assert classify_text("A person walks near a forklift in an aisle.") == "routine"
    assert classify_text("The person climbs onto the forklift and operates it.") == "other_safety_concern"
    assert (
        classify_text("The person is running near the forklift. The exact cause is not clear from the video.")
        == "potential_near_miss"
    )
    assert classify_text("The person steps back, maintaining a safe distance.") == "routine"


def test_wall_has_one_takeover_on_the_contact_window(client):
    wall = client.get("/api/safety/wall")
    assert wall.status_code == 200
    body = wall.json()
    assert body["mode"] == "indexed_footage_replay"
    assert body["feeds"] == 9
    takeovers = [camera for camera in body["cameras"] if camera["takeover"]]
    assert len(takeovers) == 1
    assert takeovers[0]["code"] == "WH-07"
    assert takeovers[0]["takeover"]["start"] == 5.0
    assert takeovers[0]["takeover"]["end"] == 10.0
    assert "contact" in takeovers[0]["takeover"]["headline"].lower() or "contact" in takeovers[0]["takeover"]["category"]
    assert "injury" not in wall.text.lower()
    assert body["events_flagged"] >= 3
    assert body["awaiting_review"] == body["events_flagged"]
    routine = [camera["code"] for camera in body["cameras"] if all(segment["category"] == "routine" for segment in camera["segments"])]
    assert len(routine) >= 3


def test_investigation_does_not_invent_identity(client):
    response = client.get("/api/safety/cameras/WH-07")
    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "contact"
    assert "unidentified" in body["person_annotation"].lower()
    assert body["window"]["precision"] == "segment"
    blob = response.text.lower()
    assert "employee id" not in blob
    assert "injury" not in body["observed"].lower()
    assert "makes contact" in body["observed"].lower()


def test_actions_persist_and_clear_the_review_count(client):
    created = client.post("/api/safety/actions", json={"camera": "WH-07", "kind": "escalate"})
    assert created.status_code == 201
    action = created.json()
    assert action["status"] == "pending_human_review"
    edited = client.patch(f"/api/safety/actions/{action['id']}", json={"body": "Officer review still open."})
    assert edited.status_code == 200
    assert "Officer review" in edited.json()["body"]
    wall = client.get("/api/safety/wall").json()
    assert wall["awaiting_review"] == wall["events_flagged"] - 1
    report = client.get("/api/safety/cameras/WH-07/report.html")
    assert report.status_code == 200
    assert "ceiling_01" in report.text
    assert "Officer review" in report.text
    missing = client.post("/api/safety/actions", json={"camera": "WH-99", "kind": "escalate"})
    assert missing.status_code == 404


def test_prevent_overlay_is_stored(client):
    created = client.post(
        "/api/safety/actions",
        json={"camera": "WH-07", "kind": "prevent", "payload": {"x": 0.1, "y": 0.5, "w": 0.3, "h": 0.2}},
    )
    assert created.status_code == 201
    assert created.json()["payload"]["x"] == 0.1
    assert created.json()["status"] == "proposed"


def test_classify_module_matches_cached_contact():
    view = investigation("WH-07")
    assert view is not None
    assert view["category"] == "contact"
    wall = load_wall()
    assert {camera["code"] for camera in wall["cameras"]} == {f"WH-0{index}" for index in range(1, 10)}
