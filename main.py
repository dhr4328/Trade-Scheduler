import os
import sys
import yfinance as yf
import pandas as pd
import requests
import numpy as np

def send_telegram_alert(symbol, current_price, signal_type):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("Telegram credentials not found. Cannot send alert.")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    if signal_type == "START":
        message = "🟢 <b>Bot Started Successfully</b> 🟢"
    elif signal_type == "ERROR":
        message = f"🔴 <b>Error Executing Bot:</b> 🔴\n<code>{current_price}</code>" # In case of error, we'll pass error msg in current_price
    else:
        message = (
            f"🚨 <b>Trade Alert: {symbol}</b> 🚨\n"
            f"<b>Signal:</b> {signal_type}\n"
            f"<b>Current Price:</b> {current_price:.2f}"
        )
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload)
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

def main():
    symbol = "^NSEI"
    try:
        print("Bot started. Notifying Telegram...")
        send_telegram_alert(symbol=symbol, current_price=0, signal_type="START")
        
        # Fetch 5-minute interval data for the last 5 days 
        # (to ensure we cover previous 2 trading days + current day, accounting for weekends)
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="5d", interval="5m")
        
        if df.empty:
            print(f"No data fetched for {symbol}.")
            sys.exit(0)
            
        # Convert timezone from UTC (or whatever yfinance returns) to 'Asia/Kolkata'
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC').tz_convert('Asia/Kolkata')
        else:
            df.index = df.index.tz_convert('Asia/Kolkata')
            
        # Filter for the previous 2 days + current day exactly
        # Get unique dates from the timezone-aware index
        unique_dates = pd.Series(df.index.date).unique()
        if len(unique_dates) > 3:
            # Keep only the last 3 trading days
            start_date = unique_dates[-3]
            df = df[df.index.date >= start_date]

        df = superBoilingerTrend(df)
        
        last_signal = df["Signal"].iloc[-1]
        current_price = float(df["Close"].iloc[-1])
        
        if last_signal in ["LONG", "SHORT"]:
            print(f"Strategy triggered! Signal: {last_signal}. Sending alert...")
            send_telegram_alert(
                symbol=symbol, 
                current_price=current_price, 
                signal_type=f"Super Bollinger Trend: {last_signal}"
            )
        else:
            print("Strategy not triggered. No alert sent.")
            
    except Exception as e:
        error_msg = str(e)
        print(f"Error executing bot: {error_msg}")
        send_telegram_alert(symbol=symbol, current_price=error_msg, signal_type="ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()
