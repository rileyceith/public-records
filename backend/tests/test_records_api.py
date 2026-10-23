from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.database as database
import app.main as main
from app.core.security import hash_password
from app.models import Agency, RecordType, User

PASSWORD = "long-enough-example-password"


@pytest.fixture
def ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database.configure_database("sqlite://")
    monkeypatch.setattr(main, "engine", database.engine)
    monkeypatch.setattr("app.api.attachments.UPLOAD_DIR", tmp_path / "attachments")
    monkeypatch.setattr("app.core.config.UPLOAD_DIR", tmp_path / "attachments")
    database.initialize_database()
    with database.SessionLocal() as db:
        agency = Agency(name="Test Agency", code="TEST")
        record_type = RecordType(name="Planning notice", default_access="public", fee=Decimal("25.00"))
        db.add_all([agency, record_type])
        db.add(
            User(
                email="admin@example.test",
                full_name="Test Administrator",
                password_hash=hash_password("correct horse battery staple"),
                role="admin",
                is_verified=True,
            )
        )
        db.commit()
        return {"agency": agency.id, "type": record_type.id}


@pytest.fixture
def client(ids):
    with TestClient(main.app) as test_client:
        yield test_client


def login(client: TestClient, email: str = "admin@example.test", password: str = "correct horse battery staple") -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": "Bearer " + token}


def record_payload(number: str, ids: dict, **overrides) -> dict:
    payload = {
        "record_number": number,
        "title": f"Planning notice {number}",
        "summary": "A sample public record used by the automated tests.",
        "record_type_id": ids["type"],
        "agency_id": ids["agency"],
        "date_of_event": "2025-02-14",
        "location_address": "1 Test Street",
        "latitude": 51.5,
        "longitude": -0.12,
        "tags": ["sample"],
    }
    payload.update(overrides)
    return payload


def make_user(client: TestClient, admin: dict, email: str, role: str, **extra) -> dict:
    response = client.post(
        "/api/auth/users",
        headers=admin,
        json={"email": email, "full_name": "Test " + role, "password": PASSWORD, "role": role, **extra},
    )
    assert response.status_code == 201, response.text
    return auth(login(client, email, PASSWORD))


def publish(client: TestClient, headers: dict, record_id: str) -> None:
    assert client.post(f"/api/records/{record_id}/publish", headers=headers).status_code == 200


def test_workflow_visibility_and_versions(client: TestClient, ids: dict):
    admin = auth(login(client))
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.post("/api/records", json=record_payload("P-001", ids)).status_code == 401

    created = client.post("/api/records", json=record_payload("P-001", ids), headers=admin)
    assert created.status_code == 201
    record = created.json()
    assert record["status"] == "draft" and record["version"] == 1
    assert client.get(f"/api/records/{record['id']}").status_code == 404
    assert client.get("/api/records").json()["total"] == 0

    publish(client, admin, record["id"])
    assert client.get("/api/records", params={"q": "sample"}).json()["total"] == 1

    updated = client.put(
        f"/api/records/{record['id']}", json=record_payload("P-001", ids, title="Updated notice"), headers=admin
    )
    assert updated.status_code == 200 and updated.json()["version"] == 2
    assert client.post("/api/records", json=record_payload("P-001", ids), headers=admin).status_code == 409

    redacted = client.post(
        f"/api/records/{record['id']}/redact", json={"fields": ["summary", "location_address"]}, headers=admin
    )
    body = redacted.json()
    assert redacted.status_code == 200 and body["status"] == "redacted" and body["summary"] == "[REDACTED]"

    assert client.post(f"/api/records/{record['id']}/archive", headers=admin).status_code == 200
    assert client.get(f"/api/records/{record['id']}").status_code == 404
    assert client.get(f"/api/records/{record['id']}", headers=admin).status_code == 200


def test_restricted_records_and_access_requests(client: TestClient, ids: dict):
    admin = auth(login(client))
    record = client.post(
        "/api/records", json=record_payload("R-001", ids, access_level="restricted", title="Sealed ruling"), headers=admin
    ).json()
    secret = client.post(
        "/api/records", json=record_payload("C-001", ids, access_level="confidential"), headers=admin
    ).json()
    publish(client, admin, record["id"])
    publish(client, admin, secret["id"])
    upload = client.post(
        f"/api/records/{record['id']}/attachments",
        headers=admin,
        files={"file": ("ruling.txt", b"Ruling text mentioning jaguar", "text/plain")},
    )
    assert upload.status_code == 201 and upload.json()["checksum_sha256"]
    attachment_id = upload.json()["id"]

    metadata = client.get(f"/api/records/{record['id']}").json()
    assert metadata["can_access"] is False and metadata["attachments"] == []
    assert client.get(f"/api/records/{secret['id']}").status_code == 404
    assert client.get(f"/api/attachments/{attachment_id}/download").status_code in (401, 403, 404)
    assert client.get("/api/records", params={"q": "jaguar"}).json()["total"] == 0

    registered = client.post(
        "/api/auth/register", json={"email": "citizen@example.test", "full_name": "Cit Izen", "password": PASSWORD}
    )
    assert registered.status_code == 201
    citizen = auth(login(client, "citizen@example.test", PASSWORD))
    request_body = {"record_id": record["id"], "request_type": "certified_copy", "purpose": "Needed for a court filing"}
    assert client.post("/api/access-requests", json=request_body, headers=citizen).status_code == 403

    assert client.patch(f"/api/auth/users/{registered.json()['id']}", json={"is_verified": True}, headers=admin).status_code == 200
    created = client.post("/api/access-requests", json=request_body, headers=citizen)
    assert created.status_code == 201, created.text
    request = created.json()
    assert Decimal(str(request["fee_amount"])) == Decimal("25.00") and request["payment_status"] == "unpaid"
    assert client.post(f"/api/access-requests/{request['id']}/approve", headers=citizen).status_code == 403
    assert client.post(f"/api/access-requests/{request['id']}/deny", json={}, headers=admin).status_code == 422
    assert client.post(f"/api/access-requests/{request['id']}/approve", headers=admin).status_code == 200
    assert client.get(f"/api/attachments/{attachment_id}/download", headers=citizen).status_code in (403, 404)
    assert client.post(f"/api/access-requests/{request['id']}/mark-paid", headers=admin).status_code == 200

    download = client.get(f"/api/attachments/{attachment_id}/download", headers=citizen)
    assert download.status_code == 200 and download.content == b"Ruling text mentioning jaguar"
    assert client.get(f"/api/records/{secret['id']}", headers=citizen).status_code == 404
    assert client.get(f"/api/records/{record['id']}", headers=citizen).json()["can_access"] is True


def test_clerk_scope_parties_and_audit(client: TestClient, ids: dict):
    admin = auth(login(client))
    clerk = make_user(client, admin, "clerk@example.test", "clerk", agency_id=ids["agency"])
    other = client.post("/api/agencies", json={"name": "Other Agency", "code": "OTH"}, headers=admin).json()
    assert client.post("/api/records", json=record_payload("K-001", ids, agency_id=other["id"]), headers=clerk).status_code == 403

    record = client.post("/api/records", json=record_payload("K-001", ids), headers=clerk)
    assert record.status_code == 201
    record_id = record.json()["id"]
    assert client.post("/api/agencies", json={"name": "X", "code": "XX"}, headers=clerk).status_code == 403
    assert client.get("/api/audit", headers=clerk).status_code == 403

    party = client.post(
        f"/api/records/{record_id}/parties",
        json={"full_name": "Jane Owner", "role": "owner", "id_number": "AB 123456"},
        headers=clerk,
    )
    assert party.status_code in (200, 201), party.text
    assert "123456" not in party.text and "id_hash" not in party.text
    link_id = party.json()["parties"][0]["id"]
    assert client.delete(f"/api/records/{record_id}/parties/{link_id}", headers=clerk).json()["parties"] == []

    auditor = make_user(client, admin, "auditor@example.test", "auditor")
    events = client.get("/api/audit", params={"record_id": record_id}, headers=auditor).json()["items"]
    assert len(events) >= 2
    assert client.put(f"/api/records/{record_id}", json=record_payload("K-001", ids), headers=auditor).status_code == 403
    assert client.delete(f"/api/records/{record_id}", headers=clerk).status_code == 403


def test_search_suggest_and_near(client: TestClient, ids: dict):
    admin = auth(login(client))
    near = client.post(
        "/api/records", json=record_payload("S-001", ids, title="Harbour wall survey", tags=["coast"]), headers=admin
    ).json()
    far = client.post(
        "/api/records", json=record_payload("S-002", ids, title="Mountain road", latitude=40.0, longitude=-3.7), headers=admin
    ).json()
    publish(client, admin, near["id"])
    publish(client, admin, far["id"])

    suggestions = client.get("/api/records/suggest", params={"prefix": "Har"}).json()
    assert "Harbour wall survey" in str(suggestions)
    assert client.get("/api/records", params={"tag": "coast"}).json()["total"] == 1
    nearby = client.get("/api/records", params={"near_lat": 51.5, "near_lng": -0.12, "radius_km": 5}).json()
    assert [item["record_number"] for item in nearby["items"]] == ["S-001"]


def test_attachments_ocr_and_validation(client: TestClient, ids: dict):
    admin = auth(login(client))
    record_id = client.post("/api/records", json=record_payload("A-001", ids), headers=admin).json()["id"]
    publish(client, admin, record_id)
    bad = client.post(
        f"/api/records/{record_id}/attachments", headers=admin, files={"file": ("x.exe", b"nope", "application/octet-stream")}
    )
    assert bad.status_code == 415
    pdf = client.post(
        f"/api/records/{record_id}/attachments", headers=admin, files={"file": ("scan.pdf", b"%PDF-1.4", "application/pdf")}
    ).json()
    assert client.post(f"/api/attachments/{pdf['id']}/ocr", headers=admin).status_code == 501
    note = client.post(
        f"/api/records/{record_id}/attachments", headers=admin, files={"file": ("notes.txt", b"quarterly minutes", "text/plain")}
    ).json()
    download = client.get(f"/api/attachments/{note['id']}/download")
    assert download.status_code == 200 and download.headers["content-disposition"].startswith("attachment;")
    assert client.delete(f"/api/attachments/{note['id']}", headers=admin).status_code == 204
    assert client.delete(f"/api/records/{record_id}", headers=admin).status_code == 204


def test_login_and_validation_errors(client: TestClient, ids: dict):
    assert client.post("/api/auth/login", json={"email": "admin@example.test", "password": "wrong password"}).status_code == 401
    admin = auth(login(client))
    short = client.post(
        "/api/auth/users", headers=admin, json={"email": "s@example.test", "full_name": "Short Pass", "password": "short"}
    )
    assert short.status_code == 422
    assert client.post("/api/records", headers=admin, json=record_payload("", ids)).status_code == 422
    events = client.get("/api/audit", headers=admin).json()["items"]
    assert all("password" not in str(event["details"]).lower() for event in events)
