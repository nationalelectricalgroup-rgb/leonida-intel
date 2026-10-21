# Leonida Intel Trend Engine (starter)

## What this does
- Runs daily with GitHub Actions and can be started manually.
- Collects metadata from public Google News RSS searches, YouTube RSS search feeds, and Google's broad daily trending-search RSS feed.
- Groups matching headlines into broad GTA 6 topic buckets.
- Maintains current scores and up to 365 daily snapshots.
- Promotes active topics, cools down quiet topics, and archives topics after 14 days without a matching observation.
- Keeps a separate cautious evidence label. It does not fact-check claims and never treats popularity as proof.

## Important limitations
- Google News results are a **content-discovery signal**, not search-volume data.
- The Google Trends RSS feed is a broad daily trending-search feed. It may have zero GTA 6 matches on many days; it is not a GTA 6 keyword-volume API.
- YouTube's RSS search endpoint may change or limit results. A feed failure is logged rather than hidden.
- The trend score is a transparent heuristic from matching feed items and distinct domains, not total views, search volume, or a precise measure of public opinion.
- The first run has no prior baseline. Rankings improve as history accumulates.
- No AI API is used. The first version uses rules and public feed metadata.
- It does not copy full articles, video descriptions, thumbnails, or copyrighted media.

## Add to the existing repository
Upload these paths into the root of the existing `leonida-intel` repository, preserving folders:
- `.github/workflows/daily-trends.yml`
- `scripts/trend_engine.py`
- `data/trends.json`
- `data/trend-history.json`
- `README-TREND-ENGINE.md`

Do not replace your existing `index.html`, `README.md`, or `data/entry-schema.json`.

## Enable workflow permissions
In GitHub:
1. Open the `leonida-intel` repository.
2. Go to **Settings → Actions → General**.
3. Find **Workflow permissions**.
4. Choose **Read and write permissions**, then save.
5. Open the **Actions** tab and enable workflows if GitHub asks.

## Run a first test
1. Open **Actions**.
2. Select **Leonida Intel Daily Trend Engine**.
3. Click **Run workflow → Run workflow**.
4. Open the run and inspect its log.
5. If successful, the bot commits `data/trends.json` and `data/trend-history.json` to the repository. That commit should trigger Cloudflare Pages to redeploy.

The scheduled run is daily at approximately 07:20 UTC. GitHub scheduled jobs can start late during busy periods. A manual run is available for testing.

## Website integration is a separate next step
This starter writes `data/trends.json`, but the current static website will not display the trend list until `index.html` is updated to fetch and render that JSON. Keep the trend data pipeline separate from factual news publishing. We should integrate the UI after the first workflow run succeeds.

## Safety and maintenance
- Respect source terms, rate limits, and access policies. Public RSS does not grant permission to republish complete works.
- Treat all feed titles as untrusted text.
- Review workflow failures periodically.
- Scores and evidence labels are heuristic; verify important claims against original sources before publishing them as facts.
