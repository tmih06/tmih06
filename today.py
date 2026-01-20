"""
GitHub Profile Stats Generator
Originally by Andrew Grant (Andrew6rant), 2022-2025
Rewritten for tmih06 - focused on comprehensive GitHub metrics
"""

import datetime
from dateutil import relativedelta
import requests
import os
import json
from dotenv import load_dotenv
from lxml import etree
import time
from PIL import Image

# Load environment variables from .env file (if it exists)
load_dotenv()

# Load configuration from info.json
with open(os.path.join(os.path.dirname(__file__), "info.json"), "r") as f:
    CONFIG = json.load(f)

# GitHub API setup
HEADERS = {"Authorization": "Bearer " + os.environ["ACCESS_TOKEN"]}
USER_NAME = CONFIG["username"]
BIRTHDAY = datetime.datetime(
    CONFIG["birthday"]["year"], CONFIG["birthday"]["month"], CONFIG["birthday"]["day"]
)

# SVG Configuration
LINE_WIDTH = 60  # Character width for right-aligned values

QUERY_COUNT = {
    "user_stats": 0,
    "contribution_years": 0,
    "contribution_calendar": 0,
    "user_getter": 0,
}


def query_count(funct_id):
    """Counts how many times the GitHub GraphQL API is called"""
    global QUERY_COUNT
    QUERY_COUNT[funct_id] += 1


def simple_request(func_name, query, variables):
    """Makes a GraphQL request with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        request = requests.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": variables},
            headers=HEADERS,
        )
        if request.status_code == 200:
            return request
        elif request.status_code in [502, 503, 504]:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                print(
                    f"       [Retry {attempt + 1}/{max_retries}] Got {request.status_code}, waiting {wait_time}s..."
                )
                time.sleep(wait_time)
                continue
        break

    if request.status_code == 403:
        raise Exception(
            f"{func_name}() failed: Rate limit or abuse detection triggered"
        )
    raise Exception(
        f"{func_name}() failed with status {request.status_code}: {request.text}"
    )


def get_user_stats():
    """
    Gets comprehensive user statistics including:
    - Repositories: count, preferred license, releases, packages, disk usage
    - Community: organizations, following, sponsoring, starred, watching
    - Engagement: sponsors, stargazers, forkers, watchers
    """
    query_count("user_stats")
    query = """
    query($login: String!) {
        user(login: $login) {
            name
            createdAt
            followers { totalCount }
            following { totalCount }
            repositories(first: 100, ownerAffiliations: [OWNER]) {
                totalCount
                totalDiskUsage
                nodes {
                    licenseInfo { spdxId }
                    releases { totalCount }
                    stargazerCount
                    forkCount
                    watchers { totalCount }
                }
            }
            packages { totalCount }
            organizations { totalCount }
            sponsoring { totalCount }
            sponsors { totalCount }
            starredRepositories { totalCount }
            watching { totalCount }
            issues { totalCount }
            pullRequests { totalCount }
            repositoriesContributedTo { totalCount }
        }
    }"""
    request = simple_request("get_user_stats", query, {"login": USER_NAME})
    response = request.json()

    if "errors" in response:
        print(f"       API Error: {response['errors']}")
        raise Exception(f"GitHub API error: {response['errors']}")

    data = response["data"]["user"]

    # Calculate preferred license
    licenses = {}
    total_releases = 0
    total_stargazers = 0
    total_forkers = 0
    total_watchers = 0

    for repo in data["repositories"]["nodes"]:
        if repo["licenseInfo"] and repo["licenseInfo"]["spdxId"]:
            lic = repo["licenseInfo"]["spdxId"]
            licenses[lic] = licenses.get(lic, 0) + 1
        total_releases += repo["releases"]["totalCount"]
        total_stargazers += repo["stargazerCount"]
        total_forkers += repo["forkCount"]
        total_watchers += repo["watchers"]["totalCount"]

    preferred_license = max(licenses, key=licenses.get) if licenses else "None"
    disk_usage_mb = data["repositories"]["totalDiskUsage"] / 1024

    return {
        "name": data["name"] or USER_NAME,
        "created_at": data["createdAt"],
        "followers": data["followers"]["totalCount"],
        "following": data["following"]["totalCount"],
        "repositories": data["repositories"]["totalCount"],
        "disk_usage_mb": disk_usage_mb,
        "preferred_license": preferred_license,
        "releases": total_releases,
        "packages": data["packages"]["totalCount"],
        "organizations": data["organizations"]["totalCount"],
        "sponsoring": data["sponsoring"]["totalCount"],
        "sponsors": data["sponsors"]["totalCount"],
        "starred": data["starredRepositories"]["totalCount"],
        "watching": data["watching"]["totalCount"],
        "issues_opened": data["issues"]["totalCount"],
        "pull_requests": data["pullRequests"]["totalCount"],
        "contributed_to": data["repositoriesContributedTo"]["totalCount"],
        "stargazers": total_stargazers,
        "forkers": total_forkers,
        "watchers": total_watchers,
    }


def get_contribution_years():
    """Gets all years the user has contributed."""
    query_count("contribution_years")
    query = """
    query($login: String!) {
        user(login: $login) {
            contributionsCollection {
                contributionYears
            }
        }
    }"""
    request = simple_request("get_contribution_years", query, {"login": USER_NAME})
    response = request.json()

    if "errors" in response:
        print(f"       API Error: {response['errors']}")
        raise Exception(f"GitHub API error: {response['errors']}")

    return response["data"]["user"]["contributionsCollection"]["contributionYears"]


def get_lines_of_code():
    """
    Fetches total lines added and deleted across all owned repositories.
    Uses the GitHub REST API to get contributor stats.
    Respects include_private_repos config option.
    """
    include_private = CONFIG.get("include_private_repos", True)
    visibility_mode = "all" if include_private else "public"
    print(f"       Fetching repository list ({visibility_mode})...")

    # Use authenticated endpoint to get repos based on visibility setting
    if include_private:
        repos_url = f"https://api.github.com/user/repos?per_page=100&affiliation=owner"
    else:
        repos_url = (
            f"https://api.github.com/users/{USER_NAME}/repos?per_page=100&type=owner"
        )

    repos_response = requests.get(repos_url, headers=HEADERS)

    if repos_response.status_code != 200:
        print(f"       Warning: Could not fetch repos ({repos_response.status_code})")
        return {"additions": 0, "deletions": 0}

    repos = repos_response.json()
    total_additions = 0
    total_deletions = 0
    processed = 0
    skipped_forks = 0

    # Count non-fork repos first
    non_fork_repos = [r for r in repos if not r.get("fork")]
    total_repos = len(non_fork_repos)

    for repo in repos:
        if repo.get("fork"):
            skipped_forks += 1
            continue  # Skip forked repos

        repo_name = repo["name"]
        is_private = repo.get("private", False)
        visibility = "private" if is_private else "public"
        stats_url = (
            f"https://api.github.com/repos/{USER_NAME}/{repo_name}/stats/contributors"
        )

        repo_additions = 0
        repo_deletions = 0
        status = "ok"

        # GitHub may need time to compute stats, retry up to 3 times
        for attempt in range(3):
            stats_response = requests.get(stats_url, headers=HEADERS)

            if stats_response.status_code == 200:
                stats = stats_response.json()
                if stats:
                    for contributor in stats:
                        if contributor.get("author", {}).get("login") == USER_NAME:
                            for week in contributor.get("weeks", []):
                                repo_additions += week.get("a", 0)
                                repo_deletions += week.get("d", 0)
                status = "ok"
                break
            elif stats_response.status_code == 202:
                # Stats are being computed, retry immediately
                status = "computing..."
                continue
            elif stats_response.status_code == 204:
                status = "empty"
                break
            else:
                status = f"error({stats_response.status_code})"
                break

        total_additions += repo_additions
        total_deletions += repo_deletions
        processed += 1
        print(
            f"       [{processed}/{total_repos}] {'***' if is_private else repo_name} ({visibility}): +{repo_additions:,} / -{repo_deletions:,} [{status}]"
        )

    print(f"       Skipped {skipped_forks} forked repos")
    return {"additions": total_additions, "deletions": total_deletions}

    return {"additions": total_additions, "deletions": total_deletions}


def get_contribution_calendar(start_date, end_date):
    """Gets the contribution calendar for a date range."""
    query_count("contribution_calendar")
    query = """
    query($login: String!, $start: DateTime!, $end: DateTime!) {
        user(login: $login) {
            contributionsCollection(from: $start, to: $end) {
                totalCommitContributions
                totalIssueContributions
                totalPullRequestContributions
                totalPullRequestReviewContributions
                contributionCalendar {
                    totalContributions
                    weeks {
                        contributionDays {
                            contributionCount
                            date
                        }
                    }
                }
            }
        }
    }"""
    request = simple_request(
        "get_contribution_calendar",
        query,
        {"login": USER_NAME, "start": start_date, "end": end_date},
    )
    response = request.json()

    if "errors" in response:
        print(f"       API Error: {response['errors']}")
        raise Exception(f"GitHub API error: {response['errors']}")

    return response["data"]["user"]["contributionsCollection"]


def calculate_streaks_and_activity(years):
    """
    Calculate contribution streaks and activity stats from contribution history.
    """
    all_days = []
    total_contributions = 0
    total_commits = 0
    total_prs = 0
    total_pr_reviews = 0
    total_issues = 0
    start_date = None

    for year in sorted(years):
        year_start = f"{year}-01-01T00:00:00Z"
        year_end = f"{year}-12-31T23:59:59Z"

        now = datetime.datetime.now()
        if year == now.year:
            year_end = now.strftime("%Y-%m-%dT23:59:59Z")

        print(f"       Fetching {year}...")
        data = get_contribution_calendar(year_start, year_end)

        total_contributions += data["contributionCalendar"]["totalContributions"]
        total_commits += data["totalCommitContributions"]
        total_prs += data["totalPullRequestContributions"]
        total_pr_reviews += data["totalPullRequestReviewContributions"]
        total_issues += data["totalIssueContributions"]

        for week in data["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                all_days.append(
                    {"date": day["date"], "count": day["contributionCount"]}
                )

        if start_date is None:
            start_date = f"{year}-01-01"

    all_days.sort(key=lambda x: x["date"])

    # Calculate streaks
    current_streak = 0
    longest_streak = 0
    longest_streak_start = None
    longest_streak_end = None
    temp_streak = 0
    temp_streak_start = None
    best_day_count = 0
    best_day_date = None

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime(
        "%Y-%m-%d"
    )

    for i, day in enumerate(all_days):
        if day["count"] > 0:
            if temp_streak == 0:
                temp_streak_start = day["date"]
            temp_streak += 1

            if day["count"] > best_day_count:
                best_day_count = day["count"]
                best_day_date = day["date"]
        else:
            if temp_streak > longest_streak:
                longest_streak = temp_streak
                longest_streak_start = temp_streak_start
                longest_streak_end = (
                    all_days[i - 1]["date"] if i > 0 else temp_streak_start
                )
            temp_streak = 0

    # Check final streak
    if temp_streak > longest_streak:
        longest_streak = temp_streak
        longest_streak_start = temp_streak_start
        longest_streak_end = all_days[-1]["date"] if all_days else temp_streak_start

    # Calculate current streak
    for day in reversed(all_days):
        if day["date"] == today or day["date"] == yesterday:
            if day["count"] > 0:
                current_streak = 1
                idx = all_days.index(day) - 1
                while idx >= 0 and all_days[idx]["count"] > 0:
                    current_streak += 1
                    idx -= 1
                break
        elif day["date"] < yesterday:
            break

    # Average per day
    total_days = len([d for d in all_days if d["date"] <= today])
    avg_per_day = total_contributions / total_days if total_days > 0 else 0

    return {
        "total_contributions": total_contributions,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "longest_streak_start": longest_streak_start,
        "longest_streak_end": longest_streak_end,
        "best_day_count": best_day_count,
        "best_day_date": best_day_date,
        "avg_per_day": avg_per_day,
        "total_commits": total_commits,
        "total_prs": total_prs,
        "total_pr_reviews": total_pr_reviews,
        "total_issues": total_issues,
        "start_date": start_date,
    }


def daily_readme(birthday):
    """Calculate age string from birthday"""
    diff = relativedelta.relativedelta(datetime.datetime.today(), birthday)
    return f"{diff.years} years, {diff.months} months, {diff.days} days"


def image_to_ascii(image_path, width=40, height=25):
    """Convert an image to ASCII art"""
    # ASCII characters from dark to light
    ASCII_CHARS = " .:-=+*#%@"

    try:
        img = Image.open(image_path)
    except FileNotFoundError:
        print(f"       Warning: Avatar image not found at {image_path}")
        return None

    # Convert to grayscale
    img = img.convert("L")

    # Resize image
    img = img.resize((width, height))

    # Convert pixels to ASCII
    pixels = list(img.getdata())
    ascii_lines = []
    for row in range(height):
        line = ""
        for col in range(width):
            pixel = pixels[row * width + col]
            # Map pixel value (0-255) to ASCII char
            char_idx = int(pixel / 256 * len(ASCII_CHARS))
            char_idx = min(char_idx, len(ASCII_CHARS) - 1)
            line += ASCII_CHARS[char_idx]
        ascii_lines.append(line)

    return ascii_lines


def format_date(date_str):
    """Format ISO date to readable format"""
    if not date_str:
        return "N/A"
    try:
        dt = datetime.datetime.strptime(date_str[:10], "%Y-%m-%d")
        return dt.strftime("%b %d, %Y")
    except:
        return date_str


def format_date_short(date_str):
    """Format ISO date to short format"""
    if not date_str:
        return "N/A"
    try:
        dt = datetime.datetime.strptime(date_str[:10], "%Y-%m-%d")
        return dt.strftime("%b %d")
    except:
        return date_str


def years_ago(date_str):
    """Calculate how many years ago from ISO date string"""
    if not date_str:
        return "Unknown"
    try:
        dt = datetime.datetime.strptime(date_str[:10], "%Y-%m-%d")
        diff = relativedelta.relativedelta(datetime.datetime.today(), dt)
        return f"{diff.years} years ago"
    except:
        return "Unknown"


def dot_pad(key, value, total_width):
    """Create a dot-padded string: 'Key: .... Value' with total width"""
    key_len = len(key) + 2  # +2 for ": "
    value_len = len(str(value))
    dots_needed = total_width - key_len - value_len
    if dots_needed < 2:
        dots_needed = 2
    dots = " " + "." * dots_needed + " "
    return dots


def generate_svg(filename, stats, activity, age, ascii_art, loc_stats, is_dark=True):
    """Generate SVG with dynamic dot padding"""

    profile = CONFIG.get("profile", {})

    # Colors
    if is_dark:
        bg_color = "#161b22"
        text_color = "#c9d1d9"
        key_color = "#ffa657"
        value_color = "#a5d6ff"
        dot_color = "#616e7f"
        add_color = "#3fb950"
        del_color = "#f85149"
    else:
        bg_color = "#ffffff"
        text_color = "#1f2328"
        key_color = "#953800"
        value_color = "#0550ae"
        dot_color = "#afb8c1"
        add_color = "#1a7f37"
        del_color = "#cf222e"

    # Data preparation
    title = profile.get("title", f"{USER_NAME}@github")
    os_val = profile.get("os", "Linux")
    uptime_val = age
    host_val = profile.get("host", "Earth")
    kernel_val = profile.get("kernel", "Developer")
    ide_val = profile.get("ide", "VSCode")

    lang_prog = profile.get("languages_programming", "Python")
    lang_comp = profile.get("languages_computer", "HTML, CSS")
    lang_real = profile.get("languages_real", "English")

    hobby_sw = profile.get("hobbies_software", "Coding")
    hobby_hw = profile.get("hobbies_hardware", "Computers")

    contact = profile.get("contact", {})
    contact_items = [(k.title(), v) for k, v in contact.items() if v]

    commits = f"{activity['total_commits']:,}"
    prs_opened = str(activity["total_prs"])
    prs_reviewed = str(activity["total_pr_reviews"])
    issues = str(stats["issues_opened"])
    current_streak = f"{activity['current_streak']} days"
    longest_streak = f"{activity['longest_streak']} days"
    longest_period = f"{format_date_short(activity['longest_streak_start'])} - {format_date_short(activity['longest_streak_end'])}, {activity['longest_streak_end'][:4] if activity['longest_streak_end'] else ''}"
    best_day = str(activity["best_day_count"])
    best_day_date = format_date(activity["best_day_date"])
    avg_day = f"~{activity['avg_per_day']:.2f}"

    repos = str(stats["repositories"])
    contributed = str(stats["contributed_to"])
    stars = str(stats["stargazers"])
    contributions = f"{activity['total_contributions']:,}"
    followers = str(stats["followers"])
    disk = f"{stats['disk_usage_mb']:.1f} MB"
    license_val = stats["preferred_license"]

    # Line width for dot padding (characters from start of value section to end)
    W = 58

    # Calculate dynamic height based on contact items
    # Base height (up to Hobbies) = 270, Contact header = 20, each contact = 20, gap = 20
    # Activity section = 100, GitHub Stats section = 80, bottom padding = 50
    base_height = 270 + 20 + len(contact_items) * 20 + 20 + 100 + 80 + 50
    svg_height = max(600, base_height)

    # Build SVG content
    svg_lines = []
    svg_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    svg_lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" font-family="Consolas,monospace" width="985px" height="{svg_height}px" font-size="16px">'
    )
    svg_lines.append("<style>")
    svg_lines.append(f".key {{fill: {key_color};}}")
    svg_lines.append(f".value {{fill: {value_color};}}")
    svg_lines.append(f".cc {{fill: {dot_color};}}")
    svg_lines.append(f".add {{fill: {add_color};}}")
    svg_lines.append(f".del {{fill: {del_color};}}")
    svg_lines.append("text, tspan {white-space: pre;}")
    svg_lines.append("</style>")
    svg_lines.append(
        f'<rect width="985px" height="{svg_height}px" fill="{bg_color}" rx="15"/>'
    )

    # ASCII Art
    svg_lines.append(f'<text x="15" y="30" fill="{text_color}" class="ascii">')
    if ascii_art:
        for i, line in enumerate(ascii_art[:25]):
            y = 30 + i * 20
            svg_lines.append(f'<tspan x="15" y="{y}">{escape_xml(line)}</tspan>')
    svg_lines.append("</text>")

    # Profile section
    svg_lines.append(f'<text x="390" y="30" fill="{text_color}">')

    # Header
    svg_lines.append(make_header(390, 30, title, 60))

    # Profile info with dynamic dots
    svg_lines.append(
        make_line(390, 50, "OS", os_val, W, dot_color, key_color, value_color)
    )
    svg_lines.append(
        make_line(390, 70, "Uptime", uptime_val, W, dot_color, key_color, value_color)
    )
    svg_lines.append(
        make_line(390, 90, "Host", host_val, W, dot_color, key_color, value_color)
    )
    svg_lines.append(
        make_line(390, 110, "Kernel", kernel_val, W, dot_color, key_color, value_color)
    )
    svg_lines.append(
        make_line(390, 130, "IDE", ide_val, W, dot_color, key_color, value_color)
    )
    svg_lines.append(f'<tspan x="390" y="150" class="cc">. </tspan>')

    # Languages
    svg_lines.append(
        make_dotted_line(390, 170, "Languages", "Programming", lang_prog, W)
    )
    svg_lines.append(make_dotted_line(390, 190, "Languages", "Real", lang_real, W))
    svg_lines.append(f'<tspan x="390" y="210" class="cc">. </tspan>')

    # Hobbies
    svg_lines.append(make_dotted_line(390, 230, "Hobbies", "Software", hobby_sw, W))
    svg_lines.append(make_dotted_line(390, 250, "Hobbies", "Hardware", hobby_hw, W))

    # Contact section
    svg_lines.append(make_header(390, 290, "Contact", 60))
    contact_y = 310
    for label, value in contact_items:
        svg_lines.append(
            make_line(
                390, contact_y, label, value, W, dot_color, key_color, value_color
            )
        )
        contact_y += 20

    # Activity section
    activity_y = 290 + 20 + len(contact_items) * 20 + 20
    svg_lines.append(make_header(390, activity_y, "Activity", 60))
    svg_lines.append(
        make_double_line(
            390, activity_y + 20, "Commits", commits, "PRs Opened", prs_opened, 28, 26
        )
    )
    svg_lines.append(
        make_double_line(
            390, activity_y + 40, "PRs Reviewed", prs_reviewed, "Issues", issues, 28, 26
        )
    )
    svg_lines.append(
        make_double_line(
            390,
            activity_y + 60,
            "Current Streak",
            current_streak,
            "Longest Streak",
            longest_streak,
            28,
            26,
        )
    )
    svg_lines.append(
        make_double_line(
            390,
            activity_y + 80,
            "Best Day",
            f"{best_day} commits",
            "Avg",
            f"{avg_day}/day",
            28,
            26,
        )
    )

    # GitHub Stats section
    stats_y = activity_y + 120
    svg_lines.append(make_header(390, stats_y, "GitHub Stats", 60))
    svg_lines.append(
        make_double_line(390, stats_y + 20, "Repos", repos, "Stars", stars, 32, 22)
    )
    svg_lines.append(
        make_double_line(
            390,
            stats_y + 40,
            "Contributions",
            contributions,
            "Followers",
            followers,
            32,
            22,
        )
    )

    # Lines of Code line (double-line format with space-padded additions/deletions)
    total_loc = loc_stats["additions"] - loc_stats["deletions"]
    total_loc_str = f"{total_loc:,}"
    additions_str = f"{loc_stats['additions']:,}"
    deletions_str = f"{loc_stats['deletions']:,}"
    svg_lines.append(
        make_loc_line(
            390, stats_y + 60, total_loc_str, additions_str, deletions_str, 32, 22
        )
    )

    svg_lines.append("</text>")
    svg_lines.append("</svg>")

    # Write file
    filepath = os.path.join(os.path.dirname(__file__), filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_lines))


def generate_ascii_svg(filename, ascii_art, svg_height=570, is_dark=True):
    """Generate standalone ASCII art SVG"""
    if is_dark:
        bg_color = "#161b22"
        text_color = "#c9d1d9"
    else:
        bg_color = "#ffffff"
        text_color = "#1f2328"

    svg_lines = []
    svg_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    svg_lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" font-family="Consolas,monospace" width="390px" height="{svg_height}px" font-size="16px">'
    )
    svg_lines.append("<style>")
    svg_lines.append("text, tspan {white-space: pre;}")
    svg_lines.append("</style>")
    svg_lines.append(
        f'<rect width="390px" height="{svg_height}px" fill="{bg_color}" rx="15"/>'
    )

    svg_lines.append(f'<text x="15" y="30" fill="{text_color}" class="ascii">')
    if ascii_art:
        for i, line in enumerate(ascii_art[:25]):
            y = 30 + i * 20
            svg_lines.append(f'<tspan x="15" y="{y}">{escape_xml(line)}</tspan>')
    svg_lines.append("</text>")
    svg_lines.append("</svg>")

    filepath = os.path.join(os.path.dirname(__file__), filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_lines))


def generate_info_svg(filename, stats, activity, age, loc_stats, is_dark=True):
    """Generate standalone info section SVG"""
    profile = CONFIG.get("profile", {})

    if is_dark:
        bg_color = "#161b22"
        text_color = "#c9d1d9"
        key_color = "#ffa657"
        value_color = "#a5d6ff"
        dot_color = "#616e7f"
        add_color = "#3fb950"
        del_color = "#f85149"
    else:
        bg_color = "#ffffff"
        text_color = "#1f2328"
        key_color = "#953800"
        value_color = "#0550ae"
        dot_color = "#afb8c1"
        add_color = "#1a7f37"
        del_color = "#cf222e"

    # Data preparation
    title = profile.get("title", f"{USER_NAME}@github")
    os_val = profile.get("os", "Linux")
    uptime_val = age
    host_val = profile.get("host", "Earth")
    kernel_val = profile.get("kernel", "Developer")
    ide_val = profile.get("ide", "VSCode")

    lang_prog = profile.get("languages_programming", "Python")
    lang_real = profile.get("languages_real", "English")

    hobby_sw = profile.get("hobbies_software", "Coding")
    hobby_hw = profile.get("hobbies_hardware", "Computers")

    contact = profile.get("contact", {})
    contact_items = [(k.title(), v) for k, v in contact.items() if v]

    commits = f"{activity['total_commits']:,}"
    prs_opened = str(activity["total_prs"])
    prs_reviewed = str(activity["total_pr_reviews"])
    issues = str(stats["issues_opened"])
    current_streak = f"{activity['current_streak']} days"
    longest_streak = f"{activity['longest_streak']} days"
    best_day = str(activity["best_day_count"])
    avg_day = f"~{activity['avg_per_day']:.2f}"

    repos = str(stats["repositories"])
    stars = str(stats["stargazers"])
    contributions = f"{activity['total_contributions']:,}"
    followers = str(stats["followers"])

    W = 58

    # Calculate dynamic height based on contact items
    base_height = 270 + 20 + len(contact_items) * 20 + 20 + 100 + 80 + 50
    svg_height = max(600, base_height)

    svg_lines = []
    svg_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    svg_lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" font-family="Consolas,monospace" width="610px" height="{svg_height}px" font-size="16px">'
    )
    svg_lines.append("<style>")
    svg_lines.append(f".key {{fill: {key_color};}}")
    svg_lines.append(f".value {{fill: {value_color};}}")
    svg_lines.append(f".cc {{fill: {dot_color};}}")
    svg_lines.append(f".add {{fill: {add_color};}}")
    svg_lines.append(f".del {{fill: {del_color};}}")
    svg_lines.append("text, tspan {white-space: pre;}")
    svg_lines.append("</style>")
    svg_lines.append(
        f'<rect width="610px" height="{svg_height}px" fill="{bg_color}" rx="15"/>'
    )

    svg_lines.append(f'<text x="15" y="30" fill="{text_color}">')

    # Header
    svg_lines.append(make_header(15, 30, title, 60))

    # Profile info
    svg_lines.append(
        make_line(15, 50, "OS", os_val, W, dot_color, key_color, value_color)
    )
    svg_lines.append(
        make_line(15, 70, "Uptime", uptime_val, W, dot_color, key_color, value_color)
    )
    svg_lines.append(
        make_line(15, 90, "Host", host_val, W, dot_color, key_color, value_color)
    )
    svg_lines.append(
        make_line(15, 110, "Kernel", kernel_val, W, dot_color, key_color, value_color)
    )
    svg_lines.append(
        make_line(15, 130, "IDE", ide_val, W, dot_color, key_color, value_color)
    )
    svg_lines.append('<tspan x="15" y="150" class="cc">. </tspan>')

    # Languages
    svg_lines.append(
        make_dotted_line(15, 170, "Languages", "Programming", lang_prog, W)
    )
    svg_lines.append(make_dotted_line(15, 190, "Languages", "Real", lang_real, W))
    svg_lines.append('<tspan x="15" y="210" class="cc">. </tspan>')

    # Hobbies
    svg_lines.append(make_dotted_line(15, 230, "Hobbies", "Software", hobby_sw, W))
    svg_lines.append(make_dotted_line(15, 250, "Hobbies", "Hardware", hobby_hw, W))

    # Contact section
    svg_lines.append(make_header(15, 290, "Contact", 60))
    contact_y = 310
    for label, value in contact_items:
        svg_lines.append(
            make_line(15, contact_y, label, value, W, dot_color, key_color, value_color)
        )
        contact_y += 20

    # Activity section
    activity_y = 290 + 20 + len(contact_items) * 20 + 20
    svg_lines.append(make_header(15, activity_y, "Activity", 60))
    svg_lines.append(
        make_double_line(
            15, activity_y + 20, "Commits", commits, "PRs Opened", prs_opened, 28, 26
        )
    )
    svg_lines.append(
        make_double_line(
            15, activity_y + 40, "PRs Reviewed", prs_reviewed, "Issues", issues, 28, 26
        )
    )
    svg_lines.append(
        make_double_line(
            15,
            activity_y + 60,
            "Current Streak",
            current_streak,
            "Longest Streak",
            longest_streak,
            28,
            26,
        )
    )
    svg_lines.append(
        make_double_line(
            15,
            activity_y + 80,
            "Best Day",
            f"{best_day} commits",
            "Avg",
            f"{avg_day}/day",
            28,
            26,
        )
    )

    # GitHub Stats section
    stats_y = activity_y + 120
    svg_lines.append(make_header(15, stats_y, "GitHub Stats", 60))
    svg_lines.append(
        make_double_line(15, stats_y + 20, "Repos", repos, "Stars", stars, 32, 22)
    )
    svg_lines.append(
        make_double_line(
            15,
            stats_y + 40,
            "Contributions",
            contributions,
            "Followers",
            followers,
            32,
            22,
        )
    )

    # Lines of Code
    total_loc = loc_stats["additions"] - loc_stats["deletions"]
    total_loc_str = f"{total_loc:,}"
    additions_str = f"{loc_stats['additions']:,}"
    deletions_str = f"{loc_stats['deletions']:,}"
    svg_lines.append(
        make_loc_line(
            15, stats_y + 60, total_loc_str, additions_str, deletions_str, 32, 22
        )
    )

    svg_lines.append("</text>")
    svg_lines.append("</svg>")

    filepath = os.path.join(os.path.dirname(__file__), filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_lines))


def escape_xml(text):
    """Escape special XML characters"""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def dots_for(count):
    """Generate dot padding of specified length"""
    if count < 2:
        count = 2
    return "." * count + " "


def make_header(x, y, title, total_width=58):
    """Create a responsive section header with dynamic dash padding"""
    # Format: "- Title -———————————————————————————————————————————-—-"
    # The dashes fill to total_width characters
    prefix = f"- {title} "
    suffix = "-—-"
    # Each em-dash (—) is 1 character
    dashes_needed = total_width - len(prefix) - len(suffix)
    if dashes_needed < 1:
        dashes_needed = 1
    dashes = "—" * dashes_needed
    return f'<tspan x="{x}" y="{y}">{prefix}</tspan>{dashes}{suffix}'


def make_line(x, y, key, value, width, dot_color, key_color, value_color):
    """Create a single line with dynamic dot padding"""
    key_len = len(key) + 4  # ". " + key + ": "
    value_len = len(str(value))
    dots_count = width - key_len - value_len
    if dots_count < 2:
        dots_count = 2
    dots = "." * dots_count + " "
    return f'<tspan x="{x}" y="{y}" class="cc">. </tspan><tspan class="key">{key}</tspan>:<tspan class="cc"> {dots}</tspan><tspan class="value">{value}</tspan>'


def make_dotted_line(x, y, prefix, suffix, value, width):
    """Create a line with prefix.suffix: ... value format"""
    key = f"{prefix}.{suffix}"
    key_len = len(key) + 4  # ". " + key + ": "
    value_len = len(str(value))
    dots_count = width - key_len - value_len
    if dots_count < 2:
        dots_count = 2
    dots = "." * dots_count + " "
    return f'<tspan x="{x}" y="{y}" class="cc">. </tspan><tspan class="key">{prefix}</tspan>.<tspan class="key">{suffix}</tspan>:<tspan class="cc"> {dots}</tspan><tspan class="value">{value}</tspan>'


def make_double_line(x, y, key1, val1, key2, val2, width1, width2):
    """Create a line with two key-value pairs separated by |"""
    key1_len = len(key1) + 4
    val1_len = len(str(val1))
    dots1_count = width1 - key1_len - val1_len
    if dots1_count < 2:
        dots1_count = 2
    dots1 = "." * dots1_count + " "

    key2_len = len(key2) + 2
    val2_len = len(str(val2))
    dots2_count = width2 - key2_len - val2_len
    if dots2_count < 2:
        dots2_count = 2
    dots2 = "." * dots2_count + " "

    return f'<tspan x="{x}" y="{y}" class="cc">. </tspan><tspan class="key">{key1}</tspan>:<tspan class="cc"> {dots1}</tspan><tspan class="value">{val1}</tspan><tspan class="cc"> | </tspan><tspan class="key">{key2}</tspan>:<tspan class="cc"> {dots2}</tspan><tspan class="value">{val2}</tspan>'


def make_loc_line(x, y, loc_total, additions, deletions, width1, width2):
    """Create the Lines of Code line with space-padded additions/deletions on the right"""
    key = "Lines of Code"
    key_len = len(key) + 4  # ". " + key + ": "
    val_len = len(str(loc_total))
    dots_count = width1 - key_len - val_len
    if dots_count < 2:
        dots_count = 2
    dots = "." * dots_count + " "

    # Right side: space-padded additions and deletions
    add_str = f"{additions}++"
    del_str = f"{deletions}--"
    right_content_len = len(add_str) + 2 + len(del_str)  # "+2" for ", " separator
    spaces_needed = width2 - right_content_len
    if spaces_needed < 1:
        spaces_needed = 1
    spaces = " " * spaces_needed

    return f'<tspan x="{x}" y="{y}" class="cc">. </tspan><tspan class="key">{key}</tspan>:<tspan class="cc"> {dots}</tspan><tspan class="value">{loc_total}</tspan><tspan class="cc"> |{spaces}</tspan><tspan class="add">{add_str}</tspan><tspan class="cc">, </tspan><tspan class="del">{del_str}</tspan>'


if __name__ == "__main__":
    print("=" * 60)
    print("GitHub Profile Stats Generator")
    print("=" * 60)
    print(f"\nUser: {USER_NAME}")
    print("-" * 60)

    start_time = time.perf_counter()

    # Step 1: Fetch comprehensive user stats
    print("\n[1/4] Fetching user statistics...")
    stats = get_user_stats()
    print(f"       Name: {stats['name']}")
    print(f"       Joined GitHub: {years_ago(stats['created_at'])}")
    print(f"       Followed by: {stats['followers']} users")

    # Step 2: Get contribution years
    print("\n[2/4] Fetching contribution years...")
    years = get_contribution_years()
    print(f"       Contributing since: {min(years)}")

    # Step 3: Calculate streaks and activity
    print("\n[3/5] Calculating contributions and streaks...")
    activity = calculate_streaks_and_activity(years)

    # Calculate age
    age = daily_readme(BIRTHDAY)

    # Step 4: Fetch lines of code
    print("\n[4/5] Fetching lines of code...")
    loc_stats = get_lines_of_code()
    print(f"       Lines added: {loc_stats['additions']:,}")
    print(f"       Lines deleted: {loc_stats['deletions']:,}")

    total_time = time.perf_counter() - start_time

    # Print summary
    print("\n" + "=" * 60)
    print(f"  {stats['name']} (@{USER_NAME})")
    print("=" * 60)
    print(f"  Commits: {activity['total_commits']:,}")
    print(f"  Contributions: {activity['total_contributions']:,}")
    print(f"  Longest Streak: {activity['longest_streak']} days")
    print("-" * 60)
    print(f"  Total time: {total_time:.2f} seconds")
    print(f"  API calls: {sum(QUERY_COUNT.values())}")
    print("=" * 60)

    # Generate ASCII art from avatar if available
    ascii_art = None
    avatar_path = CONFIG.get("profile", {}).get("avatar_path")
    if avatar_path:
        full_path = os.path.join(os.path.dirname(__file__), avatar_path)
        ascii_width = CONFIG.get("profile", {}).get("ascii_width", 40)
        ascii_height = CONFIG.get("profile", {}).get("ascii_height", 25)
        print(f"\n[5/5] Generating ASCII art from {avatar_path}...")
        ascii_art = image_to_ascii(full_path, ascii_width, ascii_height)
        if ascii_art:
            print("       ASCII art generated successfully")
        else:
            print("       Skipping ASCII art (image not found)")
    else:
        print("\n[5/5] No avatar configured, skipping ASCII art")

    # Generate SVG files
    print("\n       Generating SVG files...")
    generate_svg(
        "dark_mode.svg", stats, activity, age, ascii_art, loc_stats, is_dark=True
    )
    print("       Updated: dark_mode.svg")
    generate_svg(
        "light_mode.svg", stats, activity, age, ascii_art, loc_stats, is_dark=False
    )
    print("       Updated: light_mode.svg")

    # Generate split SVG files
    print("\n       Generating split SVG files...")

    # Calculate dynamic height based on contact items
    profile = CONFIG.get("profile", {})
    contact = profile.get("contact", {})
    contact_items = [(k, v) for k, v in contact.items() if v]
    base_height = 270 + 20 + len(contact_items) * 20 + 20 + 100 + 80 + 50
    svg_height = max(600, base_height)

    generate_ascii_svg("ascii_dark.svg", ascii_art, svg_height, is_dark=True)
    print("       Updated: ascii_dark.svg")
    generate_ascii_svg("ascii_light.svg", ascii_art, svg_height, is_dark=False)
    print("       Updated: ascii_light.svg")
    generate_info_svg("info_dark.svg", stats, activity, age, loc_stats, is_dark=True)
    print("       Updated: info_dark.svg")
    generate_info_svg("info_light.svg", stats, activity, age, loc_stats, is_dark=False)
    print("       Updated: info_light.svg")

    print("\nDone!")
