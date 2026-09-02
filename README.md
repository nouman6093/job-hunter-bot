# AI & ML Job Hunter Bot

Automated pipeline that scrapes fresh AI/ML and Python job postings across LinkedIn, Indeed, Google, and Bayt, filters out scams and senior roles, and dispatches real-time embeds directly to a Discord channel. 

Runs automatically every 20 minutes on GitHub Actions, maintaining state with an auto-committing SQLite database to prevent duplicate notifications.

---

## Demo Preview

<img width="1218" height="594" alt="image" src="https://github.com/user-attachments/assets/4d8641a2-4d28-484d-9fd9-785a7250baae" />

---

## Key Features

* **Multi-Board Aggregation**: Scrapes LinkedIn, Indeed, Google Jobs, and Bayt via `python-jobspy`.
* **Precision Filtering**:
  * **Role Level**: Hard-drops senior, lead, manager, and non-tech titles via regex.
  * **Anti-Scam**: Discards listings containing pay-to-work phrases (e.g., *registration fee*, *security deposit*).
  * **Location-Locked**: Only accepts roles located in Islamabad, Rawalpindi, or marked as Remote.
* **Dual Deduplication**: Computes SHA-256 hashes of `company + title + location` alongside clean URLs to ensure zero repeat alerts.
* **Discord Integration**: Delivers formatted embeds with dynamic color-coding (internships vs. full engineering roles) and automatic rate-limit (HTTP 429) backoff.
* **Serverless Execution**: Scheduled via GitHub Actions cron with automatic persistence of `seen_jobs.db`.

---

## File Structure

```text
├── .github/
│   └── workflows/
│       └── pipeline.yml       # GitHub Actions schedule (every 20 mins)
├── bot.py                     # Main scraper, parsing, and Discord notification script
├── requirements.txt           # Project dependencies
├── seen_jobs.db               # SQLite database tracking seen job fingerprints
└── README.md
