#!/usr/bin/env python3
"""
Aurora Station — Personal Aurora Monitor
Fork this repo to get your own aurora alert system.

How it works:
1. Set your location (latitude, longitude) in GitHub Secrets
2. Runs every 30 minutes during your local nighttime
3. Fetches Kp forecast from NOAA SWPC
4. Calculates your magnetic latitude and aurora visibility
5. Sends an alert when aurora is likely visible from your location
6. Updates your personal aurora dashboard on GitHub Pages

Zero cost: GitHub Actions + Pages + free NOAA APIs
"""

import os
import sys
import json
import math
import requests
from datetime import datetime, timezone, timedelta

# ── Configuration ──────────────────────────────────────────────────────────
LAT = float(os.environ.get("AURORA_LAT", "51.5"))
LON = float(os.environ.get("AURORA_LON", "-0.1"))
LOCATION_NAME = os.environ.get("AURORA_LOCATION_NAME", "My Location")
NOTIFICATION_WEBHOOK = os.environ.get("AURORA_WEBHOOK", "")  # Discord/Slack webhook
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")
GITHUB_WORKSPACE = os.environ.get("GITHUB_WORKSPACE", ".")

NOAA_KP_FORECAST_URL = "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json"
NOAA_3DAY_FORECAST_URL = "https://services.swpc.noaa.gov/text/3-day-forecast.txt"
NOAA_AURORA_OVAL_URL = "https://services.swpc.noaa.gov/json/ovation_aurora_latest.json"

# ── Magnetic latitude calculation ─────────────────────────────────────────
# Simplified magnetic latitude from geographic coordinates using the
# IGRF-13 dipole approximation. Good enough for aurora visibility estimation.
def geographic_to_magnetic(lat, lon):
    """Convert geographic lat/lon to magnetic latitude using simplified IGRF."""
    # North magnetic pole (2025 estimate)
    mag_pole_lat = 80.8
    mag_pole_lon = -72.4

    # Convert to radians
    lat_r = math.radians(lat)
    lon_r = math.radians(lon)
    pole_lat_r = math.radians(mag_pole_lat)
    pole_lon_r = math.radians(mag_pole_lon)

    # Angular distance to magnetic pole
    cos_d = (math.sin(lat_r) * math.sin(pole_lat_r) +
             math.cos(lat_r) * math.cos(pole_lat_r) * math.cos(lon_r - pole_lon_r))
    cos_d = max(-1, min(1, cos_d))
    d = math.degrees(math.acos(cos_d))

    # Magnetic latitude = 90 - distance to magnetic pole
    mag_lat = 90 - d
    return mag_lat


def kp_to_visibility(mag_lat, kp):
    """
    Determine aurora visibility from magnetic latitude and Kp index.
    The aurora oval extends equatorward as Kp increases.
    Returns: (visible, probability, min_kp_for_visibility)
    """
    # Minimum Kp needed for aurora to be visible from a given magnetic latitude
    # Based on the empirical relationship: mag_lat ≈ 67 - Kp * 3
    # So Kp needed = (67 - mag_lat) / 3
    min_kp = max(0, (67 - mag_lat) / 3)

    if kp >= min_kp:
        # Probability based on how far above the threshold we are
        excess = kp - min_kp
        if excess >= 2:
            probability = "Very High"
        elif excess >= 1:
            probability = "High"
        elif excess >= 0.5:
            probability = "Moderate"
        else:
            probability = "Low"
        return True, probability, min_kp
    return False, "None", min_kp


def is_nighttime(lat, lon):
    """Check if it's currently nighttime at the given location (approximate)."""
    # Simplified: use UTC offset based on longitude (15° = 1 hour)
    utc_offset = lon / 15.0
    local_hour = (datetime.now(timezone.utc).hour + utc_offset) % 24
    # Nighttime = 18:00 to 06:00 local
    return local_hour >= 18 or local_hour < 6


# ── Data fetchers ───────────────────────────────────────────────────────────
def fetch_kp():
    """Fetch the latest Kp index."""
    try:
        resp = requests.get(NOAA_KP_FORECAST_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data:
            latest = data[-1]
            return float(latest.get("kp", 0)), latest.get("time_tag", "")
    except Exception as e:
        print(f"[aurora-station] Kp fetch failed: {e}")
    return None, None


def fetch_kp_forecast():
    """Fetch the 3-day Kp forecast and extract upcoming high-Kp periods."""
    try:
        resp = requests.get(NOAA_3DAY_FORECAST_URL, timeout=15)
        resp.raise_for_status()
        text = resp.text
        # Parse the 3-day forecast text for Kp predictions
        forecast = []
        for line in text.split("\n"):
            if line.strip().startswith("NOAA Kp") or "Kp=" in line:
                forecast.append(line.strip())
        return forecast[:10]  # Return top 10 lines
    except Exception as e:
        print(f"[aurora-station] Kp forecast fetch failed: {e}")
    return []


def fetch_aurora_oval():
    """Fetch the latest aurora oval data and check if location is inside."""
    try:
        resp = requests.get(NOAA_AURORA_OVAL_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # The ovation aurora data has a 'coordinates' array with [lon, lat, probability]
        coords = data.get("coordinates", [])
        if not coords:
            return 0

        # Find the nearest grid point to our location
        min_dist = float("inf")
        nearest_prob = 0
        for row in coords:
            for point in row:
                p_lon, p_lat, prob = point
                dist = math.sqrt((p_lat - LAT) ** 2 + (p_lon - LON) ** 2)
                if dist < min_dist:
                    min_dist = dist
                    nearest_prob = prob

        return nearest_prob
    except Exception as e:
        print(f"[aurora-station] Aurora oval fetch failed: {e}")
    return 0


# ── Notification ────────────────────────────────────────────────────────────
def send_notification(kp, probability, mag_lat, oval_prob):
    """Send a Discord/Slack webhook notification when aurora is visible."""
    if not NOTIFICATION_WEBHOOK:
        return

    color = 0x22d3ee  # Cyan
    embed = {
        "title": f"🌌 Aurora Alert — {LOCATION_NAME}",
        "description": f"Aurora may be visible from your location right now!",
        "color": color,
        "fields": [
            {"name": "Kp Index", "value": str(kp), "inline": True},
            {"name": "Probability", "value": probability, "inline": True},
            {"name": "Magnetic Latitude", "value": f"{mag_lat:.1f}°", "inline": True},
            {"name": "Oval Probability", "value": f"{oval_prob:.0f}%", "inline": True},
            {"name": "Time (UTC)", "value": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "inline": True},
        ],
        "footer": {"text": "Aurora Station by Flarient"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        requests.post(NOTIFICATION_WEBHOOK, json={"embeds": [embed]}, timeout=10)
        print(f"[aurora-station] Notification sent")
    except Exception as e:
        print(f"[aurora-station] Notification failed: {e}")


# ── Dashboard generation ──────────────────────────────────────────────────
def generate_dashboard(kp, kp_forecast, mag_lat, probability, oval_prob, is_night, visible):
    """Generate a static HTML dashboard for GitHub Pages."""
    status_color = "#22d3ee" if visible else "#64748b"
    status_text = "AURORA VISIBLE" if visible else "No aurora right now"
    status_emoji = "🌌" if visible else "🌙"

    forecast_html = ""
    for line in kp_forecast[:5]:
        forecast_html += f"<div class='forecast-line'>{line}</div>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aurora Station — {LOCATION_NAME}</title>
    <meta http-equiv="refresh" content="300">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: radial-gradient(ellipse at top, #0a0620 0%, #05030f 100%);
            color: #e8eaf2;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 1rem;
        }}
        .station {{
            max-width: 500px;
            width: 100%;
            text-align: center;
        }}
        .status {{
            background: rgba(255,255,255,0.05);
            border: 1px solid {status_color}40;
            border-radius: 20px;
            padding: 2rem;
            margin-bottom: 1rem;
        }}
        .status-emoji {{ font-size: 4rem; margin-bottom: 0.5rem; }}
        .status-text {{
            font-size: 1.5rem;
            font-weight: 700;
            color: {status_color};
            letter-spacing: 0.05em;
        }}
        .location {{ color: rgba(255,255,255,0.5); font-size: 0.9rem; margin-top: 0.5rem; }}
        .metrics {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.75rem;
            margin-bottom: 1rem;
        }}
        .metric {{
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 12px;
            padding: 1rem;
        }}
        .metric-label {{ font-size: 0.7rem; color: rgba(255,255,255,0.4); text-transform: uppercase; letter-spacing: 0.1em; }}
        .metric-value {{ font-size: 1.5rem; font-weight: 700; margin-top: 0.25rem; }}
        .forecast {{
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 1rem;
            text-align: left;
        }}
        .forecast-title {{ font-size: 0.8rem; color: rgba(255,255,255,0.5); margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.1em; }}
        .forecast-line {{ font-family: monospace; font-size: 0.75rem; color: rgba(255,255,255,0.6); margin-bottom: 0.25rem; }}
        .footer {{ font-size: 0.75rem; color: rgba(255,255,255,0.3); }}
        .footer a {{ color: #6366f1; text-decoration: none; }}
        .updated {{ font-size: 0.7rem; color: rgba(255,255,255,0.3); margin-top: 0.5rem; }}
    </style>
</head>
<body>
    <div class="station">
        <div class="status">
            <div class="status-emoji">{status_emoji}</div>
            <div class="status-text">{status_text}</div>
            <div class="location">{LOCATION_NAME} ({LAT}, {LON})</div>
        </div>
        <div class="metrics">
            <div class="metric">
                <div class="metric-label">Kp Index</div>
                <div class="metric-value">{kp if kp is not None else "—"}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Probability</div>
                <div class="metric-value" style="color:{status_color}">{probability}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Magnetic Lat</div>
                <div class="metric-value">{mag_lat:.1f}°</div>
            </div>
            <div class="metric">
                <div class="metric-label">Oval Coverage</div>
                <div class="metric-value">{oval_prob:.0f}%</div>
            </div>
        </div>
        <div class="forecast">
            <div class="forecast-title">3-Day Forecast</div>
            {forecast_html if forecast_html else '<div class="forecast-line">Forecast unavailable</div>'}
        </div>
        <div class="footer">
            Powered by <a href="https://flarient.com">Flarient</a> ·
            <a href="https://github.com/flarientglobal/aurora-station">Fork your own</a>
        </div>
        <div class="updated">Updated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</div>
    </div>
</body>
</html>"""

    dashboard_path = f"{GITHUB_WORKSPACE}/docs/index.html"
    os.makedirs(os.path.dirname(dashboard_path), exist_ok=True)
    with open(dashboard_path, "w") as f:
        f.write(html)
    print(f"[aurora-station] Dashboard generated: {dashboard_path}")


# ── State tracking ────────────────────────────────────────────────────────
def load_state():
    path = f"{GITHUB_WORKSPACE}/state/last_alert.json"
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except:
            pass
    return {"last_alert_kp": 0, "last_alert_time": ""}


def save_state(state):
    path = f"{GITHUB_WORKSPACE}/state/last_alert.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


# ── Main ──────────────────────────────────────────────────────────────────
def main():
    print(f"[aurora-station] === Aurora Station — {LOCATION_NAME} ===")
    print(f"[aurora-station] Location: {LAT}, {LON}")

    # Calculate magnetic latitude
    mag_lat = geographic_to_magnetic(LAT, LON)
    print(f"[aurora-station] Magnetic latitude: {mag_lat:.1f}°")

    # Fetch data
    kp, kp_time = fetch_kp()
    kp_forecast = fetch_kp_forecast()
    oval_prob = fetch_aurora_oval()

    print(f"[aurora-station] Kp: {kp}")
    print(f"[aurora-station] Oval probability at location: {oval_prob:.1f}%")

    # Check visibility
    visible, probability, min_kp = kp_to_visibility(mag_lat, kp or 0)
    night = is_nighttime(LAT, LON)

    print(f"[aurora-station] Visible: {visible} ({probability})")
    print(f"[aurora-station] Min Kp for this location: {min_kp:.1f}")
    print(f"[aurora-station] Nighttime: {night}")

    # Generate dashboard (always)
    generate_dashboard(kp, kp_forecast, mag_lat, probability, oval_prob, night, visible)

    # Send notification only if:
    # 1. Aurora is visible
    # 2. It's nighttime
    # 3. Kp increased since last alert (avoid spam)
    if visible and night:
        state = load_state()
        last_kp = state.get("last_alert_kp", 0)
        if kp and kp > last_kp:
            send_notification(kp, probability, mag_lat, oval_prob)
            save_state({
                "last_alert_kp": kp,
                "last_alert_time": datetime.now(timezone.utc).isoformat(),
            })
            print(f"[aurora-station] Alert sent (Kp {last_kp} -> {kp})")
        else:
            print(f"[aurora-station] No alert (Kp {kp} not higher than last alert {last_kp})")
    else:
        # Reset alert state when conditions clear
        if not visible:
            save_state({"last_alert_kp": 0, "last_alert_time": ""})

    print(f"[aurora-station] Done")


if __name__ == "__main__":
    main()
