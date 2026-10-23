import base64
from domain import match, extract_skills

PASSWORD = "Test-only-passphrase-2026"


def sign_up(c, username, role):
    result = c.post("/api/register", json={"username": username, "password": PASSWORD, "name": username.title(), "role": role})
    assert result.status_code == 200
    assert c.post("/api/login", json={"username": username, "password": PASSWORD}).status_code == 200
    return result.json()


def test_skills_are_literal_and_explained():
    assert match(["python", "sql"], ["python", "docker"]) == {"score": .5, "matched": ["python"], "missing": ["docker"]}
    assert extract_skills("Python and SQL. Javascript, not Java. Django and Git.") == ["django", "git", "java", "javascript", "python", "sql"]


def test_candidate_profile_parse_and_duplicate_application(workspace):
    c = workspace.client
    assert c.post("/api/profile", json={"skills": [], "summary": ""}).status_code == 401
    sign_up(c, "candidate", "candidate")
    encoded = base64.b64encode(b"Python developer with SQL, Docker, and FastAPI experience.").decode()
    parsed = c.post("/api/resume", json={"filename": "resume.txt", "content": encoded}).json()
    assert "python" in parsed["skills"]
    # Parsing must not silently save a profile.
    assert c.get("/api/state").json()["profile"]["skills"] == []
    assert c.post("/api/profile", json={"skills": parsed["skills"], "summary": "Candidate supplied summary."}).status_code == 200
    assert c.post("/api/jobs/1/apply").status_code == 200
    assert c.post("/api/jobs/1/apply").status_code == 400
    app_id = c.get("/api/applications").json()[0]["id"]
    assert c.post("/api/applications/" + str(app_id), json={"status": "Withdrawn"}).status_code == 200
    assert c.post("/api/jobs", json={"title": "bad"}).status_code == 422
    c.post("/api/logout")
    assert c.get("/api/applications").status_code == 401


def test_employer_ownership_and_state_transitions(workspace):
    c = workspace.client
    sign_up(c, "employer", "employer")
    body = dict(title="Python Engineer", company="Test Company", location="Remote",
                skills=["python", "sql"], description="Build maintainable backend services with a small collaborative team.",
                salary_min=50000, salary_max=70000)
    job = c.post("/api/jobs", json=body).json()
    assert not job["demo"]
    assert c.post("/api/profile", json={"skills": [], "summary": ""}).status_code == 403
    c.post("/api/logout")
    sign_up(c, "applicant", "candidate")
    assert c.post("/api/jobs/" + str(job["id"]) + "/apply").status_code == 200
    application = c.get("/api/applications").json()[0]
    c.post("/api/logout")
    sign_up(c, "other_employer", "employer")
    assert c.get("/api/applications").json() == []
    assert c.post("/api/applications/" + str(application["id"]), json={"status": "Reviewing"}).status_code == 400
    c.post("/api/logout")
    c.post("/api/login", json={"username": "employer", "password": PASSWORD})
    assert len(c.get("/api/applications").json()) == 1
    assert c.post("/api/applications/" + str(application["id"]), json={"status": "Offered"}).status_code == 400
    assert c.post("/api/applications/" + str(application["id"]), json={"status": "Reviewing"}).status_code == 200
    assert c.post("/api/applications/" + str(application["id"]), json={"status": "Interview"}).status_code == 200


def test_password_hashing_and_cookie_flags(workspace):
    c = workspace.client
    sign_up(c, "secure_test", "candidate")
    with workspace.engine.store.transaction() as db:
        user = db.execute("SELECT password_hash FROM users WHERE username='secure_test'").fetchone()
    assert PASSWORD not in user["password_hash"]
    response = c.post("/api/login", json={"username": "secure_test", "password": PASSWORD})
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    assert c.post("/api/login", json={"username": "secure_test", "password": "incorrect"}).status_code == 400
