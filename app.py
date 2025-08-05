import os
import csv
import json
import logging
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_for_development")
CORS(app)

# Configuration
CSV_FILE = "progress_log.csv"
SECRET_KEY = os.environ.get("DELETE_SECRET", "SECRET123")
CSV_HEADERS = ["Email", "Student ID", "Week", "Exercise", "Status", "Feedback"]

def ensure_csv_exists():
    """Create CSV file with headers if it doesn't exist"""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(CSV_HEADERS)
        logging.info(f"Created new CSV file: {CSV_FILE}")

def read_csv_data():
    """Read all data from CSV file and return as list of dictionaries"""
    ensure_csv_exists()
    data = []
    try:
        with open(CSV_FILE, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                data.append(row)
    except Exception as e:
        logging.error(f"Error reading CSV file: {e}")
        raise
    return data

def append_to_csv(data):
    """Append a single row to the CSV file"""
    ensure_csv_exists()
    try:
        with open(CSV_FILE, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                data['email'],
                data['student_id'],
                data['week'],
                data['exercise'],
                data['status'],
                data['feedback']
            ])
        logging.info(f"Appended data to CSV: {data['email']}, {data['exercise']}")
    except Exception as e:
        logging.error(f"Error writing to CSV file: {e}")
        raise

@app.route('/')
def index():
    """Serve the main documentation/testing page"""
    return render_template('index.html')

@app.route('/log', methods=['POST'])
def log_progress():
    """POST endpoint to log student progress"""
    try:
        # Validate JSON data
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['email', 'student_id', 'week', 'exercise', 'status', 'feedback']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({"error": f"Missing or empty required field: {field}"}), 400
        
        # Validate email format (basic check)
        if '@' not in data['email']:
            return jsonify({"error": "Invalid email format"}), 400
        
        # Validate status field
        valid_statuses = ['completed', 'in_progress', 'not_started', 'submitted', 'reviewed']
        if data['status'].lower() not in valid_statuses:
            logging.warning(f"Non-standard status received: {data['status']}")
        
        # Append to CSV
        append_to_csv(data)
        
        return jsonify({
            "message": "Progress logged successfully",
            "data": data
        }), 201
        
    except Exception as e:
        logging.error(f"Error in log_progress: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/logs', methods=['GET'])
def get_logs():
    """GET endpoint to retrieve logs with optional filtering"""
    try:
        # Read all data from CSV
        all_data = read_csv_data()
        
        # Apply filters based on query parameters
        email_filter = request.args.get('email')
        student_id_filter = request.args.get('student_id')
        week_filter = request.args.get('week')
        
        filtered_data = all_data
        
        if email_filter:
            filtered_data = [row for row in filtered_data if row['Email'].lower() == email_filter.lower()]
        
        if student_id_filter:
            filtered_data = [row for row in filtered_data if row['Student ID'] == student_id_filter]
        
        if week_filter:
            filtered_data = [row for row in filtered_data if row['Week'].lower() == week_filter.lower()]
        
        return jsonify({
            "logs": filtered_data,
            "total_count": len(filtered_data),
            "filters_applied": {
                "email": email_filter,
                "student_id": student_id_filter,
                "week": week_filter
            }
        }), 200
        
    except Exception as e:
        logging.error(f"Error in get_logs: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/logs', methods=['DELETE'])
def delete_logs():
    """DELETE endpoint to clear logs with secret key protection"""
    try:
        # Check for secret key
        provided_key = request.args.get('key')
        
        if not provided_key:
            return jsonify({"error": "Secret key required"}), 400
        
        if provided_key != SECRET_KEY:
            logging.warning(f"Invalid delete attempt with key: {provided_key}")
            return jsonify({"error": "Invalid secret key"}), 403
        
        # Clear the CSV file (recreate with just headers)
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(CSV_HEADERS)
        
        logging.info("Progress logs cleared successfully")
        
        return jsonify({
            "message": "All progress logs have been cleared successfully"
        }), 200
        
    except Exception as e:
        logging.error(f"Error in delete_logs: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "Method not allowed"}), 405

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
