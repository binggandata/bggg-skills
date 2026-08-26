# NGS Trend Opportunity Radar

[中文](./README.md)

`ngs-trend-opportunity-radar` is a Codex Skill for cross-border ecommerce opportunity research. It expands a user-defined broad category into 5–10 concrete product directions, validates them with Google Trends, TikTok, Reddit, Sorftime, and Amazon written reviews, and produces an auditable opportunity pool with one Top-1 direction.

It does not promise a winning product and does not replace sampling, cost, compliance, or final launch decisions.

## What it does

1. Generates 5–10 product directions from a user-confirmed broad category.
2. Compares search change and seasonality with Google Trends.
3. Uses visible TikTok videos and comments to validate content patterns and use cases.
4. Uses independent Reddit posts and comments to add community context and alternatives.
5. Uses Sorftime to validate category economics and representative products.
6. Uses Amazon US written reviews to analyze post-purchase problems.
7. Assigns transparent A/B/C/D opportunity grades.
8. Generates a self-contained HTML report, a 10-sheet Excel workbook, and Markdown.

## Workflow

```text
Configure Sorftime MCP on first use
→ Complete the research brief
→ Generate 5–10 product directions
→ Screen search trends with Google Trends
→ Validate content and use cases with TikTok and Reddit
→ Validate category and products with Sorftime
→ Validate post-purchase problems across Amazon ASINs
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

1. Broad category:
2. Target market:
3. Sales platform:
4. Output location:
```

The Agent first echoes the candidate directions, login environment, source-specific sample plan, market limitations, and Sorftime call budget. Collection and paid calls start only after explicit user confirmation.

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

| Source | Top-5 screening | Top-1 validation |
| --- | --- | --- |
| Google Trends | All 5–10 candidates; 12 months and 53 weekly points per term | Add five-year seasonality for Top 1 |
| TikTok | At least 10 relevant videos and 5 accounts per direction | At least 20 videos, 5 parent videos, and 100 valid comments |
| Reddit | At least 10 independent relevant posts per direction | At least 10 posts, 5 comment parent posts, and 100 valid comments |
| Sorftime | Do not deeply query every candidate | One category search plus one product search for Top 1 |
| Amazon | Collect only after selecting Top 1 | 3–10 representative ASINs and at least 100 written reviews |

Counts are coverage gates, not proof by themselves. Query semantics, parent-content independence, concentration, and market coverage remain mandatory checks.

## Sorftime call budget

- Normal Top-1 flow: 2 calls.
- If product results are semantically insufficient, pagination may reach page 3: worst case 4 calls.
- Default hard cap: 5 calls.
- More than 5 calls or product page 4 requires renewed user approval.
- `product_detail`, `product_reviews`, and `category_report` are disabled by default.

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

Current test count: 31.

## Disclaimer

This project supports research and decision-making. It does not guarantee sales, profit, compliance, investment returns, or launch approval. Google, TikTok, Reddit, Sorftime, and Amazon names and trademarks belong to their respective owners. This project is an independent workflow and is not officially affiliated with those platforms.

## License

MIT. See [LICENSE](./LICENSE).
