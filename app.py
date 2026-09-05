from flask import Flask, g, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, desc
from firebase_config import *
from auth_decorator import firebase_required
from datetime import date, timedelta, datetime
import os
import sys
from dotenv import load_dotenv
from models import DailyGoalsLog, db, User, DailyCarbonLog
from carbon import (
    EMISSION_FACTORS,
    CATEGORY_MAPPING,
    calculate_carbon_emissions,
    classify_level,
    get_emission_category,
    CarbonFuzzySystem,
    generate_improvement_suggestions
)
import pymysql

print("=== 0. IMPORTS OK ===", flush=True)

# Setup MySQL driver
pymysql.install_as_MySQLdb()

# Load environment variables from .env (for local dev)
load_dotenv()

app = Flask(__name__)

print("=== 1. FLASK APP CREATED ===", flush=True)

# Read credentials from environment
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT")
DB_NAME = os.environ.get("DB_NAME")
SSL_PATH = os.environ.get("SSL_PATH")

print(f"=== 2. ENV LOADED: DB_HOST={DB_HOST}, DB_PORT={DB_PORT}, DB_NAME={DB_NAME}, SSL_PATH={SSL_PATH} ===", flush=True)

# Configure SQLAlchemy with secure credentials (supporting SSL ca.pem if provided)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
ssl_file_path = os.path.join(BASE_DIR, SSL_PATH) if SSL_PATH else None

print(f"=== 3. SSL FILE PATH: {ssl_file_path}, EXISTS: {os.path.exists(ssl_file_path) if ssl_file_path else 'N/A'} ===", flush=True)

if ssl_file_path:
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        f"?charset=utf8mb4&ssl_ca={ssl_file_path}"
    )
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        f"?charset=utf8mb4"
    )

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

print("=== 4. CONFIG SET, INITIALIZING DB... ===", flush=True)

# Initialize database
db.init_app(app)

print("=== 5. DB INITIALIZED, BEFORE create_all() ===", flush=True)

try:
    with app.app_context():
        db.create_all()
    print("=== 6. db.create_all() SUCCESS! ===", flush=True)
except Exception as e:
    print(f"=== !!! ERROR IN db.create_all(): {repr(e)} ===", flush=True)
    raise

print("=== 7. APP FULLY LOADED, ROUTES NEXT ===", flush=True)

# ============================
# ROUTE: Sync User
# ============================
@app.route('/me', methods=['POST'])
@firebase_required
def sync_user():
    from firebase_admin import auth as fb_auth
    try:
        decoded = fb_auth.get_user(request.user_uid)
        email = decoded.email
        created_at = datetime.fromtimestamp(decoded.user_metadata.creation_timestamp / 1000.0)
    except Exception as e:
        return jsonify({"message": "Failed to retrieve user from Firebase", "error": str(e)}), 500

    data = request.get_json() or {}
    username = data.get('username') or email.split("@")[0]
    profile_url = data.get('profilePicture') or "assets/images/profilePictures/default.png"

    user = User.query.filter_by(firebase_uid=request.user_uid).first()
    if not user:
        user = User(
            firebase_uid=request.user_uid,
            email=email,
            username=username,
            profilePicture=profile_url,
            joinDate=created_at,
            points=0,
            currentIslandTheme=0
        )
        db.session.add(user)
        db.session.commit()
        return jsonify({"message": "New user saved to database"}), 201

    return jsonify({"message": "User already exists in database"}), 200

# (sisanya SAMA PERSIS seperti kode asli kamu, gak ada yang diubah,
#  dari @app.route('/me', methods=['GET']) sampai baris paling bawah)
