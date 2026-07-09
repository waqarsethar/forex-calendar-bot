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
    # Define the timeframes to fetch
    timeframes = {
        "15 Minute": Interval.INTERVAL_15_MINUTES,
        "1 Hour": Interval.INTERVAL_1_HOUR,
        "4 Hour": Interval.INTERVAL_4_HOURS,
        "Daily": Interval.INTERVAL_1_DAY
    }
    
    results = {}
    
    for label, interval in timeframes.items():
        try:
            handler = TA_Handler(
                symbol="XAUUSD",
                screener="cfd",
                exchange="OANDA",
                interval=interval
            )
            results[label] = handler.get_analysis()
        except Exception as e:
            print(f"Failed to fetch {label} technicals: {e}")
            results[label] = None
            
    return results

def send_to_discord(events, gold_ta_dict):
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
            
    # --- 2. Format Multi-Timeframe Technicals ---
    ta_description = ""
    for timeframe, ta in gold_ta_dict.items():
        if ta:
            rec = ta.summary["RECOMMENDATION"].replace("_", " ").title()
            buy = ta.summary["BUY"]
            sell = ta.summary["SELL"]
            neutral = ta.summary["NEUTRAL"]
            
            # Map recommendation to an emoji for quick visual scanning
            if "Strong Buy" in rec:
                indicator = "🚀"
            elif "Buy" in rec:
                indicator = "🟢"
            elif "Strong Sell" in rec:
                indicator = "🩸"
            elif "Sell" in rec:
                indicator = "🔴"
            else:
                indicator = "⚪"
                
            ta_description += f"{indicator} **{timeframe}:** {rec} *(Buy: {buy} | Sell: {sell} | Neutral: {neutral})*\n"
        else:
            ta_description += f"⚠️ **{timeframe}:** Data Unavailable\n"

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
                "title": "📈 XAUUSD (Gold / USD) Multi-Timeframe Technicals",
                "description": ta_description,
                "color": 16766720, # Gold color hex
                "footer": {"text": "Data provided by TradingView via OANDA"}
            }
        ]
    }
        
    response = requests.post(WEBHOOK_URL, json=payload, impersonate="chrome")
    response.raise_for_status()

if __name__ == "__main__":
    if not WEBHOOK_URL:
        raise ValueError("DISCORD_WEBHOOK_URL environment variable is missing.")
    
    events = get_todays_events()
    gold_ta_dict = get_gold_technicals()
    send_to_discord(events, gold_ta_dict)
    print(f"Successfully processed events and multi-timeframe Gold technicals.")
