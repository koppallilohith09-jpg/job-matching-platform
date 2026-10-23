from pathlib import Path
from typing import Literal
from fastapi import Request, Response, HTTPException
from pydantic import BaseModel, Field, model_validator
from platform_core import create_app
from domain import Jobs, extract_skills, resume_text

ROOT = Path(__file__).parent
engine = Jobs(ROOT)
app = create_app(ROOT, "Shortlist")


def require_user(request, role=None):
    user = engine.user(request.cookies.get("shortlist"))
    if not user:
        raise HTTPException(401, "Sign in to continue.")
    if role and user["role"] != role:
        raise HTTPException(403, "This action is available to " + role + " accounts.")
    return user


class Register(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=12, max_length=200)
    name: str = Field(min_length=1, max_length=80)
    role: Literal["candidate", "employer"]


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=200)


class Profile(BaseModel):
    skills: list[str] = Field(max_length=50)
    summary: str = Field(default="", max_length=3000)

    @model_validator(mode="after")
    def bounded_skills(self):
        if any(len(s) > 60 for s in self.skills):
            raise ValueError("Skills must be short labels.")
        return self


class Resume(BaseModel):
    filename: str = Field(max_length=180)
    content: str = Field(max_length=4_100_000)


class Posting(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    company: str = Field(min_length=1, max_length=80)
    location: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=30, max_length=6000)
    skills: list[str] = Field(min_length=1, max_length=30)
    salary_min: int = Field(ge=0, le=10000000)
    salary_max: int = Field(ge=0, le=10000000)

    @model_validator(mode="after")
    def salary_range(self):
        if self.salary_max < self.salary_min or any(not s.strip() or len(s) > 60 for s in self.skills):
            raise ValueError("Check salary range and skill labels.")
        return self


class Status(BaseModel):
    status: Literal["Reviewing", "Interview", "Offered", "Rejected", "Withdrawn"]


@app.get("/api/state")
def state(request: Request):
    user = engine.user(request.cookies.get("shortlist"))
    return {"user": user, "jobs": engine.jobs(user), "profile": engine.profile(user["id"]) if user else None}


@app.post("/api/register")
def register(body: Register):
    return engine.register(body.username, body.password, body.name, body.role)


@app.post("/api/login")
def login(body: Login, request: Request, response: Response):
    token = engine.login(body.username, body.password, request.client.host if request.client else "local")
    response.set_cookie("shortlist", token, httponly=True, samesite="strict", max_age=86400, secure=False)
    return {"ok": True}


@app.post("/api/logout")
def logout(request: Request, response: Response):
    engine.logout(request.cookies.get("shortlist"))
    response.delete_cookie("shortlist")
    return {"ok": True}


@app.post("/api/profile")
def profile(body: Profile, request: Request):
    user = require_user(request, "candidate")
    return engine.save_profile(user["id"], body.skills, body.summary)


@app.post("/api/resume")
def parse_resume(body: Resume, request: Request):
    require_user(request, "candidate")
    text = resume_text(body.filename, body.content)
    return {"skills": extract_skills(text), "excerpt": text[:1500], "characters": len(text)}


@app.post("/api/jobs")
def post(body: Posting, request: Request):
    user = require_user(request, "employer")
    return engine.post(user, body.model_dump())


@app.post("/api/jobs/{job_id}/apply")
def apply(job_id: int, request: Request):
    engine.apply(require_user(request, "candidate"), job_id)
    return {"ok": True}


@app.get("/api/applications")
def applications(request: Request):
    return engine.applications(require_user(request))


@app.post("/api/applications/{application_id}")
def transition(application_id: int, body: Status, request: Request):
    engine.transition(require_user(request), application_id, body.status)
    return {"ok": True}
