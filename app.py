import streamlit as st
import pandas as pd
from datetime import datetime, date, time
from typing import List, Dict, Optional
import json
import re
import requests
import base64
import tempfile, os

TOKEN_FILE = os.path.join(tempfile.gettempdir(), "travel_planner_client_id.txt")

def save_client_id(client_id: str):
    with open(TOKEN_FILE, "w") as f:
        f.write(client_id)

def load_client_id() -> str:
    try:
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    except:
        return ""


# ============================================
# CONFIGURATION
# ============================================
st.set_page_config(
    page_title="Travel Planner",
    page_icon="✈️",
    layout="wide"
)

# ============================================
# AI EXTRACTION (GLOBAL FUNCTION)
# ============================================
def ai_extract_travel(email_text: str, subject: str = "") -> Dict:
    
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""Extract travel booking details from the email below.


Email:
{email_text[:5000]}

Rules:
- Convert dates like "03 Jul (Fri) 07:50" to ISO: 2026-07-03T07:50:00
- Extract hotel name and full address
- Extract ALL flight legs including return flights
- For transfers: extract bus, shuttle, taxi, or airport transfer bookings (e.g. Flybus, airport shuttle, hotel pickup). 
  Use "pickup_location" for where the passenger boards and "dropoff_location" for the destination.
- Use exact values from email
 
Return ONLY this JSON, no explanation:
{{"flights":[{{"airline":"","flight_number":"","departure_city":"","arrival_city":"","departure_time":"","arrival_time":"","confirmation":""}}],"hotels":[{{"hotel_name":"","address":"","check_in":"","check_out":"","confirmation":""}}],"tours":[{{"tour_name":"","date":"","time":"","confirmation":""}}],"transfers":[{{"service_name":"","pickup_location":"","dropoff_location":"","transfer_date":"","transfer_time":"","passengers":0,"confirmation":""}}]}}
 
If nothing found return: {{"flights":[],"hotels":[],"tours":[],"transfers":[]}}"""

    
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",  # ← OpenAI endpoint
            headers=headers,
            json={
                "model": "openai/gpt-oss-120b:free",   # ← valid OpenAI model, cheap and accurate
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0
            },
            timeout=30
        )

        if response.status_code != 200:
            st.write(f"❌ Error: {response.text[:200]}")
            return {"flights": [], "hotels": [], "tours": [], "transfers": []}
 
        content = response.json()["choices"][0]["message"]["content"]
        content = re.sub(r'```json|```', '', content).strip()
 
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            result["flights"]   = [f for f in result.get("flights", [])   if f.get("airline") or f.get("flight_number")]
            result["hotels"]    = [h for h in result.get("hotels", [])    if h.get("hotel_name")]
            result["tours"]     = [t for t in result.get("tours", [])     if t.get("tour_name")]
            result["transfers"] = [x for x in result.get("transfers", []) if x.get("service_name") or x.get("pickup_location")]
            return result
 
    except Exception as e:
        st.write(f"❌ Exception: {str(e)}")
 
    return {"flights": [], "hotels": [], "tours": [], "transfers": []}


# ============================================
# OUTLOOK INTEGRATION (Simplified)
# ============================================
class OutlookManager:
    def __init__(self):
        self.client_id = None
        self.access_token = None
        self.user_id = None

    def configure(self, client_id: str):
        self.client_id = client_id

    

    def get_auth_url(self) -> str:
        if not self.client_id:
            return None

        redirect_uri = "http://localhost:8501/"
        scope = "Mail.Read User.Read"

        params = {
        "client_id": self.client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": scope,
        "response_mode": "query",
        "prompt": "select_account"   # ← add this
    }

        from urllib.parse import urlencode

        auth_url = (
            "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?"
            + urlencode(params)
        )

        return auth_url

    # ✅ MUST BE INDENTED INSIDE CLASS
    def exchange_code_for_token(self, auth_code: str) -> bool:
        if not self.client_id:
            st.session_state['auth_error'] = "client_id missing"
            return False

        redirect_uri = "http://localhost:8501/"
        token_url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"

        data = {
            "client_id": self.client_id,
            "code": auth_code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "scope": "Mail.Read User.Read"    # ← no offline_access
        }

        try:
            response = requests.post(token_url, data=data)
            response_json = response.json()

            if response.status_code == 200:
                self.access_token = response_json.get("access_token")
                return True
            else:
                st.session_state['auth_error'] = str(response_json)
                return False

        except Exception as e:
            st.session_state['auth_error'] = str(e)
            return False

       

    def fetch_emails(self, top: int = 50) -> List[Dict]:
        if not self.access_token:
            return []

        headers = {"Authorization": f"Bearer {self.access_token}"}
        results = []

        searches = [
            '"booking confirmed"',
            '"flight confirmation"',
            '"hotel reservation"',
            '"check-in"',
            '"your booking"',
            '"itinerary"',
            '"reservation confirmation"',
            '"flybus"',
            '"airport transfer"',
            '"shuttle"',
            '"bus pickup"',
            '"airport pickup"',
        ]

        for term in searches:
            url = (
                f'https://graph.microsoft.com/v1.0/me/messages'
                f'?$search={term}&$top=10'
                f'&$select=subject,bodyPreview,body,receivedDateTime'
            )
            try:
                r = requests.get(url, headers=headers)
                if r.status_code == 200:
                    results.extend(r.json().get("value", []))
            except:
                continue
 
        seen = set()
        unique = []
        for e in results:
            s = e.get("subject", "")
            if s not in seen:
                seen.add(s)
                unique.append(e)
 
        return unique

    def extract_travel_info(self, emails: List[Dict]) -> Dict:
        flights, hotels, tours, transfers = [], [], [], []
 
        for email in emails:
            subject      = email.get("subject", "")
            body_preview = email.get("bodyPreview", "")
            body_html    = email.get("body", {}).get("content", "")
 
            body_clean = re.sub(r'<[^>]+>', ' ', body_html)
            body_clean = re.sub(r'\s+', ' ', body_clean).strip()
 
            full_text = subject + "\n" + (body_clean if body_clean else body_preview)
            st.text_area("Raw text sent to AI", full_text[:1000], height=150)
 
            text_lower = full_text.lower()
            if not any(k in text_lower for k in [
                "flight", "hotel", "booking", "reservation",
                "flybus", "shuttle", "transfer", "bus", "pickup", "tour", "voucher"
            ]):
                continue
 
            st.write(f"📧 **{subject[:60]}** ({len(full_text)} chars)")
 
            ai_data = ai_extract_travel(full_text, subject=subject)
            st.write(f"→ {ai_data}")
 
            flights.extend(ai_data.get("flights", []))
            hotels.extend(ai_data.get("hotels", []))
            tours.extend(ai_data.get("tours", []))
            transfers.extend(ai_data.get("transfers", []))
 
        return {"flights": flights, "hotels": hotels, "tours": tours, "transfers": transfers}

# ============================================
# TRAVEL DATA CLASSES
# ============================================
class Flight:
    def __init__(self, airline, flight_number, departure, arrival,
                 departure_date, departure_time_val, arrival_date, arrival_time_val,
                 confirmation_number=""):
        self.airline = airline
        self.flight_number = flight_number
        self.departure = departure
        self.arrival = arrival
        self.departure_date = departure_date
        self.departure_time = departure_time_val
        self.arrival_date = arrival_date
        self.arrival_time = arrival_time_val
        self.confirmation_number = confirmation_number

    def to_dict(self):
        return {
            "Airline": self.airline,
            "Flight #": self.flight_number,
            "From": self.departure,
            "To": self.arrival,
            "Departure": f"{self.departure_date} {self.departure_time.strftime('%H:%M')}",
            "Arrival": f"{self.arrival_date} {self.arrival_time.strftime('%H:%M')}",
            "Confirmation": self.confirmation_number
        }

class Hotel:
    def __init__(self, name: str, address: str,
                 check_in: date, check_out: date,
                 confirmation_number: str = ""):
        self.name = name
        self.address = address      # already exists, just needs mapping fix below
        self.check_in = check_in
        self.check_out = check_out
        self.confirmation_number = confirmation_number

    def to_dict(self):
        return {
            "Hotel": self.name,
            "Address": self.address,
            "Check-in": str(self.check_in),
            "Check-out": str(self.check_out),
            "Confirmation": self.confirmation_number
        }

class Tour:
    def __init__(self, name: str, location: str, 
                 tour_date: date, tour_time: time, 
                 confirmation_number: str = ""):
        self.name = name
        self.location = location
        self.tour_date = tour_date
        self.tour_time = tour_time
        self.confirmation_number = confirmation_number

    def to_dict(self):
        return {
            "Tour": self.name,
            "Location": self.location,
            "Date": str(self.tour_date),
            "Time": self.tour_time.strftime("%H:%M"),
            "Confirmation": self.confirmation_number
        }

# ✅ NEW: Transfer class for bus/shuttle/airport pickups
class Transfer:
    def __init__(self, service_name: str, pickup_location: str,
                 dropoff_location: str, transfer_date: date,
                 transfer_time: time, passengers: int = 1,
                 confirmation_number: str = ""):
        self.service_name      = service_name
        self.pickup_location   = pickup_location
        self.dropoff_location  = dropoff_location
        self.transfer_date     = transfer_date
        self.transfer_time     = transfer_time
        self.passengers        = passengers
        self.confirmation_number = confirmation_number
 
    def to_dict(self):
        return {
            "Service": self.service_name,
            "Pickup": self.pickup_location,
            "Dropoff": self.dropoff_location,
            "Date": str(self.transfer_date),
            "Time": self.transfer_time.strftime("%H:%M"),
            "Passengers": self.passengers,
            "Confirmation": self.confirmation_number
        }


# ============================================
# SESSION STATE
# ============================================
if 'flights'   not in st.session_state: st.session_state.flights   = []
if 'hotels'    not in st.session_state: st.session_state.hotels    = []
if 'tours'     not in st.session_state: st.session_state.tours     = []
if 'transfers' not in st.session_state: st.session_state.transfers = []   # ✅ NEW
if 'outlook_manager'   not in st.session_state: st.session_state.outlook_manager   = OutlookManager()
if 'outlook_connected' not in st.session_state: st.session_state.outlook_connected = False
if 'client_id_stored'  not in st.session_state: st.session_state.client_id_stored  = ""          


# ============================================
# AUTO-CAPTURE OAUTH CODE FROM REDIRECT URL
# ============================================
if 'auth_error' not in st.session_state:
    st.session_state['auth_error'] = ""

query_params = st.query_params

if "code" in query_params and not st.session_state.outlook_connected:
    
    recovered = load_client_id()   # ← read from file, always works
    if not recovered:
        st.session_state['auth_error'] = "client_id file not found — re-enter Client ID and try again"
        st.query_params.clear()
        st.rerun()
    
    st.session_state.client_id_stored = recovered
    st.session_state.outlook_manager.configure(recovered)

    
    auth_code = query_params["code"]
    if isinstance(auth_code, list):
        auth_code = auth_code[0]

    with st.spinner("Connecting to Outlook..."):
        success = st.session_state.outlook_manager.exchange_code_for_token(auth_code)

    if success:
        st.session_state.outlook_connected = True
        st.session_state['auth_error'] = ""
        st.query_params.clear()
        st.rerun()
    else:
        st.query_params.clear()
        st.rerun()

# Show persisted error
if st.session_state.get('auth_error'):
    st.error(f"🔴 Auth Error: {st.session_state['auth_error']}")


# ============================================
# SIDEBAR
# ============================================
with st.sidebar:
    st.header("📧 Outlook Integration")

    st.info("""
    **Setup Required:**
    1. Go to [Azure Portal](https://portal.azure.com)
    2. Register an app
    3. Add API permission: **Mail.Read**
    4. Copy your **Client ID**
    """)

    
    client_id = st.text_input("Azure Client ID", type="password", value=st.session_state.client_id_stored)  # ← persist value

    if client_id:
        st.session_state.client_id_stored = client_id                    # ← save it
        st.session_state.outlook_manager.configure(client_id)
        save_client_id(client_id)   # ← add this line

    # OAuth flow
    st.markdown("### Connect to Outlook")

    if not st.session_state.outlook_connected:
        if st.button("🔗 Get Authorization URL"):
            if client_id:
                auth_url = st.session_state.outlook_manager.get_auth_url()
                st.markdown(f"""
                **[Click here to login]({auth_url})**

                After login, you'll be redirected with a code.
                """)
            else:
                st.error("Please enter Client ID first")


    # Import emails
    if st.session_state.outlook_connected:
        st.success("✅ Connected to Outlook")

        if st.button("📥 Import Travel Emails"):
            with st.spinner("Fetching emails..."):
                emails = st.session_state.outlook_manager.fetch_emails(top=20)  # ← remove [:10]

                st.info(f"📬 Found {len(emails)} emails to process")

                if emails:
                    # Show email subjects so you can confirm right emails are fetched
                    with st.expander("📧 Emails found"):
                        for e in emails:
                            st.write(f"- {e.get('subject', 'No subject')}")

                    travel_data = st.session_state.outlook_manager.extract_travel_info(emails)

                    st.info(f"✈️ Flights extracted: {len(travel_data['flights'])}")
                    st.info(f"🏨 Hotels extracted: {len(travel_data['hotels'])}")
                    st.info(f"🎯 Tours extracted: {len(travel_data['tours'])}")
                    st.info(f"🚌 Transfers extracted: {len(travel_data['transfers'])}")  # ✅ NEW

                    for f in travel_data["flights"]:
                        # Parse departure date from AI
                        dep_date = date.today()
                        arr_date = date.today()
                        dep_time = time(0, 0)
                        arr_time = time(0, 0)
                        try:
                            if f.get("departure_time"):
                                dt = datetime.fromisoformat(f["departure_time"])
                                dep_date, dep_time = dt.date(), dt.time()
                        except:
                            pass
                        try:
                            if f.get("arrival_time"):
                                dt = datetime.fromisoformat(f["arrival_time"])
                                arr_date, arr_time = dt.date(), dt.time()
                        except:
                            pass

                        st.session_state.flights.append(Flight(
                            f.get("airline", "Unknown"),
                            f.get("flight_number", ""),
                            f.get("departure_city", ""),    # ← was hardcoded ""
                            f.get("arrival_city", ""),      # ← was hardcoded ""
                            dep_date, dep_time,
                            arr_date, arr_time,
                            f.get("confirmation", "")
                        ))
                    for h in travel_data["hotels"]:
                        check_in = date.today()
                        check_out = date.today()
                        try:
                            if h.get("check_in"):
                                check_in = datetime.fromisoformat(h["check_in"]).date()
                        except:
                            pass
                        try:
                            if h.get("check_out"):
                                check_out = datetime.fromisoformat(h["check_out"]).date()
                        except:
                            pass

                        st.session_state.hotels.append(Hotel(
                            h.get("hotel_name", "Unknown"),
                            h.get("address", ""),        # ← was hardcoded "" before
                            check_in, check_out,
                            h.get("confirmation", "")
                        ))

                    for t in travel_data["tours"]:
                        tour_date = date.today()
                        tour_time_val = time(0, 0)
                        try:
                            if t.get("date"):
                                tour_date = datetime.fromisoformat(t["date"]).date()
                        except:
                            pass

                        st.session_state.tours.append(Tour(
                            t.get("tour_name", "Unknown"), "",
                            tour_date, tour_time_val,
                            t.get("confirmation", "")
                        ))

                    # ✅ NEW: Transfers
                    for x in travel_data["transfers"]:
                        xfer_date = date.today()
                        xfer_time = time(0, 0)
                        try:
                            if x.get("transfer_date"):
                                xfer_date = datetime.fromisoformat(x["transfer_date"]).date()
                        except: pass
                        try:
                            if x.get("transfer_time"):
                                xfer_time = datetime.fromisoformat(x["transfer_time"]).time()
                        except: pass
 
                        st.session_state.transfers.append(Transfer(
                            x.get("service_name", "Unknown"),
                            x.get("pickup_location", ""),
                            x.get("dropoff_location", ""),
                            xfer_date, xfer_time,
                            x.get("passengers", 1),
                            x.get("confirmation", "")
                        ))
                    

                    st.success(f"✅ Done!")
                else:
                    st.warning("No emails found — check your search keywords or mailbox")   

        if st.button("Disconnect"):
            st.session_state.outlook_connected = False
            st.session_state.outlook_manager.access_token = None
            st.rerun()

# ============================================
# MAIN TABS  (added 🚌 Transfers)
# ============================================
tab1, tab2, tab3, tab4, tab5 = st.tabs(["✈️ Flights", "🏨 Hotels", "🎯 Tours", "🚌 Transfers", "📋 Summary"])
 
# ---- TAB 1: FLIGHTS ----
with tab1:
    st.header("✈️ Flight Details")
 
    with st.form("add_flight"):
        col1, col2 = st.columns(2)
 
        with col1:
            airline           = st.text_input("Airline", placeholder="e.g., United Airlines")
            flight_number     = st.text_input("Flight Number", placeholder="e.g., UA1234")
            departure         = st.text_input("Departure City", placeholder="e.g., New York (JFK)")
            departure_date    = st.date_input("Departure Date", key="flight_dep_date")
            departure_time_val = st.time_input("Departure Time", key="flight_dep_time")
 
        with col2:
            arrival           = st.text_input("Arrival City", placeholder="e.g., Paris (CDG)")
            arrival_date      = st.date_input("Arrival Date", key="flight_arr_date")
            arrival_time_val  = st.time_input("Arrival Time", key="flight_arr_time")
            confirmation      = st.text_input("Confirmation Number", placeholder="e.g., ABC123")
 
        if st.form_submit_button("Add Flight ✈️") and airline and flight_number:
            st.session_state.flights.append(Flight(
                airline, flight_number, departure, arrival,
                departure_date, departure_time_val,
                arrival_date, arrival_time_val, confirmation
            ))
            st.success(f"✅ Flight {airline} {flight_number} added!")
 
    if st.session_state.flights:
        st.subheader(f"📋 {len(st.session_state.flights)} Flight(s)")
        st.dataframe(pd.DataFrame([f.to_dict() for f in st.session_state.flights]),
                     use_container_width=True, hide_index=True)
        if st.button("Clear Flights"):
            st.session_state.flights = []
            st.rerun()
    else:
        st.info("No flights added yet.")
 
 
# ---- TAB 2: HOTELS ----
with tab2:
    st.header("🏨 Hotel Details")
 
    with st.form("add_hotel"):
        col1, col2 = st.columns(2)
 
        with col1:
            hotel_name    = st.text_input("Hotel Name", placeholder="e.g., Hilton Paris")
            address       = st.text_input("Address", placeholder="e.g., 123 Champs-Élysées")
            check_in      = st.date_input("Check-in Date", key="hotel_checkin")
 
        with col2:
            check_out          = st.date_input("Check-out Date", key="hotel_checkout")
            hotel_confirmation = st.text_input("Confirmation Number", placeholder="e.g., HTL789")
 
        if st.form_submit_button("Add Hotel 🏨") and hotel_name:
            st.session_state.hotels.append(Hotel(hotel_name, address, check_in, check_out, hotel_confirmation))
            st.success(f"✅ {hotel_name} added!")
 
    if st.session_state.hotels:
        st.subheader(f"📋 {len(st.session_state.hotels)} Hotel(s)")
        st.dataframe(pd.DataFrame([h.to_dict() for h in st.session_state.hotels]),
                     use_container_width=True, hide_index=True)
        if st.button("Clear Hotels"):
            st.session_state.hotels = []
            st.rerun()
    else:
        st.info("No hotels added yet.")
 
 
# ---- TAB 3: TOURS ----
with tab3:
    st.header("🎯 Tour & Activity Details")
 
    with st.form("add_tour"):
        col1, col2 = st.columns(2)
 
        with col1:
            tour_name     = st.text_input("Tour/Activity Name", placeholder="e.g., Eiffel Tower Visit")
            tour_location = st.text_input("Location", placeholder="e.g., Paris, France")
 
        with col2:
            tour_date          = st.date_input("Date", key="tour_date")
            tour_time          = st.time_input("Time", key="tour_time")
            tour_confirmation  = st.text_input("Confirmation Number", placeholder="e.g., TOUR456")
 
        if st.form_submit_button("Add Tour 🎯") and tour_name:
            st.session_state.tours.append(Tour(tour_name, tour_location, tour_date, tour_time, tour_confirmation))
            st.success(f"✅ {tour_name} added!")
 
    if st.session_state.tours:
        st.subheader(f"📋 {len(st.session_state.tours)} Tour(s)")
        st.dataframe(pd.DataFrame([t.to_dict() for t in st.session_state.tours]),
                     use_container_width=True, hide_index=True)
        if st.button("Clear Tours"):
            st.session_state.tours = []
            st.rerun()
    else:
        st.info("No tours added yet.")
 
 
# ---- TAB 4: TRANSFERS (NEW) ----
with tab4:
    st.header("🚌 Airport & Bus Transfers")
 
    with st.form("add_transfer"):
        col1, col2 = st.columns(2)
 
        with col1:
            service_name     = st.text_input("Service Name", placeholder="e.g., Flybus PLUS, Super Shuttle")
            pickup_location  = st.text_input("Pickup Location", placeholder="e.g., Keflavik Airport")
            dropoff_location = st.text_input("Dropoff Location", placeholder="e.g., Reykjavik Hotel")
 
        with col2:
            transfer_date          = st.date_input("Date", key="xfer_date")
            transfer_time          = st.time_input("Time", key="xfer_time")
            passengers             = st.number_input("Passengers", min_value=1, value=1, step=1)
            transfer_confirmation  = st.text_input("Confirmation Number", placeholder="e.g., IF-1FSLB4")
 
        if st.form_submit_button("Add Transfer 🚌") and service_name:
            st.session_state.transfers.append(Transfer(
                service_name, pickup_location, dropoff_location,
                transfer_date, transfer_time, passengers, transfer_confirmation
            ))
            st.success(f"✅ {service_name} added!")
 
    if st.session_state.transfers:
        st.subheader(f"📋 {len(st.session_state.transfers)} Transfer(s)")
        st.dataframe(pd.DataFrame([x.to_dict() for x in st.session_state.transfers]),
                     use_container_width=True, hide_index=True)
        if st.button("Clear Transfers"):
            st.session_state.transfers = []
            st.rerun()
    else:
        st.info("No transfers added yet.")
 
 
# ---- TAB 5: SUMMARY ----
with tab5:
    st.header("📋 Complete Travel Summary")
 
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("✈️ Flights",   len(st.session_state.flights))
    col2.metric("🏨 Hotels",    len(st.session_state.hotels))
    col3.metric("🎯 Tours",     len(st.session_state.tours))
    col4.metric("🚌 Transfers", len(st.session_state.transfers))
 
    st.divider()
 
    if st.session_state.flights:
        st.subheader("✈️ Flights")
        for i, flight in enumerate(st.session_state.flights, 1):
            with st.expander(f"{i}. {flight.airline} {flight.flight_number}"):
                st.write(f"**Route:** {flight.departure} → {flight.arrival}")
                st.write(f"**Departure:** {flight.departure_date} at {flight.departure_time}")
                st.write(f"**Arrival:** {flight.arrival_date} at {flight.arrival_time}")
                st.write(f"**Confirmation:** {flight.confirmation_number}")
 
    if st.session_state.hotels:
        st.subheader("🏨 Hotels")
        for i, hotel in enumerate(st.session_state.hotels, 1):
            with st.expander(f"{i}. {hotel.name}"):
                st.write(f"**Address:** {hotel.address}")
                st.write(f"**Check-in:** {hotel.check_in}")
                st.write(f"**Check-out:** {hotel.check_out}")
                st.write(f"**Confirmation:** {hotel.confirmation_number}")
 
    if st.session_state.tours:
        st.subheader("🎯 Tours")
        for i, tour in enumerate(st.session_state.tours, 1):
            with st.expander(f"{i}. {tour.name}"):
                st.write(f"**Location:** {tour.location}")
                st.write(f"**Date:** {tour.tour_date} at {tour.tour_time}")
                st.write(f"**Confirmation:** {tour.confirmation_number}")
 
    # ✅ NEW: Transfers in summary
    if st.session_state.transfers:
        st.subheader("🚌 Transfers")
        for i, xfer in enumerate(st.session_state.transfers, 1):
            with st.expander(f"{i}. {xfer.service_name}"):
                st.write(f"**Pickup:** {xfer.pickup_location}")
                st.write(f"**Dropoff:** {xfer.dropoff_location}")
                st.write(f"**Date:** {xfer.transfer_date} at {xfer.transfer_time.strftime('%H:%M')}")
                st.write(f"**Passengers:** {xfer.passengers}")
                st.write(f"**Confirmation:** {xfer.confirmation_number}")
 
    st.divider()
    st.subheader("💾 Export")
 
    if st.button("Export to CSV"):
        all_data = []
        for f in st.session_state.flights:
            all_data.append({"Type": "Flight", **f.to_dict()})
        for h in st.session_state.hotels:
            all_data.append({"Type": "Hotel", **h.to_dict()})
        for t in st.session_state.tours:
            all_data.append({"Type": "Tour", **t.to_dict()})
        for x in st.session_state.transfers:
            all_data.append({"Type": "Transfer", **x.to_dict()})   # ✅ NEW
 
        if all_data:
            df_export = pd.DataFrame(all_data)
            csv = df_export.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "travel_plan.csv", "text/csv")
        else:
            st.warning("No data to export!")
