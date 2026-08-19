# Aurora Station 🌌

**Fork your own personal aurora monitoring station.** Get free aurora alerts and a live dashboard for your location.

## Quick Start (2 minutes)

### 1. Fork this repo

Click the **Fork** button in the top right of this page.

### 2. Set your location

Go to your forked repo's **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret name | Value | Example |
|-------------|-------|--------|
| `AURORA_LAT` | Your latitude | `51.5` (London) |
| `AURORA_LON` | Your longitude | `-0.1` |
| `AURORA_LOCATION_NAME` | A label for your location | `London, UK` |
| `AURORA_WEBHOOK` | (Optional) Discord/Slack webhook URL for alerts | `https://discord.com/api/webhooks/...` |

**Find your coordinates:** [Google Maps](https://maps.google.com) → right-click your location → the coordinates appear at the top.

### 3. Enable GitHub Pages

Go to **Settings → Pages → Source: GitHub Actions**.

### 4. Wait for the first run

The monitor runs every 30 minutes. Your dashboard will be available at:

\`\`\`
https://<your-username>.github.io/aurora-station/
\`\`\`

## How It Works

1. **Every 30 minutes** — GitHub Actions runs the aurora check
2. **NOAA SWPC data** — Fetches the latest Kp index and aurora oval data
3. **Magnetic latitude** — Calculates your magnetic latitude from your geographic coordinates
4. **Visibility check** — Determines if the aurora oval extends to your location based on Kp
5. **Alert** — Sends a Discord/Slack notification when aurora is visible (only at night, only when Kp increases)
6. **Dashboard** — Updates a live HTML dashboard on GitHub Pages

## Features

- 🌌 **Real-time aurora visibility** for your exact location
- 🔔 **Discord/Slack alerts** when aurora is visible
- 📊 **Live dashboard** on GitHub Pages
- 🗺️ **Aurora oval tracking** using NOAA's OVATION model
- 🧲 **Magnetic latitude** calculation
- 🌙 **Nighttime detection** — only alerts when it's dark at your location
- 🚫 **No spam** — only alerts when Kp increases above your threshold

## Cost

**Free** — all components use free tiers:
- GitHub Actions (free for public repos)
- GitHub Pages (free)
- NOAA SWPC APIs (free, public)

## Customization

### Alert threshold

Edit `aurora_station.py` and change the visibility calculation in `kp_to_visibility()` to adjust how sensitive the alerts are.

### Check frequency

Edit `.github/workflows/aurora-station.yml` and change the cron schedule:
\`\`\`yaml
cron: '0,30 * * * *'  # Every 30 minutes (default)
cron: '0 * * * *'     # Every hour
cron: '0,15,30,45 * * * *'  # Every 15 minutes
\`\`\`

### Webhook format

The webhook payload uses Discord's embed format. For Slack, modify the `send_notification()` function in `aurora_station.py`.

## Data Sources

- [NOAA SWPC Planetary K-index](https://www.swpc.noaa.gov/products/planetary-k-index)
- [NOAA SWPC 3-Day Forecast](https://www.swpc.noaa.gov/products/3-day-forecast)
- [NOAA SWPC OVATION Aurora](https://www.swpc.noaa.gov/products/aurora-30-minute-forecast)

## About

Built by [Flarient](https://flarient.com) — the space weather intelligence platform. Part of the [Flarient Constellation](https://github.com/flarientglobal/flarient-constellation) — a GitHub-native, zero-cost space weather distribution network.

## License

MIT — fork it, modify it, share it.
