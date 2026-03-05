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
    try:
        import json
        import os
        if not os.path.exists('bot_state.json'):
            return jsonify({"error": "No bot data available. Please make sure main.py is running and fetching data."}), 400
            
        with open('bot_state.json', 'r') as f:
            data = json.load(f)
            return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)
