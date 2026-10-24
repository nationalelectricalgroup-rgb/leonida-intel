LEONIDA INTEL — SIMPLIFIED SITE

FILES TO UPLOAD TO THE ROOT OF THE EXISTING GITHUB REPOSITORY:
- index.html
- missions.html
- newsletter.html
- styles.css
- site.js
- 404.html

IMPORTANT: Do NOT delete or replace these existing automation/data items:
- data/trends.json
- data/trend-history.json
- scripts/trend_engine.py
- .github/workflows/daily-trends.yml

REMOVE THESE OLD WEBSITE PAGES FROM THE REPOSITORY (if present):
- gameplay.html
- characters.html
- tips.html
- videos.html
- release.html
- news.html

You can delete these six old pages because the simplified navigation now routes to missions.html and newsletter.html. Do not delete the data/ or scripts/ folders or the workflow.

UPLOAD:
1. Extract this ZIP.
2. Upload the six website files listed above to the repository root and replace matching files.
3. Delete the six old website pages listed above in GitHub (if present). You can do this in the same commit as the upload, or in a second commit.
4. Leave all other files alone.
5. Commit: Simplify Leonida Intel website and navigation.
6. Wait for Cloudflare Pages to deploy. Cloudflare Pages serves a root index.html and supports ordinary static HTML files. See https://developers.cloudflare.com/pages/framework-guides/deploy-anything/.

CHECKS PERFORMED ON THIS BUNDLE:
- All internal navigation targets exist in the ZIP.
- All internal fragment links point to IDs on the destination page.
- Shared stylesheet and JavaScript paths exist.
- JavaScript syntax validated with Node.js.
- JSON trend loader handles common array/topics/trends formats and shows a graceful fallback if data is unavailable.
- No newsletter form collects addresses yet. The newsletter page explicitly explains sign-up is not live until delivery and unsubscribe handling are configured.

LIMITATIONS:
- This is a static-site code check, not a live browser test of your Cloudflare deployment.
- Trend labels/ranking are heuristic. The homepage filters obvious unrelated topics but cannot replace a full audit of the trend engine.
- The hero artwork is CSS illustration and does not imply it is an official GTA VI screenshot.
