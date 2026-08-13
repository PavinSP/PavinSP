#!/usr/bin/env python3
"""Generate a self-hosted streak-stats SVG using authenticated GitHub GraphQL.
Immune to the third-party scraper failures of github-readme-streak-stats mirrors.

Walks the full account history year-by-year (GraphQL's contributionsCollection
caps each query at a 1-year window) so long-past streaks aren't silently dropped.
"""
import os, json, datetime, urllib.request

TOKEN = os.environ["GH_TOKEN"]
LOGIN = os.environ.get("GH_LOGIN", "PavinSP")

CALENDAR_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

CREATED_QUERY = """
query($login: String!) { user(login: $login) { createdAt } }
"""

def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]

created_at = datetime.datetime.fromisoformat(
    gql(CREATED_QUERY, {"login": LOGIN})["user"]["createdAt"].replace("Z", "+00:00")
)
account_start_year = created_at.year

now = datetime.datetime.now(datetime.timezone.utc)
all_days = {}
total_all_time = 0

for year in range(account_start_year, now.year + 1):
    win_from = datetime.datetime(year, 1, 1, tzinfo=datetime.timezone.utc)
    win_to = min(datetime.datetime(year + 1, 1, 1, tzinfo=datetime.timezone.utc), now)
    if win_from > now:
        break
    cal = gql(CALENDAR_QUERY, {
        "login": LOGIN,
        "from": win_from.isoformat(),
        "to": win_to.isoformat(),
    })["user"]["contributionsCollection"]["contributionCalendar"]
    total_all_time += cal["totalContributions"]
    for w in cal["weeks"]:
        for d in w["contributionDays"]:
            all_days[d["date"]] = d["contributionCount"]

days = sorted((datetime.date.fromisoformat(dt), c) for dt, c in all_days.items())
active = [d for d, c in days if c > 0]

longest = cur = 1
best_start = best_end = active[0]
run_start = active[0]
for i in range(1, len(active)):
    if (active[i] - active[i - 1]).days == 1:
        cur += 1
    else:
        if cur > longest:
            longest, best_start, best_end = cur, run_start, active[i - 1]
        cur, run_start = 1, active[i]
if cur > longest:
    longest, best_start, best_end = cur, run_start, active[-1]

today = datetime.date.today()
active_set = set(active)
cur_streak = 0
d = today if today in active_set else today - datetime.timedelta(days=1)
cur_start = None
while d in active_set:
    cur_streak += 1
    cur_start = d
    d -= datetime.timedelta(days=1)

first_active_day = active[0]

def fmt(d):
    return d.strftime("%-d %b %Y")

BG = "#0D1117"
STROKE = "#38BDAE"
NUM = "#38BDAE"
LABEL = "#9AA5CE"
DATE = "#736C97"

svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='495' height='195' viewBox='0 0 495 195'>
  <style>
    .bg {{ fill: {BG}; }}
    .num {{ font: 700 28px 'Segoe UI', Ubuntu, sans-serif; fill: {NUM}; text-anchor: middle; }}
    .label {{ font: 400 14px 'Segoe UI', Ubuntu, sans-serif; fill: {LABEL}; text-anchor: middle; }}
    .date {{ font: 400 11px 'Segoe UI', Ubuntu, sans-serif; fill: {DATE}; text-anchor: middle; }}
    .div {{ stroke: {STROKE}; stroke-opacity: 0.35; }}
  </style>
  <rect class='bg' x='0.5' y='0.5' width='494' height='194' rx='4.5' stroke='{STROKE}' stroke-opacity='0.15'/>

  <text class='num' x='95' y='78'>{total_all_time}</text>
  <text class='label' x='95' y='102'>Total Contributions</text>
  <text class='date' x='95' y='120'>{fmt(first_active_day)} - Present</text>

  <line class='div' x1='177' y1='30' x2='177' y2='165'/>

  <circle cx='247.5' cy='58' r='34' fill='none' stroke='{STROKE}' stroke-width='5'/>
  <text class='num' x='247.5' y='68' font-size='30'>{cur_streak}</text>
  <text class='label' x='247.5' y='108' font-weight='700' fill='{STROKE}'>Current Streak</text>
  <text class='date' x='247.5' y='126'>{fmt(cur_start) + ' - Present' if cur_start else 'None'}</text>

  <line class='div' x1='318' y1='30' x2='318' y2='165'/>

  <text class='num' x='400' y='78'>{longest}</text>
  <text class='label' x='400' y='102'>Longest Streak</text>
  <text class='date' x='400' y='120'>{fmt(best_start)} - {fmt(best_end)}</text>
</svg>"""

with open("streak.svg", "w") as f:
    f.write(svg)

print(f"total_all_time={total_all_time} current_streak={cur_streak} "
      f"longest={longest} ({best_start}..{best_end}) account_since={account_start_year}")
