import os
from datetime import datetime, timedelta, timezone
from curl_cffi import requests # Replaces standard requests to bypass Cloudflare

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
FF_JSON_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

def get_todays_events():
    # Impersonate Chrome to bypass Cloudflare blocks on GitHub Actions IPs
    response = requests.get(FF_JSON_URL, impersonate="chrome")
    response.raise_for_status()
    
    events = response.json()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    # Filter for events matching today's date
    return [e for e in events if e.get("date", "").startswith(today_str)]

def send_to_discord(events):
    if not events:
        print("No events scheduled for today.")
        return

    description = ""
    # Set timezone for local alert formatting
    pkt_tz = timezone(timedelta(hours=5)) 

    for e in events:
        title = e.get("title", "Unknown Event")
        impact = e.get("impact", "Low")
        country = e.get("country", "")
        date_str = e.get("date", "")
        
        # Parse the ISO string and convert to PKT
        time_str = "All Day"
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str)
                if dt.tzinfo is not None:
                    dt_pkt = dt.astimezone(pkt_tz)
                    time_str = dt_pkt.strftime("%I:%M %p")
            except ValueError:
                pass # Fallback to "All Day" if parsing fails
            
        # Map impact levels to visual indicators, including holidays
        if impact == "High":
            icon = "🔴"
        elif impact == "Medium":
            icon = "🟠"
        elif impact == "Low":
            icon = "🟡"
        elif impact == "Holiday":
            icon = "💤"
        else:
            icon = "⚪"
                
        description += f"{icon} **{time_str}** | **{country}** | {title}\n"
            
    payload = {
        "username": "Macro Alerts",
        "embeds": [
            {
                "title": f"📅 Economic Calendar Summary for {datetime.now(pkt_tz).strftime('%A, %b %d')}",
                "description": description,
                "color": 16711680, # Red
                "footer": {"text": "Times converted to Pakistan Standard Time (PKT)"}
            }
        ]
    }
        
    response = requests.post(WEBHOOK_URL, json=payload, impersonate="chrome")
    response.raise_for_status()

if __name__ == "__main__":
    if not WEBHOOK_URL:
        raise ValueError("DISCORD_WEBHOOK_URL environment variable is missing.")
    
    events = get_todays_events()
    send_to_discord(events)
    print(f"Successfully processed {len(events)} events.")
