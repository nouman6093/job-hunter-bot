import os
import sqlite3
import hashlib
import time
import re
import urllib.parse
import traceback
import requests
from jobspy import scrape_jobs

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DB_FILE = "seen_jobs.db"

# Target search queries for AI/ML roles
SEARCH_QUERIES = [
    "Machine Learning Engineer",
    "AI Engineer",
    "Data Science",
    "Deep Learning",
    "Python Developer",
    "AI Intern",
    "ML Intern"
]

# Hard Title Exclusion List
EXCLUDED_TITLE_KEYWORDS = [
    r"\bsenior\b", r"\bsr\.?\b", r"\blead\b", r"\bprincipal\b",
    r"\bmanager\b", r"\bdirector\b", r"\barchitect\b", r"\bstaff\b",
    r"\bhead of\b", r"\bsales\b", r"\bmarketing\b", r"\baccountant\b",
    r"\bhr\b", r"\bgraphics designer\b"
]

# Anti-Scam / Pay-to-Work Keywords
SCAM_KEYWORDS = [
    "registration fee", "training fee", "security deposit",
    "paid training scheme", "pay for training", "processing fee"
]

# ---------------------------------------------------------------------------
# SQLite Database Setup & Deduplication
# ---------------------------------------------------------------------------
def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS seen_jobs (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        send_discord_alert(f"⚠️ **Database Init Warning**: {e}")

def is_job_seen(job_hash: str) -> bool:
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM seen_jobs WHERE id = ?", (job_hash,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        print(f"[DB Error] Reading record failed: {e}")
        return False

def mark_job_seen(job_hash: str):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO seen_jobs (id) VALUES (?)", (job_hash,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB Error] Writing record failed: {e}")

# ---------------------------------------------------------------------------
# Discord Alert System
# ---------------------------------------------------------------------------
def send_discord_alert(message: str):
    if not DISCORD_WEBHOOK_URL:
        print(f"[Webhook Skipped] {message}")
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=10)
    except Exception as e:
        print(f"[Discord Error] Failed to send system alert: {e}")

def send_discord_embed(embed: dict):
    if not DISCORD_WEBHOOK_URL:
        print(f"[Webhook Skipped Embed] {embed.get('title')}")
        return False
    try:
        res = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=10)
        if res.status_code == 429:
            retry_after = res.json().get("retry_after", 2)
            time.sleep(retry_after)
            requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=10)
        return True
    except Exception as e:
        print(f"[Discord Error] Embed send failed: {e}")
        return False

# ---------------------------------------------------------------------------
# Filters & Helpers
# ---------------------------------------------------------------------------
def clean_url(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
    except Exception:
        return url

def is_scam(description: str) -> bool:
    if not description:
        return False
    desc_lower = description.lower()
    return any(kw in desc_lower for kw in SCAM_KEYWORDS)

def is_title_excluded(title: str) -> bool:
    if not title:
        return True
    title_lower = title.lower()
    for pattern in EXCLUDED_TITLE_KEYWORDS:
        if re.search(pattern, title_lower):
            return True
    return False

def generate_job_hash(company: str, title: str, location: str) -> str:
    norm_company = re.sub(r'\W+', '', (company or '').lower())
    norm_title = re.sub(r'\W+', '', (title or '').lower())
    norm_loc = re.sub(r'\W+', '', (location or '').lower())
    raw_str = f"{norm_company}_{norm_title}_{norm_loc}"
    return hashlib.sha256(raw_str.encode('utf-8')).hexdigest()

# ---------------------------------------------------------------------------
# Core Scraping & Processing Logic
# ---------------------------------------------------------------------------
def scrape_target_site(site_name: str, query: str):
    try:
        jobs_df = scrape_jobs(
            site_name=[site_name],
            search_term=query,
            location="Pakistan",
            country_indeed="pakistan",
            hours_old=3,
            results_wanted=15
        )
        return jobs_df
    except Exception as e:
        print(f"[Scrape Warning] Failed scraping {site_name} for query '{query}': {e}")
        send_discord_alert(f"⚠️ **Scrape Warning**: Failed `{site_name}` for query `{query}`. Skipping...")
        return None

def process_job_row(row):
    try:
        title = str(row.get('title', ''))
        company = str(row.get('company', ''))
        location = str(row.get('location', ''))
        description = str(row.get('description', ''))
        raw_url = str(row.get('job_url', ''))
        is_remote = bool(row.get('is_remote', False))
        site = str(row.get('site', 'Unknown'))

        if is_title_excluded(title):
            return

        if is_scam(description):
            return

        loc_lower = location.lower()
        is_isb_pindi = any(city in loc_lower for city in ["islamabad", "rawalpindi"])
        
        if not is_isb_pindi and not is_remote:
            return

        url_clean = clean_url(raw_url)
        job_hash = generate_job_hash(company, title, location)

        if is_job_seen(job_hash) or is_job_seen(url_clean):
            return

        embed = {
            "title": f"💼 {title}",
            "url": url_clean,
            "color": 3066993 if "intern" in title.lower() else 3447003,
            "fields": [
                {"name": "Company", "value": company or "N/A", "inline": True},
                {"name": "Location", "value": location or "Pakistan", "inline": True},
                {"name": "Platform", "value": site.capitalize(), "inline": True},
                {"name": "Work Mode", "value": "Remote" if is_remote else ("Onsite/Hybrid" if is_isb_pindi else "Check Link"), "inline": True}
            ],
            "footer": {"text": "Job Hunter Bot • Real-time Alert"}
        }

        success = send_discord_embed(embed)
        if success:
            mark_job_seen(job_hash)
            mark_job_seen(url_clean)
            time.sleep(2)

    except Exception as e:
        print(f"[Record Processing Error] Dropped malformed job entry: {e}")

# ---------------------------------------------------------------------------
# Pipeline Engine
# ---------------------------------------------------------------------------
def main():
    init_db()
    platforms = ["linkedin", "indeed", "google", "bayt"]

    for query in SEARCH_QUERIES:
        for platform in platforms:
            df = scrape_target_site(platform, query)
            if df is None or df.empty:
                continue

            for _, row in df.iterrows():
                process_job_row(row)

if __name__ == "__main__":
    try:
        main()
    except Exception as fatal_err:
        error_msg = f"🚨 **Critical Pipeline Failure**:\n```{traceback.format_exc()[:1800]}```"
        send_discord_alert(error_msg)
        raise fatal_err