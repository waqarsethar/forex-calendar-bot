import os
from datetime import datetime, timedelta, timezone
from curl_cffi import requests

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
FF_JSON_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

def get_todays_events():
    response = requests.get(FF_JSON_URL, impersonate="chrome")
    response.raise_for_status()
    
    events = response.json()
    
    # Define local timezone (PKT)
    pkt_tz = timezone(timedelta(hours=5))
    today_local_date = datetime.now(pkt_tz).date()
    
    todays_events = []
    
    for e in events:
        date_str = e.get("date", "")
        if date_str:
            try:
                # Parse the ISO 8601 string from Forex Factory
                dt = datetime.fromisoformat(date_str)
                if dt.tzinfo is not None:
                    # Convert the event time directly to PKT
                    dt_pkt = dt.astimezone(pkt_tz)
                    # Only include the event if it falls on today's local calendar day
                    if dt_pkt.date() == today_local_date:
                        # Store the pre-converted datetime object inside the dict for reuse
                        e["parsed_dt_pkt"] = dt_pkt
                        todays_events.append(e)
            except ValueError:
                pass
                
    # Sort events chronologically by time
    todays_events.sort(key=lambda x: x.get("parsed_dt_pkt"))
    return todays_events

def send_to_discord(events):
    pkt_tz = timezone(timedelta(hours=5))
    current_date_str = datetime.now(pkt_tz).strftime('%A, %b %d')
    
    if not events:
        print(f"No economic events scheduled for {current_date_str}.")
        return

    description = ""

    for e in events:
        title = e.get("title", "Unknown Event")
        impact = e.get("impact", "Low")
        country = e.get("country", "")
        dt_pkt = e.get("parsed_dt_pkt")
        
        # Format the pre-converted PKT timestamp
        time_str = dt_pkt.strftime("%I:%M %p") if dt_pkt else "All Day"
            
        if impact == "High":
            icon = "🔴"
            label = "[HIGH]"
        elif impact == "Medium":
            icon = "🟠"
            label = "[MEDIUM]"
        elif impact == "Low":
            icon = "🟡"
            label = "[LOW]"
        elif impact == "Holiday":
            icon = "💤"
            label = "[HOLIDAY]"
            time_str = "All Day"
        else:
            icon = "⚪"
            label = f"[{impact.upper()}]"
                
        # Placed the text label immediately after the color code icon
        description += f"{icon} **{label}** {time_str} | **{country}** | {title}\n"
            
    payload = {
        "username": "Macro Alerts",
        "embeds": [
            {
                "title": f"📅 Economic Calendar Summary for {current_date_str}",
                "description": description,
                "color": 16711680, # Red embed border
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
