# DP-700 Study Hub

Static study site for Microsoft DP-700, Fabric Data Engineer Associate, live at https://dp-700-hub.vercel.app (Vercel project `dp-700-hub`).

| Path | Content |
|---|---|
| `src/site.json` | Exam config: domains, tasks, topics, home tiles, mock sizes, glossary categories, accent colors |
| `src/index.html` | App shell shared by all study hubs: navigation, search, light/dark theme, chapters, glossary, sources page, quiz, mock exam, flashcards |
| `src/data/topics/` | Chapters by exam section, listed in `src/site.json` |
| `src/data/quiz/`, `src/data/cards/` | Quiz questions and flashcards per chapter |
| `src/data/resources.json` | Curated external study sources shown on the page Nguồn học |
| `src/data/glossary-parts/` | Glossary terms per chapter; the build merges them and links the first mention in each section to a popover |
| `src/icons/` | `fab-*`: official Microsoft Fabric icons (`@fabric-msft/svg-icons` 6.1.0 from https://learn.microsoft.com/en-us/fabric/fundamentals/icons); `az-*`: Azure Architecture Icons V24; `logo-*` and `dbx-*`: Databricks icons from https://github.com/oieduardorabelo/databricks-architecture-icons; other names: Tabler outline icons (MIT) recolored to the accent, for generic concepts |
| `src/figs/` | Unmodified images from learn.microsoft.com/fabric (MicrosoftDocs/fabric-docs, CC BY 4.0) used by `figure` blocks, named `<topic>-<what>.<ext>` |
| `src/fav/` | Favicons of the hosts on the page Nguồn học, downloaded by `node favicons.mjs` |
| `research/` | Skills measured from the official study guide, local only and excluded from git |
| `diagram.mjs` | ELK auto layout and SVG rendering for diagrams |
| `build.mjs` | Builds `src/` into `dist/`, merges the glossary, creates the search index and the task map |
| `validate.py` | Content rules (schema, English terms, option counts, at least 1 source per section and 3 hosts per topic) |
| `SCHEMA.md` | Content format and writing rules |

Edit content, then run:

```
python3 -I validate.py src/data/topics/*.json src/data/quiz/*.json src/data/cards/*.json src/data/glossary-parts/*.json src/data/resources.json
node build.mjs --check <topicId>   # 0 layout warnings, screenshot in preview/<topicId>.png
node build.mjs                     # full build into dist/
```

Progress sync uses the Supabase project `hnpixqdvxszxjwovtusr` (RPCs `get_progress` and `save_progress`) with its own sync code; local progress lives in `localStorage` keys from `storeKey` and `syncKey` in `src/site.json`.

Deploy: after `node build.mjs`, run `npx vercel deploy dist --prod --yes --project dp-700-hub --scope nguyen-hieps-projects` with a token of Vercel account `ntphiep` (Composio connection `legacy`).

The engine files `src/index.html`, `build.mjs`, `diagram.mjs`, `validate.py` and `favicons.mjs` are identical in `/home/harry/W/aib-c01-hub`, `/home/harry/W/databricks-dep-hub` and `/home/harry/W/dp-700-hub`. Change them in one hub, then copy them to the other two.
