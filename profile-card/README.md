# Profile Card

## Layout

```
config.yml          -> personal/manual data (identity, stack, journey, ...)
generate_card.py     -> entry point: config + API -> output/card.svg
requirements.txt
src/
  github_api.py       -> GitHub REST + GraphQL client
  statistics.py        -> repo/follower/star/contribution metrics, featured-repo selection
  languages.py          -> language byte aggregation
  svg_generator.py       -> presentation only, builds the SVG
output/
  card.svg              -> generated file, committed by CI
```

## Testing locally

```bash
pip install -r profile-card/requirements.txt
python3 profile-card/generate_card.py
```

This writes `profile-card/output/card.svg`. Open it directly in a browser
(`xdg-open profile-card/output/card.svg`) to check the layout, or open the
repo's `README.md` in a Markdown previewer that renders local images.

Unauthenticated runs work fine for a quick check (GitHub allows 60
requests/hour without a token) but skip the `CONTRIBUTIONS` row in
`github.stats`, since that needs a token (see below). Set `CARD_TOKEN` in
your shell before running to test the full card locally:

```bash
CARD_TOKEN=ghp_xxx python3 profile-card/generate_card.py
```

To confirm the output is safe to embed in a GitHub README (no elements
GitHub's SVG sanitizer strips), check for banned tags:

```bash
grep -oE '<script|<foreignObject|xlink:href' profile-card/output/card.svg
# should print nothing
```

## Testing on GitHub

Once pushed, go to the repo's **Actions** tab → *Update Profile Card* →
**Run workflow** to trigger `workflow_dispatch` manually instead of waiting
for the cron schedule. Check the run logs, then confirm
`profile-card/output/card.svg` was committed (only happens if it actually
changed) and that it renders correctly in the README on the repo's main
page.

## Enabling the CONTRIBUTIONS stat

GitHub's REST API has no "total contributions" endpoint — only GraphQL does,
and it needs a real user token (the default `GITHUB_TOKEN` Actions injects
can't resolve it for an arbitrary user). Without a token, that row is simply
omitted from `github.stats`; everything else still renders.

To enable it:

1. Create a **classic** Personal Access Token with only the `read:user` scope
   (Settings → Developer settings → Personal access tokens → Tokens
   (classic)).
2. Add it as a repository secret named `CARD_TOKEN`
   (Settings → Secrets and variables → Actions → New repository secret).

## Configuration

All manually-curated content (name, current focus, tech stack, journey,
featured project override, organizations, contacts, theme colors) lives in
`config.yml`. Anything derived from the GitHub API (repo count, followers,
stars, languages, contributions, account uptime) is never hand-edited.
