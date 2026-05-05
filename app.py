"""
JobBlast — Hosted 24/7 Automation Server
==========================================
Runs on Railway / Render / any cloud host.
Sends emails daily at 8am IST automatically.
Dashboard available at http://your-app-url/

Install:
    pip install -r requirements.txt
"""

import os, json, smtplib, time, re, threading, feedparser
import pandas as pd
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from flask import Flask, jsonify, render_template
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# ── CONFIG ────────────────────────────────────────────────────────────────────
YOUR_EMAIL    = os.environ.get("GMAIL_USER", "")
YOUR_PASS     = os.environ.get("GMAIL_PASS", "")
YOUR_NAME     = "Marrivada Venkata Chetan"
RESUME_PATH   = "Marrivada_Venkata_Chetan_Resume.pdf"
RECRUITER_CSV = "recruiters.csv"
LOG_FILE      = "jobblast_log.json"
DAILY_LIMIT   = 30
DELAY_SECONDS = 5

IST = timezone(timedelta(hours=5, minutes=30))

JOB_FEEDS = [
    "https://www.linkedin.com/jobs/search/rss?keywords=full+stack+developer+python&location=India",
    "https://www.linkedin.com/jobs/search/rss?keywords=full+stack+developer+react+django&location=India",
    "https://www.linkedin.com/jobs/search/rss?keywords=full+stack+developer&f_WT=2",
    "https://www.linkedin.com/jobs/search/rss?keywords=python+developer&location=India",
    "https://www.linkedin.com/jobs/search/rss?keywords=django+developer&location=India",
    "https://www.linkedin.com/jobs/search/rss?keywords=python+django+react&f_WT=2",
    "https://www.linkedin.com/jobs/search/rss?keywords=react+developer&location=India",
    "https://www.linkedin.com/jobs/search/rss?keywords=frontend+developer+reactjs&location=India",
    "https://www.linkedin.com/jobs/search/rss?keywords=software+engineer+python&location=India",
    "https://www.linkedin.com/jobs/search/rss?keywords=software+engineer+fresher&location=India",
    "https://www.linkedin.com/jobs/search/rss?keywords=junior+software+engineer&location=India",
    "https://www.linkedin.com/jobs/search/rss?keywords=machine+learning+engineer&location=India",
    "https://www.linkedin.com/jobs/search/rss?keywords=ai+engineer+python&location=India",
    "https://www.linkedin.com/jobs/search/rss?keywords=computer+vision+engineer&location=India",
    "https://www.linkedin.com/jobs/search/rss?keywords=backend+developer+python&location=India",
    "https://remotive.com/remote-jobs/feed/software-dev",
    "https://remotive.com/remote-jobs/feed/machine-learning",
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
]

# ── LOG MANAGEMENT ────────────────────────────────────────────────────────────

def load_log() -> dict:
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            return json.load(f)
    return {
        "sent_keys": [],
        "runs": [],
        "total_sent": 0,
        "total_skipped": 0,
        "total_failed": 0,
        "last_run": None,
        "next_run": None,
        "status": "idle",
        "activity": []
    }

def save_log(log: dict):
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)

# ── EMAIL HELPERS ─────────────────────────────────────────────────────────────

def detect_role(title: str) -> str:
    t = title.lower()
    if any(k in t for k in ["machine learning", "ml ", "ai engineer", "computer vision", "deep learning"]):
        return "ml"
    if any(k in t for k in ["react", "frontend", "front-end", "ui developer"]):
        return "frontend"
    if any(k in t for k in ["backend", "api developer", "django", "python developer"]):
        return "backend"
    return "fullstack"

def build_subject(job_title, company):
    return f"Application - {job_title} at {company} | Chetan (Python, React, Django, ML)"

def build_body(recruiter_name, company, job_title, job_url):
    role = detect_role(job_title)
    first = recruiter_name.split()[0] if recruiter_name and recruiter_name != "nan" else "there"

    pitches = {
        "ml": (
            "I'm a Computer Science (AI) graduate with hands-on experience in machine learning and computer vision. "
            "I've built real-time systems using CNNs, SVMs, OpenCV, MediaPipe, and TensorFlow — including a Human Safety "
            "Analysis System and an AI-powered chatbot with Qdrant vector database integration.",
            "  - Real-time ML pipeline: CNN + SVM + OpenCV for gesture recognition\n"
            "  - AI chatbot with Qdrant vector DB — reduced response time by 0.7s\n"
            "  - Model evaluation with Pandas, NumPy, Keras, TensorFlow\n"
            "  - 95% unit test coverage (PyTest, UnitTest)"
        ),
        "frontend": (
            "I'm a full-stack developer with strong frontend expertise in ReactJS, HTML5, CSS3, Bootstrap, and Material UI. "
            "At Wise Work, I built responsive UI components and improved page load times by 20%.",
            "  - ReactJS + Django full-stack applications in production\n"
            "  - Cross-browser compatible UI (Chrome, Firefox, Safari)\n"
            "  - 20% faster page load via frontend optimization\n"
            "  - RESTful API integration with mobile-first responsive design"
        ),
        "backend": (
            "I'm a Python and Django developer with production experience in API development and scalable system design. "
            "At Wise Work, I designed RESTful APIs achieving 2x faster response times and optimized DB partitioning for 2x peak traffic.",
            "  - Django + RESTful APIs — 2x faster after optimization\n"
            "  - Database partitioning for 2x peak traffic scalability\n"
            "  - 1200+ lines of unit tests, 95% coverage\n"
            "  - Docker, Kubernetes, GCP, CI/CD (Jenkins, Travis CI)"
        ),
        "fullstack": (
            "I'm a full-stack software engineer with experience across the complete product lifecycle — from Django/Python backends "
            "and RESTful API design to ReactJS frontends and ML integration. At Wise Work, I owned backend optimizations, "
            "AI chatbot development, and production deployments.",
            "  - Full-stack: Python, Django, ReactJS, REST APIs, SQL\n"
            "  - AI chatbot with Qdrant vector DB — 15% better user satisfaction\n"
            "  - 2x API performance + 2x traffic scalability\n"
            "  - 95% test coverage | Docker | Kubernetes | GCP | CI/CD"
        ),
    }

    pitch, highlights = pitches[role]

    return f"""Hi {first},

I came across the {job_title} opening at {company} and wanted to reach out directly.

{pitch}

A few highlights relevant to this role:
{highlights}

My resume is attached for your review. I'd love to connect if you see a potential fit.

Job I'm referencing: {job_url}

Thank you for your time, {first}!

Warm regards,
{YOUR_NAME}
Email   : venkatachetanofficial@gmail.com
Phone   : +91 9182112663

---
Reply "unsubscribe" to stop receiving emails from me.
"""

def send_email(to_email, subject, body):
    msg = MIMEMultipart()
    msg["From"]    = YOUR_EMAIL
    msg["To"]      = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    if os.path.exists(RESUME_PATH):
        with open(RESUME_PATH, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", 'attachment; filename="Chetan_Resume.pdf"')
        msg.attach(part)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(YOUR_EMAIL, YOUR_PASS)
        s.send_message(msg)

# ── CORE JOB RUNNER ───────────────────────────────────────────────────────────

def run_job_blast():
    log = load_log()
    log["status"] = "running"
    log["last_run"] = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    save_log(log)

    print(f"\n[{log['last_run']}] JobBlast run started")

    # Load recruiters
    if not os.path.exists(RECRUITER_CSV):
        log["status"] = "error"
        log["activity"].insert(0, {"time": log["last_run"], "msg": "ERROR: recruiters.csv not found", "type": "error"})
        save_log(log)
        return

    df = pd.read_csv(RECRUITER_CSV)
    recruiters = df.to_dict("records")
    sent_keys  = set(log.get("sent_keys", []))

    # Fetch jobs
    all_jobs = []
    for feed_url in JOB_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                all_jobs.append({
                    "title"  : entry.get("title", "").strip(),
                    "company": entry.get("author", "Unknown"),
                    "url"    : entry.get("link", ""),
                    "summary": entry.get("summary", ""),
                })
        except:
            pass

    # Deduplicate
    seen, jobs = set(), []
    for j in all_jobs:
        if j["url"] and j["url"] not in seen:
            seen.add(j["url"])
            jobs.append(j)

    print(f"  Found {len(jobs)} jobs | {len(recruiters)} recruiters")

    count = skipped = failed = 0

    for job in jobs:
        if count >= DAILY_LIMIT:
            break
        for rec in recruiters:
            if count >= DAILY_LIMIT:
                break

            email = str(rec.get("email", "")).strip()
            if not email or "@" not in email:
                continue

            key = f"{email}::{job['url']}"
            if key in sent_keys:
                skipped += 1
                continue

            # keyword match
            kw_raw   = str(rec.get("keywords", "software engineer|python"))
            keywords = [k.strip().lower() for k in kw_raw.split("|")]
            job_text = (job["title"] + " " + job["summary"]).lower()
            if not any(kw in job_text for kw in keywords):
                continue

            name    = str(rec.get("name", "there"))
            company = str(rec.get("company", job["company"]))
            subject = build_subject(job["title"], job["company"])
            body    = build_body(name, company, job["title"], job["url"])

            try:
                send_email(email, subject, body)
                sent_keys.add(key)
                count += 1
                ts  = datetime.now(IST).strftime("%H:%M:%S")
                cat = detect_role(job["title"]).upper()
                msg = f"[{cat}] → {email} | {job['title']}"
                print(f"  OK [{count:02d}] {msg}")
                log["activity"].insert(0, {"time": ts, "msg": msg, "type": "sent"})
                log["activity"] = log["activity"][:100]  # keep last 100
                time.sleep(DELAY_SECONDS)
            except Exception as e:
                failed += 1
                ts  = datetime.now(IST).strftime("%H:%M:%S")
                msg = f"FAILED → {email}: {str(e)[:60]}"
                log["activity"].insert(0, {"time": ts, "msg": msg, "type": "failed"})
                log["activity"] = log["activity"][:100]

    # Save run summary
    run_summary = {
        "date"   : log["last_run"],
        "sent"   : count,
        "skipped": skipped,
        "failed" : failed,
        "jobs_found": len(jobs),
    }
    log["runs"].insert(0, run_summary)
    log["runs"] = log["runs"][:30]  # keep last 30 runs
    log["sent_keys"]      = list(sent_keys)
    log["total_sent"]     = log.get("total_sent", 0) + count
    log["total_skipped"]  = log.get("total_skipped", 0) + skipped
    log["total_failed"]   = log.get("total_failed", 0) + failed
    log["status"] = "idle"
    save_log(log)

    print(f"  Done. Sent:{count} Skipped:{skipped} Failed:{failed}\n")

# ── FLASK ROUTES ──────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/api/status")
def api_status():
    log = load_log()
    log.pop("sent_keys", None)  # don't send huge list to frontend
    return jsonify(log)

@app.route("/api/run", methods=["POST"])
def api_run_now():
    """Trigger a manual run from the dashboard."""
    thread = threading.Thread(target=run_job_blast, daemon=True)
    thread.start()
    return jsonify({"status": "started"})

# ── SCHEDULER ─────────────────────────────────────────────────────────────────

def start_scheduler():
    scheduler = BackgroundScheduler(timezone=IST)
    # Run every day at 8:00 AM IST
    scheduler.add_job(run_job_blast, "cron", hour=8, minute=0)
    scheduler.start()
    # Update next run in log
    log = load_log()
    log["next_run"] = "Daily at 8:00 AM IST"
    save_log(log)
    print("Scheduler started — runs daily at 8:00 AM IST")

# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    start_scheduler()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)