import streamlit as st
import pandas as pd
from datetime import datetime, date, time
from typing import List, Dict
import json
import re
import requests
import imaplib
import email
from email import policy
from email.header import decode_header

# ============================================
# CONFIGURATION
# ============================================
st.set_page_config(
    page_title="Travel Planner",
    page_icon="✈️",
    layout="wide"
)

IMAP_SERVERS = {
    "Gmail":             "imap.gmail.com",
    "Outlook / Hotmail": "imap-mail.outlook.com",
}

TRAVEL_KEYWORDS = [
    "booking confirmed", "flight confirmation", "hotel reservation",
    "check-in", "your booking", "itinerary", "reservation confirmation",
    "flybus", "airport transfer", "shuttle", "bus pickup", "airport pickup",
    "tour confirmation", "voucher", "e-ticket",
]

# ============================================
# AI EXTRACTION
# ============================================
def ai_extract_travel(email_text: str, subject: str = "") -> Dict:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""Extract travel booking details from the email below.

Email subject: {subject}
Email body:
{email_text[:5000]}

Rules:
- Convert dates to ISO format: YYYY-MM-DDTHH:MM:00
- Extract ALL flight legs including return flights
- For transfers: extract bus, shuttle, taxi, Flybus, or airport pickup bookings.
  Use "pickup_location" for boarding point and "dropoff_location" for destination.
- Extract hotel name, address, check-in, check-out
- Use exact values from the email

Return ONLY this JSON, no explanation:
{{
  "flights": [{{"airline":"","flight_number":"","departure_city":"","arrival_city":"","departure_time":"","arrival_time":"","confirmation":""}}],
  "hotels":  [{{"hotel_name":"","address":"","check_in":"","check_out":"","confirmation":""}}],
  "tours":   [{{"tour_name":"","date":"","time":"","confirmation":""}}],
  "transfers":[{{"service_name":"","pickup_location":"","dropoff_location":"","transfer_date":"","transfer_time":"","passengers":0,"confirmation":""}}]
}}

If nothing found return: {{"flights":[],"hotels":[],"tours":[],"transfers":[]}}"""

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json={
                "model": "openai/gpt-oss-120b:free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0
            },
            timeout=30
        )

        if response.status_code != 200:
            st.warning(f"AI error: {response.text[:200]}")
            return {"flights": [], "hotels": [], "tours": [], "transfers": []}

        content = response.json()["choices"][0]["message"]["content"]
        content = re.sub(r'```json|```', '', content).strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            result["flights"]   = [f for f in result.get("flights",   []) if f.get("airline") or f.get("flight_number")]
            result["hotels"]    = [h for h in result.get("hotels",    []) if h.get("hotel_name")]
            result["tours"]     = [t for t in result.get("tours",     []) if t.get("tour_name")]
            result["transfers"] = [x for x in result.get("transfers", []) if x.get("service_name") or x.get("pickup_location")]
            return result

    except Exception as e:
        st.warning(f"AI exception: {e}")

    return {"flights": [], "hotels": [], "tours": [], "transfers": []}


# ============================================
# IMAP EMAIL MANAGER
# ============================================
class IMAPManager:
    def __init__(self):
        self.conn = None

    def connect(self, provider: str, user_email: str, app_password: str) -> bool:
        try:
            server = IMAP_SERVERS[provider]
            self.conn = imaplib.IMAP4_SSL(server, 993)
            self.conn.login(user_email, app_password)
            return True
        except imaplib.IMAP4.error as e:
            st.session_state["imap_error"] = str(e)
            return False
        except Exception as e:
            st.session_state["imap_error"] = str(e)
            return False

    def disconnect(self):
        try:
            if self.conn:
                self.conn.logout()
        except:
            pass
        self.conn = None

    def fetch_travel_emails(self, max_emails: int = 60) -> List[Dict]:
        if not self.conn:
            return []

        self.conn.select("INBOX")
        all_ids = set()

        for kw in TRAVEL_KEYWORDS:
            try:
                _, msg_ids = self.conn.search(None, f'TEXT "{kw}"')
                if msg_ids and msg_ids[0]:
                    for mid in msg_ids[0].split():
                        all_ids.add(mid)
                if len(all_ids) >= max_emails:
                    break
            except:
                continue

        emails_out = []
        seen_subjects = set()

        for mid in list(all_ids)[:max_emails]:
            try:
                _, msg_data = self.conn.fetch(mid, "(RFC822)")
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw, policy=policy.default)

                # Decode subject
                subject_raw = msg.get("Subject", "")
                subject_parts = decode_header(subject_raw)
                subject = ""
                for part, enc in subject_parts:
                    if isinstance(part, bytes):
                        subject += part.decode(enc or "utf-8", errors="replace")
                    else:
                        subject += str(part)

                if subject in seen_subjects:
                    continue
                seen_subjects.add(subject)

                # Extract plain text body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        ct = part.get_content_type()
                        if ct == "text/plain":
                            body += part.get_content()
                        elif ct == "text/html" and not body:
                            html = part.get_content()
                            body = re.sub(r'<[^>]+>', ' ', html)
                            body = re.sub(r'\s+', ' ', body).strip()
                else:
                    body = msg.get_content()

                emails_out.append({"subject": subject, "body": body})

            except Exception:
                continue

        return emails_out

    def extract_travel_info(self, emails: List[Dict]) -> Dict:
        flights, hotels, tours, transfers = [], [], [], []

        for em in emails:
            subject = em.get("subject", "")
            body    = em.get("body", "")
            full    = subject + "\n" + body

            lower = full.lower()
            if not any(k in lower for k in TRAVEL_KEYWORDS):
                continue

            st.write(f"📧 Processing: **{subject[:70]}**")
            ai_data = ai_extract_travel(full, subject=subject)

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
        self.airline            = airline
        self.flight_number      = flight_number
        self.departure          = departure
        self.arrival            = arrival
        self.departure_date     = departure_date
        self.departure_time     = departure_time_val
        self.arrival_date       = arrival_date
        self.arrival_time       = arrival_time_val
        self.confirmation_number = confirmation_number

    def to_dict(self):
        return {
            "Airline":      self.airline,
            "Flight #":     self.flight_number,
            "From":         self.departure,
            "To":           self.arrival,
            "Departure":    f"{self.departure_date} {self.departure_time.strftime('%H:%M')}",
            "Arrival":      f"{self.arrival_date} {self.arrival_time.strftime('%H:%M')}",
            "Confirmation": self.confirmation_number
        }


class Hotel:
    def __init__(self, name, address, check_in, check_out, confirmation_number=""):
        self.name                = name
        self.address             = address
        self.check_in            = check_in
        self.check_out           = check_out
        self.confirmation_number = confirmation_number

    def to_dict(self):
        return {
            "Hotel":        self.name,
            "Address":      self.address,
            "Check-in":     str(self.check_in),
            "Check-out":    str(self.check_out),
            "Confirmation": self.confirmation_number
        }


class Tour:
    def __init__(self, name, location, tour_date, tour_time, confirmation_number=""):
        self.name                = name
        self.location            = location
        self.tour_date           = tour_date
        self.tour_time           = tour_time
        self.confirmation_number = confirmation_number

    def to_dict(self):
        return {
            "Tour":         self.name,
            "Location":     self.location,
            "Date":         str(self.tour_date),
            "Time":         self.tour_time.strftime("%H:%M"),
            "Confirmation": self.confirmation_number
        }


class Transfer:
    def __init__(self, service_name, pickup_location, dropoff_location,
                 transfer_date, transfer_time, passengers=1, confirmation_number=""):
        self.service_name        = service_name
        self.pickup_location     = pickup_location
        self.dropoff_location    = dropoff_location
        self.transfer_date       = transfer_date
        self.transfer_time       = transfer_time
        self.passengers          = passengers
        self.confirmation_number = confirmation_number

    def to_dict(self):
        return {
            "Service":      self.service_name,
            "Pickup":       self.pickup_location,
            "Dropoff":      self.dropoff_location,
            "Date":         str(self.transfer_date),
            "Time":         self.transfer_time.strftime("%H:%M"),
            "Passengers":   self.passengers,
            "Confirmation": self.confirmation_number
        }


# ============================================
# SESSION STATE
# ============================================
defaults = {
    "flights":        [],
    "hotels":         [],
    "tours":          [],
    "transfers":      [],
    "imap_manager":   IMAPManager(),
    "imap_connected": False,
    "imap_error":     "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ============================================
# SIDEBAR — IMAP LOGIN
# ============================================
with st.sidebar:
    st.header("📧 Email Login")

    provider = st.selectbox("Email Provider", list(IMAP_SERVERS.keys()))

    instructions = {
        "Gmail": (
            "**Gmail setup (one-time):**\n"
            "1. Enable **2-Step Verification** in your Google Account\n"
            "2. Go to **Security → App Passwords**\n"
            "3. Generate a password for *Mail*\n"
            "4. Paste the 16-character code below"
        ),
        "Outlook / Hotmail": (
            "**Outlook setup (one-time):**\n"
            "1. Go to account.microsoft.com → **Security**\n"
            "2. Click **Advanced Security Options**\n"
            "3. Under *App Passwords*, click **Create**\n"
            "4. Paste the generated password below"
        ),
    }
    st.info(instructions[provider])

    user_email   = st.text_input("Email Address", placeholder="you@gmail.com")
    app_password = st.text_input("App Password", type="password",
                                 placeholder="16-character app password")

    if st.session_state.imap_error:
        st.error(f"🔴 {st.session_state.imap_error}")

    col_a, col_b = st.columns(2)

    with col_a:
        if not st.session_state.imap_connected:
            if st.button("🔗 Connect", use_container_width=True):
                if user_email and app_password:
                    with st.spinner("Connecting…"):
                        ok = st.session_state.imap_manager.connect(provider, user_email, app_password)
                    if ok:
                        st.session_state.imap_connected = True
                        st.session_state.imap_error = ""
                        st.rerun()
                else:
                    st.warning("Enter your email and app password first.")

    with col_b:
        if st.session_state.imap_connected:
            if st.button("Disconnect", use_container_width=True):
                st.session_state.imap_manager.disconnect()
                st.session_state.imap_connected = False
                st.rerun()

    if st.session_state.imap_connected:
        st.success("✅ Connected")
        st.divider()

        if st.button("📥 Import Travel Emails", use_container_width=True):
            with st.spinner("Scanning inbox for travel emails…"):
                raw_emails = st.session_state.imap_manager.fetch_travel_emails(max_emails=60)

            st.info(f"📬 {len(raw_emails)} relevant email(s) found")

            if raw_emails:
                with st.expander("Emails found"):
                    for e in raw_emails:
                        st.write(f"- {e['subject'][:80]}")

                with st.spinner("Extracting travel details with AI…"):
                    travel_data = st.session_state.imap_manager.extract_travel_info(raw_emails)

                st.info(f"✈️ {len(travel_data['flights'])} flight(s)")
                st.info(f"🏨 {len(travel_data['hotels'])} hotel(s)")
                st.info(f"🎯 {len(travel_data['tours'])} tour(s)")
                st.info(f"🚌 {len(travel_data['transfers'])} transfer(s)")

                # Flights
                for f in travel_data["flights"]:
                    dep_date = arr_date = date.today()
                    dep_t = arr_t = time(0, 0)
                    try:
                        dt = datetime.fromisoformat(f["departure_time"])
                        dep_date, dep_t = dt.date(), dt.time()
                    except: pass
                    try:
                        dt = datetime.fromisoformat(f["arrival_time"])
                        arr_date, arr_t = dt.date(), dt.time()
                    except: pass
                    st.session_state.flights.append(Flight(
                        f.get("airline","Unknown"), f.get("flight_number",""),
                        f.get("departure_city",""), f.get("arrival_city",""),
                        dep_date, dep_t, arr_date, arr_t, f.get("confirmation","")
                    ))

                # Hotels
                for h in travel_data["hotels"]:
                    ci = co = date.today()
                    try: ci = datetime.fromisoformat(h["check_in"]).date()
                    except: pass
                    try: co = datetime.fromisoformat(h["check_out"]).date()
                    except: pass
                    st.session_state.hotels.append(Hotel(
                        h.get("hotel_name","Unknown"), h.get("address",""),
                        ci, co, h.get("confirmation","")
                    ))

                # Tours
                for t in travel_data["tours"]:
                    td = date.today()
                    tt = time(0, 0)
                    try: td = datetime.fromisoformat(t["date"]).date()
                    except: pass
                    st.session_state.tours.append(Tour(
                        t.get("tour_name","Unknown"), "",
                        td, tt, t.get("confirmation","")
                    ))

                # Transfers
                for x in travel_data["transfers"]:
                    xd = date.today()
                    xt = time(0, 0)
                    try: xd = datetime.fromisoformat(x["transfer_date"]).date()
                    except: pass
                    try: xt = datetime.fromisoformat(x["transfer_time"]).time()
                    except: pass
                    st.session_state.transfers.append(Transfer(
                        x.get("service_name","Unknown"),
                        x.get("pickup_location",""),
                        x.get("dropoff_location",""),
                        xd, xt,
                        x.get("passengers", 1),
                        x.get("confirmation","")
                    ))

                st.success("✅ Import complete!")
            else:
                st.warning("No travel emails found in your inbox.")


# ============================================
# MAIN TABS
# ============================================
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["✈️ Flights", "🏨 Hotels", "🎯 Tours", "🚌 Transfers", "📋 Summary"]
)

# ---- FLIGHTS ----
with tab1:
    st.header("✈️ Flight Details")
    with st.form("add_flight"):
        col1, col2 = st.columns(2)
        with col1:
            airline            = st.text_input("Airline", placeholder="e.g., United Airlines")
            flight_number      = st.text_input("Flight Number", placeholder="e.g., UA1234")
            departure          = st.text_input("Departure City", placeholder="e.g., New York (JFK)")
            departure_date     = st.date_input("Departure Date", key="flight_dep_date")
            departure_time_val = st.time_input("Departure Time", key="flight_dep_time")
        with col2:
            arrival          = st.text_input("Arrival City", placeholder="e.g., Paris (CDG)")
            arrival_date     = st.date_input("Arrival Date", key="flight_arr_date")
            arrival_time_val = st.time_input("Arrival Time", key="flight_arr_time")
            confirmation     = st.text_input("Confirmation Number")

        if st.form_submit_button("Add Flight ✈️") and airline and flight_number:
            st.session_state.flights.append(Flight(
                airline, flight_number, departure, arrival,
                departure_date, departure_time_val,
                arrival_date, arrival_time_val, confirmation
            ))
            st.success(f"✅ {airline} {flight_number} added!")

    if st.session_state.flights:
        st.subheader(f"📋 {len(st.session_state.flights)} Flight(s)")
        st.dataframe(pd.DataFrame([f.to_dict() for f in st.session_state.flights]),
                     use_container_width=True, hide_index=True)
        if st.button("Clear Flights"):
            st.session_state.flights = []
            st.rerun()
    else:
        st.info("No flights added yet.")

# ---- HOTELS ----
with tab2:
    st.header("🏨 Hotel Details")
    with st.form("add_hotel"):
        col1, col2 = st.columns(2)
        with col1:
            hotel_name = st.text_input("Hotel Name", placeholder="e.g., Hilton Paris")
            address    = st.text_input("Address", placeholder="e.g., 123 Champs-Élysées")
            check_in   = st.date_input("Check-in Date", key="hotel_checkin")
        with col2:
            check_out          = st.date_input("Check-out Date", key="hotel_checkout")
            hotel_confirmation = st.text_input("Confirmation Number")

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

# ---- TOURS ----
with tab3:
    st.header("🎯 Tour & Activity Details")
    with st.form("add_tour"):
        col1, col2 = st.columns(2)
        with col1:
            tour_name     = st.text_input("Tour/Activity Name", placeholder="e.g., Eiffel Tower Visit")
            tour_location = st.text_input("Location", placeholder="e.g., Paris, France")
        with col2:
            tour_date         = st.date_input("Date", key="tour_date")
            tour_time         = st.time_input("Time", key="tour_time")
            tour_confirmation = st.text_input("Confirmation Number")

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

# ---- TRANSFERS ----
with tab4:
    st.header("🚌 Airport & Bus Transfers")
    with st.form("add_transfer"):
        col1, col2 = st.columns(2)
        with col1:
            service_name     = st.text_input("Service Name", placeholder="e.g., Flybus PLUS")
            pickup_location  = st.text_input("Pickup Location", placeholder="e.g., Keflavik Airport")
            dropoff_location = st.text_input("Dropoff Location", placeholder="e.g., Reykjavik Hotel")
        with col2:
            transfer_date         = st.date_input("Date", key="xfer_date")
            transfer_time         = st.time_input("Time", key="xfer_time")
            passengers            = st.number_input("Passengers", min_value=1, value=1, step=1)
            transfer_confirmation = st.text_input("Confirmation Number", placeholder="e.g., IF-1FSLB4")

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

# ---- SUMMARY ----
with tab5:
    st.header("📋 Complete Travel Summary")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✈️ Flights",   len(st.session_state.flights))
    c2.metric("🏨 Hotels",    len(st.session_state.hotels))
    c3.metric("🎯 Tours",     len(st.session_state.tours))
    c4.metric("🚌 Transfers", len(st.session_state.transfers))
    st.divider()

    if st.session_state.flights:
        st.subheader("✈️ Flights")
        for i, f in enumerate(st.session_state.flights, 1):
            with st.expander(f"{i}. {f.airline} {f.flight_number}"):
                st.write(f"**Route:** {f.departure} → {f.arrival}")
                st.write(f"**Departure:** {f.departure_date} at {f.departure_time}")
                st.write(f"**Arrival:** {f.arrival_date} at {f.arrival_time}")
                st.write(f"**Confirmation:** {f.confirmation_number}")

    if st.session_state.hotels:
        st.subheader("🏨 Hotels")
        for i, h in enumerate(st.session_state.hotels, 1):
            with st.expander(f"{i}. {h.name}"):
                st.write(f"**Address:** {h.address}")
                st.write(f"**Check-in:** {h.check_in} | **Check-out:** {h.check_out}")
                st.write(f"**Confirmation:** {h.confirmation_number}")

    if st.session_state.tours:
        st.subheader("🎯 Tours")
        for i, t in enumerate(st.session_state.tours, 1):
            with st.expander(f"{i}. {t.name}"):
                st.write(f"**Location:** {t.location}")
                st.write(f"**Date:** {t.tour_date} at {t.tour_time}")
                st.write(f"**Confirmation:** {t.confirmation_number}")

    if st.session_state.transfers:
        st.subheader("🚌 Transfers")
        for i, x in enumerate(st.session_state.transfers, 1):
            with st.expander(f"{i}. {x.service_name}"):
                st.write(f"**Pickup:** {x.pickup_location}")
                st.write(f"**Dropoff:** {x.dropoff_location}")
                st.write(f"**Date:** {x.transfer_date} at {x.transfer_time.strftime('%H:%M')}")
                st.write(f"**Passengers:** {x.passengers}")
                st.write(f"**Confirmation:** {x.confirmation_number}")

    st.divider()
    st.subheader("💾 Export")

    if st.button("Export to CSV"):
        all_data = []
        for f in st.session_state.flights:
            all_data.append({"Type": "Flight",   **f.to_dict()})
        for h in st.session_state.hotels:
            all_data.append({"Type": "Hotel",    **h.to_dict()})
        for t in st.session_state.tours:
            all_data.append({"Type": "Tour",     **t.to_dict()})
        for x in st.session_state.transfers:
            all_data.append({"Type": "Transfer", **x.to_dict()})

        if all_data:
            df_export = pd.DataFrame(all_data)
            csv = df_export.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download CSV", csv, "travel_plan.csv", "text/csv")
        else:
            st.warning("No data to export!")
