import os
from datetime import datetime, timedelta, timezone
from curl_cffi import requests
from tradingview_ta import TA_Handler, Interval

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
FF_JSON_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

def get_todays_events():
    response = requests.get(FF_JSON_URL, impersonate="chrome")
    response.raise_for_status()
    
    events = response.json()
    pkt_tz = timezone(timedelta(hours=5))
    today_local_date = datetime.now(pkt_tz).date()
    
    todays_events = []
    for e in events:
        date_str = e.get("date", "")
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str)
                if dt.tzinfo is not None:
                    dt_pkt = dt.astimezone(pkt_tz)
                    if dt_pkt.date() == today_local_date:
                        e["parsed_dt_pkt"] = dt_pkt
                        todays_events.append(e)
            except ValueError:
                pass
                
    todays_events.sort(key=lambda x: x.get("parsed_dt_pkt"))
    return todays_events

def get_gold_technicals():
    # Targets the exact asset and exchange requested
    handler = TA_Handler(
        symbol="XAUUSD",
        screener="forex",
        exchange="PEPPERSTONE",
        interval=Interval.INTERVAL_4_HOURS
    )
    return handler.get_analysis()

def send_to_discord(events, gold_ta):
    pkt_tz = timezone(timedelta(hours=5))
    current_date_str = datetime.now(pkt_tz).strftime('%A, %b %d')
    
    # --- 1. Format Economic Events ---
    description = ""
    if not events:
        description = "No economic events scheduled for today."
    else:
        for e in events:
            title = e.get("title", "Unknown Event")
            impact = e.get("impact", "Low")
            country = e.get("country", "")
            dt_pkt = e.get("parsed_dt_pkt")
            
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
                    
            description += f"{icon} **{label}** {time_str} | **{country}** | {title}\n"
            
    # --- 2. Format XAUUSD Technicals ---
    ta_rec = gold_ta.summary["RECOMMENDATION"].replace("_", " ").title()
    ta_buy = gold_ta.summary["BUY"]
    ta_sell = gold_ta.summary["SELL"]
    ta_neutral = gold_ta.summary["NEUTRAL"]
    
    osc_rec = gold_ta.oscillators["RECOMMENDATION"].title()
    ma_rec = gold_ta.moving_averages["RECOMMENDATION"].title()
    
    ta_description = (
        f"**Summary Gauge:** {ta_rec} (Buy: {ta_buy} | Sell: {ta_sell} | Neutral: {ta_neutral})\n"
        f"**Oscillators:** {osc_rec}\n"
        f"**Moving Averages:** {ma_rec}\n"
    )

    # Dynamically change the technical embed color based on the summary signal
    if "Sell" in ta_rec:
        embed_color = 15158332 # Red
    elif "Buy" in ta_rec:
        embed_color = 3066993 # Green
    else:
        embed_color = 9807270 # Gray
            
    # --- 3. Build Multi-Embed Payload ---
    payload = {
        "username": "Macro & Tech Alerts",
        "embeds": [
            {
                "title": f"📅 Economic Calendar Summary for {current_date_str}",
                "description": description,
                "color": 16711680,
            },
            {
                "title": "📈 XAUUSD (Gold / USD) 4H Technicals",
                "description": ta_description,
                "color": embed_color,
                "footer": {"text": "Data provided by TradingView via Pepperstone"}
            }
        ]
    }
        
    response = requests.post(WEBHOOK_URL, json=payload, impersonate="chrome")
    response.raise_for_status()

if __name__ == "__main__":
    if not WEBHOOK_URL:
        raise ValueError("DISCORD_WEBHOOK_URL environment variable is missing.")
    
    events = get_todays_events()
    gold_ta = get_gold_technicals()
    send_to_discord(events, gold_ta)
    print(f"Successfully processed {len(events)} events and Gold technicals.")
