#!/usr/bin/env python3
"""Classify forum comments with Cloudflare's Clef and write an HTML report.

Usage:
    python classify.py                                  # clef-flash, comments.json -> results.html
    python classify.py --model clef                     # the larger model
    python classify.py --model clef --criteria v2 --input comments-v2.json --output results-v2.html
    python classify.py --input comments.json --output results.html --model clef-flash

Credentials are read from cloud-flare.local.sh (never committed).
Standard library only.
"""
import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request

LABELS = ["acceptable", "toxic", "spam"]

INSTRUCTIONS = (
    "Classify `comment`, a post written by a student in the discussion forum of "
    "an online college course on Generative AI (students discuss assignments, ask "
    "doubts, and share what they built with AI tools). Pick exactly one label."
)

CRITERIA_V1 = {
    "acceptable": (
        "A genuine forum post: a question, doubt, answer, progress update, opinion, "
        "or sharing of the student's own work. Includes frustration, complaints, "
        "blunt disagreement or criticism of ideas, the course or the platform, as long as "
        "no person is being attacked. Mentioning a link to one's own assignment is fine."
    ),
    "toxic": (
        "Attacks, insults, mocking, harassment, slurs, threats or demeaning remarks "
        "aimed at a person or group (a classmate, the instructor, a community). "
        "Criticism of an idea or of the course alone is NOT toxic; "
        "contempt for a person is."
    ),
    "spam": (
        "Promotion or solicitation unrelated to the course discussion: selling "
        "services (e.g. assignment writing), ads, referral or discount links, "
        "repeated copy-pasted promotional text, phone/WhatsApp numbers for business, "
        "or irrelevant mass-posted links."
    ),
}


# Version 2: tightened after reading round 1 mistakes (clef-flash missed insults
# aimed at the TA, gender stereotypes, and generalisations about groups of students).
INSTRUCTIONS_V2 = (
    "Classify `comment`, a post written by a student in the discussion forum of "
    "an online college course on Generative AI (students discuss assignments, ask "
    "doubts, and share what they built with AI tools). Pick exactly one label. "
    "Judge who or what the comment is aimed at: criticism of work, ideas, the "
    "course or a tool is fine, but contempt aimed at people is not, even when the "
    "wording is calm, sarcastic or sounds like an 'opinion'."
)

CRITERIA_V2 = {
    "acceptable": (
        "A genuine forum post: a question, doubt, answer, progress update, opinion, "
        "or sharing of the student's own work. Includes frustration, complaints, "
        "and blunt, even harsh, criticism of work, ideas, grading policy, the course "
        "or the platform, as long as it does not demean a person or a group. "
        "Politely raising a concern about a person's work is fine. "
        "Mentioning a link to one's own assignment is fine."
    ),
    "toxic": (
        "Disrespect aimed at people, not at ideas. Pick this if the comment: "
        "insults or mocks a named or identifiable person (a classmate, the TA, the "
        "instructor), including questioning their intelligence or competence in a "
        "demeaning way ('clueless', 'go back to school'); "
        "claims someone succeeds or fails because of their gender, region, "
        "religion, caste, language, college or hostel; "
        "makes sweeping negative generalisations about a group of people "
        "('they all copy', 'those people are...'); "
        "uses slurs, threats, or harassment. "
        "A comment can be toxic even if it is polite in tone or sounds like a fact. "
        "Plain criticism of the work, the course or the grading is NOT toxic."
    ),
    "spam": (
        "Promotion or solicitation unrelated to the course discussion: selling "
        "services (e.g. assignment writing), ads, referral or discount links, "
        "repeated copy-pasted promotional text, phone/WhatsApp numbers for business, "
        "or irrelevant mass-posted links. Sharing one's own assignment or a genuinely "
        "useful free resource in reply to a question is NOT spam."
    ),
}

CRITERIA_SETS = {
    "v1": (INSTRUCTIONS, CRITERIA_V1),
    "v2": (INSTRUCTIONS_V2, CRITERIA_V2),
}


def load_credentials(path="cloud-flare.local.sh"):
    try:
        text = open(path).read()
    except FileNotFoundError:
        sys.exit(f"Missing {path}. Copy cloud-flare.sh to {path} and fill in your values.")
    creds = dict(re.findall(r'export (\w+)="([^"]*)"', text))
    try:
        return creds["CLOUDFLARE_ACCOUNT_ID"], creds["CLOUDFLARE_API_TOKEN"]
    except KeyError:
        sys.exit(f"{path} must define CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN.")


def classify(text, account, token, model, criteria_set, retries=5):
    instructions, criteria = criteria_set
    payload = {
        "state": {"comment": text},
        "questions": {
            "label": {
                "type": "choice",
                "instructions": instructions,
                "criteria": criteria,
            }
        },
    }
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/cloudflare/{model}"
    for attempt in range(retries):
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.load(resp)
            if not data.get("success"):
                raise RuntimeError(f"API error: {data.get('errors')}")
            return data["result"]["answers"]["label"]
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(2 ** attempt)  # rate limited: back off and retry
                continue
            if e.code in (401, 403):
                sys.exit("Auth failed (401/403): check account ID and token permissions.")
            raise
        except urllib.error.URLError:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise


def build_html(rows, model, source, counts):
    esc = html.escape
    body = []
    for r in rows:
        probs = " / ".join(f"{k} {v:.2f}" for k, v in r["probabilities"].items())
        low = " lowconf" if r["confidence"] < 0.5 else ""
        body.append(
            f'<tr class="row {r["label"]}{low}" data-label="{r["label"]}">'
            f'<td>{r["id"]}</td>'
            f'<td><div class="meta">{esc(r["author"])} &middot; {esc(r["thread"])} &middot; {esc(r["posted_at"])}</div>'
            f'<div>{esc(r["comment"])}</div></td>'
            f'<td><span class="badge {r["label"]}">{r["label"]}</span></td>'
            f'<td class="conf">{r["confidence"]:.2f}<div class="probs">{esc(probs)}</div></td></tr>'
        )
    summary = " &middot; ".join(f"{k}: {counts.get(k, 0)}" for k in LABELS)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Clef moderation results ({esc(model)})</title>
<style>
:root {{ --bg:#fff; --fg:#1b1f24; --muted:#667085; --line:#e4e7ec;
  --ok:#067647; --okbg:#d1fadf; --tox:#b42318; --toxbg:#fee4e2; --spam:#b54708; --spambg:#fef0c7; --low:#f4f3ff; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#14171a; --fg:#e8eaed; --muted:#98a2b3; --line:#2b3138;
  --ok:#6ce9a6; --okbg:#0b3a26; --tox:#fda29b; --toxbg:#4a1713; --spam:#fec84b; --spambg:#4a2f08; --low:#1f1d3a; }} }}
body {{ font-family: system-ui, sans-serif; background:var(--bg); color:var(--fg); margin:0; padding:16px; }}
h1 {{ font-size:1.2rem; margin:0 0 4px; }} .sub {{ color:var(--muted); margin-bottom:12px; font-size:.9rem; }}
.filters button {{ border:1px solid var(--line); background:transparent; color:var(--fg); padding:6px 12px;
  border-radius:999px; cursor:pointer; margin-right:6px; }}
.filters button.active {{ background:var(--fg); color:var(--bg); }}
.wrap {{ overflow-x:auto; margin-top:12px; }}
table {{ border-collapse:collapse; width:100%; min-width:640px; }}
td, th {{ border-bottom:1px solid var(--line); padding:8px 10px; text-align:left; vertical-align:top; }}
th {{ position:sticky; top:0; background:var(--bg); font-size:.8rem; color:var(--muted); }}
.meta {{ color:var(--muted); font-size:.78rem; margin-bottom:2px; }}
.badge {{ padding:2px 10px; border-radius:999px; font-weight:600; font-size:.8rem; }}
.badge.acceptable {{ background:var(--okbg); color:var(--ok); }}
.badge.toxic {{ background:var(--toxbg); color:var(--tox); }}
.badge.spam {{ background:var(--spambg); color:var(--spam); }}
tr.lowconf td {{ background:var(--low); }}
.conf {{ white-space:nowrap; }} .probs {{ color:var(--muted); font-size:.72rem; }}
</style></head><body>
<h1>Clef moderation results</h1>
<div class="sub">Model: {esc(model)} &middot; Source: {esc(source)} &middot; {summary}
 &middot; Shaded rows = low confidence (&lt;0.50), worth a closer look</div>
<div class="filters">
 <button class="active" data-f="all">All</button>
 <button data-f="acceptable">Acceptable</button>
 <button data-f="toxic">Toxic</button>
 <button data-f="spam">Spam</button>
 <button data-f="lowconf">Low confidence</button>
</div>
<div class="wrap"><table><thead><tr><th>ID</th><th>Comment</th><th>Clef label</th><th>Confidence</th></tr></thead>
<tbody>{"".join(body)}</tbody></table></div>
<script>
document.querySelectorAll('.filters button').forEach(b => b.onclick = () => {{
  document.querySelectorAll('.filters button').forEach(x => x.classList.remove('active'));
  b.classList.add('active');
  const f = b.dataset.f;
  document.querySelectorAll('tbody tr').forEach(tr => {{
    tr.style.display = (f === 'all' || tr.dataset.label === f || (f === 'lowconf' && tr.classList.contains('lowconf'))) ? '' : 'none';
  }});
}});
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="comments.json")
    ap.add_argument("--output", default="results.html")
    ap.add_argument("--model", default="clef-flash", choices=["clef-flash", "clef"])
    ap.add_argument("--criteria", default="v1", choices=["v1", "v2"],
                    help="v1 = original criteria (round 1), v2 = tightened criteria")
    args = ap.parse_args()

    account, token = load_credentials()
    data = json.load(open(args.input, encoding="utf-8"))
    comments = data["comments"]

    rows, counts = [], {}
    for i, c in enumerate(comments, 1):
        ans = classify(c["comment"], account, token, args.model, CRITERIA_SETS[args.criteria])
        row = {**c, "label": ans["choice"], "probabilities": ans["probabilities"],
               "confidence": ans["confidence"]}
        rows.append(row)
        counts[row["label"]] = counts.get(row["label"], 0) + 1
        print(f"[{i}/{len(comments)}] id={c['id']} -> {row['label']} ({row['confidence']:.2f})")

    json_path = args.output.rsplit(".", 1)[0] + ".json"
    json.dump(rows, open(json_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    open(args.output, "w", encoding="utf-8").write(build_html(rows, f"{args.model}, criteria {args.criteria}", args.input, counts))
    print(f"\nWrote {args.output} and {json_path}. Counts: {counts}")


if __name__ == "__main__":
    main()
