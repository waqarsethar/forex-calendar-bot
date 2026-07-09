import os
import time
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
                screener="forex",
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
            
    # --- 2. Format Multi-Timeframe Summary ---
    ta_description = ""
    for timeframe, ta in gold_ta_dict.items():
        if ta:
            rec = ta.summary["RECOMMENDATION"].replace("_", " ").title()
            buy = ta.summary["BUY"]
            sell = ta.summary["SELL"]
            neutral = ta.summary["NEUTRAL"]
            
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

    # --- 3. Send Main Payload (Calendar + Summary) ---
    main_payload = {
        "username": "Macro & Tech Alerts",
        "embeds": [
            {
                "title": f"📅 Economic Calendar Summary for {current_date_str}",
                "description": description,
                "color": 16711680,
            },
            {
                "title": "📈 XAUUSD (Gold / USD) Multi-Timeframe",
                "description": ta_description,
                "color": 16766720, 
            }
        ]
    }
    
    response = requests.post(WEBHOOK_URL, json=main_payload, impersonate="chrome")
    response.raise_for_status()

    # --- 4. Format Detailed Indicator Tables for ALL Timeframes ---
    osc_map = [
        ("Relative Strength Index (14)", "RSI", "RSI"),
        ("Stochastic %K (14, 3, 3)", "Stoch.K", "STOCH.K"),
        ("Commodity Channel Index (20)", "CCI20", "CCI"),
        ("Average Directional Index (14)", "ADX", "ADX"),
        ("Awesome Oscillator", "AO", "AO"),
        ("Momentum (10)", "Mom", "Mom"),
        ("MACD Level (12, 26)", "MACD.macd", "MACD"),
        ("Stochastic RSI Fast", "Stoch.RSI.K", "Stoch.RSI"),
        ("Williams Percent Range (14)", "W.R", "W%R"),
        ("Bull Bear Power", "BBPower", "BBP"),
        ("Ultimate Oscillator", "UO", "UO"),
    ]
    
    ma_map = [
        ("Exponential Moving Average (10)", "EMA10", "EMA10"),
        ("Simple Moving Average (10)", "SMA10", "SMA10"),
        ("Exponential Moving Average (20)", "EMA20", "EMA20"),
        ("Simple Moving Average (20)", "SMA20", "SMA20"),
        ("Exponential Moving Average (30)", "EMA30", "EMA30"),
        ("Simple Moving Average (30)", "SMA30", "SMA30"),
        ("Exponential Moving Average (50)", "EMA50", "EMA50"),
        ("Simple Moving Average (50)", "SMA50", "SMA50"),
        ("Exponential Moving Average (100)", "EMA100", "EMA100"),
        ("Simple Moving Average (100)", "SMA100", "SMA100"),
        ("Exponential Moving Average (200)", "EMA200", "EMA200"),
        ("Simple Moving Average (200)", "SMA200", "SMA200"),
        ("Ichimoku Base Line", "Ichimoku.BLine", "Ichimoku"),
        ("Volume Weighted MA (20)", "VWMA", "VWMA"),
        ("Hull Moving Average (9)", "HullMA9", "HullMA9"),
    ]

    detailed_embeds = []
    
    for timeframe, ta in gold_ta_dict.items():
        if not ta:
            continue
            
        detailed_table = "```text\n"
        detailed_table += f"{'OSCILLATORS':<34} {'VALUE':<10} {'ACTION'}\n"
        detailed_table += "-" * 54 + "\n"
        
        for name, ind_key, comp_key in osc_map:
            val = ta.indicators.get(ind_key)
            val_str = f"{val:.2f}" if isinstance(val, (float, int)) and val is not None else "N/A"
            action = ta.oscillators["COMPUTE"].get(comp_key, "Neutral").title()
            detailed_table += f"{name:<34} {val_str:<10} {action}\n"
            
        detailed_table += "\n"
        detailed_table += f"{'MOVING AVERAGES':<34} {'VALUE':<10} {'ACTION'}\n"
        detailed_table += "-" * 54 + "\n"
        
        for name, ind_key, comp_key in ma_map:
            val = ta.indicators.get(ind_key)
            val_str = f"{val:.2f}" if isinstance(val, (float, int)) and val is not None else "N/A"
            action = ta.moving_averages["COMPUTE"].get(comp_key, "Neutral").title()
            detailed_table += f"{name:<34} {val_str:<10} {action}\n"
            
        detailed_table += "```"
        
        detailed_embeds.append({
            "title": f"📊 XAUUSD {timeframe} In-Depth Indicators",
            "description": detailed_table,
            "color": 16766720,
        })

    # --- 5. Dispatch Detailed Tables in Chunks ---
    # Send 2 timeframes per message to safely stay under Discord's 6,000 character limit
    for i in range(0, len(detailed_embeds), 2):
        chunk_payload = {
            "username": "Macro & Tech Alerts",
            "embeds": detailed_embeds[i:i+2]
        }
        res = requests.post(WEBHOOK_URL, json=chunk_payload, impersonate="chrome")
        res.raise_for_status()
        time.sleep(1) # Brief pause to prevent Discord rate-limiting

if __name__ == "__main__":
    if not WEBHOOK_URL:
        raise ValueError("DISCORD_WEBHOOK_URL environment variable is missing.")
    
    events = get_todays_events()
    gold_ta_dict = get_gold_technicals()
    send_to_discord(events, gold_ta_dict)
    print(f"Successfully processed events and detailed Gold technicals for all timeframes.")
