from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import os
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from helper_functions import load_saved_models, make_predictions

# Load environment variables
load_dotenv()

# Initialize Flask App
app = Flask(__name__)

# ✅ Enable CORS for frontend
CORS(app, supports_credentials=True, origins=["http://localhost:5173"])

# Scheduler
scheduler = BackgroundScheduler()

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Load ML models
try:
    models = load_saved_models()
    logger.info("Models loaded successfully.")
except Exception as e:
    logger.error(f"Error loading models: {e}")

# Constants
CSV_FILE_PATH = './static/cnc_machine_static_data.csv'
DATABASE_URL = os.getenv("DATABASE_URL")

# Database connection
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

# Safe casting
def safe_cast(value):
    if isinstance(value, (np.integer, np.int64)): return int(value)
    if isinstance(value, (np.floating, np.float64, np.float64)): return float(value)
    if isinstance(value, (bool, np.bool_)): return bool(value)
    if isinstance(value, pd.Timestamp): return str(value)
    if isinstance(value, np.generic): return value.item()
    return value

# --- Login route ---
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if username == "admin" and password == "password":
        return jsonify({"token": "dummy-token"}), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 401

# --- Machine summary data ---
@app.route('/machine_details', methods=['POST'])
def machine_summary():
    token = request.headers.get('token')
    if not token:
        return jsonify({'error': 'Missing auth token'}), 401

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT * FROM machine ORDER BY timestamp DESC')
    rows = cursor.fetchall()
    conn.close()

    latest_data = {}
    for row in rows:
        mid = row['id']
        if mid not in latest_data:
            latest_data[mid] = row

    return jsonify({"machines": list(latest_data.values())})

# --- Machine timeseries data ---
@app.route('/machine_details/<machine_id>', methods=['GET'])
def machine_timeseries(machine_id):
    token = request.headers.get('token')
    if not token:
        return jsonify({'error': 'Missing auth token'}), 401

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
        SELECT timestamp, motor_temp_C, power_consumption_W, cutting_force_N,
               predicted_health_score, anomaly_score
        FROM machine
        WHERE id = %s
        ORDER BY timestamp DESC
        LIMIT 50
    ''', (machine_id,))
    rows = cursor.fetchall()
    conn.close()

    return jsonify({"timeSeriesData": rows})

# --- Prediction per machine ---
def process_machine_unit(machine_id, row_idx):
    try:
        df = pd.read_csv(CSV_FILE_PATH)
        if row_idx >= len(df):
            logger.warning(f"Row index {row_idx} out of bounds for machine {machine_id}")
            return False

        test_df = df.iloc[row_idx]
        results = make_predictions(test_df, models)
        timestamp_value = test_df.get('timestamp', pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'))

        record = {
            'id': machine_id,
            'timestamp': timestamp_value,
            'anomaly_score': results['anomaly_score'],
            'predicted_anomaly': bool(results['predicted_anomaly']),
            'predicted_anomaly_type': results['predicted_anomaly_type'],
            'predicted_health_score': results['predicted_health_score'],
            'predicted_days_to_maintenance': results['predicted_days_to_maintenance'],
            'motor_temp_C': test_df.get('motor_temp_C', 60),
            'power_consumption_W': test_df.get('power_consumption_W', 5000),
            'cutting_force_N': test_df.get('cutting_force_N', 200)
        }

        conn = get_db_connection()
        cursor = conn.cursor()
        columns = ', '.join(record.keys())
        placeholders = ', '.join(['%s'] * len(record))
        values = [safe_cast(v) for v in record.values()]
        cursor.execute(f'INSERT INTO machine ({columns}) VALUES ({placeholders})', values)
        cursor.execute('UPDATE factory SET row_idx = %s WHERE id = %s', ((row_idx + 1) % 10000, machine_id))
        conn.commit()
        conn.close()

        logger.info(f"Processed {machine_id}, anomaly: {record['predicted_anomaly']}")
        return True

    except Exception as e:
        logger.error(f"Error processing machine {machine_id}: {e}")
        return False

# --- Process all machines ---
def process_all_machines():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT id, row_idx FROM factory')
    pointers = cursor.fetchall()
    conn.close()

    count = 0
    for p in pointers:
        if process_machine_unit(p['id'], p['row_idx']):
            count += 1

    logger.info(f"Processed {count}/{len(pointers)} machines.")
    return count

# --- Scheduler ---
def initialize():
    scheduler.add_job(func=process_all_machines, trigger='interval', minutes=0.1)
    scheduler.start()
    logger.info("Scheduler started.")

with app.app_context():
    initialize()

# --- Health check ---
@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({"status": "running", "message": "ML service active"})

# --- Trigger manually ---
@app.route('/trigger', methods=['GET'])
def trigger():
    count = process_all_machines()
    return jsonify({"status": "success", "machines_processed": count})

# --- Get latest prediction ---
@app.route('/machine/<machine_id>', methods=['GET'])
def get_machine_prediction(machine_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
        SELECT * FROM predictions WHERE machine_id = %s
        ORDER BY timestamp DESC LIMIT 1
    ''', (machine_id,))
    prediction = cursor.fetchone()
    conn.close()
    return jsonify(prediction if prediction else {'error': 'No data'}), (200 if prediction else 404)

# --- Start app ---
if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
