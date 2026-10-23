"""Local accounts, explainable skill matching and application ownership."""
import base64
import hashlib
import hmac
import io
import json
import re
import secrets
import sqlite3
import time

from pypdf import PdfReader

from platform_core import Store, now

SKILLS = ["python", "sql", "javascript", "typescript", "react", "django", "fastapi", "flask", "postgresql",
          "docker", "kubernetes", "git", "linux", "aws", "azure", "pandas", "numpy", "scikit-learn",
          "tensorflow", "pytorch", "excel", "figma", "html", "css", "node.js", "redis", "testing",
          "statistics", "tableau", "power bi", "graphql", "rest", "java", "c++", "go", "rust"]


def extract_skills(text):
    lower = text.lower()
    return sorted(skill for skill in SKILLS if re.search(r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])", lower))


def match(profile_skills, required):
    own = {s.lower().strip() for s in profile_skills}
    found = [s for s in required if s.lower().strip() in own]
    missing = [s for s in required if s.lower().strip() not in own]
    return dict(score=len(found) / len(required) if required else 0, matched=found, missing=missing)


def demo_jobs():
    items = [
        ("Backend Engineer", "Northline", "Remote", ["python", "fastapi", "sql", "docker"], 85000, 110000),
        ("Data Analyst", "Common Ground", "Bengaluru", ["sql", "python", "pandas", "tableau"], 50000, 75000),
        ("Frontend Developer", "Aster Studio", "Remote", ["react", "typescript", "css", "testing"], 70000, 95000),
        ("Platform Engineer", "Rail & Route", "Hyderabad", ["linux", "docker", "kubernetes", "aws"], 95000, 125000),
        ("Machine Learning Engineer", "Fieldwork", "Remote", ["python", "scikit-learn", "statistics", "sql"], 90000, 120000),
        ("Product Designer", "Sunday Goods", "Pune", ["figma", "css", "html"], 60000, 85000),
    ]
    return [dict(id=i+1, employer_id=None, title=t, company=c, location=l, skills=s,
                 salary_min=low, salary_max=high, description="A fictional portfolio role at " + c + ". Work with the team to build and maintain useful products. Required skills: " + ", ".join(s) + ".",
                 created=now(), demo=True) for i, (t,c,l,s,low,high) in enumerate(items)]


class Jobs:
    def __init__(self, root):
        self.store = Store(root)
        self.attempts = {}
        with self.store.transaction() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                    role TEXT NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY, employer_id INTEGER REFERENCES users(id), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id INTEGER PRIMARY KEY REFERENCES users(id), skills TEXT NOT NULL, summary TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY, candidate_id INTEGER NOT NULL REFERENCES users(id),
                    job_id INTEGER NOT NULL REFERENCES jobs(id), status TEXT NOT NULL, created TEXT NOT NULL,
                    UNIQUE(candidate_id,job_id));
            """)
            if db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0:
                for item in demo_jobs():
                    db.execute("INSERT INTO jobs VALUES (?,?,?)", (item["id"], None, json.dumps(item)))

    def register(self, username, password, name, role):
        if not re.fullmatch(r"[a-z0-9_.-]{3,40}", username):
            raise ValueError("Username must be 3–40 lowercase letters, numbers, dots, dashes or underscores.")
        salt = secrets.token_hex(24)
        value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        try:
            with self.store.transaction() as db:
                result = db.execute("INSERT INTO users(username,name,role,salt,password_hash) VALUES (?,?,?,?,?)",
                                    (username, name, role, salt, value))
                uid = result.lastrowid
        except sqlite3.IntegrityError:
            raise ValueError("That username is already registered.")
        self.store.audit("Account registered", {"user_id": uid, "role": role})
        return {"id": uid, "name": name, "username": username, "role": role}

    def login(self, username, password, ip):
        current = time.time()
        failures = [t for t in self.attempts.get(ip, []) if current-t < 900]
        if len(failures) >= 10:
            raise ValueError("Too many failed attempts. Try again in 15 minutes.")
        with self.store.transaction() as db:
            user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        salt = bytes.fromhex(user["salt"]) if user else b"x"*24
        value = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()
        if not user or not hmac.compare_digest(value, user["password_hash"]):
            self.attempts[ip] = failures + [current]
            raise ValueError("Incorrect username or password.")
        self.attempts.pop(ip, None)
        token = secrets.token_urlsafe(32)
        with self.store.transaction() as db:
            db.execute("DELETE FROM sessions WHERE expires<?", (current,))
            db.execute("INSERT INTO sessions VALUES (?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), user["id"], current+86400))
        return token

    def user(self, token):
        if not token:
            return None
        with self.store.transaction() as db:
            row = db.execute("""SELECT u.id,u.username,u.name,u.role FROM sessions s JOIN users u ON s.user_id=u.id
                WHERE s.token_hash=? AND s.expires>?""", (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
        return dict(row) if row else None

    def logout(self, token):
        if token:
            with self.store.transaction() as db:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))

    def profile(self, uid):
        with self.store.transaction() as db:
            row = db.execute("SELECT * FROM profiles WHERE user_id=?", (uid,)).fetchone()
        return {"skills": json.loads(row["skills"]), "summary": row["summary"]} if row else {"skills": [], "summary": ""}

    def save_profile(self, uid, skills, summary):
        cleaned = sorted({s.lower().strip() for s in skills if s.strip()})
        with self.store.transaction() as db:
            db.execute("INSERT INTO profiles VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET skills=excluded.skills,summary=excluded.summary",
                       (uid, json.dumps(cleaned), summary))
        return {"skills": cleaned, "summary": summary}

    def jobs(self, user=None):
        with self.store.transaction() as db:
            items = [json.loads(r["payload"]) for r in db.execute("SELECT payload FROM jobs ORDER BY id DESC")]
        own = self.profile(user["id"])["skills"] if user and user["role"] == "candidate" else []
        return [{**item, "match": match(own, item["skills"])} for item in items]

    def post(self, user, body):
        with self.store.transaction() as db:
            cursor = db.execute("INSERT INTO jobs(employer_id,payload) VALUES (?,?)", (user["id"], "{}"))
            item = dict(**body, id=cursor.lastrowid, employer_id=user["id"], created=now(), demo=False)
            db.execute("UPDATE jobs SET payload=? WHERE id=?", (json.dumps(item), item["id"]))
        self.store.audit("Job posted", {"job_id": item["id"], "user_id": user["id"]})
        return item

    def apply(self, user, job_id):
        with self.store.transaction() as db:
            job = db.execute("SELECT id FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not job:
                raise ValueError("Job not found.")
            try:
                db.execute("INSERT INTO applications(candidate_id,job_id,status,created) VALUES (?,?,?,?)", (user["id"], job_id, "Received", now()))
            except sqlite3.IntegrityError:
                raise ValueError("You already applied to this role.")
        self.store.audit("Application submitted", {"job_id": job_id, "candidate_id": user["id"]})

    def applications(self, user):
        with self.store.transaction() as db:
            condition = "a.candidate_id=?" if user["role"] == "candidate" else "j.employer_id=?"
            rows = db.execute("""SELECT a.*,j.payload,u.name AS candidate FROM applications a
                JOIN jobs j ON a.job_id=j.id JOIN users u ON a.candidate_id=u.id
                WHERE """+condition+" ORDER BY a.id DESC", (user["id"],)).fetchall()
        return [{**dict(r), "job": json.loads(r["payload"])} for r in rows]

    def transition(self, user, application_id, status):
        allowed = {"Received": {"Reviewing", "Rejected"}, "Reviewing": {"Interview", "Rejected"},
                   "Interview": {"Offered", "Rejected"}, "Offered": set(), "Rejected": set(), "Withdrawn": set()}
        with self.store.transaction() as db:
            row = db.execute("""SELECT a.*,j.employer_id FROM applications a JOIN jobs j ON a.job_id=j.id
                WHERE a.id=?""", (application_id,)).fetchone()
            if not row:
                raise ValueError("Application not found.")
            if user["role"] == "candidate":
                valid = row["candidate_id"] == user["id"] and status == "Withdrawn" and row["status"] not in {"Rejected", "Withdrawn", "Offered"}
            else:
                valid = row["employer_id"] == user["id"] and status in allowed[row["status"]]
            if not valid:
                raise ValueError("This transition is not available for your account.")
            db.execute("UPDATE applications SET status=? WHERE id=?", (status, application_id))
        self.store.audit("Application status changed", {"id": application_id, "status": status, "actor": user["id"]})


def resume_text(filename, encoded):
    try:
        content = base64.b64decode(encoded, validate=True)
    except ValueError:
        raise ValueError("Invalid file encoding.")
    if len(content) > 3_000_000:
        raise ValueError("Resume must be under 3 MB.")
    if filename.lower().endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(content))
            if len(reader.pages) > 30:
                raise ValueError("Resume must be 30 pages or fewer.")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            raise ValueError("Could not extract this PDF. Use a text-based PDF or TXT.")
    elif filename.lower().endswith(".txt"):
        text = content.decode("utf-8", errors="replace")
    else:
        raise ValueError("Use a TXT or text-based PDF resume.")
    if not text.strip():
        raise ValueError("No text found. Scanned PDFs need OCR.")
    return text[:100000]
