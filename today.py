"""
GitHub Profile Stats Generator — tmih06
Dark mode only. GitHub stats + WakaTime charts.
"""

import base64
import datetime
import os
import time

import requests
from dateutil import relativedelta
from dotenv import load_dotenv

load_dotenv()

GH_HEADERS = {"Authorization": "Bearer " + os.environ["ACCESS_TOKEN"]}
WAKA_KEY = os.environ.get("WAKATIME_API_KEY", "")
USER_NAME = "tmih06"
BIRTHDAY = datetime.datetime(2006, 4, 8)

CONFIG = {
    "include_private_repos": True,
    "profile": {
        "title": "tmih06@github ",
        "os": "Arch Linux (btw)",
        "host": "Vietnam",
        "kernel": "AIOps",
        "ide": "neovim, opencode, claudecode",
        "languages_programming": ".py, .js, .ts, .java, .cs, .rs",
        "languages_real": "Vietnamese, English",
        "hobbies_software": "Open Source, Agent skills",
        "hobbies_hardware": "Hybrid AI Cluster",
        "contact": {
            "email": "tmih.real@gmail.com",
            "discord": "tmih06",
            "facebook": "fb.com/tmih06.real",
        },
    },
}

# ── Dark mode palette ────────────────────────────────────────────────────────
BG      = "#161b22"
TEXT    = "#c9d1d9"
KEY     = "#ffa657"
VAL     = "#a5d6ff"
DOT     = "#616e7f"
ADD     = "#3fb950"
DEL     = "#f85149"
ACCENT  = "#58a6ff"

BAR_COLORS = ["#58a6ff", "#3fb950", "#ffa657", "#f85149", "#d2a8ff",
              "#79c0ff", "#56d364", "#e3b341"]


# ── GitHub API ───────────────────────────────────────────────────────────────

def gh_query(name, query, variables):
    print(f"  -> {name}...", flush=True)
    for attempt in range(3):
        r = requests.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": variables},
            headers=GH_HEADERS,
        )
        if r.status_code == 200:
            return r.json()
        if r.status_code in (502, 503, 504) and attempt < 2:
            time.sleep((attempt + 1) * 2)
            continue
        break
    raise Exception(f"{name} failed: {r.status_code} {r.text}")


def get_user_stats():
    print("  Querying user profile...", flush=True)
    data = gh_query("get_user_stats", """
    query($login: String!) {
        user(login: $login) {
            createdAt
            followers { totalCount }
            repositories(first: 100, ownerAffiliations: [OWNER]) {
                totalCount
                totalDiskUsage
                nodes {
                    licenseInfo { spdxId }
                    stargazerCount
                    forkCount
                }
            }
            issues { totalCount }
            pullRequests { totalCount }
        }
    }""", {"login": USER_NAME})["data"]["user"]

    licenses = {}
    total_stars = 0
    for repo in data["repositories"]["nodes"]:
        if repo["licenseInfo"]:
            lic = repo["licenseInfo"]["spdxId"]
            licenses[lic] = licenses.get(lic, 0) + 1
        total_stars += repo["stargazerCount"]

    return {
        "created_at": data["createdAt"],
        "followers": data["followers"]["totalCount"],
        "repositories": data["repositories"]["totalCount"],
        "disk_mb": data["repositories"]["totalDiskUsage"] / 1024,
        "preferred_license": max(licenses, key=licenses.get) if licenses else "None",
        "issues": data["issues"]["totalCount"],
        "pull_requests": data["pullRequests"]["totalCount"],
        "stars": total_stars,
    }


def get_contribution_years():
    print("  Querying contribution years...", flush=True)
    data = gh_query("get_contribution_years", """
    query($login: String!) {
        user(login: $login) {
            contributionsCollection { contributionYears }
        }
    }""", {"login": USER_NAME})
    return data["data"]["user"]["contributionsCollection"]["contributionYears"]


def get_contribution_calendar(start, end):
    data = gh_query("get_contribution_calendar", """
    query($login: String!, $start: DateTime!, $end: DateTime!) {
        user(login: $login) {
            contributionsCollection(from: $start, to: $end) {
                totalCommitContributions
                totalPullRequestContributions
                totalPullRequestReviewContributions
                contributionCalendar {
                    totalContributions
                    weeks { contributionDays { contributionCount date } }
                }
            }
        }
    }""", {"login": USER_NAME, "start": start, "end": end})
    return data["data"]["user"]["contributionsCollection"]


def calculate_activity(years):
    print(f"  Processing {len(years)} years: {sorted(years)}", flush=True)
    all_days, total_contributions, total_commits, total_prs, total_reviews = [], 0, 0, 0, 0
    for year in sorted(years):
        print(f"    Fetching calendar {year}...", flush=True)
        end = datetime.datetime.now().strftime("%Y-%m-%dT23:59:59Z") if year == datetime.datetime.now().year else f"{year}-12-31T23:59:59Z"
        cal = get_contribution_calendar(f"{year}-01-01T00:00:00Z", end)
        total_contributions += cal["contributionCalendar"]["totalContributions"]
        total_commits += cal["totalCommitContributions"]
        total_prs += cal["totalPullRequestContributions"]
        total_reviews += cal["totalPullRequestReviewContributions"]
        for week in cal["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                all_days.append({"date": day["date"], "count": day["contributionCount"]})

    all_days.sort(key=lambda x: x["date"])
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    # Streaks
    cur_streak = longest = temp = 0
    best_day = best_count = 0
    for i, d in enumerate(all_days):
        if d["count"] > 0:
            temp += 1
            if d["count"] > best_count:
                best_count, best_day = d["count"], d["date"]
        else:
            longest = max(longest, temp)
            temp = 0
    longest = max(longest, temp)

    for d in reversed(all_days):
        if d["date"] in (today, yesterday) and d["count"] > 0:
            cur_streak = 1
            idx = all_days.index(d) - 1
            while idx >= 0 and all_days[idx]["count"] > 0:
                cur_streak += 1
                idx -= 1
            break
        elif d["date"] < yesterday:
            break

    total_days = len([d for d in all_days if d["date"] <= today])
    return {
        "total_contributions": total_contributions,
        "total_commits": total_commits,
        "total_prs": total_prs,
        "total_reviews": total_reviews,
        "current_streak": cur_streak,
        "longest_streak": longest,
        "best_day_count": best_count,
        "avg_per_day": total_contributions / total_days if total_days else 0,
    }


def get_lines_of_code():
    from concurrent.futures import ThreadPoolExecutor

    print("  Fetching repo list...", flush=True)
    r = requests.get("https://api.github.com/user/repos?per_page=100&affiliation=owner", headers=GH_HEADERS)
    if r.status_code != 200:
        return {"additions": 0, "deletions": 0}
    repos = [repo for repo in r.json() if not repo.get("fork")]
    print(f"  Processing {len(repos)} repos for LOC in parallel...", flush=True)

    def fetch_repo_loc(args):
        idx, repo = args
        url = f"https://api.github.com/repos/{USER_NAME}/{repo['name']}/stats/contributors"
        print(f"    [{idx+1}/{len(repos)}] LOC stats...", flush=True)
        for _ in range(100):
            sr = requests.get(url, headers=GH_HEADERS)
            if sr.status_code == 200:
                a = d = 0
                for c in sr.json() or []:
                    if c and c.get("author", {}).get("login") == USER_NAME:
                        for w in c.get("weeks", []):
                            a += w.get("a", 0)
                            d += w.get("d", 0)
                return a, d
            elif sr.status_code == 202:
                time.sleep(2)
            else:
                break
        return 0, 0

    adds, dels = 0, 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        for a, d in ex.map(fetch_repo_loc, enumerate(repos)):
            adds += a
            dels += d
    return {"additions": adds, "deletions": dels}


# ── WakaTime API ─────────────────────────────────────────────────────────────

def waka_headers():
    token = base64.b64encode(f"{WAKA_KEY}:".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def get_waka_stats():
    """Returns languages + editors + OS from last_30_days stats."""
    if not WAKA_KEY:
        return None
    print("  Fetching WakaTime stats...", flush=True)
    for _ in range(5):
        r = requests.get(
            "https://wakatime.com/api/v1/users/current/stats/last_30_days",
            headers=waka_headers(),
        )
        if r.status_code == 200:
            break
        if r.status_code == 202:
            time.sleep(3)
            continue
        print(f"       WakaTime stats failed: {r.status_code}")
        return None
    data = r.json().get("data", {})
    langs = data.get("languages", [])
    print(f"  WakaTime: {len(langs)} languages, daily avg {fmt_seconds(data.get('daily_average', 0))}", flush=True)
    return {
        "languages": data.get("languages", []),
        "editors": data.get("editors", [])[:6],
        "operating_systems": data.get("operating_systems", [])[:6],
        "categories": data.get("categories", []),
        "daily_average": data.get("daily_average", 0),
        "total_seconds": data.get("total_seconds", 0),
        "best_day": data.get("best_day"),
    }


def get_waka_summaries():
    """Returns last 30 days daily totals."""
    if not WAKA_KEY:
        return None
    print("  Fetching WakaTime summaries...", flush=True)
    r = requests.get(
        "https://wakatime.com/api/v1/users/current/summaries?range=last_30_days",
        headers=waka_headers(),
    )
    if r.status_code != 200:
        print(f"       WakaTime summaries failed: {r.status_code}")
        return None
    days = []
    for day in r.json().get("data", []):
        days.append({
            "date": day["range"]["date"],
            "seconds": day["grand_total"]["total_seconds"],
        })
    return days


# ── SVG helpers ──────────────────────────────────────────────────────────────

def x(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg_open(w, h):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" font-family="Consolas,monospace" '
        f'width="{w}" height="{h}" font-size="14px">'
        f'<rect width="{w}" height="{h}" fill="{BG}" rx="12"/>'
    )


def make_line(px, py, key, value, width=56):
    kl, vl = len(key) + 4, len(str(value))
    dots = "." * max(2, width - kl - vl) + " "
    return (
        f'<text x="{px}" y="{py}" font-family="Consolas,monospace" font-size="14px">'
        f'<tspan fill="{DOT}">. </tspan>'
        f'<tspan fill="{KEY}">{x(key)}</tspan>'
        f'<tspan fill="{DOT}">: {dots}</tspan>'
        f'<tspan fill="{VAL}">{x(str(value))}</tspan>'
        f'</text>'
    )


def make_header(px, py, title, width=56):
    prefix = f"- {title} "
    suffix = "-—-"
    dashes = "—" * max(1, width - len(prefix) - len(suffix))
    return (
        f'<text x="{px}" y="{py}" font-family="Consolas,monospace" font-size="14px" fill="{DOT}">'
        f'{x(prefix + dashes + suffix)}</text>'
    )


def fmt_seconds(s):
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


def fmt_date(d):
    try:
        return datetime.datetime.strptime(d[:10], "%Y-%m-%d").strftime("%b %d, %Y")
    except Exception:
        return d


# ── SVG generators ───────────────────────────────────────────────────────────

def dline(px, py, k1, v1, k2, v2, col2=340):
    """Double line with pixel-exact column alignment. col2 = x of second column."""
    def seg(kx, k, v):
        return (f'<tspan x="{kx}" fill="{DOT}">. </tspan>'
                f'<tspan fill="{KEY}">{x(k)}: </tspan>'
                f'<tspan fill="{VAL}">{x(str(v))}</tspan>')
    return (f'<text y="{py}" font-family="Consolas,monospace" font-size="14px">'
            f'{seg(px, k1, v1)}'
            f'<tspan fill="{DOT}">  |  </tspan>'
            f'{seg(col2, k2, v2)}'
            f'</text>')


def generate_github_stats(stats, activity, loc):
    W, pad = 700, 15
    H = 260  # tight fit: 9 data lines + 2 headers + spacing
    out = []
    out.append('<?xml version="1.0" encoding="UTF-8"?>')
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" font-family="Consolas,monospace" width="{W}px" height="{H}px" font-size="16px">')
    out.append('<style>.k{fill:#ffa657}.v{fill:#a5d6ff}.c{fill:#616e7f}.a{fill:#3fb950}.d{fill:#f85149} text,tspan{white-space:pre}</style>')
    out.append(f'<rect width="{W}px" height="{H}px" fill="{BG}" rx="15"/>')
    out.append(f'<text x="{pad}" y="30" fill="{TEXT}">')

    # W=700, font=16px monospace ~9.6px/char → ~70 chars fit
    COLS = 68

    def hdr(y, title):
        prefix = f"- {title} "
        suffix = "-—-"
        dashes = "—" * max(1, COLS - len(prefix) - len(suffix))
        return f'<tspan x="{pad}" y="{y}" class="c">{x(prefix + dashes + suffix)}</tspan>'

    def dbl(y, k1, v1, k2, v2, w1=32, w2=34):
        d1 = "." * max(2, w1 - len(k1) - 2 - len(str(v1))) + " "
        d2 = "." * max(2, w2 - len(k2) - 2 - len(str(v2))) + " "
        return (f'<tspan x="{pad}" y="{y}" class="c">. </tspan>'
                f'<tspan class="k">{x(k1)}</tspan>'
                f'<tspan class="c">: {d1}</tspan>'
                f'<tspan class="v">{x(str(v1))}</tspan>'
                f'<tspan class="c"> | </tspan>'
                f'<tspan class="k">{x(k2)}</tspan>'
                f'<tspan class="c">: {d2}</tspan>'
                f'<tspan class="v">{x(str(v2))}</tspan>')

    total_loc = loc["additions"] - loc["deletions"]
    add_s = f"{loc['additions']:,}++"
    del_s = f"{loc['deletions']:,}--"
    loc_val = f"{total_loc:,}"
    loc_d1 = "." * max(2, 32 - len("Lines of Code") - 2 - len(loc_val)) + " "
    loc_d2 = "." * max(2, 4) + " "
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    now_d = "." * max(2, COLS - len("Last Updated") - 4 - len(now_str)) + " "

    out.append(hdr(30, "Activity"))
    out.append(dbl(55,  "Commits",        f"{activity['total_commits']:,}", "PRs Opened",     str(activity['total_prs']),               32, 30))
    out.append(dbl(75,  "PRs Reviewed",   str(activity['total_reviews']),  "Issues",          str(stats['issues']),                     32, 30))
    out.append(dbl(95,  "Current Streak", f"{activity['current_streak']} days", "Longest Streak", f"{activity['longest_streak']} days", 32, 30))
    out.append(dbl(115, "Best Day",       f"{activity['best_day_count']} commits", "Avg",     f"~{activity['avg_per_day']:.2f}/day",     32, 30))
    out.append(hdr(145, "GitHub Stats"))
    out.append(dbl(170, "Repos",          str(stats['repositories']),      "Stars",           str(stats['stars']),                      32, 30))
    out.append(dbl(190, "Contributions",  f"{activity['total_contributions']:,}", "Followers", str(stats['followers']),                 32, 30))
    out.append(
        f'<tspan x="{pad}" y="210" class="c">. </tspan>'
        f'<tspan class="k">Lines of Code</tspan>'
        f'<tspan class="c">: {loc_d1}</tspan>'
        f'<tspan class="v">{x(loc_val)}</tspan>'
        f'<tspan class="c"> | {loc_d2}</tspan>'
        f'<tspan class="a">{x(add_s)}</tspan>'
        f'<tspan class="c">, </tspan>'
        f'<tspan class="d">{x(del_s)}</tspan>'
    )
    out.append(
        f'<tspan x="{pad}" y="230" class="c">. </tspan>'
        f'<tspan class="k">Last Updated</tspan>'
        f'<tspan class="c">: {now_d}</tspan>'
        f'<tspan class="v">{x(now_str)}</tspan>'
    )
    out.append('</text></svg>')
    _write("github_stats.svg", "\n".join(out))


def generate_waka_languages(waka):
    if not waka or not waka["languages"]:
        return
    all_langs = [l for l in waka["languages"] if l.get("percent", 0) >= 0.5]
    other_sec = sum(l.get("total_seconds", 0) for l in waka["languages"] if l.get("percent", 0) < 0.5)
    other_pct = sum(l.get("percent", 0) for l in waka["languages"] if l.get("percent", 0) < 0.5)
    if other_pct > 0:
        all_langs.append({"name": "Other", "percent": other_pct, "total_seconds": other_sec,
                          "text": fmt_seconds(other_sec)})
    n = len(all_langs)
    W, pad, bar_x, bar_w = 700, 15, 130, 380
    H = 50 + n * 26 + 20
    out = []
    out.append('<?xml version="1.0" encoding="UTF-8"?>')
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" font-family="Consolas,monospace" width="{W}px" height="{H}px" font-size="14px">')
    out.append('<style>.k{fill:#ffa657}.v{fill:#a5d6ff}.c{fill:#616e7f} text,tspan{white-space:pre}</style>')
    out.append(f'<rect width="{W}px" height="{H}px" fill="{BG}" rx="15"/>')

    # Header
    prefix = "- Languages (last 30d) "
    suffix = "-—-"
    dashes = "—" * max(1, 68 - len(prefix) - len(suffix))
    out.append(f'<text x="{pad}" y="28" font-size="16px" fill="{DOT}">{x(prefix + dashes + suffix)}</text>')

    for i, lang in enumerate(all_langs):
        y = 46 + i * 26
        pct = lang.get("percent", 0)
        filled = int(bar_w * pct / 100)
        color = BAR_COLORS[i % len(BAR_COLORS)]
        name = lang.get("name", "")
        text_val = lang.get("text", fmt_seconds(lang.get("total_seconds", 0)))
        out.append(f'<rect x="{pad}" y="{y+2}" width="8" height="8" fill="{color}" rx="2"/>')
        out.append(f'<text x="{pad+12}" y="{y+11}" font-size="13px" fill="{VAL}">{x(name)}</text>')
        out.append(f'<rect x="{bar_x}" y="{y}" width="{bar_w}" height="14" fill="{DOT}" opacity="0.15" rx="3"/>')
        if filled > 0:
            out.append(f'<rect x="{bar_x}" y="{y}" width="{filled}" height="14" fill="{color}" rx="3" opacity="0.85"/>')
        out.append(f'<text x="{bar_x+bar_w+8}" y="{y+11}" font-size="12px" fill="{DOT}">{pct:.1f}%  {x(text_val)}</text>')

    out.append('</svg>')
    _write("waka_languages.svg", "\n".join(out))



def generate_waka_editors(waka):
    if not waka or not waka["editors"]:
        return
    import math
    editors = [e for e in waka["editors"] if e.get("total_seconds", 0) > 0]
    W, H = 340, 300
    cx, cy, r = 110, 155, 85
    pad = 15

    out = [svg_open(W, H)]
    out.append(make_header(pad, pad + 14, "Editors  (last 30d)", 34))

    total = sum(e.get("total_seconds", 0) for e in editors) or 1
    angle = -math.pi / 2
    for i, ed in enumerate(editors):
        pct = ed.get("total_seconds", 0) / total
        sweep = 2 * math.pi * pct
        if sweep < 0.01:
            continue
        color = BAR_COLORS[i % len(BAR_COLORS)]
        ir = r - 22
        x1  = cx + r  * math.cos(angle);          y1  = cy + r  * math.sin(angle)
        x2  = cx + r  * math.cos(angle + sweep);  y2  = cy + r  * math.sin(angle + sweep)
        ix1 = cx + ir * math.cos(angle);          iy1 = cy + ir * math.sin(angle)
        ix2 = cx + ir * math.cos(angle + sweep);  iy2 = cy + ir * math.sin(angle + sweep)
        large = 1 if sweep > math.pi else 0
        out.append(f'<path d="M {ix1:.2f} {iy1:.2f} L {x1:.2f} {y1:.2f} A {r} {r} 0 {large} 1 {x2:.2f} {y2:.2f} L {ix2:.2f} {iy2:.2f} A {ir} {ir} 0 {large} 0 {ix1:.2f} {iy1:.2f} Z" fill="{color}" stroke="{BG}" stroke-width="2"/>')
        angle += sweep

    daily_avg = fmt_seconds(waka.get("daily_average", 0))
    out.append(f'<text x="{cx}" y="{cy-8}" text-anchor="middle" font-family="Consolas,monospace" font-size="11px" fill="{DOT}">avg/day</text>')
    out.append(f'<text x="{cx}" y="{cy+12}" text-anchor="middle" font-family="Consolas,monospace" font-size="16px" font-weight="bold" fill="{ACCENT}">{x(daily_avg)}</text>')

    lx, ly = cx + r + 15, 50
    for i, ed in enumerate(editors):
        color = BAR_COLORS[i % len(BAR_COLORS)]
        out.append(f'<rect x="{lx}" y="{ly}" width="10" height="10" fill="{color}" rx="2"/>')
        out.append(f'<text x="{lx+16}" y="{ly+10}" font-family="Consolas,monospace" font-size="13px" fill="{TEXT}">{x(ed.get("name",""))}</text>')
        out.append(f'<text x="{lx+16}" y="{ly+23}" font-family="Consolas,monospace" font-size="11px" fill="{DOT}">{ed.get("percent",0):.1f}%  {x(ed.get("text",""))}</text>')
        ly += 36

    out.append("</svg>")
    _write("waka_editors.svg", "\n".join(out))


def generate_waka_activity(days):
    if not days:
        return
    W, H = 340, 230
    pad, bar_area_h, bar_area_y = 15, 130, 50
    n = len(days)
    slot = (W - pad * 2) // n
    bar_w = max(4, slot - 2)
    max_sec = max((d["seconds"] for d in days), default=1) or 1
    avg_sec = sum(d["seconds"] for d in days) / n

    out = [svg_open(W, H)]
    out.append(make_header(pad, pad + 14, "Daily Activity  (last 30d)", 34))

    for i, day in enumerate(days):
        bx = pad + i * slot
        sec = day["seconds"]
        bh = int(bar_area_h * sec / max_sec) if sec > 0 else 2
        by = bar_area_y + bar_area_h - bh
        color = ACCENT if i == n - 1 else BAR_COLORS[0]
        out.append(f'<rect x="{bx}" y="{by}" width="{bar_w}" height="{bh}" fill="{color}" rx="2" opacity="0.85"/>')
        if i % 5 == 0 or i == n - 1:
            try:
                label = datetime.datetime.strptime(day["date"], "%Y-%m-%d").strftime("%m/%d")
            except Exception:
                label = day["date"][-5:]
            out.append(f'<text x="{bx + bar_w//2}" y="{bar_area_y + bar_area_h + 18}" text-anchor="middle" font-family="Consolas,monospace" font-size="11px" fill="{DOT}">{x(label)}</text>')
        if sec > max_sec * 0.35:
            out.append(f'<text x="{bx + bar_w//2}" y="{by - 4}" text-anchor="middle" font-family="Consolas,monospace" font-size="10px" fill="{TEXT}">{x(fmt_seconds(sec))}</text>')

    # Avg line
    avg_y = bar_area_y + bar_area_h - int(bar_area_h * avg_sec / max_sec)
    out.append(f'<line x1="{pad}" y1="{avg_y}" x2="{W - pad}" y2="{avg_y}" stroke="{DEL}" stroke-width="1" stroke-dasharray="4,3" opacity="0.7"/>')
    out.append(f'<text x="{W - pad - 2}" y="{avg_y - 4}" text-anchor="end" font-family="Consolas,monospace" font-size="10px" fill="{DEL}">avg {x(fmt_seconds(avg_sec))}</text>')

    out.append("</svg>")
    _write("waka_activity.svg", "\n".join(out))


def generate_waka_os(waka):
    if not waka or not waka.get("operating_systems"):
        return
    oses = waka["operating_systems"]
    W, pad = 340, 15
    bar_x, bar_w = 100, 180
    row_h = 44
    H = 55 + len(oses) * row_h + 15

    out = [svg_open(W, H)]
    out.append(make_header(pad, pad + 14, "Operating Systems  (last 30d)", 34))

    for i, os_item in enumerate(oses):
        y = pad + 36 + i * row_h
        pct = os_item.get("percent", 0)
        filled = int(bar_w * pct / 100)
        color = BAR_COLORS[i % len(BAR_COLORS)]
        name = os_item.get("name", "")
        text_val = os_item.get("text", fmt_seconds(os_item.get("total_seconds", 0)))

        out.append(
            f'<text x="{pad}" y="{y + 15}" font-family="Consolas,monospace" '
            f'font-size="14px" fill="{VAL}">{x(name)}</text>'
        )
        out.append(
            f'<rect x="{bar_x}" y="{y}" width="{bar_w}" height="22" '
            f'fill="{DOT}" opacity="0.25" rx="4"/>'
        )
        if filled > 0:
            out.append(
                f'<rect x="{bar_x}" y="{y}" width="{filled}" height="22" '
                f'fill="{color}" rx="4"/>'
            )
        out.append(
            f'<text x="{bar_x + bar_w + 8}" y="{y + 15}" font-family="Consolas,monospace" '
            f'font-size="12px" fill="{DOT}">{pct:.1f}%  {x(text_val)}</text>'
        )

    out.append("</svg>")
    _write("waka_os.svg", "\n".join(out))


def generate_waka_ai(waka):
    """Horizontal stacked bar: AI Coding vs Human Coding vs other categories."""
    if not waka or not waka.get("categories"):
        return
    import math
    cats = [c for c in waka["categories"] if c.get("total_seconds", 0) > 0]
    W, H = 340, 170
    pad = 15
    bar_y, bar_h = 55, 36
    bar_w = W - pad * 2

    out = [svg_open(W, H)]
    out.append(make_header(pad, pad + 14, "Coding Activity  (last 30d)", 34))

    # Stacked bar
    total = sum(c.get("total_seconds", 0) for c in cats) or 1
    cx = pad
    for i, cat in enumerate(cats):
        pct = cat["total_seconds"] / total
        w = int(bar_w * pct)
        color = BAR_COLORS[i % len(BAR_COLORS)]
        radius = "0"
        if i == 0: radius = "4 0 0 4"
        elif i == len(cats) - 1: radius = "0 4 4 0"
        out.append(f'<rect x="{cx}" y="{bar_y}" width="{w}" height="{bar_h}" fill="{color}" rx="{radius}"/>')
        cx += w

    # Legend below bar
    lx, ly = pad, bar_y + bar_h + 20
    for i, cat in enumerate(cats):
        color = BAR_COLORS[i % len(BAR_COLORS)]
        pct = cat["total_seconds"] / total * 100
        name = cat.get("name", "")
        text_val = cat.get("text", "")
        label = f'{name}: {pct:.1f}%  {text_val}'
        out.append(f'<rect x="{lx}" y="{ly-9}" width="8" height="8" fill="{color}" rx="2"/>')
        out.append(f'<text x="{lx+12}" y="{ly}" font-family="Consolas,monospace" font-size="12px" fill="{TEXT}">{x(label)}</text>')
        lx += len(label) * 7 + 20
        if lx > W - 100:
            lx = pad
            ly += 20

    out.append("</svg>")
    _write("waka_ai.svg", "\n".join(out))


def _write(filename, content):
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"       Written: {filename}")


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from concurrent.futures import ThreadPoolExecutor, as_completed

    print("=" * 50)
    print("GitHub Profile Stats Generator")
    print("=" * 50)

    print("\nFetching data in parallel...")
    with ThreadPoolExecutor(max_workers=6) as ex:
        f_stats    = ex.submit(get_user_stats)
        f_years    = ex.submit(get_contribution_years)
        f_loc      = ex.submit(get_lines_of_code)
        f_waka     = ex.submit(get_waka_stats)
        f_waka_days= ex.submit(get_waka_summaries)

        stats     = f_stats.result()
        years     = f_years.result()
        loc       = f_loc.result()
        waka      = f_waka.result()
        waka_days = f_waka_days.result()

    print("\nCalculating activity & streaks...")
    activity = calculate_activity(years)

    print("\nGenerating SVGs...")
    generate_github_stats(stats, activity, loc)
    generate_waka_languages(waka)
    generate_waka_editors(waka)
    generate_waka_activity(waka_days)
    generate_waka_os(waka)
    generate_waka_ai(waka)

    print("\nDone!")
