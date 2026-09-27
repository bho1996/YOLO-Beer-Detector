# 🍻 1M Beers — website

A static Vue 3 + Vite + ECharts site. It doesn't need a server: it's rebuilt and published on
GitHub Pages every time the bot pushes `1m_beers.db` (see `.github/workflows/pages.yml`).

```
bot (NAS) ──push 1m_beers.db──▶ GitHub Action ──export_data.py──▶ data.json ──▶ GitHub Pages
                                                                        ▲
                                            the page re-checks it every 60 s (auto-update)
```

## Local development
```bash
cd web
npm install
npm run data     # creates public/data.json from ../1m_beers.db (needs python + pandas)
npm run dev
```

## Configuration
Set these as **Repository variables** (Settings → Secrets and variables → Actions → Variables),
or put them in `web/.env` when developing locally with the `VITE_` prefix:
`STRIPE_LINK`, `PAYPAL_LINK`, `BUYMEACOFFEE_LINK`, `MONTHLY_COSTS_EUR`,
`DONATED_THIS_MONTH_EUR`, `SUPPORTERS` (comma separated), `PINT_PRICE_EUR`.

## Counting rules
- Global counter: approved photo = 1 beer, down video = 1 beer. The headline number is the
  bot's `OFFICIAL_TOTAL` (kept in line with the group). The part the bot didn't track is shown as "untracked".
- Leaderboards: approved photo = 1 point, down video = 5 points.
