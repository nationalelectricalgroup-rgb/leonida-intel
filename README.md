# Leonida Intel — GTA 6 Knowledge Hub (prototype v0.1)

A zero-cost, static prototype for an independent GTA 6 fan knowledge hub.

## Included
- Responsive landing page and search
- Evidence/status labels: Confirmed, Reported — verify, Rumour/theory, Guide/reference
- Basic relevance-ranked briefing cards
- Searchable knowledge entries and category/status filters
- Location directory with source notes
- Video/content section ready for a source-compliant ranking pipeline
- Post-launch guide placeholders
- No external libraries, paid APIs, analytics, accounts, cookies or trackers

## Run locally
Open `index.html` in a browser. It is a static site and needs no build step.

## Deploy free with Cloudflare Pages
1. Create a GitHub account/repository and upload `index.html` (plus this README and `data/`).
2. In Cloudflare, open Workers & Pages -> Create -> Pages -> Connect to Git.
3. Select the repository. For a plain static site, leave the build command blank and set the build output directory to `/` (or the repository root, depending on the dashboard).
4. Deploy. Cloudflare provides a free `pages.dev` address. Do not buy a custom domain for the prototype.

Check current plan terms and limits before deployment; free-plan details can change.

## Editing the starter data
For this first prototype, entries are embedded in the JavaScript arrays in `index.html` (`entries`, `locations`, and `videos`). This keeps the demo simple. The next build step should move data to JSON and add a scheduled ingestion/review workflow.

## Important limitations
- This is a prototype, not yet an autonomous publishing system.
- Sample entries are manually seeded and need re-checking before relying on them. Dates indicate the prototype's last check, not a guarantee that facts remain current.
- The location explorer is a directory, not a geospatial interactive map.
- Video ranking is illustrative and not connected to YouTube or any crawler.
- No email collection or newsletter sending is enabled.
- No prices or retailer discounts are asserted; offer data needs region, currency, source URL and last-checked timestamp.
- Only scrape public content where permitted; respect terms, robots guidance, rate limits, copyright and privacy law. Store concise summaries, evidence notes and links, not copied articles.
- Clearly identify the site as an unofficial fan project. Do not use Rockstar logos, game assets, leaked material or imply endorsement.
- Before publication, verify all factual entries and update the source timestamps. Any unverified claims should stay labelled as rumours/theories.

## Next milestones
1. Verify the content and evidence policy.
2. Research competitors and test demand.
3. Move entries into a structured JSON dataset with source, source type, evidence, confidence, timestamps, tags and relationships.
4. Add compliant scheduled source discovery and duplicate detection.
5. Add a real map layer only when we have reliable, permitted location data.
6. Add opt-in newsletter only after choosing a no-cost sending method and setting safeguards.
7. Add analytics using a privacy-conscious free option only if useful.

## Ranking model (proposed)
Relevance 30%, source quality 25%, evidence strength 20%, freshness 15%, distinctiveness/usefulness 10%.
Hard rule: a high score cannot turn a rumour into a confirmed fact. Evidence status and ranking are separate.
