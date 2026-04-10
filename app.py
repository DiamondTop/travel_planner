import streamlit as st
import requests
import msal
import pandas as pd
from datetime import datetime

# =============================
# AUTHENTICATION (MSAL)
# =============================
def get_access_token():
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
    accounts = app.get_accounts()

    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
    else:
        flow = app.initiate_device_flow(scopes=SCOPES)
        st.write(flow["message"])
        result = app.acquire_token_by_device_flow(flow)

    if "access_token" in result:
        return result["access_token"]
    else:
        st.error("Authentication failed")
        return None

# =============================
# FETCH EMAILS FROM OUTLOOK
# =============================
def fetch_emails(token):
    headers = {"Authorization": f"Bearer {token}"}
    url = "https://graph.microsoft.com/v1.0/me/messages?$search=\"flight OR hotel OR booking OR itinerary\""

    response = requests.get(url, headers=headers)
    data = response.json()

    return data.get("value", [])

# =============================
# SIMPLE PARSER (upgrade later)
# =============================
def extract_data(email_body):
    results = {
        "type": "unknown",
        "details": email_body[:200]
    }

    text = email_body.lower()

    if "flight" in text:
        results["type"] = "flight"
    elif "hotel" in text:
        results["type"] = "hotel"
    elif "tour" in text or "experience" in text:
        results["type"] = "activity"

    return results

# =============================
# BUILD ITINERARY
# =============================
def build_itinerary(emails):
    structured = []

    for email in emails:
        body = email.get("body", {}).get("content", "")
        parsed = extract_data(body)

        structured.append({
            "subject": email.get("subject"),
            "type": parsed["type"],
            "preview": parsed["details"]
        })

    return pd.DataFrame(structured)

# =============================
# STREAMLIT UI
# =============================
st.set_page_config(page_title="AI Travel Planner", layout="wide")

st.title("✈️ AI Travel Planner (Outlook)")
st.write("Auto-build your itinerary from Outlook emails")

if st.button("Connect to Outlook"):
    token = get_access_token()

    if token:
        emails = fetch_emails(token)
        df = build_itinerary(emails)

        st.success("Travel data extracted!")

        st.dataframe(df)

        # Download option
        csv = df.to_csv(index=False)
        st.download_button("Download Itinerary", csv, "itinerary.csv", "text/csv")

# =============================
# NEXT STEPS NOTE
# =============================
st.markdown("""
### 🚀 Next Steps to Monetize:
- Add AI extraction (OpenAI) for structured parsing
- Add timeline/day planner view
- Add calendar sync
- Add PDF itinerary export
- Add premium tier ($5–$10/month)
""")
