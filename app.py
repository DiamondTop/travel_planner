import streamlit as st
import pandas as pd
from datetime import datetime, date, time
from typing import List, Dict, Optional
import json
import re
import requests

# Microsoft Authentication Library
import msal

# ============================================
# CONFIGURATION
# ============================================
st.set_page_config(
    page_title="Travel Planner",
    page_icon="✈️",
    layout="wide"
)

# ============================================
# OUTLOOK INTEGRATION CLASS
# ============================================
class OutlookManager:
    def __init__(self):
        self.client_id = None
        self.tenant_id = "common"  # Use "common" for multi-tenant
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scopes = ["Mail.Read", "User.Read"]
        self.app = None
        self.access_token = None

    def configure(self, client_id: str):
        """Initialize MSAL app"""
        self.client_id = client_id
        self.app = msal.PublicClientApplication(
            self.client_id,
            authority=self.authority
        )

    def get_token_interactive(self):
        """Get token via interactive login (opens browser)"""
        if not self.app:
            st.error("Please configure client ID first")
            return None

        # Try to get token from cache
        accounts = self.app.get_accounts()
        if accounts:
            result = self.app.acquire_token_silent(
                self.scopes,
                account=accounts[0]
            )
            if result:
                return result["access_token"]

        # If no cached token, do interactive login
        result = self.app.initiate_device_flow(scopes=self.scopes)

        if "user_code" in result:
            st.markdown(f"""
            ### 🔐 Login Required
            1. Go to: [https://microsoft.com/devicelogin](https://microsoft.com/devicelogin)
            2. Enter code: **{result["user_code"]}**
            3. Sign in with your Outlook account
            """)

            # Wait for token
            with st.spinner("Waiting for login..."):
                while True:
                    result = self.app.acquire_token_by_device_flow(result)
                    if "access_token" in result:
                        return result["access_token"]
                    elif "error" in result:
                        st.error(f"Login failed: {result.get('error_description', 'Unknown error')}")
                        return None

    def fetch_emails(self, search_query: str = None) -> List[Dict]:
        """Fetch emails from Outlook"""
        if not self.access_token:
            return []

        headers = {"Authorization": f"Bearer {self.access_token}"}

        # Build query
        if search_query:
            filter_query = f"$filter=subject eq '{search_query}'"
        else:
            filter_query = ""

        # Get emails (limit to recent 50)
        endpoint = f"https://graph.microsoft.com/v1.0/me/messages?$top=50"

        try:
            response = requests.get(endpoint, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return data.get("value", [])
            else:
                st.error(f"Error fetching emails: {response.status_code}")
                return []
        except Exception as e:
            st.error(f"Error: {str(e)}")
            return []

    def extract_travel_info(self, emails: List[Dict]) -> Dict:
        """Extract flight, hotel, tour info from emails"""
        flights = []
        hotels = []
        tours = []

        # Keywords to search
        flight_keywords = ["flight", "airline", "boarding", "departure", "arrival"]
        hotel_keywords = ["hotel", "accommodation", "check-in", "check-out", "reservation"]
        tour_keywords = ["tour", "excursion", "activity", "ticket", "admission"]

        for email in emails:
            subject = email.get("subject", "").lower()
            body = email.get("body", {}).get("content", "").lower()
            text = subject + " " + body

            # Extract flight info
            if any(kw in text for kw in flight_keywords):
                flight_info = self._parse_flight_email(email)
                if flight_info:
                    flights.append(flight_info)

            # Extract hotel info
            elif any(kw in text for kw in hotel_keywords):
                hotel_info = self._parse_hotel_email(email)
                if hotel_info:
                    hotels.append(hotel_info)

            # Extract tour info
            elif any(kw in text for kw in tour_keywords):
                tour_info = self._parse_tour_email(email)
                if tour_info:
                    tours.append(tour_info)

        return {
            "flights": flights,
            "hotels": hotels,
            "tours": tours
        }

    def _parse_flight_email(self, email: str) -> Optional[Dict]:
        """Parse flight confirmation from email"""
        text = email.get("subject", "") + " " + email.get("body", {}).get("content", "")

        # Extract flight number (e.g., UA1234, AA567)
        flight_match = re.search(r'([A-Z]{2}\d{3,4})', text)
        flight_number = flight_match.group(1) if flight_match else "Unknown"

        # Extract date
        date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', text)
        flight_date = date_match.group(1) if date_match else ""

        # Extract confirmation
        conf_match = re.search(r'confirmation[:\s]*([A-Z0-9]{5,})', text, re.IGNORECASE)
        confirmation = conf_match.group(1) if conf_match else ""

        return {
            "airline": "Extracted",
            "flight_number": flight_number,
            "date": flight_date,
            "confirmation": confirmation,
            "subject": email.get("subject", "")
        }

    def _parse_hotel_email(self, email: Dict) -> Optional[Dict]:
        """Parse hotel confirmation from email"""
        text = email.get("subject", "") + " " + email.get("body", {}).get("content", "")

        # Extract hotel name (often in subject)
        hotel_name = email.get("subject", "").replace("Confirmation", "").replace("Booking", "").strip()

        # Extract dates
        date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})\s*[-to]+\s*(\d{1,2}/\d{1,2}/\d{2,4})', text)
        check_in = date_match.group(1) if date_match else ""
        check_out = date_match.group(2) if date_match else ""

        # Extract confirmation
        conf_match = re.search(r'confirmation[:\s]*([A-Z0-9]{5,})', text, re.IGNORECASE)
        confirmation = conf_match.group(1) if conf_match else ""

        return {
            "hotel_name": hotel_name,
            "check_in": check_in,
            "check_out": check_out,
            "confirmation": confirmation,
            "subject": email.get("subject", "")
        }

    def _parse_tour_email(self, email: Dict) -> Optional[Dict]:
        """Parse tour/activity confirmation from email"""
        text = email.get("subject", "") + " " + email.get("body", {}).get("content", "")

        # Extract tour name
        tour_name = email.get("subject", "").replace("Confirmation", "").replace("Ticket", "").strip()

        # Extract date
        date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', text)
        tour_date = date_match.group(1) if date_match else ""

        # Extract confirmation
        conf_match = re.search(r'confirmation[:\s]*([A-Z0-9]{5,})', text, re.IGNORECASE)
        confirmation = conf_match.group(1) if conf_match else ""

        return {
            "tour_name": tour_name,
            "date": tour_date,
            "confirmation": confirmation,
            "subject": email.get("subject", "")
        }

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
# SIDEBAR - OUTLOOK SETTINGS
# ============================================
with st.sidebar:
    st.header("📧 Outlook Integration")

    st.markdown("### Step 1: Enter Client ID")
    client_id = st.text_input(
        "Azure Client ID", 
        type="password",
        help="Get this from Azure Portal > App Registrations"
    )

    if client_id:
        st.session_state.outlook_manager.configure(client_id)
        st.success("✅ Client ID configured")

    st.markdown("### Step 2: Connect to Outlook")

    if st.button("🔗 Connect to Outlook", type="primary"):
        if not client_id:
            st.error("Please enter Client ID first")
        else:
            with st.spinner("Opening login window..."):
                token = st.session_state.outlook_manager.get_token_interactive()
                if token:
                    st.session_state.outlook_manager.access_token = token
                    st.session_state.outlook_connected = True
                    st.success("✅ Connected to Outlook!")
                else:
                    st.error("Failed to connect")

    if st.session_state.outlook_connected:
        st.markdown("### Step 3: Import Emails")

        search_term = st.text_input("Search emails (optional)", placeholder="e.g., flight, hotel")

        if st.button("📥 Import Travel Emails"):
            with st.spinner("Fetching emails..."):
                emails = st.session_state.outlook_manager.fetch_emails()
                if emails:
                    travel_data = st.session_state.outlook_manager.extract_travel_info(emails)

                    # Add extracted flights
                    for f in travel_data["flights"]:
                        st.session_state.flights.append(Flight(
                            f.get("airline", "Unknown"),
                            f.get("flight_number", "Unknown"),
                            "", "",  # departure/arrival
                            date.today(), time(0,0),
                            date.today(), time(0,0),
                            f.get("confirmation", "")
                        ))

                    # Add extracted hotels
                    for h in travel_data["hotels"]:
                        st.session_state.hotels.append(Hotel(
                            h.get("hotel_name", "Unknown Hotel"),
                            "",
                            date.today(), date.today(),
                            h.get("confirmation", "")
                        ))

                    # Add extracted tours
                    for t in travel_data["tours"]:
                        st.session_state.tours.append(Tour(
                            t.get("tour_name", "Unknown Tour"),
                            "",
                            date.today(), time(0,0),
                            t.get("confirmation", "")
                        ))

                    st.success(f"✅ Imported {len(travel_data['flights'])} flights, {len(travel_data['hotels'])} hotels, {len(travel_data['tours'])} tours")
                else:
                    st.warning("No emails found")

    st.divider()

    if st.button("Disconnect Outlook"):
        st.session_state.outlook_connected = False
        st.session_state.outlook_manager.access_token = None
        st.rerun()

# ============================================
# MAIN TABS
# ============================================
tab1, tab2, tab3, tab4 = st.tabs(["✈️ Flights", "🏨 Hotels", "🎯 Tours", "📋 Summary"])

# FLIGHTS TAB
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
            flight = Flight(
                airline, flight_number,
                departure, arrival,
                departure_date, departure_time_val,
                arrival_date, arrival_time_val,
                confirmation
            )
            st.session_state.flights.append(flight)
            st.success(f"✅ Flight {airline} {flight_number} added!")

    if st.session_state.flights:
        st.subheader(f"📋 {len(st.session_state.flights)} Flight(s)")
        df = pd.DataFrame([f.to_dict() for f in st.session_state.flights])
        st.dataframe(df, use_container_width=True, hide_index=True)

        if st.button("Clear All Flights", key="clear_flights"):
            st.session_state.flights = []
            st.rerun()
    else:
        st.info("No flights added yet. Add manually or import from Outlook.")

# HOTELS TAB
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

        if st.button("Clear All Hotels", key="clear_hotels"):
            st.session_state.hotels = []
            st.rerun()
    else:
        st.info("No hotels added yet. Add manually or import from Outlook.")

# TOURS TAB
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

        if st.button("Clear All Tours", key="clear_tours"):
            st.session_state.tours = []
            st.rerun()
    else:
        st.info("No tours added yet. Add manually or import from Outlook.")

# SUMMARY TAB
with tab4:
    st.header("📋 Complete Travel Summary")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("✈️ Flights", len(st.session_state.flights))
    with col2:
        st.metric("🏨 Hotels", len(st.session_state.hotels))
    with col3:
        st.metric("🎯 Tours", len(st.session_state.tours))

    st.divider()

    if st.session_state.flights:
        st.subheader("✈️ Flights")
        for i, flight in enumerate(st.session_state.flights, 1):
            with st.expander(f"{i}. {flight.airline} {flight.flight_number}"):
                st.write(f"**Route:** {flight.departure} → {flight.arrival}")
                st.write(f"**Departure:** {flight.departure_date} at {flight.departure_time}")
                st.write(f"**Arrival:** {flight.arrival_date} at {flight.arrival_time}")
                if flight.confirmation_number:
                    st.write(f"**Confirmation:** {flight.confirmation_number}")

    if st.session_state.hotels:
        st.subheader("🏨 Hotels")
        for i, hotel in enumerate(st.session_state.hotels, 1):
            with st.expander(f"{i}. {hotel.name}"):
                st.write(f"**Address:** {hotel.address}")
                st.write(f"**Check-in:** {hotel.check_in}")
                st.write(f"**Check-out:** {hotel.check_out}")
                if hotel.confirmation_number:
                    st.write(f"**Confirmation:** {hotel.confirmation_number}")

    if st.session_state.tours:
        st.subheader("🎯 Tours & Activities")
        for i, tour in enumerate(st.session_state.tours, 1):
            with st.expander(f"{i}. {tour.name}"):
                st.write(f"**Location:** {tour.location}")
                st.write(f"**Date:** {tour.tour_date} at {tour.tour_time}")
                if tour.confirmation_number:
                    st.write(f"**Confirmation:** {tour.confirmation_number}")

    st.divider()
    st.subheader("💾 Export Travel Plan")

    if st.button("Export to CSV 📊"):
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
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name="travel_plan.csv",
                mime="text/csv"
            )
        else:
            st.warning("No data to export!")
