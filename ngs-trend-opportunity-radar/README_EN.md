# NGS Trend Opportunity Radar

[中文](./README.md)

`ngs-trend-opportunity-radar` is a Codex Skill for cross-border ecommerce opportunity research. It uses the official Sorftime category tree, asks the user which branches to expand, adds a market report for every confirmed direction, screens all directions with Google Trends, TikTok, and Reddit, then deep-validates the user-selected Top N with Sorftime products and Amazon written reviews.

It does not promise a winning product and does not replace sampling, cost, compliance, or final launch decisions.

## What it does

1. Uses the official Sorftime category tree and lets the user choose which branches to expand.
2. Keeps every semantically relevant concrete product direction and discloses exclusions.
3. Runs Google Trends, TikTok, and Reddit screening for every valid direction.
4. Explains each direction's passes, blockers, keep/drop decision, and reasons.
5. Lets the user choose Top N for deep validation.
6. Searches representative products and analyzes Amazon US reviews for each selected direction.
7. Assigns A/B/C/D grades to the full pool and improvement directions to deep-validated candidates.
8. Generates a self-contained HTML report, a 10-sheet Excel workbook, and Markdown.

## Workflow

```text
Configure Sorftime MCP on first use
→ Complete the research brief
→ Show first-level branches from the official Sorftime category tree
→ Let the user confirm branches (four expansions by default)
→ Add one Sorftime market report per confirmed direction
→ Screen every valid direction with Google Trends, TikTok, and Reddit
→ Show the complete funnel, blockers, and exclusion reasons
→ Let the user choose Top N
→ Deep-validate Top N with Sorftime products and Amazon multi-ASIN reviews
→ Produce an A/B/C/D opportunity pool and product directions
```

## First use

### 1. Configure Sorftime MCP

Open <https://open.sorftime.com/mcp>, register, and follow the page instructions to add your Sorftime Key to your AI tool's MCP settings.

New registrations currently receive three days and 100 calls. Promotions may change; the latest terms on the Sorftime page prevail.

Never paste the Key into a chat, Issue, log, report, or Skill file. After configuration, reply only with “configured.”

### 2. Complete the research brief

```text
[Trend Opportunity Research Brief]

1. Starting research category:
2. Target market:
3. Sales platform:
4. Output location:
```

The Agent first echoes the login environment, market limitations, and category-tree budget. Each research category defaults to five tree calls: one first-level view and four user-confirmed branch expansions. The user may choose fewer, more, or none. Each confirmed parent branch becomes one candidate direction, receives one market report, and then enters free-source screening. The user chooses Top N only after seeing the full funnel.

## Installation

Python 3.10 or later is required.

```bash
git clone https://github.com/binggandata/bggg-skills.git
cd bggg-skills
mkdir -p ~/.codex/skills
cp -R ngs-trend-opportunity-radar bggg-data-amazon ~/.codex/skills/
```

For development, use a symlink:

```bash
ln -s "$PWD/ngs-trend-opportunity-radar" ~/.codex/skills/ngs-trend-opportunity-radar
ln -s "$PWD/bggg-data-amazon" ~/.codex/skills/bggg-data-amazon
```

The TikTok CDP collector requires Python Playwright:

```bash
python3 -m pip install -r ngs-trend-opportunity-radar/scripts/requirements.txt
```

Amazon review collection depends on `bggg-data-amazon` from this repository. Excel generation uses `@oai/artifact-tool` from the Codex Spreadsheets runtime. Outside Codex, provide a compatible workbook-generation environment.

## Invocation

```text
Use ngs-trend-opportunity-radar to research multi-platform product opportunities.
```

## Default sample gates

| Source | All-direction screening | User-selected Top-N validation |
| --- | --- | --- |
| Google Trends | Every valid direction; 12 months and 53 weekly points per term | Optional five-year seasonality |
| TikTok | At least 10 relevant videos and 5 accounts per direction | No mandatory 100-comment gate by default |
| Reddit | At least 10 independent relevant posts per direction | No mandatory 100-comment gate by default |
| Sorftime | Official category tree plus one market report per direction | Product search for every selected direction |
| Amazon | Not collected during screening | 3–10 representative ASINs and at least 100 written reviews per direction |

Counts are coverage gates, not proof by themselves. Query semantics, parent-content independence, concentration, and market coverage remain mandatory checks.

## Sorftime call budget

- Each research category defaults to five category-tree calls: one first-level view plus four confirmed branch expansions.
- Market reports cost one call per confirmed direction and are counted separately.
- After the user chooses Top N, product-pool validation adds at least N and at most 3 × N calls.
- Forecasts above five calls require explicit approval of the minimum and worst-case budget.
- `product_detail` and `product_reviews` are disabled by default; `category_report` supplies market size for every candidate.

## Reddit and authenticated old Reddit

```text
OAuth when configured
→ public JSON on www.reddit.com
→ same-origin JSON in a user-confirmed logged-in old.reddit.com session
→ visible DOM in logged-in old Reddit
```

Anonymous API collection never targets old Reddit. A 403, login wall, challenge, or non-JSON response is a route failure, not evidence of zero demand.

## Output

The three user-facing deliverables are:

```text
report/report.html
report/research_data.xlsx
report/report.md
```

The Excel workbook contains 10 sheets: Data Coverage, Google Trends, TikTok Videos, TikTok Comments, Reddit Posts, Reddit Comments, Sorftime Category, Sorftime Products, Amazon Reviews, and Evidence Index.

Raw JSON/JSONL, internal CSV files, screenshots, failure logs, and validation artifacts remain in the user-selected run directory and are not committed.

## Security and privacy

- Never persist Sorftime Keys, Reddit tokens, cookies, passwords, or browser credentials.
- Ask the user to choose when multiple browser login environments are available.
- The TikTok collector only navigates, scrolls, and reads visible pages. It does not like, comment, follow, message, or publish.
- Never bypass CAPTCHA, challenge pages, risk controls, or login walls.
- Report image fetching accepts public HTTP(S) URLs only and rejects localhost, loopback, private, and link-local IPs.
- `.gitignore` excludes outputs, `node_modules`, caches, archives, and local run data.

Use the Skill in accordance with applicable law, platform terms, and your organization's data-governance policies.

## Development and tests

```bash
python3 -m unittest discover -s ngs-trend-opportunity-radar/tests -p 'test_*.py'
```

Current test count: 33.

## Disclaimer

This project supports research and decision-making. It does not guarantee sales, profit, compliance, investment returns, or launch approval. Google, TikTok, Reddit, Sorftime, and Amazon names and trademarks belong to their respective owners. This project is an independent workflow and is not officially affiliated with those platforms.

## License

MIT. See [LICENSE](./LICENSE).
