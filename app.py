import os
import json
import logging
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

# Firebase Admin / Firestore
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# -----------------------------------------------------------------------------
# App & logging setup
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_for_development")
CORS(app)

# Secrets / config
DELETE_SECRET = os.environ.get("DELETE_SECRET", "SECRET123")
COLLECTION = "progress_logs"

# -----------------------------------------------------------------------------
# Firebase initialization (service-account JSON provided via env var)
# -----------------------------------------------------------------------------
def init_firebase():
    """
    Initialize Firebase Admin SDK using the full JSON pasted in the env var
    FIREBASE_SERVICE_ACCOUNT_JSON. Do NOT store the JSON file on disk in prod.
    """
    if not firebase_admin._apps:
        sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
        if not sa_json:
            raise RuntimeError(
                "FIREBASE_SERVICE_ACCOUNT_JSON env var is missing.\n"
                "In Firebase Console -> Project settings -> Service accounts -> "
                "Generate new private key, then paste the entire JSON into this env var."
            )
        cred = credentials.Certificate(json.loads(sa_json))
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firebase()

# -----------------------------------------------------------------------------
# Firestore helpers (mirror your CSV semantics)
# -----------------------------------------------------------------------------
def add_progress_row(data: dict):
    """
    Insert one log record into Firestore.
    Normalize a few fields to support case-insensitive filters later.
    """
    doc = {
        "Email": data["email"].strip().lower(),
        "Student ID": str(data["student_id"]).strip(),
        "Week": str(data["week"]).strip().lower(),
        "Exercise": str(data["exercise"]).strip(),
        "Status": str(data["status"]).strip(),
        "Feedback": str(data["feedback"]).strip(),
        "created_at": firestore.SERVER_TIMESTAMP,
    }
    db.collection(COLLECTION).add(doc)
    logging.info(f"[Firestore] Appended: {doc['Email']} / {doc['Exercise']}")

def query_logs(email=None, student_id=None, week=None):
    """
    Fetch logs with optional equality filters. Firestore supports chaining
    equality filters as used here. For larger datasets, consider adding
    order_by('created_at') and limits.
    """
    q = db.collection(COLLECTION)
    if email:
        q = q.where("Email", "==", email.strip().lower())
    if student_id:
        q = q.where("Student ID", "==", str(student_id).strip())
    if week:
        q = q.where("Week", "==", str(week).strip().lower())

    docs = q.stream()
    return [doc.to_dict() | {"_id": doc.id} for doc in docs]

def get_all_logs():
    docs = db.collection(COLLECTION).stream()
    return [doc.to_dict() | {"_id": doc.id} for doc in docs]

def clear_all_logs():
    """
    Batch delete all docs in the collection. Commits every ~450 ops to avoid
    oversized batches/timeouts.
    """
    batch = db.batch()
    count = 0
    for d in db.collection(COLLECTION).stream():
        batch.delete(d.reference)
        count += 1
        if count % 450 == 0:
            batch.commit()
            batch = db.batch()
    batch.commit()
    return count

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    """
    Serve your landing page. If 'templates/index.html' doesn't exist, we return
    a simple OK string instead of a 500.
    """
    try:
        return render_template("index.html")
    except Exception:
        return "OK", 200

@app.route("/log", methods=["POST"])
def log_progress():
    """
    POST: Add a progress log.
    Body (JSON): { email, student_id, week, exercise, status, feedback }
    """
    try:
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400
        data = request.get_json()

        required = ["email", "student_id", "week", "exercise", "status", "feedback"]
        for f in required:
            if f not in data or not str(data[f]).strip():
                return jsonify({"error": f"Missing or empty required field: {f}"}), 400

        if "@" not in data["email"]:
            return jsonify({"error": "Invalid email format"}), 400

        valid_statuses = {"completed", "in_progress", "not_started", "submitted", "reviewed"}
        if str(data["status"]).strip().lower() not in valid_statuses:
            logging.warning(f"[Firestore] Non-standard status: {data['status']}")

        add_progress_row(data)
        return jsonify({"message": "Progress logged successfully", "data": data}), 201

    except Exception as e:
        logging.exception("Error in /log")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/logs", methods=["GET"])
def get_logs_route():
    """
    GET: Retrieve logs with optional filters: ?email=&student_id=&week=
    """
    try:
        email = request.args.get("email")
        student_id = request.args.get("student_id")
        week = request.args.get("week")

        logs = query_logs(email=email, student_id=student_id, week=week)
        return jsonify({
            "logs": logs,
            "total_count": len(logs),
            "filters_applied": {"email": email, "student_id": student_id, "week": week},
        }), 200

    except Exception as e:
        logging.exception("Error in GET /logs")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/logs/all", methods=["GET"])
def get_all_logs_and_validate():
    """
    GET: Fetch ALL logs (no filters) and emit a healthcheck log token.
    """
    try:
        logs = get_all_logs()
        logger = logging.getLogger()
        test_token = f"healthcheck:{os.getpid()}"
        logger.debug(f"[HEALTHCHECK] {test_token}")
        return jsonify({
            "logs": logs,
            "total_count": len(logs),
            "logging_validation": {
                "logger_level": logging.getLevelName(logger.level),
                "handlers": [type(h).__name__ for h in logger.handlers],
                "firestore_ok": True,
                "emitted_test_log_token": test_token
            }
        }), 200
    except Exception as e:
        logging.exception("Error in GET /logs/all")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/logs", methods=["DELETE"])
def delete_logs():
    """
    DELETE: Clear all logs. Requires ?key=DELETE_SECRET
    """
    try:
        provided_key = request.args.get("key")
        if not provided_key:
            return jsonify({"error": "Secret key required"}), 400
        if provided_key != DELETE_SECRET:
            logging.warning(f"Invalid delete attempt with key: {provided_key}")
            return jsonify({"error": "Invalid secret key"}), 403

        deleted = clear_all_logs()
        logging.info(f"[Firestore] Deleted {deleted} documents")
        return jsonify({"message": f"All progress logs cleared ({deleted} docs)"}), 200

    except Exception as e:
        logging.exception("Error in DELETE /logs")
        return jsonify({"error": "Internal server error"}), 500

# -----------------------------------------------------------------------------
# Error handlers
# -----------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "Method not allowed"}), 405

# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # In production on Render, they set the PORT env var.
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
