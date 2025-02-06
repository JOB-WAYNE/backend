from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_cors import CORS
from flask_migrate import Migrate
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Enable CORS
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# PostgreSQL Configuration for SQLAlchemy
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SUPABASE_DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize database and Marshmallow
db = SQLAlchemy(app)
ma = Marshmallow(app)
migrate = Migrate(app, db)

# Initialize Supabase client
url = "https://tapjyolyumtxqfvsukwi.supabase.co"  # Replace with your actual Supabase URL
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRhcGp5b2x5dW10eHFmdnN1a3dpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Mzg4MjQ5MDksImV4cCI6MjA1NDQwMDkwOX0.YSXGAtvc6uo4o8_d5wHPWFIQ7JHb1D0Sb0dcsf-jNd8"  # Replace with your actual Supabase key
supabase: Client = create_client(url, key)

# Models
class Doctor(db.Model):
    __tablename__ = "doctors"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    available = db.Column(db.Boolean, default=True)

class Appointment(db.Model):
    __tablename__ = "appointments"
    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(100), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    doctor = db.relationship("Doctor", backref=db.backref("appointments", lazy=True))

# Schemas
class DoctorSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Doctor
        include_relationships = True
        load_instance = True

class AppointmentSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Appointment
        include_fk = True
        load_instance = True

doctor_schema = DoctorSchema()
doctors_schema = DoctorSchema(many=True)
appointment_schema = AppointmentSchema()
appointments_schema = AppointmentSchema(many=True)

# Routes
@app.route("/")
def home():
    return jsonify({"message": "Flask Backend is Running"}), 200

@app.route("/doctors", methods=["GET"])
def get_doctors():
    try:
        doctors = Doctor.query.filter_by(available=True).all()
        return jsonify(doctors_schema.dump(doctors)), 200
    except Exception as e:
        logger.error(f"Error fetching doctors: {str(e)}")
        return jsonify({"message": "Error fetching doctors"}), 500

@app.route("/doctors", methods=["POST"])
def add_doctor():
    try:
        name = request.json.get("name")
        specialization = request.json.get("specialization")
        available = request.json.get("available", True)

        if not name or not specialization:
            return jsonify({"message": "Both name and specialization are required."}), 400

        new_doctor = Doctor(name=name, specialization=specialization, available=available)
        db.session.add(new_doctor)
        db.session.commit()

        # Insert the doctor into Supabase as well (if required)
        supabase.table('doctors').insert({"name": name, "specialization": specialization, "available": available}).execute()

        logger.info(f"Doctor {name} added successfully.")
        return jsonify(doctor_schema.dump(new_doctor)), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding doctor: {str(e)}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

@app.route("/appointments", methods=["POST"])
def book_appointment():
    try:
        patient_name = request.json.get("patient_name")
        doctor_id = request.json.get("doctor_id")
        date_str = request.json.get("date")

        if not patient_name or not doctor_id or not date_str:
            return jsonify({"message": "Patient name, doctor ID, and date are required."}), 400

        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"message": "Invalid date format. Use YYYY-MM-DD."}), 400

        doctor = Doctor.query.get(doctor_id)
        if not doctor:
            return jsonify({"message": "Doctor not found."}), 404
        if not doctor.available:
            return jsonify({"message": "Doctor is not available for booking."}), 400

        new_appointment = Appointment(patient_name=patient_name, doctor_id=doctor_id, date=date)
        db.session.add(new_appointment)
        db.session.commit()

        # Insert the appointment into Supabase as well (if required)
        supabase.table('appointments').insert({"patient_name": patient_name, "doctor_id": doctor_id, "date": str(date)}).execute()

        logger.info(f"Appointment booked for {patient_name} with Dr. {doctor.name} on {date}.")
        return jsonify(appointment_schema.dump(new_appointment)), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error booking appointment: {str(e)}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

@app.route('/test_supabase', methods=['GET'])
def test_supabase_connection():
    try:
        response = supabase.table('doctors').select('*').execute()
        return jsonify({"message": "Connected to Supabase", "data": response.data}), 200
    except Exception as e:
        return jsonify({"message": "Failed to connect to Supabase", "error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
