import streamlit as st
import pandas as pd
from datetime import datetime, date, time
from typing import List, Dict, Optional
import json
import re
import requests

# ============================================
# CONFIGURATION
# ============================================
st.set_page_config(
    page_title="Travel Planner",
    page_icon="✈️",
    layout="wide"
)

# ============================================
# OUTLOOK INTEGRATION (Simplified)
# ============================================
class OutlookManager:
    def __init__(self):
        self.client_id = None
        self.access_token = None
        self.user_id = None

    def configure(self, client_id: str):
        """Store client ID"""
        self.client_id = client_id

    def get_auth_url(self) -> str:
        """Generate OAuth authorization URL"""
        if not self.client_id:
            return None

        redirect_uri = "http://localhost:8501/"
        scope = "Mail.Read User.Read offline_access"

        auth_url = (
            f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?"
            f"client_id={self.client_id}&"
            f"response_type=code&"
            f"redirect_uri={redirect_uri}&"
            f"scope={scope}&"
            f"response_mode=query"
        )
        return auth_url

    def exchange_code_for_token(self, auth_code: str) -> bool:
        """Exchange authorization code for access token"""
        if not self.client_id:
            return False

        redirect_uri = "http://localhost:8501/"

        token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

        data = {
            "client_id": self.client_id,
            "code": auth_code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }

        try:
            response = requests.post(token_url, data=data)
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                return True
            else:
                st.error(f"Token exchange failed: {response.text}")
                return False
        except Exception as e:
            st.error(f"Error: {str(e)}")
            return False

    def fetch_emails(self, top: int = 50) -> List[Dict]:
        """Fetch emails from Outlook"""
        if not self.access_token:
            return []

        headers = {"Authorization": f"Bearer {self.access_token}"}
        endpoint = f"https://graph.microsoft.com/v1.0/me/messages?$top={top}"

        try:
            response = requests.get(endpoint, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return data.get("value", [])
            else:
                st.error(f"Error: {response.status_code}")
                return []
        except Exception as e:
            st.error(f"Error: {str(e)}")
            return []

    def extract_travel_info(self, emails: List[Dict]) -> Dict:
        """Extract travel info from emails"""
        flights = []
        hotels = []
        tours = []

        flight_keywords = ["flight", "airline", "boarding pass", "departure", "arrived"]
        hotel_keywords = ["hotel", "accommodation", "check-in", "check-out", "reservation"]
        tour_keywords = ["tour", "excursion", "ticket", "admission", "museum"]

        for email in emails:
            subject = email.get("subject", "").lower()
            body_preview = email.get("bodyPreview", "").lower()
            text = subject + " " + body_preview

            # Extract flight info
            if any(kw in text for kw in flight_keywords):
                flight_match = re.search(r'([A-Z]{2}\d{3,4})', text)
                conf_match = re.search(r'(?:confirmation|conf|booking)[:\s#]*([A-Z0-9]{5,})', text, re.IGNORECASE)

                if flight_match or "flight" in subject:
                    flights.append({
                        "airline": "Extracted",
                        "flight_number": flight_match.group(1) if flight_match else "TBD",
                        "confirmation": conf_match.group(1) if conf_match else "",
                        "subject": email.get("subject", "")
                    })

            # Extract hotel info
            elif any(kw in text for kw in hotel_keywords):
                conf_match = re.search(r'(?:confirmation|conf|booking)[:\s#]*([A-Z0-9]{5,})', text, re.IGNORECASE)
                hotels.append({
                    "hotel_name": email.get("subject", "").replace("Confirmation", "").replace("Booking", "").strip()[:50],
                    "confirmation": conf_match.group(1) if conf_match else "",
                    "subject": email.get("subject", "")
                })

            # Extract tour info
            elif any(kw in text for kw in tour_keywords):
                conf_match = re.search(r'(?:confirmation|conf|booking)[:\s#]*([A-Z0-9]{5,})', text, re.IGNORECASE)
                tours.append({
                    "tour_name": email.get("subject", "").replace("Confirmation", "").replace("Ticket", "").strip()[:50],
                    "confirmation": conf_match.group(1) if conf_match else "",
                    "subject": email.get("subject", "")
                })

        return {"flights": flights, "hotels": hotels, "tours": tours}

# ============================================
# TRAVEL DATA CLASSES
# ============================================
class Flight:
    def __init__(self, airline: str, flight_number: str, 
                 departure: str, arrival: str, 
                 departure_date: date, departure_time_val: time,
                 arrival_date: date, arrival_time_val: time,
                 confirmation_number: str = ""):
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
            "Departure": f"{self.departure_date} {self.departure_time}",
            "Arrival": f"{self.arrival_date} {self.arrival_time}",
            "Confirmation": self.confirmation_number
        }

class Hotel:
    def __init__(self, name: str, address: str, 
                 check_in: date, check_out: date,
                 confirmation_number: str = ""):
        self.name = name
        self.address = address
        self.check_in = check_in
        self.check_out = check_out
        self.confirmation_number = confirmation_number

    def to_dict(self):
        return {
            "Hotel": self.name,
            "Address": self.address,
            "Check-in": self.check_in,
            "Check-out": self.check_out,
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
            "Date": self.tour_date,
            "Time": self.tour_time,
            "Confirmation": self.confirmation_number
        }

# ============================================
# SESSION STATE
# ============================================
if 'flights' not in st.session_state:
    st.session_state.flights = []
if 'hotels' not in st.session_state:
    st.session_state.hotels = []
if 'tours' not in st.session_state:
    st.session_state.tours = []
if 'outlook_manager' not in st.session_state:
    st.session_state.outlook_manager = OutlookManager()
if 'outlook_connected' not in st.session_state:
    st.session_state.outlook_connected = False


# ============================================
# AUTO-CAPTURE OAUTH CODE FROM REDIRECT URL
# ============================================
query_params = st.query_params

if "code" in query_params and not st.session_state.outlook_connected:
    auth_code = query_params["code"]
    with st.spinner("Exchanging code for token..."):
        success = st.session_state.outlook_manager.exchange_code_for_token(auth_code)
        if success:
            st.session_state.outlook_connected = True
            # Clear the code from URL
            st.query_params.clear()
            st.rerun()
        else:
            st.error("Token exchange failed. Try reconnecting.")


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

    client_id = st.text_input("Azure Client ID", type="password")

    if client_id:
        st.session_state.outlook_manager.configure(client_id)

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
                emails = st.session_state.outlook_manager.fetch_emails()

                if emails:
                    travel_data = st.session_state.outlook_manager.extract_travel_info(emails)

                    # Add flights
                    for f in travel_data["flights"]:
                        st.session_state.flights.append(Flight(
                            f.get("airline", "Unknown"), f.get("flight_number", ""),
                            "", "", date.today(), time(0,0), date.today(), time(0,0),
                            f.get("confirmation", "")
                        ))

                    # Add hotels
                    for h in travel_data["hotels"]:
                        st.session_state.hotels.append(Hotel(
                            h.get("hotel_name", "Unknown"), "",
                            date.today(), date.today(),
                            h.get("confirmation", "")
                        ))

                    # Add tours
                    for t in travel_data["tours"]:
                        st.session_state.tours.append(Tour(
                            t.get("tour_name", "Unknown"), "",
                            date.today(), time(0,0),
                            t.get("confirmation", "")
                        ))

                    st.success(f"✅ Imported: {len(travel_data['flights'])} flights, {len(travel_data['hotels'])} hotels, {len(travel_data['tours'])} tours")
                else:
                    st.warning("No emails found")

        if st.button("Disconnect"):
            st.session_state.outlook_connected = False
            st.session_state.outlook_manager.access_token = None
            st.rerun()

# ============================================
# MAIN TABS
# ============================================
tab1, tab2, tab3, tab4 = st.tabs(["✈️ Flights", "🏨 Hotels", "🎯 Tours", "📋 Summary"])

with tab1:
    st.header("✈️ Flight Details")

    with st.form("add_flight"):
        col1, col2 = st.columns(2)

        with col1:
            airline = st.text_input("Airline", placeholder="e.g., United Airlines")
            flight_number = st.text_input("Flight Number", placeholder="e.g., UA1234")
            departure = st.text_input("Departure City", placeholder="e.g., New York (JFK)")
            departure_date = st.date_input("Departure Date", key="flight_dep_date")
            departure_time_val = st.time_input("Departure Time", key="flight_dep_time")

        with col2:
            arrival = st.text_input("Arrival City", placeholder="e.g., Paris (CDG)")
            arrival_date = st.date_input("Arrival Date", key="flight_arr_date")
            arrival_time_val = st.time_input("Arrival Time", key="flight_arr_time")
            confirmation = st.text_input("Confirmation Number", placeholder="e.g., ABC123")

        submitted = st.form_submit_button("Add Flight ✈️")

        if submitted and airline and flight_number:
            flight = Flight(airline, flight_number, departure, arrival,
                          departure_date, departure_time_val, arrival_date, arrival_time_val, confirmation)
            st.session_state.flights.append(flight)
            st.success(f"✅ Flight {airline} {flight_number} added!")

    if st.session_state.flights:
        st.subheader(f"📋 {len(st.session_state.flights)} Flight(s)")
        df = pd.DataFrame([f.to_dict() for f in st.session_state.flights])
        st.dataframe(df, use_container_width=True, hide_index=True)

        if st.button("Clear Flights"):
            st.session_state.flights = []
            st.rerun()
    else:
        st.info("No flights added yet.")

with tab2:
    st.header("🏨 Hotel Details")

    with st.form("add_hotel"):
        col1, col2 = st.columns(2)

        with col1:
            hotel_name = st.text_input("Hotel Name", placeholder="e.g., Hilton Paris")
            address = st.text_input("Address", placeholder="e.g., 123 Champs-Élysées")
            check_in = st.date_input("Check-in Date", key="hotel_checkin")

        with col2:
            check_out = st.date_input("Check-out Date", key="hotel_checkout")
            hotel_confirmation = st.text_input("Confirmation Number", placeholder="e.g., HTL789")

        submit_hotel = st.form_submit_button("Add Hotel 🏨")

        if submit_hotel and hotel_name:
            hotel = Hotel(hotel_name, address, check_in, check_out, hotel_confirmation)
            st.session_state.hotels.append(hotel)
            st.success(f"✅ {hotel_name} added!")

    if st.session_state.hotels:
        st.subheader(f"📋 {len(st.session_state.hotels)} Hotel(s)")
        df = pd.DataFrame([h.to_dict() for h in st.session_state.hotels])
        st.dataframe(df, use_container_width=True, hide_index=True)

        if st.button("Clear Hotels"):
            st.session_state.hotels = []
            st.rerun()
    else:
        st.info("No hotels added yet.")

with tab3:
    st.header("🎯 Tour & Activity Details")

    with st.form("add_tour"):
        col1, col2 = st.columns(2)

        with col1:
            tour_name = st.text_input("Tour/Activity Name", placeholder="e.g., Eiffel Tower Visit")
            tour_location = st.text_input("Location", placeholder="e.g., Paris, France")

        with col2:
            tour_date = st.date_input("Date", key="tour_date")
            tour_time = st.time_input("Time", key="tour_time")
            tour_confirmation = st.text_input("Confirmation Number", placeholder="e.g., TOUR456")

        submit_tour = st.form_submit_button("Add Tour 🎯")

        if submit_tour and tour_name:
            tour = Tour(tour_name, tour_location, tour_date, tour_time, tour_confirmation)
            st.session_state.tours.append(tour)
            st.success(f"✅ {tour_name} added!")

    if st.session_state.tours:
        st.subheader(f"📋 {len(st.session_state.tours)} Tour(s)")
        df = pd.DataFrame([t.to_dict() for t in st.session_state.tours])
        st.dataframe(df, use_container_width=True, hide_index=True)

        if st.button("Clear Tours"):
            st.session_state.tours = []
            st.rerun()
    else:
        st.info("No tours added yet.")

with tab4:
    st.header("📋 Complete Travel Summary")

    col1, col2, col3 = st.columns(3)
    col1.metric("✈️ Flights", len(st.session_state.flights))
    col2.metric("🏨 Hotels", len(st.session_state.hotels))
    col3.metric("🎯 Tours", len(st.session_state.tours))

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

        if all_data:
            df_export = pd.DataFrame(all_data)
            csv = df_export.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "travel_plan.csv", "text/csv")
        else:
            st.warning("No data to export!")
