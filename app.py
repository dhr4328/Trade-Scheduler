import os
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import yfinance as yf
import pandas as pd
from main import superBoilingerTrend
import numpy as np
import math

app = Flask(__name__, static_folder='static')
CORS(app)

def clean_float(val):
    if pd.isna(val) or math.isnan(val) or val is None:
        return None
    return float(val)

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def static_proxy(path):
    return send_from_directory(app.static_folder, path)

@app.route('/api/bot-data')
def get_bot_data():
    from flask import request
    try:
        import json
        import os
        symbol = request.args.get('symbol', 'NSEI')
        file_path = f'bot_state_{symbol}.json'
        # Fallback to the old format if explicitly requested or testing locally
        if not os.path.exists(file_path):
            if os.path.exists('bot_state.json') and symbol == 'NSEI':
                file_path = 'bot_state.json'
            else:
                return jsonify({"error": f"No bot data available for {symbol}. Please make sure main.py is running and fetching data."}), 400
            
        with open(file_path, 'r') as f:
            data = json.load(f)
            return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)
