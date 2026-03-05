import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import yfinance as yf
import pandas as pd
import requests
import numpy as np
import asyncio
def send_telegram_alert(symbol, current_price, signal_type):
    bot_token = "8792428947:AAFCJ2AP1y49AxHdb7vmGHQs1oRz8g7J6zo" # Hardcoded value
    chat_id = "1112002477" # Hardcoded value
    
    if not bot_token or not chat_id:
        print("Telegram credentials not found. Cannot send alert.")
        return

    if signal_type == "START":
        message = "🟢 <b>Bot Started Successfully. Monitoring active.</b> 🟢"
    elif signal_type == "STOP":
        message = "🛑 <b>Market Closed. Bot Stopped.</b> 🛑"
    elif signal_type == "ERROR":
        message = f"🔴 <b>Error Executing Bot:</b> 🔴\n<code>{current_price}</code>" # In case of error, we'll pass error msg in current_price
    else:
        message = (
            f"🚨 <b>Trade Alert: {symbol}</b> 🚨\n"
            f"<b>Signal:</b> {signal_type}\n"
            f"<b>Current Price:</b> {current_price:.2f}"
        )
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("Alert sent successfully!")
    except Exception as e:
        print(f"Failed to send alert: {e}")

def superBoilingerTrend(df, period=12, mult=2.0):
    df = df.copy()

    df["bb_up"] = df["High"].rolling(period).mean() + \
                  df["High"].rolling(period).std() * mult

    df["bb_dn"] = df["Low"].rolling(period).mean() - \
                  df["Low"].rolling(period).std() * mult

    sbt = np.zeros(len(df))
    signal = [None] * len(df)

    for i in range(1, len(df)):
        close = float(df["Close"].iloc[i])
        prev_close = float(df["Close"].iloc[i-1])
        prev_sbt = sbt[i-1]

        bb_up = df["bb_up"].iloc[i]
        bb_dn = df["bb_dn"].iloc[i]

        if np.isnan(bb_up) or np.isnan(bb_dn):
            sbt[i] = prev_sbt
            continue

        # Trailing Logic
        if close > prev_sbt:
            current_sbt = max(prev_sbt, float(bb_dn))
        else:
            current_sbt = min(prev_sbt, float(bb_up))

        # Signal Logic
        if close > prev_sbt and prev_close <= prev_sbt:
            signal[i] = "LONG"
            current_sbt = float(bb_dn)

        elif close < prev_sbt and prev_close >= prev_sbt:
            signal[i] = "SHORT"
            current_sbt = float(bb_up)

        sbt[i] = current_sbt

    df["SBT"] = sbt
    df["Signal"] = signal

    return df

def fetch_and_analyze(symbol):
    # Fetch 5-minute interval data for the last 5 days 
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="5d", interval="5m")
    
    if df.empty:
        print(f"No data fetched for {symbol}.")
        return
        
    # Convert timezone to 'Asia/Kolkata'
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert('Asia/Kolkata')
    else:
        df.index = df.index.tz_convert('Asia/Kolkata')
        
    # Filter for the previous 2 days + current day exactly
    unique_dates = pd.Series(df.index.date).unique()
    if len(unique_dates) > 3:
        start_date = unique_dates[-3]
        df = df[df.index.date >= start_date]

    df = superBoilingerTrend(df)
    
    last_signal = df["Signal"].iloc[-1]
    current_price = float(df["Close"].iloc[-1])
    latest_time = df.index[-1].strftime('%H:%M')
    
    print(f"[{latest_time}] Last closed candle price: {current_price:.2f} | Expected Signal: {last_signal}")
    
    if last_signal in ["LONG", "SHORT"]:
        print(f"Strategy triggered ({last_signal})! Sending alert...")
        send_telegram_alert(
            symbol=symbol, 
            current_price=current_price, 
            signal_type=f"Super Bollinger Trend: {last_signal}"
        )

def get_next_sleep_time():
    """
    Calculate seconds to sleep until the next 5-minute interval (e.g., :00, :05, :10).
    Adds a small buffer of 5 seconds to ensure we fetch slightly after the candle closes.
    """
    now = datetime.now()
    minutes_to_next = 5 - (now.minute % 5)
    seconds_to_sleep = (minutes_to_next * 60) - now.second + 5
    return seconds_to_sleep

def main():
    symbol = "^NSEI"
    try:
        print("Bot started. Notifying Telegram...")
        send_telegram_alert(symbol=symbol, current_price=0, signal_type="START")
        
        ist = ZoneInfo('Asia/Kolkata')
        
        while True:
            # Check current time in IST
            now_ist = datetime.now(ist)
            
            # Stop condition: if it's past 3:35 PM IST (15:35)
            # 3:30 is market close, one extra check at 3:35 is fine to capture last 3:30 candle.
            if now_ist.hour > 15 or (now_ist.hour == 15 and now_ist.minute > 35):
                print("Market closed. Stopping bot loop.")
                send_telegram_alert(symbol=symbol, current_price=0, signal_type="STOP")
                break
                
            try:
                # Only analyze if we are inside market hours
                if now_ist.hour > 9 or (now_ist.hour == 9 and now_ist.minute >= 15):
                    fetch_and_analyze(symbol)
                else:
                    print("Market hasn't opened yet (pre 9:15 AM). Just waiting...")
            except Exception as e:
                print(f"Error during fetch/analysis: {e}")
                
            # Sleep until the next 5-minute mark
            sleep_sec = get_next_sleep_time()
            print(f"Sleeping for {sleep_sec} seconds until next check...")
            time.sleep(sleep_sec)
            
    except Exception as e:
        error_msg = str(e)
        print(f"Fatal error executing bot: {error_msg}")
        send_telegram_alert(symbol=symbol, current_price=error_msg, signal_type="ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()
