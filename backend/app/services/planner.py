"""Turn an investigator's question into a small set of search queries."""

from __future__ import annotations


def plan_queries(question: str) -> list[str]:
    text = " ".join(question.split())
    if not text:
        return []
    queries = [text[:300]]
    lowered = text.lower()
    extras: list[str] = []
    if any(word in lowered for word in ("forklift", "warehouse", "pallet", "aisle", "equipment")):
        extras = [
            "person standing or walking near a forklift",
            "forklift moving in a warehouse aisle",
        ]
    elif any(word in lowered for word in ("vehicle", "car", "truck", "intersection", "traffic")):
        extras = [
            "vehicle stopped near other vehicles or a person",
            "vehicle moving through the scene",
        ]
    elif any(word in lowered for word in ("person", "people", "someone", "individual")):
        extras = ["person walking through the scene"]
    for extra in extras:
        if extra.lower() not in lowered and extra not in queries:
            queries.append(extra)
    return queries[:3]


def contradiction_query(question: str) -> str:
    lowered = question.lower()
    if "forklift" in lowered or "warehouse" in lowered:
        return "forklift stationary in an empty warehouse aisle"
    if any(word in lowered for word in ("vehicle", "car", "truck")):
        return "road or street with no stopped vehicle and no pedestrian"
    return "empty scene with no people"
