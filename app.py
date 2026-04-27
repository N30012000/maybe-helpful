"""
Air Sial Safety Management System (SMS) v3.0
Complete Aviation Safety Reporting Application

Developed for Air Sial - Pakistan's Premium Airline
© 2024 Air Sial. All Rights Reserved.
"""

# Standard library imports
import base64
import hashlib
import io
import json
import os
import random
import re
import smtplib
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Optional, Dict, List, Any, Tuple

# Third-party imports
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
import numpy as np

# Optional pydeck for geospatial mapping
try:
    import pydeck as pdk
    PYDECK_AVAILABLE = True
except ImportError:
    pdk = None
    PYDECK_AVAILABLE = False

# PDF generation
try:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    APP_NAME = "Air Sial Corporate Safety"
    APP_VERSION = "3.0.0"
    APP_SUBTITLE = "Safety Management System"
    COMPANY_NAME = "Air Sial"
    COMPANY_IATA = "PF"
    COMPANY_ICAO = "SIS"
    CAA_COUNTRY = "Pakistan"
    CAA_AUTHORITY = "Pakistan Civil Aviation Authority (PCAA)"
    AOC_NUMBER = "AOC-PK-0XX"
    HAZARD_SLA_DAYS = 15
    INCIDENT_SLA_DAYS = 30
    BIRD_STRIKE_SLA_DAYS = 7
    LASER_STRIKE_SLA_DAYS = 7
    TCAS_SLA_DAYS = 14
    SLA_CRITICAL_DAYS = 3
    SLA_WARNING_DAYS = 7
    SAFETY_EMAIL = "safety@airsial.com"
    CAA_EMAIL = "reporting@caapakistan.com.pk"
    TIMEZONE = "Asia/Karachi"
    UTC_OFFSET = 5
    MAX_UPLOAD_SIZE_MB = 10
    ALLOWED_IMAGE_TYPES = ['png', 'jpg', 'jpeg', 'bmp', 'tiff', 'webp']
    ALLOWED_DOC_TYPES = ['pdf', 'docx', 'xlsx']

# ============================================================================
# ENUMERATIONS
# ============================================================================

class UserRole(Enum):
    ADMIN = "admin"
    SAFETY_MANAGER = "safety_manager"
    INVESTIGATOR = "investigator"
    DEPARTMENT_HEAD = "department_head"
    REPORTER = "reporter"
    VIEWER = "viewer"

class ReportStatus(Enum):
    DRAFT = "Draft"
    SUBMITTED = "Submitted"
    UNDER_REVIEW = "Under Review"
    CLOSED = "Closed"

class RiskLevel(Enum):
    EXTREME = "Extreme"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class ReportType(Enum):
    AIRCRAFT_INCIDENT = "aircraft_incident"
    BIRD_STRIKE = "bird_strike"
    LASER_STRIKE = "laser_strike"
    TCAS_REPORT = "tcas_report"
    HAZARD_REPORT = "hazard_report"
    FSR = "fsr"
    CAPTAIN_DBR = "captain_dbr"

# ============================================================================
# LOOKUP TABLES
# ============================================================================

DEPARTMENTS = [
    "Flight Operations", "Engineering & Maintenance", "Cabin Services",
    "Ground Operations", "Cargo Operations", "Flight Training",
    "Quality Assurance", "Safety Department", "Security Department",
    "Commercial", "Airport Operations - SKT", "Airport Operations - KHI",
    "Airport Operations - LHE", "Airport Operations - ISB",
    "Human Resources", "Finance", "IT Department", "Corporate Office",
    "Crew Scheduling", "Flight Dispatch", "Ramp Operations"
]

# AIRCRAFT_FLEET: dict keyed by registration
AIRCRAFT_FLEET = {
    "AP-BMA": {"type": "ATR 72-600", "msn": "1234", "config": "70Y", "engines": "PW127M", "mtow": "23000"},
    "AP-BMB": {"type": "ATR 72-600", "msn": "1235", "config": "70Y", "engines": "PW127M", "mtow": "23000"},
    "AP-BMC": {"type": "ATR 72-600", "msn": "1236", "config": "70Y", "engines": "PW127M", "mtow": "23000"},
    "AP-BMD": {"type": "ATR 72-600", "msn": "1237", "config": "70Y", "engines": "PW127M", "mtow": "23000"},
    "AP-BME": {"type": "ATR 72-600", "msn": "1238", "config": "70Y", "engines": "PW127M", "mtow": "23000"},
    "AP-BMF": {"type": "ATR 72-500", "msn": "1100", "config": "68Y", "engines": "PW127F", "mtow": "22800"},
    "AP-BMG": {"type": "ATR 72-500", "msn": "1101", "config": "68Y", "engines": "PW127F", "mtow": "22800"},
    "AP-BMH": {"type": "A320-200", "msn": "5500", "config": "180Y", "engines": "CFM56-5B", "mtow": "78000"},
    "AP-BMI": {"type": "A320-200", "msn": "5501", "config": "180Y", "engines": "CFM56-5B", "mtow": "78000"},
    "AP-BMJ": {"type": "A320neo", "msn": "8000", "config": "186Y", "engines": "PW1100G", "mtow": "79000"},
}

# AIRPORTS: dict keyed by ICAO
AIRPORTS = {
    "OPSK": {"name": "Sialkot International Airport", "city": "Sialkot", "country": "Pakistan", "base": True, "iata": "SKT", "elevation": "837ft"},
    "OPKC": {"name": "Jinnah International Airport", "city": "Karachi", "country": "Pakistan", "base": True, "iata": "KHI", "elevation": "100ft"},
    "OPLA": {"name": "Allama Iqbal International Airport", "city": "Lahore", "country": "Pakistan", "base": True, "iata": "LHE", "elevation": "712ft"},
    "OPIS": {"name": "Islamabad International Airport", "city": "Islamabad", "country": "Pakistan", "base": True, "iata": "ISB", "elevation": "1665ft"},
    "OPPS": {"name": "Peshawar Bacha Khan Airport", "city": "Peshawar", "country": "Pakistan", "base": False, "iata": "PEW", "elevation": "1158ft"},
    "OPQT": {"name": "Quetta International Airport", "city": "Quetta", "country": "Pakistan", "base": False, "iata": "UET", "elevation": "5267ft"},
    "OPFA": {"name": "Faisalabad International Airport", "city": "Faisalabad", "country": "Pakistan", "base": False, "iata": "LYP", "elevation": "591ft"},
    "OPMT": {"name": "Multan International Airport", "city": "Multan", "country": "Pakistan", "base": False, "iata": "MUX", "elevation": "403ft"},
    "OMDB": {"name": "Dubai International Airport", "city": "Dubai", "country": "UAE", "base": False, "iata": "DXB", "elevation": "62ft"},
    "OMSJ": {"name": "Sharjah International Airport", "city": "Sharjah", "country": "UAE", "base": False, "iata": "SHJ", "elevation": "111ft"},
    "OMAA": {"name": "Abu Dhabi International Airport", "city": "Abu Dhabi", "country": "UAE", "base": False, "iata": "AUH", "elevation": "88ft"},
    "OERK": {"name": "King Khalid International Airport", "city": "Riyadh", "country": "Saudi Arabia", "base": False, "iata": "RUH", "elevation": "2049ft"},
    "OEJN": {"name": "King Abdulaziz International Airport", "city": "Jeddah", "country": "Saudi Arabia", "base": False, "iata": "JED", "elevation": "48ft"},
    "OTHH": {"name": "Hamad International Airport", "city": "Doha", "country": "Qatar", "base": False, "iata": "DOH", "elevation": "13ft"},
    "OBBI": {"name": "Bahrain International Airport", "city": "Bahrain", "country": "Bahrain", "base": False, "iata": "BAH", "elevation": "6ft"},
}

# Helper: list of "ICAO - Name" strings for selectboxes
def airport_options():
    return [f"{icao} - {data['name']}" for icao, data in AIRPORTS.items()]

def aircraft_reg_options():
    return list(AIRCRAFT_FLEET.keys())

def get_aircraft_type(reg):
    return AIRCRAFT_FLEET.get(reg, {}).get("type", "")

def get_aircraft_msn(reg):
    return AIRCRAFT_FLEET.get(reg, {}).get("msn", "")

def get_aircraft_engines(reg):
    return AIRCRAFT_FLEET.get(reg, {}).get("engines", "")

FLIGHT_PHASES = [
    "Pre-flight / Ground Operations", "Taxi Out", "Takeoff Roll",
    "Initial Climb (0-1000ft AGL)", "Climb (1000-10000ft)",
    "Climb (Above 10000ft)", "Cruise", "Descent (Above 10000ft)",
    "Descent (10000ft-1000ft)", "Approach", "Final Approach",
    "Landing Roll", "Taxi In", "Post-flight / Parking", "Go-Around", "Holding"
]

INCIDENT_CATEGORIES = [
    "Abnormal Runway Contact", "Aerodrome", "Air Traffic Management",
    "Aircraft Damage", "Cabin Safety Events", "CFIT",
    "Collision / Near Collision", "De/Anti-icing Operations", "Depressurization",
    "Engine Failure / Malfunction", "Fire / Smoke", "Flight Crew Incapacitation",
    "Fuel Related", "Ground Collision", "Ground Handling", "Icing",
    "Landing Gear", "LOC-G", "LOC-I", "Low Altitude Operations", "Maintenance",
    "Medical Emergency", "Navigation Error", "Other", "Runway Excursion",
    "Runway Incursion", "Security Related", "System / Component Failure",
    "Turbulence Encounter", "Undershoot / Overshoot", "Unruly Passenger",
    "Unstable Approach", "Weather", "Wildlife Strike", "Windshear / Microburst"
]

HAZARD_CATEGORIES = [
    "Aircraft Systems", "Airport Infrastructure", "ATC/Navigation", "Cabin Safety",
    "Cargo Handling", "Documentation/Procedures", "Environmental", "Equipment/Tools",
    "Fatigue/Human Factors", "Flight Operations", "Fuel Operations", "Ground Operations",
    "Maintenance", "Passenger Handling", "Ramp Safety", "Security", "Training",
    "Weather Related", "Wildlife/Bird Activity", "Other"
]

BIRD_SPECIES = [
    "Unknown", "House Crow", "Jungle Crow", "Black Kite", "Brahminy Kite",
    "Pariah Kite", "Vulture (Egyptian)", "Vulture (Griffon)", "Pigeon / Rock Dove",
    "Myna", "Starling", "Sparrow", "Swift", "Swallow", "Egret", "Heron",
    "Lapwing", "Plover", "Sandpiper", "Owl", "Eagle", "Falcon", "Hawk",
    "Hoopoe", "Kingfisher", "Parakeet / Parrot", "Bat (Mammal)",
    "Multiple Species", "Unidentified Flock", "Other (Specify)"
]

BIRD_SIZES = ["Small (<100g)", "Medium-Small (100-500g)", "Medium (500g-1kg)",
              "Medium-Large (1-2kg)", "Large (2-5kg)", "Very Large (>5kg)"]

# Laser colors - simple string list
LASER_COLORS = [
    "Green (532nm)", "Red (630-670nm)", "Blue (445-488nm)", "Violet/Purple (405nm)",
    "Yellow/Amber (570-590nm)", "White (Multi-wavelength)", "Infrared (Not visible)",
    "Unknown/Could not determine", "Multiple Colors"
]

LASER_INTENSITIES = [
    "1 - Low (Barely visible, no visual effect)",
    "2 - Moderate (Visible but not distracting)",
    "3 - Significant (Distracting, momentary startle)",
    "4 - High (Bright, glare/flash blindness)",
    "5 - Very High (Extremely bright, disorientation/pain)"
]

TCAS_ALERT_TYPES = [
    "Traffic Advisory (TA) Only",
    "Resolution Advisory (RA) - Climb",
    "Resolution Advisory (RA) - Descend",
    "Resolution Advisory (RA) - Level Off",
    "Resolution Advisory (RA) - Maintain Vertical Speed",
    "Resolution Advisory (RA) - Adjust Vertical Speed",
    "Resolution Advisory (RA) - Crossing Climb",
    "Resolution Advisory (RA) - Crossing Descend",
    "Resolution Advisory (RA) - Reversal",
    "Preventive RA - Don't Climb",
    "Preventive RA - Don't Descend",
    "Multi-Aircraft Encounter",
]

WEATHER_CONDITIONS = [
    "VMC - Clear", "VMC - Few Clouds", "VMC - Scattered", "VMC - Broken",
    "IMC - Overcast", "IMC - Low Visibility", "Rain - Light", "Rain - Moderate",
    "Rain - Heavy", "Thunderstorm Vicinity", "Thunderstorm", "Fog", "Mist",
    "Haze", "Dust/Sand", "Snow", "Icing Conditions", "Turbulence - Light",
    "Turbulence - Moderate", "Turbulence - Severe", "Windshear Reported",
    "Crosswind (Significant)", "Gusty Conditions"
]

DAMAGE_LEVELS = ["None", "Minor", "Moderate", "Major", "Severe", "Destroyed"]

EFFECT_ON_FLIGHT_OPTIONS = [
    "None - Flight continued normally",
    "Precautionary landing at destination",
    "Precautionary landing at alternate",
    "Return to departure airport",
    "Emergency landing",
    "Aborted takeoff",
    "Aborted approach / Go-around",
    "Other"
]

CREW_EFFECTS_LASER = [
    "Glare", "Flash Blindness", "Afterimage", "Eye Pain/Discomfort",
    "Eye Watering", "Disorientation", "Headache", "Temporary Vision Loss",
    "Startle/Distraction", "No Effect"
]

AIRCRAFT_PARTS_STRUCK = [
    "Radome", "Windshield", "Nose/Fuselage", "Engine #1", "Engine #2",
    "Propeller", "Wing Leading Edge", "Wing Trailing Edge", "Fuselage",
    "Landing Gear", "Tail/Empennage", "Lights", "Pitot/Static", "Other"
]

CREW_POSITIONS = [
    "Captain (PIC)", "First Officer (SIC)", "Relief First Officer",
    "Check Captain", "TRI/TRE", "Line Training Captain",
    "Cabin Manager / Purser", "Senior Cabin Crew", "Cabin Crew",
    "Loadmaster", "Observer"
]

# ============================================================================
# ICAO RISK MATRIX
# ============================================================================

LIKELIHOOD_SCALE = {
    1: {"name": "Extremely Improbable", "description": "Almost inconceivable that the event will occur"},
    2: {"name": "Improbable", "description": "Very unlikely to occur"},
    3: {"name": "Remote", "description": "Unlikely but possible to occur"},
    4: {"name": "Occasional", "description": "Likely to occur sometimes"},
    5: {"name": "Frequent", "description": "Likely to occur many times"}
}

SEVERITY_SCALE = {
    "A": {"name": "Catastrophic", "description": "Equipment destroyed, multiple deaths"},
    "B": {"name": "Hazardous", "description": "Large reduction in safety margins"},
    "C": {"name": "Major", "description": "Significant reduction in safety margins"},
    "D": {"name": "Minor", "description": "Nuisance, operating limitations"},
    "E": {"name": "Negligible", "description": "Little consequence"}
}

RISK_MATRIX = {
    ("5","A"): "Extreme", ("5","B"): "Extreme", ("5","C"): "High", ("5","D"): "Medium", ("5","E"): "Low",
    ("4","A"): "Extreme", ("4","B"): "High",    ("4","C"): "High", ("4","D"): "Medium", ("4","E"): "Low",
    ("3","A"): "High",    ("3","B"): "High",    ("3","C"): "Medium","3","D": "Medium", ("3","E"): "Low",
    ("2","A"): "High",    ("2","B"): "Medium",  ("2","C"): "Medium",("2","D"): "Low",  ("2","E"): "Low",
    ("1","A"): "Medium",  ("1","B"): "Low",     ("1","C"): "Low",   ("1","D"): "Low",  ("1","E"): "Low",
}

# Fix the dict literal above - tuples as keys must be consistent
RISK_MATRIX = {}
_rm_raw = [
    (5,"A","Extreme"),(5,"B","Extreme"),(5,"C","High"),(5,"D","Medium"),(5,"E","Low"),
    (4,"A","Extreme"),(4,"B","High"),(4,"C","High"),(4,"D","Medium"),(4,"E","Low"),
    (3,"A","High"),(3,"B","High"),(3,"C","Medium"),(3,"D","Medium"),(3,"E","Low"),
    (2,"A","High"),(2,"B","Medium"),(2,"C","Medium"),(2,"D","Low"),(2,"E","Low"),
    (1,"A","Medium"),(1,"B","Low"),(1,"C","Low"),(1,"D","Low"),(1,"E","Low"),
]
for _l,_s,_r in _rm_raw:
    RISK_MATRIX[(str(_l),_s)] = _r

RISK_ACTIONS = {
    "Extreme": {"action": "STOP OPERATIONS", "color": "#DC3545", "timeline": "Immediate", "description": "Immediate action required."},
    "High":    {"action": "URGENT CORRECTIVE ACTION", "color": "#FD7E14", "timeline": "Within 24-48 hours", "description": "Senior management attention required."},
    "Medium":  {"action": "CORRECTIVE ACTION REQUIRED", "color": "#FFC107", "timeline": "Within 15 days", "description": "Management responsibility."},
    "Low":     {"action": "MONITOR AND REVIEW", "color": "#28A745", "timeline": "Next scheduled review", "description": "Accept risk with monitoring."},
}

LIKELIHOOD_DEFINITIONS = {
    "1": "Extremely Improbable - Almost inconceivable that the event will occur",
    "2": "Improbable - Very unlikely to occur",
    "3": "Remote - Unlikely to occur but possible",
    "4": "Occasional - Likely to occur sometimes",
    "5": "Frequent - Likely to occur many times"
}

SEVERITY_DEFINITIONS = {
    "A": "Catastrophic - Equipment destroyed, multiple deaths",
    "B": "Hazardous - Large reduction in safety margins, serious injury or death",
    "C": "Major - Significant reduction in safety margins, serious incident",
    "D": "Minor - Nuisance, operating limitations, minor incident",
    "E": "Negligible - Little consequences"
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_risk_level(likelihood: int, severity: str) -> str:
    return RISK_MATRIX.get((str(likelihood), severity.upper()), "Medium")

def generate_report_number(prefix: str) -> str:
    date_str = datetime.now().strftime("%Y%m%d")
    unique_id = str(uuid.uuid4())[:6].upper()
    return f"{prefix}-{date_str}-{unique_id}"

def get_pakistan_time() -> datetime:
    return datetime.utcnow() + timedelta(hours=Config.UTC_OFFSET)

def get_logo_path():
    possible_paths = ["logo.png", "./logo.png", "assets/logo.png", "images/logo.png"]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

# ============================================================================
# DYNAMIC STATISTICS
# ============================================================================

def get_report_counts() -> dict:
    return {
        'bird_strikes': len(st.session_state.get('bird_strikes', [])),
        'laser_strikes': len(st.session_state.get('laser_strikes', [])),
        'tcas_reports': len(st.session_state.get('tcas_reports', [])),
        'hazard_reports': len(st.session_state.get('hazard_reports', [])),
        'aircraft_incidents': len(st.session_state.get('aircraft_incidents', [])),
        'fsr_reports': len(st.session_state.get('fsr_reports', [])),
        'captain_dbr': len(st.session_state.get('captain_dbr', []))
    }

def get_total_reports() -> int:
    return sum(get_report_counts().values())

def get_risk_distribution() -> dict:
    distribution = {"Extreme": 0, "High": 0, "Medium": 0, "Low": 0}
    for rt in ['hazard_reports', 'aircraft_incidents', 'bird_strikes', 'laser_strikes', 'tcas_reports']:
        for report in st.session_state.get(rt, []):
            risk = report.get('risk_level', 'Low')
            if risk in distribution:
                distribution[risk] += 1
    return distribution

def get_open_investigations() -> int:
    open_statuses = ['Open', 'Under Review', 'Submitted', 'Investigation In Progress', 'Pending Review']
    count = 0
    for rt in ['bird_strikes', 'laser_strikes', 'tcas_reports', 'hazard_reports', 'aircraft_incidents']:
        for r in st.session_state.get(rt, []):
            if r.get('status', 'Open') not in ['Closed', 'Investigation Complete']:
                count += 1
    return count

def get_high_risk_count() -> int:
    count = 0
    for rt in ['hazard_reports', 'aircraft_incidents', 'bird_strikes', 'laser_strikes', 'tcas_reports']:
        for r in st.session_state.get(rt, []):
            if r.get('risk_level', '') in ['High', 'Extreme']:
                count += 1
    return count

def get_recent_reports(limit: int = 5) -> list:
    all_reports = []
    type_icons = {
        'bird_strikes': '🐦', 'laser_strikes': '🔴', 'tcas_reports': '📡',
        'hazard_reports': '⚠️', 'aircraft_incidents': '🚨',
        'fsr_reports': '📋', 'captain_dbr': '👨‍✈️'
    }
    for rt in type_icons:
        for r in st.session_state.get(rt, []):
            all_reports.append({
                'type': rt, 'icon': type_icons[rt],
                'id': r.get('id', 'N/A'),
                'date': r.get('date', str(datetime.now().date())),
                'status': r.get('status', 'Open'),
                'risk_level': r.get('risk_level', 'Low'),
                'reporter': r.get('reported_by', 'Anonymous'),
                'description': r.get('description', r.get('narrative', r.get('hazard_description', 'No description')))
            })
    all_reports.sort(key=lambda x: x['date'], reverse=True)
    return all_reports[:limit]

# ============================================================================
# OCR SIMULATION
# ============================================================================

def simulate_ocr_extraction(form_type: str) -> dict:
    random.seed(int(time.time()))
    regs = list(AIRCRAFT_FLEET.keys())
    icaos = list(AIRPORTS.keys())
    flights = [f"PF-{random.randint(100,999)}" for _ in range(5)]

    base = {
        "flight_number": random.choice(flights),
        "aircraft_reg": random.choice(regs),
        "incident_date": (date.today() - timedelta(days=random.randint(0,7))).isoformat(),
        "incident_time": f"{random.randint(5,22):02d}:{random.randint(0,59):02d}",
        "departure_airport": random.choice(icaos),
        "arrival_airport": random.choice(icaos),
    }

    if form_type == "bird_strike":
        base.update({
            "flight_phase": random.choice(FLIGHT_PHASES[:8]),
            "altitude_agl": random.randint(0, 3000),
            "bird_species": random.choice(BIRD_SPECIES[:10]),
            "bird_size": random.choice(BIRD_SIZES),
            "number_seen": random.randint(1, 20),
            "number_struck": random.randint(1, 5),
            "parts_struck": random.sample(AIRCRAFT_PARTS_STRUCK, random.randint(1, 3)),
            "damage_level": random.choice(DAMAGE_LEVELS[:4]),
            "effect_on_flight": random.choice(EFFECT_ON_FLIGHT_OPTIONS[:4]),
            "narrative": "Bird strike during approach phase.",
            "captain_name": f"Capt. Ahmed Shah",
        })
    elif form_type == "laser_strike":
        base.update({
            "flight_phase": random.choice(["Approach", "Final Approach"]),
            "altitude_agl": random.randint(1500, 8000),
            "laser_color": random.choice(LASER_COLORS[:5]),
            "duration_seconds": random.randint(2, 30),
            "crew_effects": random.sample(CREW_EFFECTS_LASER[:6], random.randint(1, 3)),
            "narrative": "Laser illumination during approach.",
            "captain_name": f"Capt. Ahmed Shah",
        })
    elif form_type == "tcas_report":
        base.update({
            "flight_phase": "Cruise",
            "altitude_fl": random.randint(10000, 35000),
            "tcas_alert_type": random.choice(TCAS_ALERT_TYPES[:6]),
            "narrative": "TCAS RA received at FL350.",
            "captain_name": f"Capt. Ahmed Shah",
        })
    elif form_type == "hazard_report":
        base.update({
            "hazard_title": "Safety observation on ramp",
            "hazard_description": "Potential hazard identified during routine operations.",
            "suggested_actions": "Enhanced monitoring recommended.",
            "reporter_name": "Safety Officer",
        })

    return base

def render_ocr_uploader(form_type: str) -> Optional[dict]:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%);
                border: 2px dashed #3B82F6; border-radius: 12px;
                padding: 2rem; text-align: center; margin-bottom: 1.5rem;">
        <div style="font-size: 3rem;">📷</div>
        <h4 style="color: #1E40AF; margin: 0;">Scan Handwritten Form</h4>
        <p style="color: #64748B; font-size: 0.9rem; margin-top: 0.5rem;">
            Upload an image of a filled form to auto-extract data using OCR</p>
    </div>
    """, unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Upload Form Image",
        type=['png', 'jpg', 'jpeg', 'bmp', 'tiff', 'webp', 'pdf'],
        key=f"ocr_upload_{form_type}"
    )

    if uploaded_file is not None:
        col1, col2 = st.columns([1, 1])
        with col1:
            if uploaded_file.type and uploaded_file.type.startswith('image'):
                st.image(uploaded_file, caption="Uploaded Form", use_container_width=True)
            else:
                st.info(f"📄 PDF: {uploaded_file.name}")
        with col2:
            if st.button("🔍 Extract Data with OCR", key=f"extract_{form_type}", use_container_width=True):
                with st.spinner("Processing OCR..."):
                    for i in range(0, 101, 20):
                        time.sleep(0.1)
                    extracted = simulate_ocr_extraction(form_type)
                    st.session_state[f'ocr_data_{form_type}'] = extracted
                    st.success("✅ Extraction complete!")
                    with st.expander("View Extracted Data"):
                        for k, v in extracted.items():
                            if isinstance(v, list):
                                v = ", ".join(str(x) for x in v)
                            st.write(f"**{k.replace('_',' ').title()}:** {v}")
                    return extracted

    return st.session_state.get(f'ocr_data_{form_type}')

# ============================================================================
# CSS
# ============================================================================

def apply_custom_css():
    st.markdown("""
    <style>
    .stApp { background: #F8FAFC; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .risk-badge { display: inline-block; padding: 0.35rem 0.75rem; border-radius: 20px;
                  font-size: 0.75rem; font-weight: 600; }
    .risk-extreme { background: #FEE2E2; color: #DC2626; }
    .risk-high { background: #FFEDD5; color: #EA580C; }
    .risk-medium { background: #FEF9C3; color: #CA8A04; }
    .risk-low { background: #DCFCE7; color: #16A34A; }
    </style>
    """, unsafe_allow_html=True)

# ============================================================================
# HEADER
# ============================================================================

def render_header():
    current_time = get_pakistan_time()
    col_logo, col_title, col_time = st.columns([1, 4, 2])
    with col_logo:
        logo_path = get_logo_path()
        if logo_path:
            try:
                st.image(logo_path, width=80)
            except:
                st.markdown('<span style="font-size:3rem;">🛡️✈️</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span style="font-size:3rem;">🛡️✈️</span>', unsafe_allow_html=True)
    with col_title:
        st.markdown(f'<div style="padding-top:0.5rem;"><h2 style="color:#1E40AF;margin:0;font-weight:700;">{Config.APP_NAME}</h2><p style="color:#64748B;margin:0;font-size:0.9rem;">{Config.APP_SUBTITLE} v{Config.APP_VERSION} | {Config.COMPANY_ICAO} | AOC: {Config.AOC_NUMBER}</p></div>', unsafe_allow_html=True)
    with col_time:
        st.markdown(f'<div style="text-align:right;padding-top:0.5rem;"><div style="color:#64748B;font-size:0.8rem;">🇵🇰 Pakistan Standard Time</div><div style="color:#1E40AF;font-size:1.3rem;font-weight:700;">{current_time.strftime("%H:%M:%S")}</div><div style="color:#64748B;font-size:0.8rem;">{current_time.strftime("%A, %d %B %Y")}</div></div>', unsafe_allow_html=True)
    st.markdown('<div style="background:linear-gradient(135deg,#1E40AF 0%,#3B82F6 100%);height:4px;border-radius:4px;margin:0.5rem 0 1rem 0;"></div>', unsafe_allow_html=True)

# ============================================================================
# RISK MATRIX COMPONENTS
# ============================================================================

def render_risk_badge(risk_level: str) -> str:
    colors = {
        "Extreme": ("#DC2626", "#FEE2E2"),
        "High":    ("#EA580C", "#FFEDD5"),
        "Medium":  ("#CA8A04", "#FEF9C3"),
        "Low":     ("#16A34A", "#DCFCE7"),
    }
    tc, bg = colors.get(risk_level, ("#64748B", "#F1F5F9"))
    return f'<span style="background:{bg};color:{tc};padding:4px 12px;border-radius:20px;font-weight:600;font-size:0.85rem;">{risk_level}</span>'

def render_visual_risk_matrix():
    st.markdown("""
    <div style="overflow-x:auto;">
    <table style="border-collapse:collapse;width:100%;min-width:500px;font-size:0.8rem;">
    <tr>
        <th style="border:1px solid #CBD5E1;padding:8px;background:#F1F5F9;"></th>
        <th style="border:1px solid #CBD5E1;padding:8px;background:#F1F5F9;text-align:center;">A<br><small>Catastrophic</small></th>
        <th style="border:1px solid #CBD5E1;padding:8px;background:#F1F5F9;text-align:center;">B<br><small>Hazardous</small></th>
        <th style="border:1px solid #CBD5E1;padding:8px;background:#F1F5F9;text-align:center;">C<br><small>Major</small></th>
        <th style="border:1px solid #CBD5E1;padding:8px;background:#F1F5F9;text-align:center;">D<br><small>Minor</small></th>
        <th style="border:1px solid #CBD5E1;padding:8px;background:#F1F5F9;text-align:center;">E<br><small>Negligible</small></th>
    </tr>
    <tr><td style="border:1px solid #CBD5E1;padding:8px;background:#F1F5F9;font-weight:bold;">5 - Frequent</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#FEE2E2;text-align:center;color:#DC2626;font-weight:bold;">5A</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#FEE2E2;text-align:center;color:#DC2626;font-weight:bold;">5B</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#FFEDD5;text-align:center;color:#EA580C;font-weight:bold;">5C</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#FEF9C3;text-align:center;color:#CA8A04;font-weight:bold;">5D</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#DCFCE7;text-align:center;color:#16A34A;font-weight:bold;">5E</td></tr>
    <tr><td style="border:1px solid #CBD5E1;padding:8px;background:#F1F5F9;font-weight:bold;">4 - Occasional</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#FEE2E2;text-align:center;color:#DC2626;font-weight:bold;">4A</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#FFEDD5;text-align:center;color:#EA580C;font-weight:bold;">4B</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#FFEDD5;text-align:center;color:#EA580C;font-weight:bold;">4C</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#FEF9C3;text-align:center;color:#CA8A04;font-weight:bold;">4D</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#DCFCE7;text-align:center;color:#16A34A;font-weight:bold;">4E</td></tr>
    <tr><td style="border:1px solid #CBD5E1;padding:8px;background:#F1F5F9;font-weight:bold;">3 - Remote</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#FFEDD5;text-align:center;color:#EA580C;font-weight:bold;">3A</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#FFEDD5;text-align:center;color:#EA580C;font-weight:bold;">3B</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#FEF9C3;text-align:center;color:#CA8A04;font-weight:bold;">3C</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#FEF9C3;text-align:center;color:#CA8A04;font-weight:bold;">3D</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#DCFCE7;text-align:center;color:#16A34A;font-weight:bold;">3E</td></tr>
    <tr><td style="border:1px solid #CBD5E1;padding:8px;background:#F1F5F9;font-weight:bold;">2 - Improbable</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#FFEDD5;text-align:center;color:#EA580C;font-weight:bold;">2A</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#FEF9C3;text-align:center;color:#CA8A04;font-weight:bold;">2B</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#FEF9C3;text-align:center;color:#CA8A04;font-weight:bold;">2C</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#DCFCE7;text-align:center;color:#16A34A;font-weight:bold;">2D</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#DCFCE7;text-align:center;color:#16A34A;font-weight:bold;">2E</td></tr>
    <tr><td style="border:1px solid #CBD5E1;padding:8px;background:#F1F5F9;font-weight:bold;">1 - Extremely Improbable</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#FEF9C3;text-align:center;color:#CA8A04;font-weight:bold;">1A</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#DCFCE7;text-align:center;color:#16A34A;font-weight:bold;">1B</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#DCFCE7;text-align:center;color:#16A34A;font-weight:bold;">1C</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#DCFCE7;text-align:center;color:#16A34A;font-weight:bold;">1D</td>
        <td style="border:1px solid #CBD5E1;padding:8px;background:#DCFCE7;text-align:center;color:#16A34A;font-weight:bold;">1E</td></tr>
    </table></div>
    """, unsafe_allow_html=True)

# ============================================================================
# STATIC WEATHER WIDGET
# ============================================================================

STATIC_WEATHER_DATA = {
    "OPSK": {"city": "Sialkot",    "temp": 18, "icon": "🌤️", "wind": 12},
    "OPKC": {"city": "Karachi",    "temp": 28, "icon": "☀️",  "wind": 15},
    "OPLA": {"city": "Lahore",     "temp": 20, "icon": "🌫️", "wind": 8},
    "OPIS": {"city": "Islamabad",  "temp": 15, "icon": "☁️",  "wind": 10},
    "OMDB": {"city": "Dubai",      "temp": 32, "icon": "☀️",  "wind": 18},
}

def render_weather_widget():
    st.markdown("#### 🌤️ Current Weather at Key Airports")
    cols = st.columns(5)
    for col, (icao, data) in zip(cols, STATIC_WEATHER_DATA.items()):
        with col:
            st.markdown(f"""<div style="background:white;border-radius:12px;padding:1rem;text-align:center;
                border:1px solid #E2E8F0;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
                <div style="font-size:2rem;">{data['icon']}</div>
                <div style="font-size:1.5rem;font-weight:700;color:#1E40AF;">{data['temp']}°C</div>
                <div style="color:#64748B;font-size:0.85rem;">{data['city']}</div>
                <div style="font-size:0.75rem;color:#94A3B8;">💨 {data['wind']} km/h</div>
            </div>""", unsafe_allow_html=True)

# ============================================================================
# BIRD STRIKE FORM
# ============================================================================

def render_bird_strike_form():
    st.markdown("## 🐦 Bird Strike Report Form")
    st.markdown("*Complete all applicable sections for bird/wildlife strike incidents*")

    ocr_data = st.session_state.get('ocr_data_bird_strike', {}) or {}

    with st.expander("📷 Upload Form Image for OCR Autofill", expanded=False):
        extracted = render_ocr_uploader("bird_strike")
        if extracted:
            ocr_data = extracted
            st.session_state['ocr_data_bird_strike'] = extracted

    if ocr_data:
        st.info("✨ Form pre-filled with OCR extracted data. Please verify and correct any fields.")

    with st.form("bird_strike_form"):
        # Section A
        st.markdown("### Section A: Incident Identification")
        col1, col2, col3 = st.columns(3)
        with col1:
            incident_id = st.text_input("Incident Reference Number",
                value=generate_report_number("BS"), disabled=True)
        with col2:
            try:
                inc_date_val = datetime.strptime(ocr_data.get('incident_date', date.today().isoformat()), '%Y-%m-%d').date()
            except:
                inc_date_val = date.today()
            incident_date = st.date_input("Date of Incident *", value=inc_date_val)
        with col3:
            try:
                inc_time_val = datetime.strptime(ocr_data.get('incident_time', '12:00'), '%H:%M').time()
            except:
                inc_time_val = datetime.now().time()
            incident_time = st.time_input("Time of Incident (UTC) *", value=inc_time_val)

        col1, col2 = st.columns(2)
        with col1:
            time_of_day = st.selectbox("Time of Day *", ["Dawn", "Day", "Dusk", "Night"], index=1)
        with col2:
            reported_by = st.text_input("Reported By *",
                value=ocr_data.get('reported_by', st.session_state.get('username', '')))

        # Section B
        st.markdown("### Section B: Flight Information")
        col1, col2, col3 = st.columns(3)
        with col1:
            flight_number = st.text_input("Flight Number *",
                value=ocr_data.get('flight_number', ''), placeholder="e.g., PF-101")
        with col2:
            reg_list = [""] + aircraft_reg_options()
            default_reg_idx = 0
            if ocr_data.get('aircraft_reg') in reg_list:
                default_reg_idx = reg_list.index(ocr_data['aircraft_reg'])
            aircraft_reg = st.selectbox("Aircraft Registration *", options=reg_list, index=default_reg_idx)
        with col3:
            aircraft_type = st.text_input("Aircraft Type", value=get_aircraft_type(aircraft_reg), disabled=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            ap_opts = [""] + airport_options()
            origin_airport = st.selectbox("Origin Airport *", options=ap_opts, index=0, key="bs_origin")
        with col2:
            destination_airport = st.selectbox("Destination Airport *", options=ap_opts, index=0, key="bs_dest")
        with col3:
            fp_idx = FLIGHT_PHASES.index(ocr_data['flight_phase']) if ocr_data.get('flight_phase') in FLIGHT_PHASES else 6
            flight_phase = st.selectbox("Phase of Flight *", options=FLIGHT_PHASES, index=fp_idx)

        # Section C
        st.markdown("### Section C: Strike Location & Conditions")
        col1, col2, col3 = st.columns(3)
        with col1:
            strike_airport = st.selectbox("Airport of Strike", options=ap_opts, index=0, key="bs_strike_apt")
        with col2:
            altitude_agl = st.number_input("Altitude AGL (feet) *",
                min_value=0, max_value=50000, value=int(ocr_data.get('altitude_agl', 0)), step=100)
        with col3:
            altitude_msl = st.number_input("Altitude MSL (feet)",
                min_value=0, max_value=50000, value=int(ocr_data.get('altitude_agl', 0)), step=100)

        col1, col2, col3 = st.columns(3)
        with col1:
            indicated_speed = st.number_input("IAS (knots) *", min_value=0, max_value=500,
                value=int(ocr_data.get('indicated_speed', 0)), step=5)
        with col2:
            runway_used = st.text_input("Runway Used", value=ocr_data.get('runway_used', ''),
                placeholder="e.g., 36L")
        with col3:
            weather_conditions = st.selectbox("Weather Conditions", options=WEATHER_CONDITIONS, index=0)

        # Section D
        st.markdown("### Section D: Bird/Wildlife Details")
        col1, col2, col3 = st.columns(3)
        with col1:
            sp_list = BIRD_SPECIES
            sp_idx = sp_list.index(ocr_data['bird_species']) if ocr_data.get('bird_species') in sp_list else 0
            bird_species = st.selectbox("Bird Species", options=sp_list, index=sp_idx)
        with col2:
            sz_idx = BIRD_SIZES.index(ocr_data['bird_size']) if ocr_data.get('bird_size') in BIRD_SIZES else 2
            bird_size = st.selectbox("Bird Size *", options=BIRD_SIZES, index=sz_idx)
        with col3:
            number_struck = st.number_input("Number Struck", min_value=1, max_value=100,
                value=int(ocr_data.get('number_struck', 1)), step=1)

        number_seen = st.number_input("Number Seen", min_value=1, max_value=1000,
            value=max(int(ocr_data.get('number_seen', 1)), int(ocr_data.get('number_struck', 1))), step=1)

        # Section E
        st.markdown("### Section E: Aircraft Parts Struck")
        default_parts = ocr_data.get('parts_struck', [])
        if not isinstance(default_parts, list):
            default_parts = []
        parts_struck = st.multiselect("Parts Struck *", options=AIRCRAFT_PARTS_STRUCK, default=default_parts)

        col1, col2 = st.columns(2)
        with col1:
            engine_ingested = st.selectbox("Engine Ingestion?",
                ["No", "Yes - Engine 1", "Yes - Engine 2", "Yes - Both Engines", "Suspected"])
        with col2:
            windshield_penetrated = st.selectbox("Windshield Penetrated?",
                ["No", "Yes - Cracked only", "Yes - Penetrated", "Yes - Shattered"])

        # Section F
        st.markdown("### Section F: Damage Assessment")
        col1, col2 = st.columns(2)
        with col1:
            dm_idx = DAMAGE_LEVELS.index(ocr_data['damage_level']) if ocr_data.get('damage_level') in DAMAGE_LEVELS else 0
            damage_level = st.selectbox("Damage Level *", options=DAMAGE_LEVELS, index=dm_idx)
        with col2:
            aircraft_oos = st.selectbox("Aircraft Out of Service?",
                ["No", "Yes - Minor (<24h)", "Yes - Significant (1-7 days)", "Yes - Major (>7 days)"])

        damage_description = st.text_area("Damage Description", value=ocr_data.get('damage_description', ''),
            placeholder="Describe all visible damage...", height=80)

        # Section G
        st.markdown("### Section G: Effect on Flight")
        col1, col2 = st.columns(2)
        with col1:
            ef_idx = EFFECT_ON_FLIGHT_OPTIONS.index(ocr_data['effect_on_flight']) \
                if ocr_data.get('effect_on_flight') in EFFECT_ON_FLIGHT_OPTIONS else 0
            effect_on_flight = st.selectbox("Effect on Flight *", options=EFFECT_ON_FLIGHT_OPTIONS, index=ef_idx)
        with col2:
            emergency_declared = st.selectbox("Emergency Declared?", ["No", "PAN PAN", "MAYDAY"])

        # Section H
        st.markdown("### Section H: Crew Information")
        col1, col2 = st.columns(2)
        with col1:
            captain_name = st.text_input("Captain Name *", value=ocr_data.get('captain_name', ''))
        with col2:
            fo_name = st.text_input("First Officer Name", value=ocr_data.get('fo_name', ''))

        # Section I
        st.markdown("### Section I: Notifications")
        notifications_made = st.multiselect("Notifications Made",
            options=["ATC Tower", "Airport Wildlife Control", "Company Operations Control",
                     "Safety Department", "Maintenance Control", "PCAA", "Station Manager"],
            default=["Safety Department", "Company Operations Control"])

        atc_informed = st.selectbox("ATC Informed?", ["Yes - Immediately", "Yes - After landing", "No"])

        # Section J
        st.markdown("### Section J: Narrative")
        narrative = st.text_area("Detailed Narrative *", value=ocr_data.get('narrative', ''),
            placeholder="Provide a detailed description of the bird strike...", height=150)

        recommendations = st.text_area("Safety Recommendations",
            placeholder="Suggest preventive measures...", height=80)

        # Section K
        st.markdown("### Section K: Safety Department Use")
        col1, col2, col3 = st.columns(3)
        with col1:
            investigation_status = st.selectbox("Investigation Status",
                ["Open - Pending Review", "Open - Under Investigation",
                 "Closed - No Further Action", "Closed - Corrective Actions Implemented"])
        with col2:
            assigned_investigator = st.selectbox("Assigned To",
                ["Unassigned", "Safety Manager", "Safety Officer", "Quality Manager"])
        with col3:
            priority_level = st.selectbox("Priority", ["Low", "Medium", "High", "Critical"], index=1)

        uploaded_photos = st.file_uploader("Upload Photos/Documents",
            type=['png', 'jpg', 'jpeg', 'pdf', 'docx'],
            accept_multiple_files=True, key="bs_attachments")

        st.markdown("---")
        submitted = st.form_submit_button("📤 Submit Bird Strike Report",
            use_container_width=True, type="primary")

        if submitted:
            errors = []
            if not flight_number:
                errors.append("Flight Number is required")
            if not aircraft_reg:
                errors.append("Aircraft Registration is required")
            if not captain_name:
                errors.append("Captain Name is required")
            if not narrative:
                errors.append("Detailed Narrative is required")
            if not parts_struck:
                errors.append("At least one part struck must be selected")

            if errors:
                for e in errors:
                    st.error(f"❌ {e}")
            else:
                if damage_level in ["Severe", "Destroyed"]:
                    risk_level = "Extreme"
                elif damage_level in ["Major", "Moderate"]:
                    risk_level = "High"
                elif damage_level == "Minor":
                    risk_level = "Medium"
                else:
                    risk_level = "Low"

                report_data = {
                    'id': incident_id,
                    'type': 'Bird Strike',
                    'date': incident_date.isoformat(),
                    'time': incident_time.strftime('%H:%M'),
                    'time_of_day': time_of_day,
                    'reported_by': reported_by,
                    'flight_number': flight_number,
                    'aircraft_reg': aircraft_reg,
                    'aircraft_type': aircraft_type,
                    'origin': origin_airport.split(' - ')[0] if origin_airport else '',
                    'destination': destination_airport.split(' - ')[0] if destination_airport else '',
                    'flight_phase': flight_phase,
                    'altitude_agl': altitude_agl,
                    'altitude_msl': altitude_msl,
                    'indicated_speed': indicated_speed,
                    'runway': runway_used,
                    'weather': weather_conditions,
                    'bird_species': bird_species,
                    'bird_size': bird_size,
                    'number_struck': number_struck,
                    'number_seen': number_seen,
                    'parts_struck': parts_struck,
                    'engine_ingested': engine_ingested,
                    'windshield_penetrated': windshield_penetrated,
                    'damage_level': damage_level,
                    'aircraft_oos': aircraft_oos,
                    'damage_description': damage_description,
                    'effect_on_flight': effect_on_flight,
                    'emergency_declared': emergency_declared,
                    'captain_name': captain_name,
                    'first_officer': fo_name,
                    'notifications': notifications_made,
                    'atc_informed': atc_informed,
                    'narrative': narrative,
                    'recommendations': recommendations,
                    'status': investigation_status,
                    'assigned_to': assigned_investigator,
                    'priority': priority_level,
                    'risk_level': risk_level,
                    'attachments': len(uploaded_photos) if uploaded_photos else 0,
                    'created_at': datetime.now().isoformat(),
                    'department': 'Flight Operations',
                    'description': narrative
                }

                if 'bird_strikes' not in st.session_state:
                    st.session_state.bird_strikes = []
                st.session_state.bird_strikes.append(report_data)
                st.session_state['ocr_data_bird_strike'] = None

                st.balloons()
                st.success(f"""✅ **Bird Strike Report Submitted!**
                
**Reference:** {incident_id}  
**Risk Level:** {risk_level}  
**Status:** {investigation_status}""")

# ============================================================================
# LASER STRIKE FORM
# ============================================================================

def render_laser_strike_form():
    st.markdown("## 🔦 Laser Strike / Illumination Report Form")

    ocr_data = st.session_state.get('ocr_data_laser_strike', {}) or {}

    with st.expander("📷 Upload Form Image for OCR Autofill", expanded=False):
        extracted = render_ocr_uploader("laser_strike")
        if extracted:
            ocr_data = extracted
            st.session_state['ocr_data_laser_strike'] = extracted

    with st.form("laser_strike_form"):
        st.markdown("### Section A: Incident Identification")
        col1, col2, col3 = st.columns(3)
        with col1:
            incident_id = st.text_input("Reference Number", value=generate_report_number("LS"), disabled=True)
        with col2:
            try:
                inc_date_val = datetime.strptime(ocr_data.get('incident_date', date.today().isoformat()), '%Y-%m-%d').date()
            except:
                inc_date_val = date.today()
            incident_date = st.date_input("Date *", value=inc_date_val, key="ls_date")
        with col3:
            try:
                inc_time_val = datetime.strptime(ocr_data.get('incident_time', '12:00'), '%H:%M').time()
            except:
                inc_time_val = datetime.now().time()
            incident_time = st.time_input("Time (UTC) *", value=inc_time_val, key="ls_time")

        reported_by = st.text_input("Reported By *",
            value=ocr_data.get('reported_by', st.session_state.get('username', '')))

        st.markdown("### Section B: Flight Information")
        col1, col2, col3 = st.columns(3)
        with col1:
            flight_number = st.text_input("Flight Number *",
                value=ocr_data.get('flight_number', ''), placeholder="e.g., PF-101", key="ls_flt")
        with col2:
            reg_list = [""] + aircraft_reg_options()
            default_reg_idx = reg_list.index(ocr_data['aircraft_reg']) \
                if ocr_data.get('aircraft_reg') in reg_list else 0
            aircraft_reg = st.selectbox("Aircraft Registration *", options=reg_list,
                index=default_reg_idx, key="ls_reg")
        with col3:
            aircraft_type = st.text_input("Aircraft Type", value=get_aircraft_type(aircraft_reg),
                disabled=True, key="ls_type")

        ap_opts = [""] + airport_options()
        col1, col2, col3 = st.columns(3)
        with col1:
            origin_airport = st.selectbox("Origin *", options=ap_opts, index=0, key="ls_origin")
        with col2:
            destination_airport = st.selectbox("Destination *", options=ap_opts, index=0, key="ls_dest")
        with col3:
            fp_idx = FLIGHT_PHASES.index(ocr_data['flight_phase']) \
                if ocr_data.get('flight_phase') in FLIGHT_PHASES else 9
            flight_phase = st.selectbox("Phase of Flight *", options=FLIGHT_PHASES, index=fp_idx, key="ls_phase")

        st.markdown("### Section C: Location")
        col1, col2, col3 = st.columns(3)
        with col1:
            incident_airport = st.selectbox("Nearest Airport", options=ap_opts, index=0, key="ls_apt")
        with col2:
            altitude_agl = st.number_input("Altitude AGL (feet) *", min_value=0, max_value=50000,
                value=int(ocr_data.get('altitude_agl', 0)), step=100, key="ls_alt")
        with col3:
            position_desc = st.text_input("Position Description",
                placeholder="e.g., 5nm final RWY 36L")

        st.markdown("### Section D: Laser Characteristics")
        col1, col2, col3 = st.columns(3)
        with col1:
            lc_idx = LASER_COLORS.index(ocr_data['laser_color']) \
                if ocr_data.get('laser_color') in LASER_COLORS else 0
            laser_color = st.selectbox("Laser Color *", options=LASER_COLORS, index=lc_idx)
        with col2:
            duration_seconds = st.number_input("Duration (seconds) *", min_value=1, max_value=300,
                value=int(ocr_data.get('duration_seconds', 5)), step=1)
        with col3:
            intensity = st.selectbox("Perceived Intensity *", options=LASER_INTENSITIES, index=2)

        source_direction = st.selectbox("Direction of Source",
            ["Ahead", "Left", "Right", "Below", "Behind", "Multiple", "Unknown"])

        st.markdown("### Section E: Crew Effects")
        default_effects = ocr_data.get('crew_effects', [])
        if not isinstance(default_effects, list):
            default_effects = []
        crew_effects = st.multiselect("Crew Effects *", options=CREW_EFFECTS_LASER, default=default_effects)

        col1, col2 = st.columns(2)
        with col1:
            pf_affected = st.selectbox("Pilot Flying Affected?",
                ["No", "Yes - Minor", "Yes - Moderate", "Yes - Severe"])
        with col2:
            recovery_time = st.selectbox("Recovery Time",
                ["Immediate (<10s)", "Short (10-30s)", "Moderate (30s-2min)",
                 "Extended (2-5min)", "Prolonged (>5min)"])

        medical_attention = st.selectbox("Medical Attention Required?",
            ["No", "Yes - First aid only", "Yes - Medical examination",
             "Yes - Hospital treatment", "Pending evaluation"])

        st.markdown("### Section F: Effect on Flight")
        effect_on_flight = st.selectbox("Effect on Flight *",
            ["None - Continued normally", "Minor - Increased vigilance",
             "Moderate - Temporary loss of visual reference",
             "Significant - Autopilot engaged", "Severe - Go-around executed",
             "Severe - Flight diverted", "Critical - Emergency declared"])

        emergency_declared = st.selectbox("Emergency Declared?", ["No", "PAN PAN", "MAYDAY"],
            key="ls_emerg")

        st.markdown("### Section G: Notifications")
        notifications_made = st.multiselect("Notifications Made",
            options=["ATC Tower", "Company Operations Control", "Safety Department",
                     "PCAA", "Airport Security", "Local Police"],
            default=["ATC Tower", "Safety Department"])

        atc_notified = st.selectbox("ATC Notified?",
            ["Yes - During event", "Yes - After landing", "No"])
        police_notified = st.selectbox("Police Notified?", ["Yes", "No", "Pending"], index=1)

        st.markdown("### Section H: Narrative")
        col1, col2 = st.columns(2)
        with col1:
            captain_name = st.text_input("Captain Name *",
                value=ocr_data.get('captain_name', ''), key="ls_cap")
        with col2:
            fo_name = st.text_input("First Officer Name", key="ls_fo")

        narrative = st.text_area("Detailed Narrative *", value=ocr_data.get('narrative', ''),
            placeholder="Describe the laser illumination event...", height=150)

        st.markdown("### Section I: Status")
        col1, col2, col3 = st.columns(3)
        with col1:
            investigation_status = st.selectbox("Investigation Status",
                ["Open - Pending Review", "Open - Under Investigation",
                 "Referred to Authorities", "Closed - No Further Action"], key="ls_status")
        with col2:
            assigned_investigator = st.selectbox("Assigned To",
                ["Unassigned", "Safety Manager", "Safety Officer", "Security"], key="ls_assign")
        with col3:
            priority_level = st.selectbox("Priority", ["Low", "Medium", "High", "Critical"],
                index=1, key="ls_priority")

        st.markdown("---")
        submitted = st.form_submit_button("📤 Submit Laser Strike Report",
            use_container_width=True, type="primary")

        if submitted:
            errors = []
            if not flight_number:
                errors.append("Flight Number is required")
            if not aircraft_reg:
                errors.append("Aircraft Registration is required")
            if not captain_name:
                errors.append("Captain Name is required")
            if not narrative:
                errors.append("Detailed Narrative is required")

            if errors:
                for e in errors:
                    st.error(f"❌ {e}")
            else:
                if "5 - Very High" in intensity or medical_attention not in ["No", "Yes - First aid only"]:
                    risk_level = "Extreme"
                elif "4 - High" in intensity or emergency_declared != "No":
                    risk_level = "High"
                elif "3 - Significant" in intensity:
                    risk_level = "Medium"
                else:
                    risk_level = "Low"

                report_data = {
                    'id': incident_id,
                    'type': 'Laser Strike',
                    'date': incident_date.isoformat(),
                    'time': incident_time.strftime('%H:%M'),
                    'reported_by': reported_by,
                    'flight_number': flight_number,
                    'aircraft_reg': aircraft_reg,
                    'aircraft_type': aircraft_type,
                    'origin': origin_airport.split(' - ')[0] if origin_airport else '',
                    'destination': destination_airport.split(' - ')[0] if destination_airport else '',
                    'flight_phase': flight_phase,
                    'altitude_agl': altitude_agl,
                    'position': position_desc,
                    'laser_color': laser_color,
                    'duration_seconds': duration_seconds,
                    'intensity': intensity,
                    'source_direction': source_direction,
                    'crew_effects': crew_effects,
                    'pf_affected': pf_affected,
                    'recovery_time': recovery_time,
                    'medical_attention': medical_attention,
                    'effect_on_flight': effect_on_flight,
                    'emergency_declared': emergency_declared,
                    'notifications': notifications_made,
                    'atc_notified': atc_notified,
                    'police_notified': police_notified,
                    'captain_name': captain_name,
                    'first_officer': fo_name,
                    'narrative': narrative,
                    'description': narrative,
                    'status': investigation_status,
                    'assigned_to': assigned_investigator,
                    'priority': priority_level,
                    'risk_level': risk_level,
                    'created_at': datetime.now().isoformat(),
                    'department': 'Flight Operations'
                }

                if 'laser_strikes' not in st.session_state:
                    st.session_state.laser_strikes = []
                st.session_state.laser_strikes.append(report_data)
                st.session_state['ocr_data_laser_strike'] = None

                st.balloons()
                st.success(f"✅ **Laser Strike Report Submitted!** Reference: {incident_id} | Risk: {risk_level}")

# ============================================================================
# TCAS REPORT FORM
# ============================================================================

def render_tcas_report_form():
    st.markdown("## ✈️ TCAS / Airborne Conflict Report Form")

    ocr_data = st.session_state.get('ocr_data_tcas_report', {}) or {}

    with st.expander("📷 Upload Form Image for OCR Autofill", expanded=False):
        extracted = render_ocr_uploader("tcas_report")
        if extracted:
            ocr_data = extracted
            st.session_state['ocr_data_tcas_report'] = extracted

    with st.form("tcas_report_form"):
        st.markdown("### Section A: Incident Identification")
        col1, col2, col3 = st.columns(3)
        with col1:
            incident_id = st.text_input("Reference Number", value=generate_report_number("TCAS"), disabled=True)
        with col2:
            try:
                inc_date_val = datetime.strptime(ocr_data.get('incident_date', date.today().isoformat()), '%Y-%m-%d').date()
            except:
                inc_date_val = date.today()
            incident_date = st.date_input("Date *", value=inc_date_val, key="tcas_date")
        with col3:
            try:
                inc_time_val = datetime.strptime(ocr_data.get('incident_time', '12:00'), '%H:%M').time()
            except:
                inc_time_val = datetime.now().time()
            incident_time = st.time_input("Time (UTC) *", value=inc_time_val, key="tcas_time")

        col1, col2 = st.columns(2)
        with col1:
            reported_by = st.text_input("Reported By *",
                value=ocr_data.get('reported_by', st.session_state.get('username', '')))
        with col2:
            reporter_position = st.selectbox("Position", options=CREW_POSITIONS)

        st.markdown("### Section B: Own Aircraft")
        col1, col2, col3 = st.columns(3)
        with col1:
            flight_number = st.text_input("Flight Number *",
                value=ocr_data.get('flight_number', ''), placeholder="e.g., PF-101", key="tcas_flt")
        with col2:
            reg_list = [""] + aircraft_reg_options()
            default_reg_idx = reg_list.index(ocr_data['aircraft_reg']) \
                if ocr_data.get('aircraft_reg') in reg_list else 0
            aircraft_reg = st.selectbox("Aircraft Registration *", options=reg_list,
                index=default_reg_idx, key="tcas_reg")
        with col3:
            aircraft_type = st.text_input("Aircraft Type", value=get_aircraft_type(aircraft_reg),
                disabled=True, key="tcas_type")

        ap_opts = [""] + airport_options()
        col1, col2, col3 = st.columns(3)
        with col1:
            origin_airport = st.selectbox("Origin *", options=ap_opts, index=0, key="tcas_origin")
        with col2:
            destination_airport = st.selectbox("Destination *", options=ap_opts, index=0, key="tcas_dest")
        with col3:
            fp_idx = FLIGHT_PHASES.index(ocr_data['flight_phase']) \
                if ocr_data.get('flight_phase') in FLIGHT_PHASES else 6
            flight_phase = st.selectbox("Phase of Flight *", options=FLIGHT_PHASES,
                index=fp_idx, key="tcas_phase")

        st.markdown("### Section C: Position at Time of Event")
        col1, col2, col3 = st.columns(3)
        with col1:
            altitude_fl = st.number_input("Altitude / FL (feet) *", min_value=0, max_value=50000,
                value=int(ocr_data.get('altitude_fl', 0)), step=500)
        with col2:
            indicated_speed = st.number_input("IAS (knots)", min_value=0, max_value=600,
                value=int(ocr_data.get('indicated_speed', 0)), step=10)
        with col3:
            heading = st.number_input("Heading (°)", min_value=0, max_value=360, value=0, step=5)

        position_description = st.text_input("Position / Fix",
            placeholder="e.g., 25nm SE of OPLA VOR on airway G-500")

        st.markdown("### Section D: TCAS Alert")
        col1, col2 = st.columns(2)
        with col1:
            tcas_alert_type = st.selectbox("Alert Type *", options=TCAS_ALERT_TYPES)
        with col2:
            ra_sense = st.selectbox("RA Sense",
                ["N/A - TA only", "Climb", "Descend", "Level Off", "Adjust Vertical Speed"])

        col1, col2, col3 = st.columns(3)
        with col1:
            ra_complied = st.selectbox("RA Complied With?",
                ["Yes - Fully", "Yes - Partially", "No", "N/A - TA only"])
        with col2:
            time_to_cpa = st.number_input("Time to CPA (s)", min_value=0, max_value=120, value=30)
        with col3:
            ra_duration = st.number_input("RA Duration (s)", min_value=0, max_value=120, value=15)

        st.markdown("### Section E: Traffic Information")
        col1, col2 = st.columns(2)
        with col1:
            traffic_callsign = st.text_input("Traffic Callsign (if known)")
        with col2:
            traffic_altitude = st.text_input("Traffic Altitude", placeholder="e.g., FL350")

        st.markdown("### Section F: Minimum Separation")
        col1, col2 = st.columns(2)
        with col1:
            vertical_separation = st.number_input("Vertical Separation (feet) *",
                min_value=0, max_value=10000, value=500, step=100)
        with col2:
            horizontal_separation = st.number_input("Horizontal Separation (nm)",
                min_value=0.0, max_value=20.0, value=1.0, step=0.1)

        st.markdown("### Section G: ATC Coordination")
        col1, col2 = st.columns(2)
        with col1:
            atc_unit = st.text_input("ATC Unit", placeholder="e.g., Lahore Approach")
        with col2:
            atc_informed = st.selectbox("ATC Informed of RA?",
                ["Yes - During event", "Yes - After event", "No", "N/A - TA only"])

        atc_instructions = st.text_area("ATC Instructions Received",
            placeholder="Detail any traffic advisories or instructions...", height=60)

        st.markdown("### Section H: Crew Actions")
        crew_actions = st.multiselect("Actions Taken",
            options=["Followed RA guidance", "Visual acquisition attempted",
                     "Reported to ATC", "Autopilot disconnected", "No action required (TA only)"],
            default=["Followed RA guidance", "Reported to ATC"])

        col1, col2 = st.columns(2)
        with col1:
            captain_name = st.text_input("Captain Name *",
                value=ocr_data.get('captain_name', ''), key="tcas_cap")
        with col2:
            fo_name = st.text_input("First Officer Name", key="tcas_fo")

        st.markdown("### Section I: Narrative")
        narrative = st.text_area("Detailed Narrative *", value=ocr_data.get('narrative', ''),
            placeholder="Describe the TCAS event in detail...", height=150)

        st.markdown("### Section J: Status")
        col1, col2, col3 = st.columns(3)
        with col1:
            investigation_status = st.selectbox("Status",
                ["Open - Pending Review", "Open - Under Investigation",
                 "Referred to PCAA", "Closed - No Further Action"], key="tcas_status")
        with col2:
            assigned_investigator = st.selectbox("Assigned To",
                ["Unassigned", "Safety Manager", "Safety Officer", "Flight Ops Manager"],
                key="tcas_assign")
        with col3:
            fdr_requested = st.selectbox("FDR Data Requested?", ["Yes", "No", "Pending"], index=1)

        st.markdown("---")
        submitted = st.form_submit_button("📤 Submit TCAS Report",
            use_container_width=True, type="primary")

        if submitted:
            errors = []
            if not flight_number:
                errors.append("Flight Number is required")
            if not aircraft_reg:
                errors.append("Aircraft Registration is required")
            if not captain_name:
                errors.append("Captain Name is required")
            if not narrative:
                errors.append("Detailed Narrative is required")

            if errors:
                for e in errors:
                    st.error(f"❌ {e}")
            else:
                if "RA" in tcas_alert_type and vertical_separation < 300:
                    risk_level = "Extreme"
                elif "RA" in tcas_alert_type and vertical_separation < 500:
                    risk_level = "High"
                elif "RA" in tcas_alert_type:
                    risk_level = "Medium"
                else:
                    risk_level = "Low"

                report_data = {
                    'id': incident_id,
                    'type': 'TCAS Report',
                    'date': incident_date.isoformat(),
                    'time': incident_time.strftime('%H:%M'),
                    'reported_by': reported_by,
                    'reporter_position': reporter_position,
                    'flight_number': flight_number,
                    'aircraft_reg': aircraft_reg,
                    'aircraft_type': aircraft_type,
                    'origin': origin_airport.split(' - ')[0] if origin_airport else '',
                    'destination': destination_airport.split(' - ')[0] if destination_airport else '',
                    'flight_phase': flight_phase,
                    'altitude_fl': altitude_fl,
                    'indicated_speed': indicated_speed,
                    'heading': heading,
                    'position': position_description,
                    'tcas_alert_type': tcas_alert_type,
                    'ra_sense': ra_sense,
                    'ra_complied': ra_complied,
                    'time_to_cpa': time_to_cpa,
                    'ra_duration': ra_duration,
                    'traffic_callsign': traffic_callsign,
                    'traffic_altitude': traffic_altitude,
                    'vertical_separation': vertical_separation,
                    'horizontal_separation': horizontal_separation,
                    'atc_unit': atc_unit,
                    'atc_informed': atc_informed,
                    'atc_instructions': atc_instructions,
                    'crew_actions': crew_actions,
                    'captain_name': captain_name,
                    'first_officer': fo_name,
                    'narrative': narrative,
                    'description': narrative,
                    'status': investigation_status,
                    'assigned_to': assigned_investigator,
                    'fdr_requested': fdr_requested,
                    'risk_level': risk_level,
                    'created_at': datetime.now().isoformat(),
                    'department': 'Flight Operations'
                }

                if 'tcas_reports' not in st.session_state:
                    st.session_state.tcas_reports = []
                st.session_state.tcas_reports.append(report_data)
                st.session_state['ocr_data_tcas_report'] = None

                st.balloons()
                st.success(f"✅ **TCAS Report Submitted!** Reference: {incident_id} | Risk: {risk_level}")

# ============================================================================
# AIRCRAFT INCIDENT FORM
# ============================================================================

def render_incident_form():
    st.markdown("## ⚠️ Aircraft Incident / Occurrence Report Form")

    ocr_data = st.session_state.get('ocr_data_incident_report', {}) or {}

    with st.expander("📷 Upload Form Image for OCR Autofill", expanded=False):
        extracted = render_ocr_uploader("incident_report")
        if extracted:
            ocr_data = extracted
            st.session_state['ocr_data_incident_report'] = extracted

    with st.form("incident_form"):
        st.markdown("### Section A: Notification Type")
        col1, col2 = st.columns(2)
        with col1:
            incident_id = st.text_input("Reference Number", value=generate_report_number("INC"), disabled=True)
        with col2:
            notification_type = st.selectbox("Notification Type *",
                ["Accident", "Serious Incident", "Incident",
                 "Occurrence - No Safety Impact", "Ground Event", "Security Related"], index=2)

        col1, col2, col3 = st.columns(3)
        with col1:
            try:
                inc_date_val = datetime.strptime(ocr_data.get('incident_date', date.today().isoformat()), '%Y-%m-%d').date()
            except:
                inc_date_val = date.today()
            incident_date = st.date_input("Date *", value=inc_date_val, key="inc_date")
        with col2:
            try:
                inc_time_val = datetime.strptime(ocr_data.get('incident_time', '12:00'), '%H:%M').time()
            except:
                inc_time_val = datetime.now().time()
            incident_time = st.time_input("Time (UTC) *", value=inc_time_val, key="inc_time")
        with col3:
            reported_by = st.text_input("Reported By *",
                value=ocr_data.get('reported_by', st.session_state.get('username', '')))

        st.markdown("### Section B: Aircraft Information")
        col1, col2, col3 = st.columns(3)
        with col1:
            reg_list = [""] + aircraft_reg_options()
            default_reg_idx = reg_list.index(ocr_data['aircraft_reg']) \
                if ocr_data.get('aircraft_reg') in reg_list else 0
            aircraft_reg = st.selectbox("Aircraft Registration *", options=reg_list,
                index=default_reg_idx, key="inc_reg")
        with col2:
            aircraft_type = st.text_input("Aircraft Type", value=get_aircraft_type(aircraft_reg),
                disabled=True, key="inc_type")
        with col3:
            msn = st.text_input("MSN", value=get_aircraft_msn(aircraft_reg), disabled=True)

        col1, col2 = st.columns(2)
        with col1:
            dm_idx = DAMAGE_LEVELS.index(ocr_data['aircraft_damage']) \
                if ocr_data.get('aircraft_damage') in DAMAGE_LEVELS else 0
            aircraft_damage = st.selectbox("Aircraft Damage *", options=DAMAGE_LEVELS, index=dm_idx)
        with col2:
            fire_occurred = st.selectbox("Fire Occurred?",
                ["No", "Yes - In flight", "Yes - On ground", "Yes - After impact"])

        st.markdown("### Section C: Flight Information")
        col1, col2, col3 = st.columns(3)
        with col1:
            flight_number = st.text_input("Flight Number *",
                value=ocr_data.get('flight_number', ''), placeholder="e.g., PF-101", key="inc_flt")
        with col2:
            flight_type = st.selectbox("Flight Type",
                ["Scheduled Passenger", "Non-Scheduled", "Cargo",
                 "Ferry/Positioning", "Training", "Test Flight"])
        with col3:
            flight_rules = st.selectbox("Flight Rules", ["IFR", "VFR", "SVFR"])

        ap_opts = [""] + airport_options()
        col1, col2, col3 = st.columns(3)
        with col1:
            origin_airport = st.selectbox("Origin *", options=ap_opts, index=0, key="inc_origin")
        with col2:
            destination_airport = st.selectbox("Destination *", options=ap_opts, index=0, key="inc_dest")
        with col3:
            fp_idx = FLIGHT_PHASES.index(ocr_data['flight_phase']) \
                if ocr_data.get('flight_phase') in FLIGHT_PHASES else 6
            flight_phase = st.selectbox("Phase of Flight *", options=FLIGHT_PHASES,
                index=fp_idx, key="inc_phase")

        st.markdown("### Section D: Location")
        col1, col2 = st.columns(2)
        with col1:
            incident_location = st.selectbox("Location", options=ap_opts, index=0)
        with col2:
            altitude = st.number_input("Altitude (feet)", min_value=0, max_value=50000, value=0, step=500)

        st.markdown("### Section E: Incident Category")
        incident_category = st.selectbox("Primary Category *", options=INCIDENT_CATEGORIES)
        incident_description = st.text_area("Brief Description *",
            value=ocr_data.get('description', ''),
            placeholder="Describe what happened...", height=100)

        st.markdown("### Section F: Weather")
        col1, col2 = st.columns(2)
        with col1:
            weather_conditions = st.selectbox("Weather", options=WEATHER_CONDITIONS, index=0)
        with col2:
            visibility_nm = st.number_input("Visibility (nm)", min_value=0.0, max_value=50.0,
                value=10.0, step=0.5)

        st.markdown("### Section G: Crew Information")
        col1, col2 = st.columns(2)
        with col1:
            captain_name = st.text_input("Captain Name *",
                value=ocr_data.get('captain_name', ''), key="inc_cap")
            captain_license = st.text_input("Captain License")
        with col2:
            fo_name = st.text_input("First Officer Name", key="inc_fo")
            fo_license = st.text_input("FO License")

        st.markdown("### Section H: Passengers")
        col1, col2, col3 = st.columns(3)
        with col1:
            pax_adult = st.number_input("Adults", min_value=0, max_value=300, value=0, step=1)
        with col2:
            pax_child = st.number_input("Children", min_value=0, max_value=100, value=0, step=1)
        with col3:
            pax_infant = st.number_input("Infants", min_value=0, max_value=50, value=0, step=1)

        st.markdown("### Section I: Injuries")
        col1, col2 = st.columns(2)
        with col1:
            crew_injuries = st.selectbox("Crew Injuries",
                ["No injuries", "Minor", "Serious", "Fatal"])
        with col2:
            pax_injuries = st.selectbox("Passenger Injuries",
                ["No injuries", "Minor", "Serious", "Fatal"])

        st.markdown("### Section J: Emergency Response")
        col1, col2 = st.columns(2)
        with col1:
            emergency_declared = st.selectbox("Emergency Declared?",
                ["No", "PAN PAN", "MAYDAY"], key="inc_emerg")
        with col2:
            evacuation = st.selectbox("Evacuation?",
                ["No", "Yes - Precautionary", "Yes - Emergency"])

        st.markdown("### Section K: Notifications")
        notifications_required = st.multiselect("Notifications Made",
            options=["PCAA", "AAIB", "Operator Safety", "Airport Authority",
                     "Insurance", "Aircraft Manufacturer"],
            default=["PCAA", "Operator Safety"])

        pcaa_notified = st.selectbox("PCAA Notified?",
            ["Yes - Within 24 hours", "Yes - Within 72 hours", "Pending", "Not required"])

        st.markdown("### Section L: Narrative")
        narrative = st.text_area("Detailed Narrative *", value=ocr_data.get('narrative', ''),
            placeholder="Provide a comprehensive description...", height=200)

        immediate_actions = st.text_area("Immediate Actions Taken",
            placeholder="Actions taken following the incident...", height=80)

        col1, col2, col3 = st.columns(3)
        with col1:
            investigation_status = st.selectbox("Status",
                ["Open - Initial Report", "Open - Under Investigation",
                 "Closed - Recommendations Issued", "Referred to Authority"], key="inc_status")
        with col2:
            assigned_investigator = st.selectbox("Assigned To",
                ["Unassigned", "Safety Manager", "Safety Officer",
                 "External Investigator", "PCAA Team"], key="inc_assign")
        with col3:
            fdr_preserved = st.selectbox("FDR Data", ["Preserved", "Requested", "N/A", "Pending"])

        uploaded_files = st.file_uploader("Upload Photos/Documents",
            type=['png', 'jpg', 'jpeg', 'pdf', 'docx'],
            accept_multiple_files=True, key="inc_files")

        st.markdown("---")
        submitted = st.form_submit_button("📤 Submit Incident Report",
            use_container_width=True, type="primary")

        if submitted:
            errors = []
            if not flight_number:
                errors.append("Flight Number is required")
            if not aircraft_reg:
                errors.append("Aircraft Registration is required")
            if not captain_name:
                errors.append("Captain Name is required")
            if not narrative:
                errors.append("Detailed Narrative is required")
            if not incident_description:
                errors.append("Brief Description is required")

            if errors:
                for e in errors:
                    st.error(f"❌ {e}")
            else:
                if notification_type == "Accident" or "Fatal" in (crew_injuries + pax_injuries):
                    risk_level = "Extreme"
                elif notification_type == "Serious Incident" or aircraft_damage in ["Major", "Severe", "Destroyed"]:
                    risk_level = "High"
                elif notification_type == "Incident":
                    risk_level = "Medium"
                else:
                    risk_level = "Low"

                report_data = {
                    'id': incident_id,
                    'type': 'Aircraft Incident',
                    'notification_type': notification_type,
                    'date': incident_date.isoformat(),
                    'time': incident_time.strftime('%H:%M'),
                    'reported_by': reported_by,
                    'aircraft_reg': aircraft_reg,
                    'aircraft_type': aircraft_type,
                    'aircraft_damage': aircraft_damage,
                    'fire_occurred': fire_occurred,
                    'flight_number': flight_number,
                    'flight_type': flight_type,
                    'flight_rules': flight_rules,
                    'origin': origin_airport.split(' - ')[0] if origin_airport else '',
                    'destination': destination_airport.split(' - ')[0] if destination_airport else '',
                    'flight_phase': flight_phase,
                    'incident_location': incident_location,
                    'altitude': altitude,
                    'incident_category': incident_category,
                    'description': incident_description,
                    'weather': weather_conditions,
                    'visibility': visibility_nm,
                    'captain_name': captain_name,
                    'captain_license': captain_license,
                    'fo_name': fo_name,
                    'fo_license': fo_license,
                    'pax': {'adult': pax_adult, 'child': pax_child, 'infant': pax_infant},
                    'crew_injuries': crew_injuries,
                    'pax_injuries': pax_injuries,
                    'emergency_declared': emergency_declared,
                    'evacuation': evacuation,
                    'notifications': notifications_required,
                    'pcaa_notified': pcaa_notified,
                    'narrative': narrative,
                    'immediate_actions': immediate_actions,
                    'status': investigation_status,
                    'assigned_to': assigned_investigator,
                    'fdr_preserved': fdr_preserved,
                    'risk_level': risk_level,
                    'attachments': len(uploaded_files) if uploaded_files else 0,
                    'created_at': datetime.now().isoformat(),
                    'department': 'Safety Department'
                }

                if 'aircraft_incidents' not in st.session_state:
                    st.session_state.aircraft_incidents = []
                st.session_state.aircraft_incidents.append(report_data)
                st.session_state['ocr_data_incident_report'] = None

                st.balloons()
                st.success(f"""✅ **Incident Report Submitted!** Reference: {incident_id} | Risk: {risk_level}
{"⚠️ **IMPORTANT:** Notify PCAA immediately for Accident/Serious Incident." if notification_type in ['Accident', 'Serious Incident'] else ""}""")

# ============================================================================
# HAZARD REPORT FORM
# ============================================================================

def render_hazard_form():
    st.markdown("## 🔶 Hazard Report Form")
    st.markdown("*Report identified hazards, unsafe conditions, and potential risks*")

    ocr_data = st.session_state.get('ocr_data_hazard_report', {}) or {}

    with st.expander("📷 Upload Form Image for OCR Autofill", expanded=False):
        extracted = render_ocr_uploader("hazard_report")
        if extracted:
            ocr_data = extracted
            st.session_state['ocr_data_hazard_report'] = extracted

    with st.form("hazard_form"):
        st.markdown("### Section A: Reporter Information")
        col1, col2, col3 = st.columns(3)
        with col1:
            hazard_id = st.text_input("Hazard Reference Number",
                value=generate_report_number("HAZ"), disabled=True)
        with col2:
            report_date = st.date_input("Date of Report *", value=date.today())
        with col3:
            reporter_department = st.selectbox("Department", options=DEPARTMENTS)

        col1, col2 = st.columns(2)
        with col1:
            reporter_name = st.text_input("Reporter Name",
                value=st.session_state.get('username', ''),
                help="Leave blank for anonymous reporting")
        with col2:
            anonymous_report = st.checkbox("Submit as Anonymous Report")

        st.markdown("### Section B: Hazard Identification")
        col1, col2 = st.columns(2)
        with col1:
            try:
                haz_date_val = datetime.strptime(ocr_data.get('hazard_date', date.today().isoformat()), '%Y-%m-%d').date()
            except:
                haz_date_val = date.today()
            hazard_date = st.date_input("Date Observed *", value=haz_date_val)
        with col2:
            hazard_time = st.time_input("Time Observed", value=datetime.now().time())

        hc_idx = HAZARD_CATEGORIES.index(ocr_data['hazard_category']) \
            if ocr_data.get('hazard_category') in HAZARD_CATEGORIES else 0
        hazard_category = st.selectbox("Hazard Category *", options=HAZARD_CATEGORIES, index=hc_idx)

        hazard_title = st.text_input("Hazard Title *",
            value=ocr_data.get('hazard_title', ''),
            placeholder="Brief descriptive title")

        ap_opts_w_other = [""] + airport_options() + ["Aircraft", "Training Facility", "Office", "Other"]
        col1, col2 = st.columns(2)
        with col1:
            hazard_location = st.selectbox("Location *", options=ap_opts_w_other, index=0)
        with col2:
            specific_location = st.text_input("Specific Location",
                placeholder="e.g., Apron 3, Gate 5, Hangar 2")

        col1, col2, col3 = st.columns(3)
        with col1:
            flight_number = st.text_input("Flight Number (if applicable)", key="haz_flt")
        with col2:
            reg_list = ["N/A"] + aircraft_reg_options()
            aircraft_reg = st.selectbox("Aircraft Reg (if applicable)",
                options=reg_list, index=0, key="haz_reg")
        with col3:
            flight_phase = st.selectbox("Phase (if applicable)",
                options=["N/A"] + FLIGHT_PHASES, index=0, key="haz_phase")

        hazard_description = st.text_area("Detailed Hazard Description *",
            value=ocr_data.get('hazard_description', ocr_data.get('description', '')),
            placeholder="Describe the hazard in detail...", height=150)

        st.markdown("### Section C: Risk Assessment (ICAO Matrix)")
        render_visual_risk_matrix()

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Likelihood**")
            likelihood = st.select_slider("Likelihood", options=[1, 2, 3, 4, 5], value=3,
                format_func=lambda x: f"{x} - {LIKELIHOOD_SCALE[x]['name']}")
            st.caption(LIKELIHOOD_DEFINITIONS[str(likelihood)])
        with col2:
            st.markdown("**Severity**")
            severity_opts = ["E - Negligible", "D - Minor", "C - Major", "B - Hazardous", "A - Catastrophic"]
            severity_full = st.selectbox("Severity", options=severity_opts, index=2)
            severity = severity_full.split(" - ")[0]
            st.caption(SEVERITY_DEFINITIONS.get(severity, ""))

        risk_code = f"{likelihood}{severity}"
        risk_level = calculate_risk_level(likelihood, severity)
        risk_info = RISK_ACTIONS[risk_level]

        st.markdown(f"""<div style="background:{risk_info['color']}15;border:2px solid {risk_info['color']};
            border-radius:12px;padding:1.5rem;margin:1rem 0;text-align:center;">
            <div style="font-size:2rem;font-weight:700;color:{risk_info['color']};">{risk_code}</div>
            <div style="margin:0.5rem 0;">{render_risk_badge(risk_level)}</div>
            <div style="font-size:0.9rem;color:#475569;margin-top:1rem;">
                <strong>Action:</strong> {risk_info['action']}<br>
                <strong>Timeline:</strong> {risk_info['timeline']}
            </div></div>""", unsafe_allow_html=True)

        risk_justification = st.text_area("Risk Assessment Justification",
            placeholder="Explain your reasoning...", height=80)

        st.markdown("### Section D: Existing Controls")
        existing_controls = st.text_area("Existing Controls / Barriers",
            placeholder="Describe existing controls...", height=80)
        control_effectiveness = st.selectbox("Effectiveness of Existing Controls",
            ["Effective", "Partially Effective", "Ineffective", "None", "Unknown"], index=4)

        st.markdown("### Section E: Suggested Actions")
        suggested_actions = st.text_area("Suggested Corrective/Preventive Actions *",
            value=ocr_data.get('suggested_actions', ''),
            placeholder="What actions do you suggest?", height=100)
        urgency = st.selectbox("Urgency",
            ["Immediate - Within 24 hours", "Short-term - Within 1 week",
             "Medium-term - Within 1 month", "Long-term - Within 3 months",
             "Routine - Next review cycle"], index=2)

        st.markdown("### Section F: Status (Safety Dept)")
        col1, col2, col3 = st.columns(3)
        with col1:
            status = st.selectbox("Status",
                ["Open - Pending Review", "Open - Under Assessment",
                 "Open - Action Assigned", "Monitoring",
                 "Closed - Action Completed", "Closed - Risk Accepted"], index=0)
        with col2:
            assigned_to = st.selectbox("Assigned To",
                ["Unassigned", "Safety Manager", "Safety Officer",
                 "Quality Manager", "Department Head"])
        with col3:
            target_date = st.date_input("Target Completion Date",
                value=date.today() + timedelta(days=30))

        uploaded_files = st.file_uploader("Upload Photos/Documents",
            type=['png', 'jpg', 'jpeg', 'pdf', 'docx'],
            accept_multiple_files=True, key="haz_files")

        st.markdown("---")
        submitted = st.form_submit_button("📤 Submit Hazard Report",
            use_container_width=True, type="primary")

        if submitted:
            errors = []
            if not hazard_title:
                errors.append("Hazard Title is required")
            if not hazard_location:
                errors.append("Location is required")
            if not hazard_description:
                errors.append("Hazard Description is required")
            if not suggested_actions:
                errors.append("Suggested Actions are required")

            if errors:
                for e in errors:
                    st.error(f"❌ {e}")
            else:
                report_data = {
                    'id': hazard_id,
                    'type': 'Hazard Report',
                    'date': report_date.isoformat(),
                    'reporter_name': "" if anonymous_report else reporter_name,
                    'reporter_department': reporter_department,
                    'anonymous': anonymous_report,
                    'hazard_date': hazard_date.isoformat(),
                    'hazard_time': hazard_time.strftime('%H:%M'),
                    'category': hazard_category,
                    'title': hazard_title,
                    'hazard_title': hazard_title,
                    'location': hazard_location,
                    'specific_location': specific_location,
                    'description': hazard_description,
                    'hazard_description': hazard_description,
                    'likelihood': str(likelihood),
                    'severity': severity,
                    'risk_code': risk_code,
                    'risk_level': risk_level,
                    'risk_justification': risk_justification,
                    'existing_controls': existing_controls,
                    'control_effectiveness': control_effectiveness,
                    'suggested_actions': suggested_actions,
                    'urgency': urgency,
                    'status': status,
                    'assigned_to': assigned_to,
                    'target_date': target_date.isoformat(),
                    'attachments': len(uploaded_files) if uploaded_files else 0,
                    'created_at': datetime.now().isoformat(),
                    'department': reporter_department,
                    'reported_by': reporter_name
                }

                if 'hazard_reports' not in st.session_state:
                    st.session_state.hazard_reports = []
                st.session_state.hazard_reports.append(report_data)
                st.session_state['ocr_data_hazard_report'] = None

                st.balloons()
                st.success(f"""✅ **Hazard Report Submitted!**
**Reference:** {hazard_id} | **Risk:** {risk_code} - {risk_level}
{"⚠️ Management review required for High/Extreme risk." if risk_level in ['High', 'Extreme'] else ""}""")

# ============================================================================
# FSR FORM
# ============================================================================

def render_fsr_form():
    st.markdown("## 🛫 Flight Services Report (FSR)")

    with st.form("fsr_form"):
        st.markdown("### Section A: Flight Information")
        col1, col2 = st.columns(2)
        with col1:
            report_id = st.text_input("Report Reference Number",
                value=generate_report_number("FSR"), disabled=True)
        with col2:
            flight_date = st.date_input("Flight Date *", value=date.today())

        col1, col2, col3 = st.columns(3)
        with col1:
            flight_number = st.text_input("Flight Number *", placeholder="e.g., PF-101")
        with col2:
            reg_list = [""] + aircraft_reg_options()
            aircraft_reg = st.selectbox("Aircraft Registration *", options=reg_list, index=0)
        with col3:
            aircraft_type = st.text_input("Aircraft Type",
                value=get_aircraft_type(aircraft_reg), disabled=True)

        ap_opts = [""] + airport_options()
        col1, col2 = st.columns(2)
        with col1:
            origin = st.selectbox("Origin *", options=ap_opts, index=0, key="fsr_origin")
        with col2:
            destination = st.selectbox("Destination *", options=ap_opts, index=0, key="fsr_dest")

        col1, col2 = st.columns(2)
        with col1:
            std = st.time_input("STD", value=datetime.strptime("08:00", "%H:%M").time())
        with col2:
            atd = st.time_input("ATD", value=datetime.strptime("08:15", "%H:%M").time())

        st.markdown("### Section B: Crew Information")
        col1, col2 = st.columns(2)
        with col1:
            captain_name = st.text_input("Captain Name")
        with col2:
            sccm_name = st.text_input("SCCM Name *", placeholder="Senior Cabin Crew Member")

        cabin_crew_count = st.number_input("Number of Cabin Crew", min_value=1, max_value=20, value=4)

        st.markdown("### Section C: Passenger Load")
        col1, col2, col3 = st.columns(3)
        with col1:
            pax_business = st.number_input("Business Class", min_value=0, max_value=50, value=0)
        with col2:
            pax_economy = st.number_input("Economy Class", min_value=0, max_value=300, value=0)
        with col3:
            pax_infant = st.number_input("Infants", min_value=0, max_value=50, value=0)

        st.markdown("### Section D: Service Quality Ratings")
        col1, col2 = st.columns(2)
        with col1:
            boarding_rating = st.slider("Boarding Process", 1, 5, 4)
            catering_rating = st.slider("Catering Quality", 1, 5, 4)
            cabin_cleanliness = st.slider("Cabin Cleanliness", 1, 5, 4)
        with col2:
            crew_service = st.slider("Crew Service Quality", 1, 5, 4)
            overall_rating = st.slider("Overall Experience", 1, 5, 4)

        st.markdown("### Section E: Issues & Irregularities")
        issues_reported = st.multiselect("Issues Encountered",
            options=["No issues", "Catering - Short loaded", "Catering - Quality issues",
                     "Cabin - Equipment malfunction", "Cabin - Seat issues",
                     "Passenger - Unruly behavior", "Passenger - Medical emergency",
                     "Passenger - Complaint", "Baggage - Mishandling",
                     "Ground handling - Issues", "Delay - ATC", "Delay - Technical", "Other"],
            default=["No issues"])

        issue_details = st.text_area("Issue Details", height=100,
            placeholder="Describe any issues in detail...")

        st.markdown("### Section F: Delays")
        col1, col2 = st.columns(2)
        with col1:
            departure_delay = st.number_input("Departure Delay (minutes)", min_value=0, max_value=600, value=0, step=5)
        with col2:
            arrival_delay = st.number_input("Arrival Delay (minutes)", min_value=0, max_value=600, value=0, step=5)

        delay_reason = "N/A"
        if departure_delay > 0 or arrival_delay > 0:
            delay_reason = st.selectbox("Delay Reason",
                ["Aircraft - Technical", "Aircraft - Late arrival", "Weather",
                 "ATC - Slot", "Passengers - Late boarding", "Ground handling", "Other"])

        st.markdown("### Section G: Additional Remarks")
        additional_remarks = st.text_area("Additional Remarks", height=80,
            placeholder="Any other observations...")

        reported_by = st.text_input("Report Submitted By *",
            value=st.session_state.get('username', ''))

        st.markdown("---")
        submitted = st.form_submit_button("📤 Submit Flight Services Report",
            use_container_width=True, type="primary")

        if submitted:
            errors = []
            if not flight_number:
                errors.append("Flight Number is required")
            if not aircraft_reg:
                errors.append("Aircraft Registration is required")
            if not sccm_name:
                errors.append("SCCM Name is required")
            if not reported_by:
                errors.append("Reporter Name is required")

            if errors:
                for e in errors:
                    st.error(f"❌ {e}")
            else:
                if "Passenger - Unruly behavior" in issues_reported or "Passenger - Medical emergency" in issues_reported:
                    risk_level = "Medium"
                elif "No issues" not in issues_reported and issues_reported:
                    risk_level = "Low"
                else:
                    risk_level = "Low"

                report_data = {
                    'id': report_id,
                    'type': 'Flight Services Report',
                    'date': flight_date.isoformat(),
                    'flight_number': flight_number,
                    'aircraft_reg': aircraft_reg,
                    'origin': origin.split(' - ')[0] if origin else '',
                    'destination': destination.split(' - ')[0] if destination else '',
                    'std': std.strftime('%H:%M'),
                    'atd': atd.strftime('%H:%M'),
                    'captain': captain_name,
                    'sccm': sccm_name,
                    'cabin_crew_count': cabin_crew_count,
                    'pax': {'business': pax_business, 'economy': pax_economy, 'infant': pax_infant,
                            'total': pax_business + pax_economy},
                    'ratings': {'boarding': boarding_rating, 'catering': catering_rating,
                                'cleanliness': cabin_cleanliness, 'crew_service': crew_service,
                                'overall': overall_rating},
                    'issues': issues_reported,
                    'issue_details': issue_details,
                    'departure_delay': departure_delay,
                    'arrival_delay': arrival_delay,
                    'delay_reason': delay_reason,
                    'remarks': additional_remarks,
                    'reported_by': reported_by,
                    'description': issue_details or "Flight services report - no issues",
                    'risk_level': risk_level,
                    'status': 'Open - Pending Review',
                    'created_at': datetime.now().isoformat(),
                    'department': 'Cabin Services'
                }

                if 'fsr_reports' not in st.session_state:
                    st.session_state.fsr_reports = []
                st.session_state.fsr_reports.append(report_data)

                st.balloons()
                st.success(f"✅ **FSR Submitted!** Reference: {report_id} | Overall: {overall_rating}/5")

# ============================================================================
# CAPTAIN'S DEBRIEF FORM
# ============================================================================

def render_captain_dbr_form():
    st.markdown("## 👨‍✈️ Captain's Debrief Report (DBR)")

    with st.form("captain_dbr_form"):
        st.markdown("### Section A: Flight Information")
        col1, col2 = st.columns(2)
        with col1:
            report_id = st.text_input("Reference Number", value=generate_report_number("DBR"), disabled=True)
        with col2:
            flight_date = st.date_input("Flight Date *", value=date.today())

        col1, col2, col3 = st.columns(3)
        with col1:
            flight_number = st.text_input("Flight Number *", placeholder="e.g., PF-101")
        with col2:
            reg_list = [""] + aircraft_reg_options()
            aircraft_reg = st.selectbox("Aircraft Registration *", options=reg_list, index=0)
        with col3:
            aircraft_type = st.text_input("Aircraft Type",
                value=get_aircraft_type(aircraft_reg), disabled=True)

        ap_opts = [""] + airport_options()
        col1, col2 = st.columns(2)
        with col1:
            origin = st.selectbox("Origin *", options=ap_opts, index=0, key="dbr_origin")
        with col2:
            destination = st.selectbox("Destination *", options=ap_opts, index=0, key="dbr_dest")

        st.markdown("### Section B: Flight Times (UTC)")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            off_blocks = st.time_input("Off Blocks", value=datetime.strptime("08:00", "%H:%M").time())
        with col2:
            takeoff_time = st.time_input("Takeoff", value=datetime.strptime("08:15", "%H:%M").time())
        with col3:
            landing_time = st.time_input("Landing", value=datetime.strptime("09:45", "%H:%M").time())
        with col4:
            on_blocks = st.time_input("On Blocks", value=datetime.strptime("10:00", "%H:%M").time())

        col1, col2 = st.columns(2)
        with col1:
            block_time_hrs = st.number_input("Block Time (hours)", min_value=0.0, max_value=20.0,
                value=2.0, step=0.1)
        with col2:
            flight_time_hrs = st.number_input("Flight Time (hours)", min_value=0.0, max_value=20.0,
                value=1.5, step=0.1)

        st.markdown("### Section C: Fuel")
        col1, col2, col3 = st.columns(3)
        with col1:
            fuel_departure = st.number_input("Block Fuel (kg)", min_value=0, max_value=100000, value=5000, step=100)
        with col2:
            fuel_arrival = st.number_input("Remaining Fuel (kg)", min_value=0, max_value=100000, value=2500, step=100)
        with col3:
            fuel_planned = st.number_input("Planned Burn (kg)", min_value=0, max_value=50000, value=2400, step=100)

        st.markdown("### Section D: Weather")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Departure**")
            dep_weather = st.selectbox("Departure Weather", options=WEATHER_CONDITIONS, index=0)
            dep_wind = st.text_input("Departure Wind", placeholder="e.g., 360/10kt")
        with col2:
            st.markdown("**Arrival**")
            arr_weather = st.selectbox("Arrival Weather", options=WEATHER_CONDITIONS, index=0)
            arr_wind = st.text_input("Arrival Wind", placeholder="e.g., 270/15kt G25kt")

        enroute_remarks = st.text_area("En-route Remarks",
            placeholder="Turbulence, CB, icing, wind shear...", height=60)

        st.markdown("### Section E: Approach & Landing")
        col1, col2, col3 = st.columns(3)
        with col1:
            runway_used = st.text_input("Runway Used", placeholder="e.g., 36L")
        with col2:
            approach_type = st.selectbox("Approach Type",
                ["ILS CAT I", "ILS CAT II", "ILS CAT III", "VOR", "RNAV (GPS)",
                 "Visual", "Circling", "Other"])
        with col3:
            landing_quality = st.selectbox("Landing Quality",
                ["Smooth", "Normal", "Firm", "Hard", "Go-around executed"], index=1)

        approach_stable = st.selectbox("Approach Stabilized?",
            ["Yes - Fully stabilized", "Yes - Minor corrections", "No - Go-around", "N/A"])

        st.markdown("### Section F: Technical Status")
        col1, col2 = st.columns(2)
        with col1:
            mel_items = st.selectbox("MEL Items Active?",
                ["No", "Yes - 1 item", "Yes - 2 items", "Yes - 3+ items"])
        with col2:
            tech_issues = st.selectbox("Technical Issues During Flight?",
                ["No issues", "Minor - No operational impact",
                 "Moderate - Operational limitation",
                 "Significant - Procedure deviation",
                 "Serious - Emergency procedure"])

        tech_description = ""
        if tech_issues != "No issues":
            tech_description = st.text_area("Technical Issue Description", height=80)

        st.markdown("### Section G: Crew Information")
        col1, col2 = st.columns(2)
        with col1:
            captain_name = st.text_input("Captain Name *")
            captain_license = st.text_input("Captain License")
        with col2:
            fo_name = st.text_input("First Officer Name")
            fdp_status = st.selectbox("FDP Status",
                ["Within limits", "Extended - Pre-planned",
                 "Extended - Operational", "Near limits"])

        crew_fatigue = st.selectbox("Crew Fatigue Level",
            ["Normal - Well rested", "Mild - Acceptable",
             "Moderate - Noticeable", "High - Performance concern"])

        st.markdown("### Section H: Safety Observations")
        safety_observations = st.text_area("Safety Observations",
            placeholder="Any safety-related observations or concerns...", height=100)

        overall_flight = st.selectbox("Overall Flight Assessment",
            ["Normal - Routine flight",
             "Minor variations - Within normal operations",
             "Notable events - Documented for review",
             "Significant issues - Requires follow-up",
             "Safety concern - Immediate review required"])

        st.markdown("---")
        submitted = st.form_submit_button("📤 Submit Captain's Debrief",
            use_container_width=True, type="primary")

        if submitted:
            errors = []
            if not flight_number:
                errors.append("Flight Number is required")
            if not aircraft_reg:
                errors.append("Aircraft Registration is required")
            if not captain_name:
                errors.append("Captain Name is required")

            if errors:
                for e in errors:
                    st.error(f"❌ {e}")
            else:
                if tech_issues in ["Significant - Procedure deviation", "Serious - Emergency procedure"] or \
                   "Immediate review required" in overall_flight:
                    risk_level = "High"
                elif tech_issues != "No issues" or "Requires follow-up" in overall_flight:
                    risk_level = "Medium"
                else:
                    risk_level = "Low"

                report_data = {
                    'id': report_id,
                    'type': "Captain's Debrief",
                    'date': flight_date.isoformat(),
                    'flight_number': flight_number,
                    'aircraft_reg': aircraft_reg,
                    'aircraft_type': aircraft_type,
                    'origin': origin.split(' - ')[0] if origin else '',
                    'destination': destination.split(' - ')[0] if destination else '',
                    'times': {
                        'off_blocks': off_blocks.strftime('%H:%M'),
                        'takeoff': takeoff_time.strftime('%H:%M'),
                        'landing': landing_time.strftime('%H:%M'),
                        'on_blocks': on_blocks.strftime('%H:%M')
                    },
                    'block_time': block_time_hrs,
                    'flight_time': flight_time_hrs,
                    'fuel': {'departure': fuel_departure, 'arrival': fuel_arrival,
                             'used': fuel_departure - fuel_arrival, 'planned': fuel_planned},
                    'weather': {'dep': dep_weather, 'dep_wind': dep_wind,
                                'arr': arr_weather, 'arr_wind': arr_wind,
                                'enroute': enroute_remarks},
                    'approach': {'runway': runway_used, 'type': approach_type,
                                 'stable': approach_stable, 'quality': landing_quality},
                    'technical': {'mel_items': mel_items, 'issues': tech_issues,
                                  'description': tech_description},
                    'captain_name': captain_name,
                    'captain_license': captain_license,
                    'fo_name': fo_name,
                    'fdp_status': fdp_status,
                    'crew_fatigue': crew_fatigue,
                    'safety_observations': safety_observations,
                    'overall_assessment': overall_flight,
                    'description': safety_observations or overall_flight,
                    'reported_by': captain_name,
                    'risk_level': risk_level,
                    'status': 'Open - Pending Review',
                    'created_at': datetime.now().isoformat(),
                    'department': 'Flight Operations'
                }

                if 'captain_dbr' not in st.session_state:
                    st.session_state.captain_dbr = []
                st.session_state.captain_dbr.append(report_data)

                st.balloons()
                st.success(f"✅ **Captain's Debrief Submitted!** Reference: {report_id}")

# ============================================================================
# DASHBOARD
# ============================================================================

def generate_trend_data():
    monthly_counts = defaultdict(int)
    all_reports = []
    for rt in ['bird_strikes', 'laser_strikes', 'tcas_reports',
               'aircraft_incidents', 'hazard_reports', 'fsr_reports', 'captain_dbr']:
        all_reports.extend(st.session_state.get(rt, []))

    for report in all_reports:
        date_str = report.get('date') or report.get('incident_date') or report.get('report_date')
        if date_str:
            try:
                if isinstance(date_str, str):
                    date_obj = datetime.strptime(date_str[:10], '%Y-%m-%d')
                else:
                    date_obj = date_str
                month_key = date_obj.strftime('%b %Y')
                monthly_counts[month_key] += 1
            except:
                pass

    if not monthly_counts:
        months = []
        for i in range(5, -1, -1):
            month_date = datetime.now() - timedelta(days=i * 30)
            months.append({'Month': month_date.strftime('%b'), 'Reports': 0})
        return months

    sorted_months = sorted(monthly_counts.items(),
                           key=lambda x: datetime.strptime(x[0], '%b %Y'))
    return [{'Month': m, 'Reports': c} for m, c in sorted_months[-6:]]


def render_dashboard():
    report_counts = get_report_counts()
    risk_distribution = get_risk_distribution()
    total_reports = get_total_reports()
    high_risk_count = get_high_risk_count()
    recent_reports = get_recent_reports(10)

    st.markdown("""
    <div style="background:linear-gradient(135deg,#1e3c72 0%,#2a5298 100%);
                padding:30px;border-radius:15px;margin-bottom:25px;color:white;">
        <h1 style="margin:0;font-size:2.2rem;">📊 Safety Dashboard</h1>
        <p style="margin:10px 0 0 0;opacity:0.9;font-size:1.1rem;">
            Real-time safety metrics and performance indicators</p>
    </div>
    """, unsafe_allow_html=True)

    render_weather_widget()
    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("### 📈 Key Performance Indicators")
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

    open_count = get_open_investigations()
    closed_count = total_reports - open_count
    closure_rate = (closed_count / total_reports * 100) if total_reports > 0 else 0

    with kpi_col1:
        st.metric("Total Reports", total_reports)
    with kpi_col2:
        st.metric("Open Investigations", open_count)
    with kpi_col3:
        st.metric("High/Extreme Risk", high_risk_count)
    with kpi_col4:
        st.metric("Closure Rate", f"{closure_rate:.0f}%")

    st.markdown("### 📋 Reports by Category")
    cat_cols = st.columns(7)
    report_types = [
        ("🐦", "Bird Strikes",  report_counts['bird_strikes'],    "#FF6B6B"),
        ("🔴", "Laser Strikes", report_counts['laser_strikes'],   "#4ECDC4"),
        ("✈️", "TCAS Events",   report_counts['tcas_reports'],    "#45B7D1"),
        ("⚠️", "Incidents",     report_counts['aircraft_incidents'], "#96CEB4"),
        ("🔶", "Hazards",       report_counts['hazard_reports'],  "#FFEAA7"),
        ("📝", "FSR Reports",   report_counts['fsr_reports'],     "#DDA0DD"),
        ("👨‍✈️","Capt Debrief",  report_counts['captain_dbr'],     "#98D8C8"),
    ]
    for col, (icon, label, count, color) in zip(cat_cols, report_types):
        with col:
            st.markdown(f"""<div style="background:white;padding:20px;border-radius:12px;
                text-align:center;border-left:4px solid {color};
                box-shadow:0 2px 10px rgba(0,0,0,0.1);">
                <div style="font-size:2rem;">{icon}</div>
                <div style="font-size:1.8rem;font-weight:bold;color:#333;">{count}</div>
                <div style="font-size:0.8rem;color:#666;">{label}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.markdown("### 📊 Risk Distribution")
        if any(risk_distribution.values()):
            fig = px.pie(
                values=list(risk_distribution.values()),
                names=list(risk_distribution.keys()),
                color=list(risk_distribution.keys()),
                color_discrete_map={'Extreme': '#DC3545', 'High': '#FD7E14',
                                    'Medium': '#FFC107', 'Low': '#28A745'},
                hole=0.4
            )
            fig.update_layout(height=300, margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No risk data yet. Submit reports to see distribution.")

    with chart_col2:
        st.markdown("### 📈 Monthly Trend")
        trend_data = generate_trend_data()
        if trend_data:
            trend_df = pd.DataFrame(trend_data)
            fig = px.line(trend_df, x='Month', y='Reports', markers=True,
                          color_discrete_sequence=['#667eea'])
            fig.update_layout(height=300, margin=dict(t=20, b=20, l=20, r=20),
                              showlegend=False, xaxis_title="", yaxis_title="Count")
            fig.update_traces(line=dict(width=3), marker=dict(size=10))
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 🕐 Recent Activity")
    if recent_reports:
        for report in recent_reports[:5]:
            risk_color = {'Extreme': '#DC3545', 'High': '#FD7E14',
                          'Medium': '#FFC107', 'Low': '#28A745'}.get(report.get('risk_level', 'Low'), '#6C757D')
            st.markdown(f"""<div style="background:white;padding:15px;border-radius:10px;
                margin-bottom:10px;border-left:4px solid {risk_color};
                box-shadow:0 2px 5px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <span style="font-size:1.2rem;">{report.get('icon','📄')}</span>
                        <strong style="margin-left:10px;">{report.get('id','N/A')}</strong>
                        <span style="color:#666;margin-left:10px;">{report.get('type','Report')}</span>
                    </div>
                    <span style="background:{risk_color};color:white;padding:3px 10px;
                        border-radius:15px;font-size:0.8rem;">{report.get('risk_level','Low')}</span>
                </div>
                <div style="color:#888;font-size:0.85rem;margin-top:8px;">
                    📅 {report.get('date','N/A')} | 👤 {report.get('reporter','Anonymous')}
                </div>
            </div>""", unsafe_allow_html=True)
    else:
        st.info("No recent reports. Submit a report to see activity here.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📝 Submit New Report", use_container_width=True):
            st.session_state['current_page'] = 'Hazard Report'
            st.rerun()
    with col2:
        if st.button("📋 View All Reports", use_container_width=True):
            st.session_state['current_page'] = 'View Reports'
            st.rerun()

# ============================================================================
# VIEW REPORTS
# ============================================================================

def filter_by_date(date_str, start_date, end_date):
    if date_str == 'N/A':
        return True
    try:
        if isinstance(date_str, str):
            report_date = datetime.strptime(date_str[:10], '%Y-%m-%d').date()
        else:
            report_date = date_str
        return start_date <= report_date <= end_date
    except:
        return True


def render_view_reports():
    st.markdown("""
    <div style="background:linear-gradient(135deg,#1e3c72 0%,#2a5298 100%);
                padding:30px;border-radius:15px;margin-bottom:25px;color:white;">
        <h1 style="margin:0;font-size:2.2rem;">📋 View Reports</h1>
        <p style="margin:10px 0 0 0;opacity:0.9;">Search, filter, and manage all safety reports</p>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("🔍 Search & Filter", expanded=True):
        filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
        with filter_col1:
            report_type_filter = st.selectbox("Report Type",
                ["All Types", "Bird Strike", "Laser Strike", "TCAS Report",
                 "Aircraft Incident", "Hazard Report", "FSR Report", "Captain's Debrief"])
        with filter_col2:
            risk_filter = st.selectbox("Risk Level", ["All Levels", "Extreme", "High", "Medium", "Low"])
        with filter_col3:
            status_filter = st.selectbox("Status",
                ["All Status", "Open - Pending Review", "Open - Under Investigation",
                 "Closed - No Further Action", "Closed"])
        with filter_col4:
            try:
                date_range = st.date_input("Date Range",
                    value=(datetime.now() - timedelta(days=365), datetime.now()))
            except:
                date_range = (datetime.now() - timedelta(days=365), datetime.now())

        search_query = st.text_input("🔎 Search by ID, description, or reporter", "")

    all_reports = []
    type_map = {
        "Bird Strike":         ("bird_strikes",         "🐦"),
        "Laser Strike":        ("laser_strikes",        "🔴"),
        "TCAS Report":         ("tcas_reports",         "✈️"),
        "Aircraft Incident":   ("aircraft_incidents",   "⚠️"),
        "Hazard Report":       ("hazard_reports",       "🔶"),
        "FSR Report":          ("fsr_reports",          "📝"),
        "Captain's Debrief":   ("captain_dbr",          "👨‍✈️"),
    }

    for display_name, (state_key, icon) in type_map.items():
        for report in st.session_state.get(state_key, []):
            all_reports.append({
                'id': report.get('id', 'N/A'),
                'type': display_name,
                'icon': icon,
                'date': report.get('date', 'N/A'),
                'reporter': report.get('reported_by', report.get('reporter_name',
                             report.get('captain_name', 'Anonymous'))),
                'risk_level': report.get('risk_level', 'Low'),
                'status': report.get('status', 'Open'),
                'description': report.get('description', report.get('narrative',
                               report.get('hazard_description', 'No description'))),
                'raw_data': report
            })

    filtered = all_reports.copy()

    if report_type_filter != "All Types":
        filtered = [r for r in filtered if r['type'] == report_type_filter]
    if risk_filter != "All Levels":
        filtered = [r for r in filtered if r['risk_level'] == risk_filter]
    if status_filter != "All Status":
        filtered = [r for r in filtered if r['status'] == status_filter]
    if search_query:
        ql = search_query.lower()
        filtered = [r for r in filtered if
                    ql in r['id'].lower() or
                    ql in r['reporter'].lower() or
                    ql in r['description'].lower()]
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start_d, end_d = date_range
        filtered = [r for r in filtered if filter_by_date(r['date'], start_d, end_d)]

    filtered.sort(key=lambda x: x['date'] if x['date'] != 'N/A' else '', reverse=True)

    st.markdown(f"**Found {len(filtered)} reports**")

    if filtered:
        tab_cards, tab_table = st.tabs(["📋 Card View", "📊 Table View"])

        with tab_cards:
            for idx, report in enumerate(filtered):
                risk_colors = {
                    'Extreme': ('#DC3545', '#FFF5F5'),
                    'High':    ('#FD7E14', '#FFF8F0'),
                    'Medium':  ('#FFC107', '#FFFBEB'),
                    'Low':     ('#28A745', '#F0FFF4'),
                }
                border_color, _ = risk_colors.get(report['risk_level'], ('#6C757D', '#F8F9FA'))

                with st.expander(
                    f"{report['icon']} **{report['id']}** — {report['type']} | {report['date']}"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write(f"**Date:** {report['date']}")
                        st.write(f"**Type:** {report['type']}")
                    with col2:
                        st.write(f"**Reporter:** {report['reporter']}")
                        st.write(f"**Status:** {report['status']}")
                    with col3:
                        st.markdown(f"**Risk:** {render_risk_badge(report['risk_level'])}", unsafe_allow_html=True)

                    st.markdown("---")
                    st.markdown(f"**Description:** {report['description'][:400]}")

                    act_col1, act_col2, act_col3 = st.columns(3)
                    with act_col1:
                        if st.button("👁️ View Details", key=f"view_{idx}_{report['id']}",
                                     use_container_width=True):
                            st.session_state['selected_report'] = report
                            st.session_state['current_page'] = 'Report Detail'
                            st.rerun()
                    with act_col2:
                        new_status = st.selectbox("Update Status",
                            ["Open - Pending Review", "Open - Under Investigation",
                             "Closed - No Further Action", "Closed"],
                            key=f"stat_{idx}_{report['id']}")
                        if st.button("✅ Update", key=f"upd_{idx}_{report['id']}",
                                     use_container_width=True):
                            report['raw_data']['status'] = new_status
                            st.success("Updated!")
                            st.rerun()
                    with act_col3:
                        if REPORTLAB_AVAILABLE:
                            if st.button("📄 PDF", key=f"pdf_{idx}_{report['id']}",
                                         use_container_width=True):
                                generate_report_pdf(report)

        with tab_table:
            table_data = [{
                'ID': r['id'], 'Type': r['type'], 'Date': r['date'],
                'Reporter': r['reporter'], 'Risk': r['risk_level'], 'Status': r['status']
            } for r in filtered]
            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

            csv = df.to_csv(index=False)
            st.download_button("📥 Export CSV", csv, "safety_reports.csv", "text/csv")
    else:
        st.info("No reports found. Try adjusting the filters or submit a new report.")

# ============================================================================
# REPORT DETAIL
# ============================================================================

def render_report_detail():
    report = st.session_state.get('selected_report')

    if not report:
        st.warning("No report selected.")
        if st.button("← Back to Reports"):
            st.session_state['current_page'] = 'View Reports'
            st.rerun()
        return

    if st.button("← Back to Reports"):
        st.session_state['current_page'] = 'View Reports'
        st.rerun()

    risk_color = {'Extreme': '#DC3545', 'High': '#FD7E14',
                  'Medium': '#FFC107', 'Low': '#28A745'}.get(report.get('risk_level', 'Low'), '#6C757D')

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1e3c72 0%,#2a5298 100%);
                padding:30px;border-radius:15px;margin:20px 0;color:white;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
                <span style="font-size:2.5rem;">{report.get('icon','📄')}</span>
                <h1 style="display:inline;margin-left:15px;font-size:2rem;">{report.get('id','N/A')}</h1>
                <p style="margin:10px 0 0 0;opacity:0.9;">{report.get('type','Report')}</p>
            </div>
            <span style="background:{risk_color};color:white;padding:10px 25px;
                         border-radius:25px;font-size:1.2rem;font-weight:bold;">
                {report.get('risk_level','Low')} Risk
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab_details, tab_actions = st.tabs(["📋 Details", "⚡ Actions"])

    with tab_details:
        raw = report.get('raw_data', report)
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Report ID:** {report.get('id','N/A')}")
            st.write(f"**Type:** {report.get('type','N/A')}")
            st.write(f"**Date:** {report.get('date','N/A')}")
        with col2:
            st.write(f"**Reporter:** {report.get('reporter','N/A')}")
            st.write(f"**Risk Level:** {report.get('risk_level','N/A')}")
            st.write(f"**Status:** {report.get('status','N/A')}")

        st.markdown("**Description:**")
        st.markdown(f"""<div style="background:#F8F9FA;padding:20px;border-radius:10px;
            border-left:4px solid #667eea;">{report.get('description','No description')}</div>""",
            unsafe_allow_html=True)

        with st.expander("View All Report Data"):
            if isinstance(raw, dict):
                for key, value in raw.items():
                    if key != 'raw_data':
                        st.write(f"**{key.replace('_',' ').title()}:** {value}")

    with tab_actions:
        st.markdown("### Status Update")
        col1, col2 = st.columns(2)
        with col1:
            new_status = st.selectbox("Update To:",
                ["Open - Pending Review", "Open - Under Investigation",
                 "Closed - No Further Action", "Closed"])
            notes = st.text_area("Notes:", height=80)
            if st.button("✅ Update Status", use_container_width=True):
                raw_data = report.get('raw_data', report)
                raw_data['status'] = new_status
                st.success(f"Status updated to: {new_status}")
        with col2:
            assignee = st.selectbox("Assign To:",
                ["Unassigned", "Safety Manager", "Safety Officer",
                 "Quality Manager", "Flight Ops Manager"])
            if st.button("📌 Assign", use_container_width=True):
                st.success(f"Assigned to: {assignee}")

        if REPORTLAB_AVAILABLE:
            if st.button("📄 Generate PDF", use_container_width=True):
                generate_report_pdf(report)

# ============================================================================
# AI ASSISTANT
# ============================================================================

def generate_ai_response(query):
    q = query.lower()
    counts = get_report_counts()
    total = get_total_reports()
    high = get_high_risk_count()
    dist = get_risk_distribution()

    if any(w in q for w in ['trend', 'pattern']):
        return f"""📊 **Safety Trend Analysis**

Current reporting is active across all categories. Total reports: {total}.

Risk distribution: Extreme: {dist['Extreme']}, High: {dist['High']}, Medium: {dist['Medium']}, Low: {dist['Low']}

Proactive hazard reporting indicates a healthy safety culture. Continue monitoring high-risk items closely."""

    elif any(w in q for w in ['risk', 'danger']):
        return f"""⚠️ **Risk Summary**

- Total: {total} reports
- High/Extreme Risk: {high} items requiring priority action
- Extreme: {dist['Extreme']} | High: {dist['High']} | Medium: {dist['Medium']} | Low: {dist['Low']}

All high/extreme items should have assigned owners and documented mitigation plans."""

    elif 'bird' in q:
        return f"""🐦 **Bird Strike Analysis**

Total bird strikes: {counts['bird_strikes']}

Most strikes occur during approach/landing phases. Wildlife hazard programs are active at key airports. 
Consider enhanced crew awareness briefings during migration seasons."""

    elif 'laser' in q:
        return f"""🔴 **Laser Strike Analysis**

Total laser strikes: {counts['laser_strikes']}

All incidents reported to authorities. GPS coordinates captured for law enforcement. 
Crews following standard illumination event procedures."""

    elif 'tcas' in q:
        return f"""✈️ **TCAS Analysis**

Total TCAS events: {counts['tcas_reports']}

All RA events followed correctly. Compliance rate at target. Data shared with PCAA for airspace analysis."""

    elif any(w in q for w in ['summary', 'briefing', 'overview']):
        return f"""📋 **Safety Briefing — {datetime.now().strftime('%d %B %Y')}**

**Statistics:**
- Total Reports: {total}
- High/Extreme Risk: {high}
- Bird Strikes: {counts['bird_strikes']}
- Hazard Reports: {counts['hazard_reports']}
- Incidents: {counts['aircraft_incidents']}

**Focus Areas:** Continue monitoring seasonal wildlife activity and pending corrective actions."""

    else:
        return f"""🤖 I understand you're asking about: *"{query}"*

Current system: **{total}** total reports | **{high}** high/extreme risk items.

You can ask about: risk trends, bird strikes, laser strikes, TCAS events, hazards, or request a safety briefing."""


def render_ai_assistant():
    if 'ai_chat_history' not in st.session_state:
        st.session_state.ai_chat_history = []

    st.markdown("""
    <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                padding:30px;border-radius:15px;margin-bottom:25px;color:white;">
        <h1 style="margin:0;font-size:2.2rem;">🤖 AI Safety Assistant</h1>
        <p style="margin:10px 0 0 0;opacity:0.9;">Intelligent analysis and insights</p>
    </div>
    """, unsafe_allow_html=True)

    # Chat history
    for message in st.session_state.ai_chat_history:
        if message['role'] == 'user':
            st.markdown(f"""<div style="display:flex;justify-content:flex-end;margin:10px 0;">
                <div style="background:#667eea;color:white;padding:12px 18px;border-radius:18px 18px 4px 18px;max-width:70%;">
                    {message['content']}</div></div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div style="display:flex;justify-content:flex-start;margin:10px 0;">
                <div style="background:#F8F9FA;color:#333;padding:12px 18px;border-radius:18px 18px 18px 4px;
                    max-width:80%;border:1px solid #E0E0E0;">
                    <div style="font-size:0.75rem;color:#666;margin-bottom:6px;">🤖 AI Assistant</div>
                    {message['content']}</div></div>""", unsafe_allow_html=True)

    st.markdown("---")
    col1, col2 = st.columns([5, 1])
    with col1:
        user_input = st.text_input("Ask me anything about safety...", key="ai_input",
            placeholder="e.g., What are the main risk trends?")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        send = st.button("📤 Send", use_container_width=True)

    if send and user_input:
        st.session_state.ai_chat_history.append({'role': 'user', 'content': user_input})
        response = generate_ai_response(user_input)
        st.session_state.ai_chat_history.append({'role': 'assistant', 'content': response})
        st.rerun()

    st.markdown("### 💡 Quick Queries")
    suggestions = [
        "Show me a safety summary", "What are the risk trends?",
        "Bird strike analysis", "Laser strike analysis",
        "TCAS event overview", "What actions are pending?"
    ]
    sugg_cols = st.columns(3)
    for i, sug in enumerate(suggestions):
        with sugg_cols[i % 3]:
            if st.button(sug, key=f"sug_{i}", use_container_width=True):
                st.session_state.ai_chat_history.append({'role': 'user', 'content': sug})
                st.session_state.ai_chat_history.append(
                    {'role': 'assistant', 'content': generate_ai_response(sug)})
                st.rerun()

    if st.button("🗑️ Clear Chat"):
        st.session_state.ai_chat_history = []
        st.rerun()

# ============================================================================
# GEOSPATIAL MAP
# ============================================================================

AIRPORT_COORDS = {
    "OPLA": (31.5216, 74.4036), "OPKC": (24.9065, 67.1609),
    "OPIS": (33.6167, 73.0992), "OPSK": (32.5356, 74.3633),
    "OPPS": (33.9939, 71.5146), "OPQT": (30.2514, 66.9378),
    "OPFA": (31.3650, 72.9945), "OPMT": (30.2033, 71.4192),
    "OMDB": (25.2532, 55.3657), "OMSJ": (25.3286, 55.5136),
    "OTHH": (25.2731, 51.6080), "OEJN": (21.6796, 39.1565),
}

def render_geospatial_map():
    st.markdown("""
    <div style="background:linear-gradient(135deg,#1e3c72 0%,#2a5298 100%);
                padding:30px;border-radius:15px;margin-bottom:25px;color:white;">
        <h1 style="margin:0;font-size:2.2rem;">🗺️ Geospatial Incident Map</h1>
        <p style="margin:10px 0 0 0;opacity:0.9;">Safety events by location</p>
    </div>
    """, unsafe_allow_html=True)

    map_data = []
    for rt in ['bird_strikes', 'laser_strikes', 'tcas_reports',
               'aircraft_incidents', 'hazard_reports']:
        for r in st.session_state.get(rt, []):
            origin = r.get('origin', '')
            coords = AIRPORT_COORDS.get(origin)
            if coords:
                map_data.append({
                    'latitude': coords[0], 'longitude': coords[1],
                    'id': r.get('id', 'N/A'),
                    'type': r.get('type', rt),
                    'risk_level': r.get('risk_level', 'Low'),
                    'date': r.get('date', 'N/A'),
                    'location': origin
                })

    if not map_data:
        # Show base airports
        map_data = [{'latitude': c[0], 'longitude': c[1], 'id': k, 'type': 'Airport',
                     'risk_level': 'Low', 'date': 'N/A', 'location': k}
                    for k, c in AIRPORT_COORDS.items()]

    df = pd.DataFrame(map_data)

    if PYDECK_AVAILABLE and pdk is not None:
        color_map = {
            'Extreme': [220, 53, 69, 200], 'High': [253, 126, 20, 200],
            'Medium': [255, 193, 7, 200],  'Low': [40, 167, 69, 200]
        }
        df['color'] = df['risk_level'].map(lambda x: color_map.get(x, [108, 117, 125, 200]))

        try:
            layer = pdk.Layer('ScatterplotLayer', data=df,
                get_position='[longitude, latitude]',
                get_color='color', get_radius=80000, pickable=True)
            view = pdk.ViewState(latitude=30.0, longitude=70.0, zoom=4, pitch=0)
            deck = pdk.Deck(layers=[layer], initial_view_state=view,
                tooltip={'text': '{type}\n{id}\nRisk: {risk_level}'})
            st.pydeck_chart(deck)
        except Exception as e:
            st.map(df[['latitude', 'longitude']])
    else:
        st.map(df[['latitude', 'longitude']])

    st.markdown("### 📊 Incident Location Summary")
    st.dataframe(df[['id', 'type', 'risk_level', 'date', 'location']],
                 use_container_width=True, hide_index=True)

# ============================================================================
# PREDICTIVE MONITOR
# ============================================================================

def render_predictive_monitor():
    st.markdown("""
    <div style="background:linear-gradient(135deg,#1e3c72 0%,#2a5298 100%);
                padding:30px;border-radius:15px;margin-bottom:25px;color:white;">
        <h1 style="margin:0;font-size:2.2rem;">🔮 Predictive Safety Monitor</h1>
        <p style="margin:10px 0 0 0;opacity:0.9;">AI-powered safety trend prediction</p>
    </div>
    """, unsafe_allow_html=True)

    total = get_total_reports()
    high = get_high_risk_count()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Risk Exposure", f"{(high/total*100):.1f}%" if total > 0 else "0%")
    with col2:
        st.metric("Reporting Activity", "Active" if total > 0 else "No Data")
    with col3:
        st.metric("Response Time", "Within SLA")
    with col4:
        st.metric("Training Currency", "95%")

    st.markdown("### 🚨 Predictive Alerts")
    alerts = [
        {"title": "Seasonal Bird Activity", "timeframe": "Next 2 weeks", "confidence": "85%",
         "rec": "Enhanced wildlife awareness briefings for LHE/KHI routes"},
        {"title": "Monsoon Weather Pattern", "timeframe": "Next month", "confidence": "78%",
         "rec": "Review thunderstorm avoidance procedures"},
        {"title": "Holiday Schedule Fatigue", "timeframe": "Holiday period", "confidence": "72%",
         "rec": "Monitor duty hours and ensure adequate rest periods"},
    ]

    for alert in alerts:
        c = int(alert['confidence'].replace('%', ''))
        color = '#28A745' if c >= 80 else '#FFC107' if c >= 60 else '#DC3545'
        st.markdown(f"""<div style="background:white;padding:20px;border-radius:10px;
            margin-bottom:15px;border-left:4px solid {color};">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <strong>{alert['title']}</strong>
                <span style="background:{color};color:white;padding:3px 10px;
                    border-radius:15px;font-size:0.8rem;">{alert['confidence']} confidence</span>
            </div>
            <div style="color:#666;margin:8px 0;">⏰ {alert['timeframe']}</div>
            <div style="background:#F8F9FA;padding:10px;border-radius:5px;">
                💡 {alert['rec']}</div>
        </div>""", unsafe_allow_html=True)

# ============================================================================
# DATA MANAGEMENT
# ============================================================================

def render_data_management():
    st.markdown("""
    <div style="background:linear-gradient(135deg,#1e3c72 0%,#2a5298 100%);
                padding:30px;border-radius:15px;margin-bottom:25px;color:white;">
        <h1 style="margin:0;font-size:2.2rem;">💾 Data Management</h1>
        <p style="margin:10px 0 0 0;opacity:0.9;">Export, import, and manage safety data</p>
    </div>
    """, unsafe_allow_html=True)

    tab_export, tab_backup = st.tabs(["📤 Export", "💾 Backup"])

    with tab_export:
        st.markdown("### Export Safety Data")
        export_types = st.multiselect("Select Data to Export",
            ["Bird Strikes", "Laser Strikes", "TCAS Reports",
             "Aircraft Incidents", "Hazard Reports", "FSR Reports", "Captain Debriefs"],
            default=["Hazard Reports"])

        type_map = {
            "Bird Strikes": "bird_strikes", "Laser Strikes": "laser_strikes",
            "TCAS Reports": "tcas_reports", "Aircraft Incidents": "aircraft_incidents",
            "Hazard Reports": "hazard_reports", "FSR Reports": "fsr_reports",
            "Captain Debriefs": "captain_dbr"
        }

        if st.button("📥 Generate Export", use_container_width=True):
            export_data = []
            for name in export_types:
                key = type_map.get(name, '')
                for item in st.session_state.get(key, []):
                    flat = {k: str(v) for k, v in item.items() if not isinstance(v, (dict, list))}
                    flat['report_type'] = name
                    export_data.append(flat)

            if export_data:
                df = pd.DataFrame(export_data)
                csv = df.to_csv(index=False)
                st.download_button("📥 Download CSV", csv,
                    f"safety_export_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
                st.success(f"✅ {len(export_data)} records ready for export.")
            else:
                st.warning("No data found for selected types.")

    with tab_backup:
        st.markdown("### System Backup")
        if st.button("💾 Create Full Backup", use_container_width=True):
            backup_data = {
                'timestamp': datetime.now().isoformat(),
                'bird_strikes': st.session_state.get('bird_strikes', []),
                'laser_strikes': st.session_state.get('laser_strikes', []),
                'tcas_reports': st.session_state.get('tcas_reports', []),
                'aircraft_incidents': st.session_state.get('aircraft_incidents', []),
                'hazard_reports': st.session_state.get('hazard_reports', []),
                'fsr_reports': st.session_state.get('fsr_reports', []),
                'captain_dbr': st.session_state.get('captain_dbr', []),
            }
            backup_json = json.dumps(backup_data, indent=2, default=str)
            st.download_button("📥 Download Backup", backup_json,
                f"sms_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                "application/json")
            st.success("✅ Backup created!")

# ============================================================================
# IOSA COMPLIANCE
# ============================================================================

def render_iosa_compliance():
    st.markdown("""
    <div style="background:linear-gradient(135deg,#1e3c72 0%,#2a5298 100%);
                padding:30px;border-radius:15px;margin-bottom:25px;color:white;">
        <h1 style="margin:0;font-size:2.2rem;">✈️ IOSA Compliance Tracker</h1>
        <p style="margin:10px 0 0 0;opacity:0.9;">IATA Operational Safety Audit Standards</p>
    </div>
    """, unsafe_allow_html=True)

    iosa_sections = {
        'ORG': {'name': 'Organization and Management System', 'standards': 45, 'compliant': 43},
        'FLT': {'name': 'Flight Operations', 'standards': 120, 'compliant': 115},
        'OPS': {'name': 'Operational Control', 'standards': 35, 'compliant': 34},
        'MNT': {'name': 'Aircraft Engineering and Maintenance', 'standards': 85, 'compliant': 82},
        'CAB': {'name': 'Cabin Operations', 'standards': 40, 'compliant': 38},
        'GRH': {'name': 'Ground Handling', 'standards': 55, 'compliant': 52},
        'CGO': {'name': 'Cargo Operations', 'standards': 30, 'compliant': 29},
        'SEC': {'name': 'Security Management', 'standards': 45, 'compliant': 44},
    }

    total_std = sum(s['standards'] for s in iosa_sections.values())
    total_comp = sum(s['compliant'] for s in iosa_sections.values())
    overall = (total_comp / total_std * 100)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Overall Compliance", f"{overall:.1f}%")
    with col2:
        st.metric("Total Standards", total_std)
    with col3:
        st.metric("Standards Met", total_comp)
    with col4:
        st.metric("Gaps", total_std - total_comp)

    st.markdown("### Compliance by Section")
    for code, data in iosa_sections.items():
        rate = data['compliant'] / data['standards'] * 100
        gap = data['standards'] - data['compliant']
        color = '#28A745' if rate >= 95 else '#FFC107' if rate >= 90 else '#DC3545'
        with st.expander(f"**{code}** — {data['name']} ({rate:.1f}%)"):
            st.progress(rate / 100)
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"Standards: {data['standards']} | Compliant: {data['compliant']} | Gaps: {gap}")
            with col2:
                if gap > 0:
                    st.warning(f"⚠️ {gap} gap(s)")

# ============================================================================
# RAMP INSPECTIONS
# ============================================================================

def render_ramp_inspection():
    st.markdown("""
    <div style="background:linear-gradient(135deg,#1e3c72 0%,#2a5298 100%);
                padding:30px;border-radius:15px;margin-bottom:25px;color:white;">
        <h1 style="margin:0;font-size:2.2rem;">🛬 Ramp Safety Inspections</h1>
    </div>
    """, unsafe_allow_html=True)

    tab_new, tab_view = st.tabs(["➕ New Inspection", "📋 View Inspections"])

    with tab_new:
        with st.form("ramp_form"):
            col1, col2 = st.columns(2)
            with col1:
                insp_id = st.text_input("Inspection ID",
                    value=generate_report_number("RAMP"), disabled=True)
                insp_date = st.date_input("Date", value=date.today())
            with col2:
                inspector = st.text_input("Inspector Name")
                insp_type = st.selectbox("Type",
                    ["Pre-Flight", "Transit", "Post-Flight", "Random", "Follow-up"])

            airport = st.selectbox("Airport", options=[""] + airport_options())
            observations = st.text_area("Observations", height=150)
            rating = st.select_slider("Overall Rating",
                options=["Non-Compliant", "Needs Improvement", "Satisfactory", "Good", "Excellent"],
                value="Satisfactory")

            submitted = st.form_submit_button("✅ Submit Inspection",
                use_container_width=True, type="primary")
            if submitted and inspector:
                data_entry = {
                    'id': insp_id, 'date': str(insp_date), 'airport': airport,
                    'inspector': inspector, 'type': insp_type,
                    'observations': observations, 'rating': rating, 'status': 'Completed'
                }
                if 'ramp_inspections' not in st.session_state:
                    st.session_state.ramp_inspections = []
                st.session_state.ramp_inspections.append(data_entry)
                st.success(f"✅ Inspection {insp_id} submitted!")

    with tab_view:
        inspections = st.session_state.get('ramp_inspections', [])
        if inspections:
            for insp in inspections:
                rc = {'Excellent': '#28A745', 'Good': '#20C997', 'Satisfactory': '#FFC107',
                      'Needs Improvement': '#FD7E14', 'Non-Compliant': '#DC3545'}
                color = rc.get(insp.get('rating', 'Satisfactory'), '#6C757D')
                st.markdown(f"""<div style="background:white;padding:15px;border-radius:10px;
                    margin-bottom:10px;border-left:4px solid {color};">
                    <strong>{insp['id']}</strong> — {insp.get('airport','')} | {insp['date']}
                    <span style="background:{color};color:white;padding:2px 8px;border-radius:10px;
                        float:right;font-size:0.8rem;">{insp['rating']}</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.info("No inspections yet.")

# ============================================================================
# AUDIT FINDINGS
# ============================================================================

def render_audit_findings():
    st.markdown("""
    <div style="background:linear-gradient(135deg,#1e3c72 0%,#2a5298 100%);
                padding:30px;border-radius:15px;margin-bottom:25px;color:white;">
        <h1 style="margin:0;font-size:2.2rem;">🔍 Audit Findings Tracker</h1>
    </div>
    """, unsafe_allow_html=True)

    if 'audit_findings' not in st.session_state:
        st.session_state.audit_findings = [
            {'id': 'AUD-2025-001', 'source': 'Internal Audit', 'date': '2025-11-15',
             'area': 'Flight Operations', 'finding': 'CRM training records incomplete',
             'classification': 'Minor', 'status': 'Open', 'due_date': '2025-12-31',
             'owner': 'Training Manager'},
            {'id': 'AUD-2025-002', 'source': 'PCAA Inspection', 'date': '2025-10-20',
             'area': 'Maintenance', 'finding': 'Tool calibration certificates expired',
             'classification': 'Major', 'status': 'In Progress', 'due_date': '2025-12-15',
             'owner': 'Quality Manager'},
        ]

    findings = st.session_state.audit_findings
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Findings", len(findings))
    with col2:
        st.metric("Open", sum(1 for f in findings if f['status'] == 'Open'))
    with col3:
        st.metric("Major", sum(1 for f in findings if f['classification'] == 'Major'))

    st.markdown("### Findings Register")
    for finding in findings:
        sc = {'Major': '#DC3545', 'Minor': '#FFC107', 'Observation': '#17A2B8'}
        color = sc.get(finding['classification'], '#6C757D')
        with st.expander(f"**{finding['id']}** — {finding['area']} [{finding['classification']}]"):
            st.write(f"**Finding:** {finding['finding']}")
            st.write(f"**Source:** {finding['source']} | **Date:** {finding['date']}")
            st.write(f"**Owner:** {finding['owner']} | **Due:** {finding['due_date']}")
            new_status = st.selectbox("Update Status", ["Open", "In Progress", "Closed"],
                index=["Open", "In Progress", "Closed"].index(finding.get('status', 'Open')),
                key=f"af_{finding['id']}")
            if st.button("Update", key=f"af_btn_{finding['id']}"):
                finding['status'] = new_status
                st.success("Updated!")

# ============================================================================
# MOC WORKFLOW
# ============================================================================

def render_moc_workflow():
    st.markdown("""
    <div style="background:linear-gradient(135deg,#1e3c72 0%,#2a5298 100%);
                padding:30px;border-radius:15px;margin-bottom:25px;color:white;">
        <h1 style="margin:0;font-size:2.2rem;">🔄 Management of Change</h1>
    </div>
    """, unsafe_allow_html=True)

    tab_new, tab_pending = st.tabs(["➕ New Request", "⏳ Pending"])

    with tab_new:
        with st.form("moc_form"):
            change_title = st.text_input("Change Title")
            change_type = st.selectbox("Change Type",
                ["Operational Procedure", "Equipment/System", "Organization",
                 "Regulatory Compliance", "Training Program", "Route/Destination"])
            description = st.text_area("Description", height=120)
            justification = st.text_area("Business Justification", height=80)

            col1, col2 = st.columns(2)
            with col1:
                likelihood = st.slider("Risk Likelihood", 1, 5, 3)
            with col2:
                severity_sel = st.selectbox("Risk Severity",
                    ["E - Negligible", "D - Minor", "C - Major", "B - Hazardous", "A - Catastrophic"],
                    index=2)

            submitted = st.form_submit_button("Submit Change Request",
                use_container_width=True, type="primary")
            if submitted and change_title:
                moc = {
                    'id': generate_report_number("MOC"),
                    'title': change_title, 'type': change_type,
                    'description': description, 'status': 'Pending Review',
                    'date': datetime.now().strftime('%Y-%m-%d')
                }
                if 'moc_requests' not in st.session_state:
                    st.session_state.moc_requests = []
                st.session_state.moc_requests.append(moc)
                st.success(f"✅ {moc['id']} submitted!")

    with tab_pending:
        mocs = st.session_state.get('moc_requests', [])
        pending = [m for m in mocs if m['status'] == 'Pending Review']
        if pending:
            for m in pending:
                st.markdown(f"""<div style="background:white;padding:15px;border-radius:10px;
                    margin-bottom:10px;border-left:4px solid #FFC107;">
                    <strong>{m['id']}</strong> — {m['title']}<br>
                    <small style="color:#666;">Type: {m['type']} | {m['date']}</small>
                </div>""", unsafe_allow_html=True)
        else:
            st.info("No pending change requests.")

# ============================================================================
# PDF GENERATION
# ============================================================================

def generate_report_pdf(report):
    if not REPORTLAB_AVAILABLE:
        st.error("PDF generation requires reportlab. Install with: pip install reportlab")
        return

    try:
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        c.setFillColor(HexColor('#1e3c72'))
        c.rect(0, height - 100, width, 100, fill=True)
        c.setFillColor(HexColor('#FFFFFF'))
        c.setFont("Helvetica-Bold", 24)
        c.drawString(50, height - 50, "AIR SIAL")
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 70, "Safety Management System")

        c.setFillColor(HexColor('#333333'))
        y = height - 140

        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, y, f"Report: {report.get('id', 'N/A')}")
        y -= 30

        c.setFont("Helvetica", 11)
        for detail in [
            f"Type: {report.get('type', 'N/A')}",
            f"Date: {report.get('date', 'N/A')}",
            f"Reporter: {report.get('reporter', 'N/A')}",
            f"Risk Level: {report.get('risk_level', 'N/A')}",
            f"Status: {report.get('status', 'N/A')}",
        ]:
            c.drawString(50, y, detail)
            y -= 20

        y -= 15
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "Description:")
        y -= 18
        c.setFont("Helvetica", 10)

        desc = str(report.get('description', 'No description'))
        words = desc.split()
        line = ""
        for word in words:
            if len(line + word) < 90:
                line += word + " "
            else:
                c.drawString(50, y, line)
                y -= 14
                line = word + " "
                if y < 80:
                    c.showPage()
                    y = height - 50
        if line:
            c.drawString(50, y, line)

        c.setFillColor(HexColor('#666666'))
        c.setFont("Helvetica", 8)
        c.drawString(50, 30, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        c.drawString(width - 200, 30, "Air Sial Safety Management System")

        c.save()
        buffer.seek(0)

        st.download_button(
            "📥 Download PDF", buffer,
            f"{report.get('id', 'report')}_report.pdf", "application/pdf"
        )
        st.success("PDF generated!")

    except Exception as e:
        st.error(f"PDF error: {str(e)}")

# ============================================================================
# SETTINGS
# ============================================================================

def render_settings():
    st.markdown("""
    <div style="background:linear-gradient(135deg,#1e3c72 0%,#2a5298 100%);
                padding:30px;border-radius:15px;margin-bottom:25px;color:white;">
        <h1 style="margin:0;font-size:2.2rem;">⚙️ System Settings</h1>
    </div>
    """, unsafe_allow_html=True)

    settings = st.session_state.get('app_settings', {})

    tab_general, tab_users = st.tabs(["🏢 General", "👥 Users"])

    with tab_general:
        st.markdown("### General Settings")
        company_name = st.text_input("Company Name", value=settings.get('company_name', 'Air Sial'))
        company_code = st.text_input("ICAO Operator Code", value=settings.get('company_code', 'PF'))
        timezone = st.selectbox("Timezone",
            ["Asia/Karachi (PKT)", "UTC", "Asia/Dubai", "Europe/London"])
        email_notifications = st.checkbox("Enable Email Notifications",
            value=settings.get('email_notifications', True))
        items_per_page = st.slider("Reports Per Page", 10, 100,
            value=settings.get('items_per_page', 25), step=5)

        if st.button("💾 Save Settings", use_container_width=True):
            st.session_state['app_settings'] = {
                'company_name': company_name,
                'company_code': company_code,
                'timezone': timezone,
                'email_notifications': email_notifications,
                'items_per_page': items_per_page,
                'last_updated': datetime.now().isoformat()
            }
            st.success("✅ Settings saved!")

    with tab_users:
        st.markdown("### User Management")
        users = st.session_state.get('users_db', {})
        for uname, udata in users.items():
            st.markdown(f"""<div style="background:white;padding:12px;border-radius:8px;
                margin-bottom:8px;border:1px solid #E0E0E0;">
                <strong>👤 {uname}</strong> — {udata.get('role','N/A')}
                <span style="color:#888;font-size:0.85rem;float:right;">{udata.get('email','')}</span>
            </div>""", unsafe_allow_html=True)

# ============================================================================
# EMAIL CENTER
# ============================================================================

def render_email_center():
    st.markdown("""
    <div style="background:linear-gradient(135deg,#1e3c72 0%,#2a5298 100%);
                padding:30px;border-radius:15px;margin-bottom:25px;color:white;">
        <h1 style="margin:0;font-size:2.2rem;">📧 Email Center</h1>
        <p style="margin:10px 0 0 0;opacity:0.9;">Manage safety communications</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("compose_email_form"):
        to_address = st.text_input("To:", placeholder="email@airsial.com")
        cc_address = st.text_input("CC:", placeholder="Optional")
        subject = st.text_input("Subject:")
        body = st.text_area("Message:", height=250)
        high_priority = st.checkbox("🔴 High Priority")

        submitted = st.form_submit_button("📤 Send Email", type="primary")
        if submitted:
            if to_address and subject and body:
                if 'sent_emails' not in st.session_state:
                    st.session_state.sent_emails = []
                st.session_state.sent_emails.append({
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'to': to_address, 'subject': subject, 'status': 'Sent'
                })
                st.success("✅ Email sent!")
            else:
                st.warning("Please fill in To, Subject, and Message.")

    # Show sent
    sent = st.session_state.get('sent_emails', [])
    if sent:
        st.markdown("### 📤 Sent Emails")
        for e in reversed(sent[-10:]):
            st.markdown(f"""<div style="background:white;padding:12px;border-radius:8px;
                margin-bottom:8px;border:1px solid #E0E0E0;">
                <strong>{e['subject']}</strong><br>
                <small style="color:#666;">To: {e['to']} | {e['date']}</small>
            </div>""", unsafe_allow_html=True)

# ============================================================================
# LOGIN
# ============================================================================

def render_login_page():
    if 'users_db' not in st.session_state:
        st.session_state.users_db = {
            'admin':    {'password': 'admin123',    'role': 'Administrator',  'email': 'admin@airsial.com'},
            'safety':   {'password': 'safety123',   'role': 'Safety Officer', 'email': 'safety@airsial.com'},
            'viewer':   {'password': 'viewer123',   'role': 'Viewer',         'email': 'viewer@airsial.com'},
            'pilot':    {'password': 'pilot123',    'role': 'Flight Crew',    'email': 'pilot@airsial.com'},
            'engineer': {'password': 'engineer123', 'role': 'Maintenance',    'email': 'engineer@airsial.com'},
            'manager':  {'password': 'manager123',  'role': 'Management',     'email': 'manager@airsial.com'},
        }

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style="text-align:center;padding:30px 0;">
            <div style="font-size:4rem;">✈️</div>
            <h1 style="color:#1e3c72;">AIR SIAL</h1>
            <h3 style="color:#64748B;">Safety Management System v3.0</h3>
        </div>
        """, unsafe_allow_html=True)

        tab_signin, tab_register = st.tabs(["🔐 Sign In", "📝 Register"])

        with tab_signin:
            with st.form("signin_form"):
                username = st.text_input("Username", placeholder="Enter username")
                password = st.text_input("Password", type="password", placeholder="Enter password")
                submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)

                if submitted:
                    users = st.session_state.users_db
                    ukey = username.lower().strip()
                    if ukey in users and users[ukey]['password'] == password:
                        st.session_state.authenticated = True
                        st.session_state.username = username
                        st.session_state.user_role = users[ukey]['role']
                        st.success("✅ Login successful!")
                        st.rerun()
                    elif username and password:
                        st.error("❌ Invalid username or password")
                    else:
                        st.warning("Please enter username and password")

            with st.expander("📋 Demo Credentials"):
                st.markdown("""
| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | Administrator |
| safety | safety123 | Safety Officer |
| pilot | pilot123 | Flight Crew |
| engineer | engineer123 | Maintenance |
| viewer | viewer123 | Viewer |
""")

        with tab_register:
            with st.form("register_form"):
                new_username = st.text_input("Username")
                new_email = st.text_input("Email")
                new_password = st.text_input("Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                new_role = st.selectbox("Role", ["Viewer", "Flight Crew", "Maintenance", "Safety Officer"])
                agree = st.checkbox("I agree to the Terms of Service")
                reg_submitted = st.form_submit_button("Create Account", use_container_width=True)

                if reg_submitted:
                    if not all([new_username, new_email, new_password, confirm_password]):
                        st.error("Please fill all fields")
                    elif new_username.lower() in st.session_state.users_db:
                        st.error("Username already exists")
                    elif new_password != confirm_password:
                        st.error("Passwords don't match")
                    elif len(new_password) < 6:
                        st.error("Password must be at least 6 characters")
                    elif not agree:
                        st.error("Please agree to Terms of Service")
                    else:
                        st.session_state.users_db[new_username.lower()] = {
                            'password': new_password, 'role': new_role, 'email': new_email
                        }
                        st.success(f"✅ Account created for {new_username}! Please sign in.")

# ============================================================================
# SIDEBAR
# ============================================================================

def render_sidebar():
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center;padding:20px 0;border-bottom:1px solid #eee;">
            <div style="font-size:2.5rem;">✈️</div>
            <h2 style="color:#1e3c72;margin:5px 0;">AIR SIAL</h2>
            <p style="color:#666;font-size:0.85rem;margin:0;">Safety Management System</p>
            <p style="color:#888;font-size:0.75rem;">v3.0</p>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.get('authenticated'):
            st.markdown(f"""
            <div style="background:#F0F4F8;padding:12px;border-radius:8px;margin:10px 0;text-align:center;">
                <div style="font-size:1.5rem;">👤</div>
                <div style="font-weight:bold;">{st.session_state.get('username','User')}</div>
                <div style="color:#666;font-size:0.85rem;">{st.session_state.get('user_role','Viewer')}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("### 📍 Navigation")

        nav_items = [
            ("📊 Dashboard", "Dashboard"),
            ("📋 View Reports", "View Reports"),
        ]
        for label, page in nav_items:
            if st.button(label, use_container_width=True, key=f"nav_{page}"):
                st.session_state['current_page'] = page
                st.rerun()

        with st.expander("➕ Submit Reports"):
            sub_items = [
                ("🐦 Bird Strike", "Bird Strike Report"),
                ("🔴 Laser Strike", "Laser Strike Report"),
                ("✈️ TCAS Report", "TCAS Report"),
                ("⚠️ Incident Report", "Aircraft Incident Report"),
                ("🔶 Hazard Report", "Hazard Report"),
                ("📝 Flight Services", "FSR Report"),
                ("👨‍✈️ Captain Debrief", "Captain Debrief"),
            ]
            for label, page in sub_items:
                if st.button(label, key=f"nav_{page}", use_container_width=True):
                    st.session_state['current_page'] = page
                    st.rerun()

        advanced_items = [
            ("🤖 AI Assistant", "AI Assistant"),
            ("📧 Email Center", "Email Center"),
            ("🗺️ Geospatial Map", "Geospatial Map"),
            ("✈️ IOSA Compliance", "IOSA Compliance"),
            ("🛬 Ramp Inspections", "Ramp Inspections"),
            ("🔍 Audit Findings", "Audit Findings"),
            ("🔄 Mgmt of Change", "MoC Workflow"),
            ("🔮 Predictive Monitor", "Predictive Monitor"),
            ("💾 Data Management", "Data Management"),
            ("⚙️ Settings", "Settings"),
        ]

        user_role = st.session_state.get('user_role', 'Viewer')
        restricted_pages = ["Email Center", "IOSA Compliance", "Audit Findings",
                            "MoC Workflow", "Data Management", "Settings"]

        for label, page in advanced_items:
            if page in restricted_pages and user_role == 'Viewer':
                continue
            if st.button(label, key=f"nav_{page}", use_container_width=True):
                st.session_state['current_page'] = page
                st.rerun()

        total = get_total_reports()
        high = get_high_risk_count()
        st.markdown("---")
        st.markdown(f"""
        <div style="background:#F0F4F8;padding:12px;border-radius:8px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                <span>Total Reports</span><strong>{total}</strong>
            </div>
            <div style="display:flex;justify-content:space-between;">
                <span>High Risk</span>
                <strong style="color:#DC3545;">{high}</strong>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state['authenticated'] = False
            st.session_state['username'] = None
            st.session_state['user_role'] = None
            st.rerun()

# ============================================================================
# SESSION STATE
# ============================================================================

def initialize_session_state():
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False
    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = 'Dashboard'

    for rt in ['bird_strikes', 'laser_strikes', 'tcas_reports',
               'aircraft_incidents', 'hazard_reports', 'fsr_reports',
               'captain_dbr', 'ramp_inspections', 'moc_requests']:
        if rt not in st.session_state:
            st.session_state[rt] = []

    for ocr_key in ['ocr_data_bird_strike', 'ocr_data_laser_strike',
                    'ocr_data_tcas_report', 'ocr_data_incident_report',
                    'ocr_data_hazard_report']:
        if ocr_key not in st.session_state:
            st.session_state[ocr_key] = None

    if 'ai_chat_history' not in st.session_state:
        st.session_state['ai_chat_history'] = []
    if 'app_settings' not in st.session_state:
        st.session_state['app_settings'] = {}

# ============================================================================
# ROUTER
# ============================================================================

def route_to_page():
    page = st.session_state.get('current_page', 'Dashboard')
    routing = {
        'Dashboard':              render_dashboard,
        'View Reports':           render_view_reports,
        'Bird Strike Report':     render_bird_strike_form,
        'Laser Strike Report':    render_laser_strike_form,
        'TCAS Report':            render_tcas_report_form,
        'Aircraft Incident Report': render_incident_form,
        'Hazard Report':          render_hazard_form,
        'FSR Report':             render_fsr_form,
        'Captain Debrief':        render_captain_dbr_form,
        'Report Detail':          render_report_detail,
        'AI Assistant':           render_ai_assistant,
        'Email Center':           render_email_center,
        'Geospatial Map':         render_geospatial_map,
        'IOSA Compliance':        render_iosa_compliance,
        'Ramp Inspections':       render_ramp_inspection,
        'Audit Findings':         render_audit_findings,
        'MoC Workflow':           render_moc_workflow,
        'Predictive Monitor':     render_predictive_monitor,
        'Data Management':        render_data_management,
        'Settings':               render_settings,
    }
    fn = routing.get(page, render_dashboard)
    try:
        fn()
    except Exception as e:
        st.error(f"Error rendering page '{page}': {str(e)}")
        st.exception(e)

# ============================================================================
# FOOTER
# ============================================================================

def render_footer():
    st.markdown("---")
    st.markdown("""
    <div style="text-align:center;color:#888;padding:15px;font-size:0.85rem;">
        Air Sial Safety Management System v3.0 | © 2025 Air Sial. All rights reserved.
    </div>
    """, unsafe_allow_html=True)

# ============================================================================
# MAIN
# ============================================================================

def main():
    st.set_page_config(
        page_title=f"{Config.APP_NAME} v{Config.APP_VERSION}",
        page_icon="✈️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    initialize_session_state()
    apply_custom_css()

    if not st.session_state.get('authenticated', False):
        render_login_page()
        return

    render_sidebar()
    render_header()
    route_to_page()
    render_footer()


if __name__ == "__main__":
    main()
