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
BOT_TOKEN = "8792428947:AAFCJ2AP1y49AxHdb7vmGHQs1oRz8g7J6zo" # Hardcoded value
CHAT_ID = "1112002477" # Hardcoded value

latest_status = {
    "symbol": "^NSEI",
    "time": "N/A",
    "price": 0.0,
    "signal": "N/A",
    "sbt": 0.0
}
last_update_id = None
last_notified_timestamp = None

def send_telegram_message(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram credentials not found. Cannot send message.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to send message: {e}")

def send_telegram_alert(symbol, current_price, signal_type):
    if signal_type == "START":
        message = "🟢 <b>Bot Started Successfully. Monitoring active.</b> 🟢\nSend /status to check current bot status."
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
    send_telegram_message(message)
    print(f"Alert sent: {signal_type}")

def check_telegram_commands(timeout=10):
    global last_update_id
    if not BOT_TOKEN or not CHAT_ID:
        return
        
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"timeout": timeout, "allowed_updates": ["message"]}
    if last_update_id:
        params["offset"] = last_update_id
        
    try:
        response = requests.get(url, params=params, timeout=timeout + 5)
        response.raise_for_status()
        data = response.json()
        
        if data.get("ok"):
            for result in data.get("result", []):
                update_id = result.get("update_id")
                last_update_id = update_id + 1
                
                message = result.get("message", {})
                text = message.get("text", "")
                chat = message.get("chat", {})
                sender_chat_id = str(chat.get("id", ""))
                msg_date = message.get("date", 0)
                
                if sender_chat_id == CHAT_ID:  # only respond to authorized chat
                    # Process commands if they are not older than 5 minutes
                    if text.startswith("/status") and time.time() - msg_date < 300:
                        send_status_message()
    except requests.exceptions.RequestException:
        pass  # Ignore timeout errors or connection errors during polling
    except Exception as e:
        print(f"Error checking Telegram commands: {e}")

def send_status_message():
    message = (
        f"📊 <b>Bot Status Report</b> 📊\n"
        f"<b>Symbol:</b> {latest_status['symbol']}\n"
        f"<b>Last Fetch Time:</b> {latest_status['time']}\n"
        f"<b>Last Price:</b> {latest_status['price']:.2f}\n"
        f"<b>SBT Value:</b> {latest_status['sbt']:.2f}\n"
        f"<b>Last Signal:</b> {latest_status['signal']}"
    )
    send_telegram_message(message)

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

def save_dashboard_data(symbol, df, current_price, last_signal):
    import json
    try:
        dashboard_data = []
        for idx, row in df.iterrows():
            ts = int(idx.timestamp())
            dashboard_data.append({
                "time": ts + 19800,
                "open": None if pd.isna(row['Open']) else float(row['Open']),
                "high": None if pd.isna(row['High']) else float(row['High']),
                "low": None if pd.isna(row['Low']) else float(row['Low']),
                "close": None if pd.isna(row['Close']) else float(row['Close']),
                "sbt": None if pd.isna(row['SBT']) else float(row['SBT']),
                "signal": row['Signal'] if not pd.isna(row['Signal']) else None,
                "bb_up": None if pd.isna(row['bb_up']) else float(row['bb_up']),
                "bb_dn": None if pd.isna(row['bb_dn']) else float(row['bb_dn']),
            })
            
        with open('bot_state.json', 'w') as f:
            json.dump({
                "symbol": symbol,
                "latest_price": current_price,
                "latest_sbt": dashboard_data[-1]["sbt"] if dashboard_data else None,
                "latest_signal": last_signal if not pd.isna(last_signal) else "NONE",
                "chart_data": dashboard_data
            }, f)
        print("Updated dashboard state successfully.")
    except Exception as e:
        print(f"Error saving dashboard data: {e}")

def fetch_and_analyze(symbol):
    global latest_status, last_notified_timestamp
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
    
    # Get current state from the very last row
    current_price = float(df["Close"].iloc[-1])
    latest_time = df.index[-1].strftime('%H:%M')
    last_row_signal = df["Signal"].iloc[-1]
    
    # Find the last active signal for status display
    active_signal = df["Signal"].dropna().iloc[-1] if not df["Signal"].dropna().empty else "NONE"
    
    # Update global latest_status for the /status command
    latest_status.update({
        "symbol": symbol,
        "time": latest_time,
        "price": current_price,
        "signal": active_signal,
        "sbt": float(df["SBT"].iloc[-1])
    })
    
    print(f"[{latest_time}] Last candle price: {current_price:.2f} | Last Active Signal: {active_signal}")
    
    # Save latest state for the dashboard
    save_dashboard_data(symbol, df, current_price, last_row_signal)
    
    if last_notified_timestamp is None:
        # Initialize to avoid firing old alerts, but allow catching recently missed ones
        last_notified_timestamp = df.index[-3] if len(df) >= 3 else df.index[0]
        
    recent_df = df.tail(3)
    for idx, row in recent_df.iterrows():
        sig = row['Signal']
        if not pd.isna(sig) and idx > last_notified_timestamp:
            print(f"Strategy triggered ({sig}) at {idx.strftime('%H:%M')}! Sending alert...")
            send_telegram_alert(
                symbol=symbol, 
                current_price=float(row['Close']), 
                signal_type=f"Super Bollinger Trend: {sig}"
            )
            last_notified_timestamp = idx

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
                
            # Wait until the next 5-minute mark, while polling for commands
            sleep_sec = get_next_sleep_time()
            print(f"Waiting for {sleep_sec} seconds until next check, polling for commands...")
            end_time = time.time() + sleep_sec
            while time.time() < end_time:
                time_left = end_time - time.time()
                if time_left <= 0:
                    break
                poll_timeout = max(1, min(10, int(time_left)))
                check_telegram_commands(timeout=poll_timeout)
            
    except Exception as e:
        error_msg = str(e)
        print(f"Fatal error executing bot: {error_msg}")
        send_telegram_alert(symbol=symbol, current_price=error_msg, signal_type="ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()
