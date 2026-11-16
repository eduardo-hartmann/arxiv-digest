# arxiv-digest

A personal daily arXiv digest with Claude as the reading agent.

Every weekday morning a GitHub Action:

1. **Collects your feedback.** It reads the 👍/👎/💬 issues you opened from the
   site and updates `interests_learned.md`.
2. **Fetches** today's announcements (new + cross-lists) from arXiv RSS.
3. **Screens** the high-volume categories (cs.LG, cs.AI, astro-ph.CO/IM) by title.
4. **Ranks** astro-ph.GA plus the promoted papers on title + abstract. Each
   paper gets two scores: *relevance to you* and *importance for the field*.
5. **Deep-reads** the top 3–5 PDFs and writes 5–10 minute summaries. Every
   claim is cited to a page, section, figure or table.
6. **Briefs** the next 15, flags big-for-the-field papers outside your niche,
   and lists everything else by score.
7. Commits `digests/YYYY-MM-DD.md` and publishes the site to GitHub Pages.

```
config.yaml              categories, counts, weights, models
interests.md             YOUR interests (edit this! the agent never touches it)
interests_learned.md     agent-maintained preferences learned from feedback
prompts/*.md             prompts for screen / rank / deep / brief / learn
digest/                  the pipeline (python -m digest.run)
site/                    static site builder + stylesheet
digests/, data/          daily output (markdown + JSON)
feedback/log.jsonl       every piece of feedback you've given
```

## Setup (about 15 minutes)

You need a GitHub account and your Claude Pro subscription.

### 1. Create the repository
Create a new **public** repo on GitHub, e.g. `arxiv-digest`. Then upload these
files:

```bash
cd arxiv-digest
git init -b main && git add . && git commit -m "Initial commit"
git remote add origin git@github.com:<you>/arxiv-digest.git
git push -u origin main
```

> **Public or private?** On a free GitHub account, Pages only works from
> public repos. The site carries `noindex` and `robots.txt` so search engines
> skip it, but the repo itself is visible on your profile. If you have
> GitHub Pro you can make the repo private instead. The site URL will still be
> reachable by anyone who has the link. Either way, **only you can give
> feedback**: the pipeline ignores issues opened by anyone except the repo
> owner, and only you can push.

### 2. Get a Claude Code token (uses your Pro subscription, not paid API)
On your laptop:

```bash
npm install -g @anthropic-ai/claude-code   # needs Node 18+
claude setup-token                          # opens a browser, prints sk-ant-oat01-...
```

In the repo go to **Settings → Secrets and variables → Actions → New
repository secret**. Name it `CLAUDE_CODE_OAUTH_TOKEN` and paste the token as
the value. The token lasts about a year; repeat this step when it expires.

### 3. Turn on GitHub Pages
**Settings → Pages → Build and deployment → Source: "GitHub Actions"**.

### 4. Allow the workflow to write
**Settings → Actions → General → Workflow permissions → "Read and write
permissions"** → Save.

### 5. Edit `interests.md`
This file matters more than anything else. A draft is already there. Make it
concrete: topics, surveys, methods, people you never want to miss, and what
you *don't* care about.

### 6. First run
Go to **Actions → daily-digest → Run workflow**. Tick *force* if you are
re-running on the same day. The run takes around 10–20 minutes. Your site
will be at `https://<you>.github.io/arxiv-digest/`.

After that the workflow runs on its own at **05:30 UTC, Monday to Friday**.
To change the time, edit the `cron` line in `.github/workflows/daily.yml`.

## Giving feedback

Every paper has **👍 more like this** and **👎 not for me** links, and the top
of each digest has **💬 Leave a note for the agent**. Each link opens a
pre-filled GitHub issue. Add a comment if you want (for example "good, but I
care about the method, not the cosmology") and submit. On the next run the
agent:

- records the issue in `feedback/log.jsonl`, then comments on and closes it,
- rewrites `interests_learned.md` from your whole feedback history,
- shows your recent feedback to the ranker as examples.

Notes are treated as direct instructions, for example "show me fewer LLM
benchmark papers" or "always deep-read new DESI DR papers". You can also edit
`interests.md` or `interests_learned.md` by hand at any time.

## Tuning

Everything lives in `config.yaml`:

- `full_categories` / `screened_categories`: what gets read
- `deep_dive.min/max/min_score`: how many papers get a full read
- `weights`: your relevance vs. importance for the field
- `models`: `haiku` / `sonnet` / `opus` for each step

**Usage:** a typical day uses one haiku screening pass, one or two sonnet
ranking calls, 3–5 paper reads of about 35k tokens each, and one briefing
call. That fits comfortably in the Pro plan, and running at 05:30 keeps it out
of your working-hours usage window. If you hit limits, set `deep_dive.max: 3`
or lower `pdf_max_chars`.

## Running locally

```bash
pip install -r requirements.txt
python -m digest.run --force     # uses your logged-in `claude` CLI
python site/build.py             # builds the site into _site/
```

Offline test, without arXiv or Claude:
`DIGEST_MOCK=1 python -m digest.run --fixture papers.json --date 2026-11-17`

## Security notes

- Claude runs with **all tools disabled**. Text goes in on stdin and the answer
  comes back on stdout. Python does all downloading and writing. A
  prompt-injection hidden in a paper can therefore at worst distort that day's
  text; it can't run commands or change the repo.
- The workflow only triggers on schedule, on manual dispatch, or on your own
  pushes. Never on issues or PRs from other people.

## Ideas for later
- Audio: turn the top picks into an MP3 with `edge-tts` and commit it next to
  the digest.
- Zotero: push 👍 papers to a Zotero collection through the Zotero web API.
