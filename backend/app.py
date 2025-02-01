from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required, JWTManager
from flask_marshmallow import Marshmallow
from flask_migrate import Migrate
from flask_cors import CORS
import bcrypt
import os
import logging
import re
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()

# Validate environment variables
required_env_vars = ['JWT_SECRET_KEY']
for var in required_env_vars:
    if not os.getenv(var):
        raise ValueError(f"Environment variable '{var}' not set")

app = Flask(__name__)

# SQLite Configuration
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///'+os.path.join(BASE_DIR, 'hospital_management.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')

CORS(app)  # Enable CORS for development

db = SQLAlchemy(app)
jwt = JWTManager(app)
ma = Marshmallow(app)
migrate = Migrate(app, db)

# Models
class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    available = db.Column(db.Boolean, default=True)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(100), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    doctor = db.relationship('Doctor', backref=db.backref('appointments', lazy=True))

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

# Create tables
with app.app_context():
    db.create_all()

@app.route('/doctors', methods=['GET'])
@jwt_required()
def get_doctors():
    try:
        doctors = Doctor.query.all()
        return jsonify(doctors_schema.dump(doctors))
    except Exception as e:
        logger.error(f"Error retrieving doctors: {str(e)}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

@app.route('/doctors', methods=['POST'])
@jwt_required()
def add_doctor():
    try:
        name = request.json['name']
        specialization = request.json['specialization']
        new_doctor = Doctor(name=name, specialization=specialization)
        db.session.add(new_doctor)
        db.session.commit()
        return jsonify(doctor_schema.dump(new_doctor)), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding doctor: {str(e)}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

@app.route('/appointments', methods=['POST'])
@jwt_required()
def book_appointment():
    try:
        patient_name = request.json['patient_name']
        doctor_id = request.json['doctor_id']
        date = request.json['date']
        new_appointment = Appointment(patient_name=patient_name, doctor_id=doctor_id, date=date)
        db.session.add(new_appointment)
        db.session.commit()
        return jsonify(appointment_schema.dump(new_appointment)), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error booking appointment: {str(e)}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    try:
        # Email validation
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return jsonify({"message": "Invalid email format"}), 400

        # Fetch member by email (Assuming you have a Member model)
        member = Member.query.filter_by(email=email).first()

        if not member:
            return jsonify({"message": f"User with email {email} does not exist"}), 400

        # Check password
        if not bcrypt.checkpw(password.encode('utf-8'), member.password.encode('utf-8')):
            return jsonify({"message": "Invalid password"}), 400

        # Don't return the actual password, mask it
        member.password = "########"

        # Create access token
        access_token = create_access_token(identity=str(member.id), expires_delta=timedelta(minutes=60))
        logger.info(f"Successful login for user: {member.email}")
        return jsonify({
            "message": f"Welcome {member.name}",
            "member": member_schema.dump(member),
            "access_token": access_token
        })
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    if os.getenv('FLASK_ENV') == 'development':
        app.run(debug=True)
    else:
        app.run()