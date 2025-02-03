from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_cors import CORS
from flask_migrate import Migrate
import os
import logging
from datetime import datetime

# Initialize the app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Enable CORS for all routes

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# SQLite Configuration
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "hospital_management.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize database and marshmallow
db = SQLAlchemy(app)
ma = Marshmallow(app)
migrate = Migrate(app, db)

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

# Instantiate schemas
doctor_schema = DoctorSchema()
doctors_schema = DoctorSchema(many=True)
appointment_schema = AppointmentSchema()
appointments_schema = AppointmentSchema(many=True)

# Insert sample data if doctors table is empty
@app.before_first_request
def insert_sample_data():
    if Doctor.query.count() == 0:  # Check if the doctors table is empty
        doctor1 = Doctor(name="Dr. Alice Johnson", specialization="Cardiologist", available=True)
        doctor2 = Doctor(name="Dr. Bob Smith", specialization="Dermatologist", available=False)
        doctor3 = Doctor(name="Dr. Carol Lee", specialization="Neurologist", available=True)
        doctor4 = Doctor(name="Dr. David Wilson", specialization="Pediatrician", available=True)
        
        db.session.add_all([doctor1, doctor2, doctor3, doctor4])
        db.session.commit()
        logger.info("Sample doctors added to the database.")

# Create tables if they don't exist
with app.app_context():
    db.create_all()

# Test Route
@app.route("/")
def home():
    return jsonify({"message": "Flask Backend is Running"}), 200

# Get all doctors
@app.route("/doctors", methods=["GET"])
def get_doctors():
    try:
        doctors = Doctor.query.all()
        return jsonify(doctors_schema.dump(doctors)), 200
    except Exception as e:
        logger.error(f"Error fetching doctors: {str(e)}")
        return jsonify({"message": "Error fetching doctors"}), 500

# Add a new doctor
@app.route("/doctors", methods=["POST"])
def add_doctor():
    try:
        name = request.json.get("name")
        specialization = request.json.get("specialization")

        if not name or not specialization:
            return jsonify({"message": "Both name and specialization are required."}), 400

        new_doctor = Doctor(name=name, specialization=specialization)
        db.session.add(new_doctor)
        db.session.commit()

        logger.info(f"Doctor {name} added successfully.")
        return jsonify(doctor_schema.dump(new_doctor)), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding doctor: {str(e)}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

# Book an appointment
@app.route("/appointments", methods=["POST"])
def book_appointment():
    try:
        patient_name = request.json.get("patient_name")
        doctor_id = request.json.get("doctor_id")
        date_str = request.json.get("date")

        if not patient_name or not doctor_id or not date_str:
            return jsonify({"message": "Patient name, doctor ID, and date are required."}), 400

        # Convert date from string to Python date object
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"message": "Invalid date format. Use YYYY-MM-DD."}), 400

        doctor = Doctor.query.get(doctor_id)
        if not doctor:
            return jsonify({"message": "Doctor not found."}), 404

        new_appointment = Appointment(patient_name=patient_name, doctor_id=doctor_id, date=date)
        db.session.add(new_appointment)
        db.session.commit()

        logger.info(f"Appointment booked for {patient_name} with Dr. {doctor.name} on {date}.")
        return jsonify(appointment_schema.dump(new_appointment)), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error booking appointment: {str(e)}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

# Run the app
if __name__ == "__main__":
    app.run(debug=True)
