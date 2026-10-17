def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    deep = client.get("/api/health")
    assert deep.status_code == 200
    body = deep.json()
    assert body["provider"] == "mock"
    assert body["synthetic"] is True


def test_create_and_fetch_case(client):
    created = client.post(
        "/api/cases",
        json={"title": "Warehouse check", "description": "Person near a forklift", "camera_ids": ["sdg_warehouse_cam-2"], "location": "warehouse3"},
    )
    assert created.status_code == 201
    case_id = created.json()["id"]
    fetched = client.get(f"/api/cases/{case_id}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Warehouse check"
    listing = client.get("/api/cases")
    assert any(item["id"] == case_id for item in listing.json()["cases"])


def test_invalid_case(client):
    response = client.post("/api/cases", json={"title": "", "description": "x"})
    assert response.status_code == 422


def test_missing_case(client):
    assert client.get("/api/cases/case_missing").status_code == 404
    assert client.post("/api/cases/case_missing/investigate", json={}).status_code == 404


def test_search_and_investigate_cites_real_fixtures(client):
    created = client.post(
        "/api/cases",
        json={
            "title": "Synthetic warehouse",
            "description": "Find a person near a forklift and reconstruct the sequence.",
            "camera_ids": ["sdg_warehouse_cam-2"],
            "location": "warehouse3",
        },
    )
    case_id = created.json()["id"]
    search = client.post("/api/videos/search", json={"query": "person near forklift", "camera_id": "sdg_warehouse_cam-2"})
    assert search.status_code == 200
    results = search.json()["results"]
    assert results
    assert all("SYNTHETIC FIXTURE" in item["observation"] for item in results)
    assert all(item["camera_id"] == "sdg_warehouse_cam-2" for item in results)
    investigation = client.post(f"/api/cases/{case_id}/investigate", json={})
    assert investigation.status_code == 200
    body = investigation.json()
    evidence_ids = {item["id"] for item in body["evidence"]}
    assert evidence_ids
    for item in body["evidence"]:
        assert "SYNTHETIC FIXTURE" in item["observation"]
    for group in body["timeline"]["groups"]:
        times = [event["relative_time"] for event in group["events"]]
        assert times == sorted(times)
    assert len(body["timeline"]["groups"]) == 1
    for hypothesis in body["hypotheses"]:
        assert set(hypothesis["supporting_evidence_ids"]).issubset(evidence_ids)
        assert set(hypothesis["contradicting_evidence_ids"]).issubset(evidence_ids)
    for line in body["findings"]["observed"]:
        assert any(evidence_id in line for evidence_id in evidence_ids)
    stream = client.get(f"/api/media/stream?item_id={results[0]['id']}")
    assert stream.status_code == 404
    assert "Synthetic" in stream.json()["detail"]


def test_unsynchronised_recordings_stay_in_separate_groups(client):
    created = client.post(
        "/api/cases",
        json={"title": "Mixed", "description": "person and vehicle activity"},
    )
    body = client.post(f"/api/cases/{created.json()['id']}/investigate", json={}).json()
    groups = body["timeline"]["groups"]
    assert len(groups) == 2
    parents = {group["group_id"] for group in groups}
    assert "mock://parents/warehouse-parent-a" in parents
    assert "mock://parents/street-parent-b" in parents
    warehouse = next(group for group in groups if group["group_id"].endswith("warehouse-parent-a"))
    assert [event["relative_time"] for event in warehouse["events"]] == [0.0, 5.0]
    assert all(event["absolute_time"] is None for group in groups for event in group["events"])


def test_empty_search(client):
    response = client.post("/api/videos/search", json={"query": "nothing here", "camera_id": "no-camera"})
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_ask_rejects_unknown_by_only_citing_retrieved_ids(client):
    created = client.post(
        "/api/cases",
        json={"title": "Ask", "description": "person near a forklift", "camera_ids": ["sdg_warehouse_cam-2"]},
    )
    case_id = created.json()["id"]
    client.post(f"/api/cases/{case_id}/investigate", json={})
    answer = client.post(f"/api/cases/{case_id}/ask", json={"question": "What remains uncertain about the forklift?"})
    assert answer.status_code == 200
    evidence = {item["id"] for item in client.get(f"/api/cases/{case_id}/evidence").json()["evidence"]}
    assert set(answer.json()["evidence_ids"]).issubset(evidence)
    for evidence_id in answer.json()["evidence_ids"]:
        assert evidence_id in answer.json()["answer"]
