import streamlit as st
import pandas as pd
from datetime import datetime
import microsoft.graph as graph
import os
from typing import List, Dict, Optional

# ============================================
# CONFIGURATION
# ============================================
st.set_page_config(
    page_title="Travel Planner",
    page_icon="✈️",
    layout="wide"
)

# ============================================
# OUTLOOK API CONFIGURATION (PLACEHOLDER)
# ============================================
class OutlookClient:
    def __init__(self, client_id: str, client_secret: str, tenant_id: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.settings_configured = False

    def configure(self):
        """Initialize Outlook API client"""
        # This is a placeholder - you need to set up proper Azure app registration
        # and obtain valid credentials
        if not all([self.client_id, self.client_secret, self.tenant_id]):
            return False

        # Code for actual Outlook API connection would go here
        # Using Microsoft Graph API
        self.settings_configured = True
        return True

    def fetch_emails(self, subject_filter: str = None) -> List[Dict]:
        """Fetch emails from Outlook"""
        # Placeholder - implement actual API calls to Microsoft Graph
        # Example: https://docs.microsoft.com/en-us/graph/api/user-list-messages
        return []

# ============================================
# TRAVEL DATA CLASSES
# ============================================
class Flight:
    def __init__(self, airline: str, flight_number: str, 
                 departure: str, arrival: str, 
                 departure_time: str, arrival_time: str,
                 confirmation_number: str = ""):
        self.airline = airline
        self.flight_number = flight_number
        self.departure = departure
        self.arrival = arrival
        self.departure_time = departure_time
        self.arrival_time = arrival_time
        self.confirmation_number = confirmation_number

    def to_dict(self):
        return {
            "Airline": self.airline,
            "Flight #": self.flight_number,
            "From": self.departure,
            "To": self.arrival,
            "Departure": self.departure_time,
            "Arrival": self.arrival_time,
            "Confirmation": self.confirmation_number
        }

class Hotel:
    def __init__(self, name: str, address: str, 
                 check_in: str, check_out: str,
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
                 date: str, time: str, 
                 confirmation_number: str = ""):
        self.name = name
        self.location = location
        self.date = date
        self.time = time
        self.confirmation_number = confirmation_number

    def to_dict(self):
        return {
            "Tour": self.name,
            "Location": self.location,
            "Date": self.date,
            "Time": self.time,
            "Confirmation": self.confirmation_number
        }

# ============================================
# SESSION STATE MANAGEMENT
# ============================================
if 'flights' not in st.session_state:
    st.session_state.flights = []
if 'hotels' not in st.session_state:
    st.session_state.hotels = []
if 'tours' not in st.session_state:
    st.session_state.tours = []

# ============================================
# SIDEBAR - OUTLOOK SETTINGS
# ============================================
with st.sidebar:
    st.header("⚙️ Outlook Integration")

    st.info("""
    **Setup Instructions:**
    1. Go to Azure Portal
    2. Register a new app
    3. Add API permissions (Mail.Read)
    4. Get your credentials
    """)

    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Client Secret", type="password")
    tenant_id = st.text_input("Tenant ID", type="password")

    if st.button("Connect to Outlook"):
        if client_id and client_secret and tenant_id:
            st.session_state.outlook_client = OutlookClient(
                client_id, client_secret, tenant_id
            )
            st.success("Connected to Outlook!")
        else:
            st.error("Please fill in all credentials")

    st.divider()

    if st.button("Import from Outlook Emails"):
        st.warning("""
        This feature requires:
        - Valid Azure credentials
        - Proper API permissions
        - Email search implementation

        Contact a developer for full implementation.
        """)

# ============================================
# MAIN TABS
# ============================================
tab1, tab2, tab3, tab4 = st.tabs(["✈️ Flights", "🏨 Hotels", "🎯 Tours", "📋 Summary"])

# --------------------------------------------
# FLIGHTS TAB
# --------------------------------------------
with tab1:
    st.header("✈️ Flight Details")

    with st.form("add_flight"):
        col1, col2 = st.columns(2)

        with col1:
            airline = st.text_input("Airline")
            flight_number = st.text_input("Flight Number")
            departure = st.text_input("Departure City")
            departure_date = st.date_input("Departure Date")
            departure_time = st.time_input("Departure Time")

        with col2:
            arrival = st.text_input("Arrival City")
            arrival_date = st.date_input("Arrival Date")
            arrival_time = st.time_input("Arrival Time")
            confirmation = st.text_input("Confirmation Number")

        submitted = st.form_submit_button("Add Flight")

        if submitted and airline:
            flight = Flight(
                airline, flight_number,
                departure, arrival,
                f"{departure_date} {departure_time}",
                f"{arrival_date} {arrival_time}",
                confirmation
            )
            st.session_state.flights.append(flight)
            st.success("Flight added!")

    # Display flights
    if st.session_state.flights:
        df = pd.DataFrame([f.to_dict() for f in st.session_state.flights])
        st.dataframe(df, use_container_width=True)

        if st.button("Clear All Flights"):
            st.session_state.flights = []
            st.rerun()

# --------------------------------------------
# HOTELS TAB
# --------------------------------------------
with tab2:
    st.header("🏨 Hotel Details")

    with st.form("add_hotel"):
        col1, col2 = st.columns(2)

        with col1:
            hotel_name = st.text_input("Hotel Name")
            address = st.text_input("Address")
            check_in = st.date_input("Check-in Date")

        with col2:
            check_out = st.date_input("Check-out Date")
            hotel_confirmation = st.text_input("Confirmation Number")

        submit_hotel = st.form_submit_button("Add Hotel")

        if submit_hotel and hotel_name:
            hotel = Hotel(hotel_name, address, check_in, check_out, hotel_confirmation)
            st.session_state.hotels.append(hotel)
            st.success("Hotel added!")

    if st.session_state.hotels:
        df = pd.DataFrame([h.to_dict() for h in st.session_state.hotels])
        st.dataframe(df, use_container_width=True)

        if st.button("Clear All Hotels"):
            st.session_state.hotels = []
            st.rerun()

# --------------------------------------------
# TOURS TAB
# --------------------------------------------
with tab3:
    st.header("🎯 Tour & Activity Details")

    with st.form("add_tour"):
        col1, col2 = st.columns(2)

        with col1:
            tour_name = st.text_input("Tour/Activity Name")
            tour_location = st.text_input("Location")

        with col2:
            tour_date = st.date_input("Date")
            tour_time = st.time_input("Time")
            tour_confirmation = st.text_input("Confirmation Number")

        submit_tour = st.form_submit_button("Add Tour")

        if submit_tour and tour_name:
            tour = Tour(tour_name, tour_location, tour_date, tour_time, tour_confirmation)
            st.session_state.tours.append(tour)
            st.success("Tour added!")

    if st.session_state.tours:
        df = pd.DataFrame([t.to_dict() for t in st.session_state.tours])
        st.dataframe(df, use_container_width=True)

        if st.button("Clear All Tours"):
            st.session_state.tours = []
            st.rerun()

# --------------------------------------------
# SUMMARY TAB
# --------------------------------------------
with tab4:
    st.header("📋 Complete Travel Summary")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Flights", len(st.session_state.flights))
    with col2:
        st.metric("Total Hotels", len(st.session_state.hotels))
    with col3:
        st.metric("Total Tours", len(st.session_state.tours))

    st.divider()

    if st.session_state.flights:
        st.subheader("✈️ Flights")
        for i, flight in enumerate(st.session_state.flights, 1):
            st.write(f"**{i}. {flight.airline} {flight.flight_number}**")
            st.write(f"   {flight.departure} → {flight.arrival}")
            st.write(f"   {flight.departure_time} - {flight.arrival_time}")
            if flight.confirmation_number:
                st.write(f"   Confirmation: {flight.confirmation_number}")
            st.write("---")

    if st.session_state.hotels:
        st.subheader("🏨 Hotels")
        for i, hotel in enumerate(st.session_state.hotels, 1):
            st.write(f"**{i}. {hotel.name}**")
            st.write(f"   {hotel.address}")
            st.write(f"   Check-in: {hotel.check_in} | Check-out: {hotel.check_out}")
            if hotel.confirmation_number:
                st.write(f"   Confirmation: {hotel.confirmation_number}")
            st.write("---")

    if st.session_state.tours:
        st.subheader("🎯 Tours & Activities")
        for i, tour in enumerate(st.session_state.tours, 1):
            st.write(f"**{i}. {tour.name}**")
            st.write(f"   {tour.location}")
            st.write(f"   {tour.date} at {tour.time}")
            if tour.confirmation_number:
                st.write(f"   Confirmation: {tour.confirmation_number}")
            st.write("---")

    # Export option
    st.divider()
    if st.button("Export to CSV"):
        # Create combined dataframe
        all_data = []
        for f in st.session_state.flights:
            all_data.append({"Type": "Flight", **f.to_dict()})
        for h in st.session_state.hotels:
            all_data.append({"Type": "Hotel", **h.to_dict()})
        for t in st.session_state.tours:
            all_data.append({"Type": "Tour", **t.to_dict()})

        if all_data:
            df_export = pd.DataFrame(all_data)
            csv = df_export.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name="travel_plan.csv",
                mime="text/csv"
            )
