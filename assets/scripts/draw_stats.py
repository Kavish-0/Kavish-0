import os
import json
import urllib.request
from xml.sax.saxutils import escape

USER = os.environ["GH_USER"]
TOKEN = os.environ["GH_TOKEN"]
RAMP = " .:+*#@"   # quiet -> loud
CW = 8.0           # width of one character cell

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { weekday contributionCount } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      nodes { languages(first: 10) { edges { size node { name } } } }
    }
  }
}
"""

STYLE = """<style>
text{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px;fill:#4c1d95}
.dim{fill:#8c959f}
.acc{fill:#7c3aed}
@media (prefers-color-scheme:dark){text{fill:#ddd6fe}.dim{fill:#7d8590}.acc{fill:#a78bfa}}
</style>"""


def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(f"GraphQL error: {body['errors']}")
    return body["data"]["user"]


def line(s, y, cls=""):
    # every character gets its own x, so the grid never drifts
    xs = " ".join(f"{i * CW:.1f}" for i in range(len(s)))
    return (f'<text x="{xs}" y="{y}" class="{cls}" '
            f'xml:space="preserve">{escape(s)}</text>')


def svg(parts, w, h):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">{STYLE}{"".join(parts)}</svg>\n')


def write(path, content):
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
    if old != content:  # only touch files that changed
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("updated", path)


def draw_streak(days):
    longest = run = 0
    for c in days:
        run = run + 1 if c else 0
        longest = max(longest, run)

    current = 0
    rev = days[::-1]
    if rev and rev[0] == 0:  # today isn't over yet
        rev = rev[1:]
    for c in rev:
        if c == 0:
            break
        current += 1

    parts = [
        line(f"CURRENT STREAK  {current:>4} DAYS", 20, "acc"),
        line(f"LONGEST STREAK  {longest:>4} DAYS", 42, "dim"),
    ]
    write("assets/streak.svg", svg(parts, 280, 52))


def draw_year(weeks, total):
    counts = [d["contributionCount"] for w in weeks for d in w["contributionDays"]]
    peak = max(counts, default=0) or 1
    labels = {1: "MON ", 3: "WED ", 5: "FRI "}

    parts = [line(f"LAST YEAR · {total} CONTRIBUTIONS", 16, "dim")]
    for r in range(7):
        row = labels.get(r, "    ")
        for w in weeks:
            day = next((d for d in w["contributionDays"] if d["weekday"] == r), None)
            if day is None:
                row += " "
            elif day["contributionCount"] == 0:
                row += "."
            else:
                level = 2 + round(day["contributionCount"] / peak * (len(RAMP) - 3))
                row += RAMP[level]
        parts.append(line(row, 38 + r * 16))

    width = int((4 + len(weeks)) * CW) + 10
    write("assets/year.svg", svg(parts, width, 38 + 7 * 16))


def draw_languages(repos):
    totals = {}
    for repo in repos:
        for e in repo["languages"]["edges"]:
            name = e["node"]["name"]
            totals[name] = totals.get(name, 0) + e["size"]

    grand = sum(totals.values())
    top = sorted(totals.items(), key=lambda kv: -kv[1])[:6]

    if not top:
        parts = [line("NO PUBLIC REPOSITORIES YET", 20, "dim")]
        write("assets/languages.svg", svg(parts, 300, 30))
        return

    parts = []
    for i, (name, size) in enumerate(top):
        pct = size / grand
        filled = round(pct * 24)
        bar = "#" * filled + "." * (24 - filled)
        label = name.upper()[:12]
        parts.append(line(f"{label:<12} {bar} {pct:6.1%}", 20 + i * 22,
                          "acc" if i == 0 else ""))
    write("assets/languages.svg", svg(parts, 360, 20 + len(top) * 22))


def main():
    os.makedirs("assets", exist_ok=True)
    user = fetch()
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    days = [d["contributionCount"] for w in weeks for d in w["contributionDays"]]

    draw_streak(days)
    draw_year(weeks, cal["totalContributions"])
    draw_languages(user["repositories"]["nodes"])


if __name__ == "__main__":
    main()
