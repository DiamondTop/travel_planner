import streamlit as st
import pandas as pd
from datetime import datetime, date, time
from typing import List, Dict, Optional
import json

# ============================================
# CONFIGURATION
# ============================================
st.set_page_config(
    page_title="Travel Planner",
    page_icon="✈️",
    layout="wide"
)

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
# SESSION STATE MANAGEMENT
# ============================================
if 'flights' not in st.session_state:
    st.session_state.flights = []
if 'hotels' not in st.session_state:
    st.session_state.hotels = []
if 'tours' not in st.session_state:
    st.session_state.tours = []
if 'outlook_connected' not in st.session_state:
    st.session_state.outlook_connected = False

# ============================================
# SIDEBAR - SETTINGS
# ============================================
with st.sidebar:
    st.header("⚙️ Outlook Integration")

    st.info("""
    **To enable Outlook import:**

    1. Go to [Azure Portal](https://portal.azure.com)
    2. Register an app
    3. Add API permissions: `Mail.Read`
    4. Get credentials (Client ID, Secret, Tenant ID)

    Contact a developer for full implementation.
    """)

    # Simple toggle to simulate connection
    outlook_enabled = st.toggle("Enable Outlook (Coming Soon)")

    if outlook_enabled:
        st.warning("Outlook integration requires additional setup. Use manual entry for now.")

    st.divider()

    # Theme toggle
    if st.toggle("Dark Mode"):
        st.markdown("""
        <style>
        .stApp {background-color: #1e1e1e; color: white;}
        </style>
        """, unsafe_allow_html=True)

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

    # Display flights
    if st.session_state.flights:
        st.subheader(f"📋 {len(st.session_state.flights)} Flight(s)")
        df = pd.DataFrame([f.to_dict() for f in st.session_state.flights])
        st.dataframe(df, use_container_width=True, hide_index=True)

        if st.button("Clear All Flights", key="clear_flights"):
            st.session_state.flights = []
            st.rerun()
    else:
        st.info("No flights added yet. Use the form above to add flights.")

# --------------------------------------------
# HOTELS TAB
# --------------------------------------------
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
        st.info("No hotels added yet. Use the form above to add hotels.")

# --------------------------------------------
# TOURS TAB
# --------------------------------------------
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
        st.info("No tours added yet. Use the form above to add tours.")

# --------------------------------------------
# SUMMARY TAB
# --------------------------------------------
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

    # Flight Summary
    if st.session_state.flights:
        st.subheader("✈️ Flights")
        for i, flight in enumerate(st.session_state.flights, 1):
            with st.expander(f"{i}. {flight.airline} {flight.flight_number}"):
                st.write(f"**Route:** {flight.departure} → {flight.arrival}")
                st.write(f"**Departure:** {flight.departure_date} at {flight.departure_time}")
                st.write(f"**Arrival:** {flight.arrival_date} at {flight.arrival_time}")
                if flight.confirmation_number:
                    st.write(f"**Confirmation:** {flight.confirmation_number}")

    # Hotel Summary
    if st.session_state.hotels:
        st.subheader("🏨 Hotels")
        for i, hotel in enumerate(st.session_state.hotels, 1):
            with st.expander(f"{i}. {hotel.name}"):
                st.write(f"**Address:** {hotel.address}")
                st.write(f"**Check-in:** {hotel.check_in}")
                st.write(f"**Check-out:** {hotel.check_out}")
                if hotel.confirmation_number:
                    st.write(f"**Confirmation:** {hotel.confirmation_number}")

    # Tour Summary
    if st.session_state.tours:
        st.subheader("🎯 Tours & Activities")
        for i, tour in enumerate(st.session_state.tours, 1):
            with st.expander(f"{i}. {tour.name}"):
                st.write(f"**Location:** {tour.location}")
                st.write(f"**Date:** {tour.tour_date} at {tour.tour_time}")
                if tour.confirmation_number:
                    st.write(f"**Confirmation:** {tour.confirmation_number}")

    # Export option
    st.divider()
    st.subheader("💾 Export Travel Plan")

    col1, col2 = st.columns(2)

    with col1:
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
                st.warning("No data to export. Add some travel details first!")

    with col2:
        if st.button("Save to JSON 📄"):
            data = {
                "flights": [f.to_dict() for f in st.session_state.flights],
                "hotels": [h.to_dict() for h in st.session_state.hotels],
                "tours": [t.to_dict() for t in st.session_state.tours]
            }
            json_str = json.dumps(data, indent=2, default=str)
            st.download_button(
                label="Download JSON",
                data=json_str,
                file_name="travel_plan.json",
                mime="application/json"
            )
