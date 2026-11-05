# Freshness playbook

How this hub stays current. The same file is used in `ntphiep/aib-c01-hub`, `ntphiep/databricks-dep-hub` and `ntphiep/dp-700-hub`.

## How it works

1. Every Monday at 00:00 UTC the workflow `.github/workflows/freshness.yml` runs `python3 -I freshness.py`. The script reads `src/watch.json` and every source url in `src/data/`. It does not use an LLM.
2. The script keeps its state on the branch `freshness`. When something changed it writes `freshness/reports/<date>.json` and `.md` on that branch and opens a GitHub issue with label `freshness`.
3. Every Monday at 02:00 UTC a scheduled Claude Code cloud agent follows the section "Agent steps" below. It pushes a branch `claude/freshness-<date>`.
4. The workflow `.github/workflows/freshness-pr.yml` opens a pull request from that branch when it changes files. The owner reviews and merges it.

## Agent steps

You work in a clone of this repository. Do not spawn subagents. Today's date comes from `date -u +%F`.

1. Run `git fetch origin freshness` and `git ls-remote --heads origin 'claude/freshness-*'`. The newest date in those branch names is the last processed report. List the reports with `git ls-tree --name-only origin/freshness freshness/reports/`. The reports to process are the `.json` files dated after the last processed report. If there are none, stop and print "No new freshness report".
2. Read each report with `git show origin/freshness:freshness/reports/<date>.json`. Read `SCHEMA.md` and `src/site.json` completely before you edit anything.
3. Handle the items in this order. For every item open the official page with WebFetch; memory is only a hypothesis.
   - `exam`: the exam guide changed. Compare the new guide with `src/site.json` (domains, tasks, weights) and the topics. Update every place that no longer matches, including `research/` when the folder is in the repository. This has the highest priority.
   - `releases`: new release notes. Keep only items that change a fact the hub teaches or that the exam outline in `src/site.json` covers: a rename, GA or preview status, a deprecation, a changed default or limit, a new feature inside an exam task. Add or fix the text with callout tone `new` and the release-note url as the source. Ignore the other items.
   - `changed`: the page cited in `where` has a newer version. Compare the page with the hub text in that section and fix what differs.
   - `broken` and `moved`: replace the url with the current official page after you confirm it supports the same fact. A redirect to a different topic (for example a retired whitepaper) means the source is gone: find the current official source or remove the claim.
   - `unreachable`: open the url with WebFetch. Change nothing when it still works.
4. Keep every rule of `SCHEMA.md`: Vietnamese text with English terms, at least 1 source per section, real vendor images only, license rules for figures.
5. Run the checks in `README.md`: the validator must print OK and `npm ci && node build.mjs` must report 0 layout warnings.
6. Create the branch `claude/freshness-<date of the newest processed report>`, commit and push it, even when nothing needed a change (then use `git commit --allow-empty`), so the next run knows this report is done.
   - Commit subject: `Freshness update <date>` or `Freshness review <date>: no content change`.
   - Commit body: one line per changed fact with the file, the old and new statement and the source url, then one line listing the report items that needed no change and why. The pull request uses this body as its description.
7. Do not edit `freshness.py`, the workflows or this file. Do not push to `main` or `freshness`.
