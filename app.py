import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import os
from openai import OpenAI

# =============================
# CONFIG
# =============================
st.set_page_config(page_title="AI Travel Planner", layout="wide")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

CLIENT_ID = os.getenv("CLIENT_ID")
TENANT_ID = "common"
REDIRECT_URI = "http://localhost:8501"

# =============================
# AUTH (OAUTH LOGIN)
# =============================
def get_auth_url():
    return (
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize?"
        f"client_id={CLIENT_ID}&response_type=token&redirect_uri={REDIRECT_URI}&"
        f"scope=User.Read Mail.Read"
    )

# =============================
# FETCH EMAILS
# =============================
def fetch_emails(token):
    headers = {"Authorization": f"Bearer {token}"}
    url = "https://graph.microsoft.com/v1.0/me/messages?$top=20"

    res = requests.get(url, headers=headers)
    data = res.json()

    return data.get("value", [])



# =============================
    prompt = f"""
    Extract structured travel data from this email.

    Return JSON:
    type: flight/hotel/activity
    date:
    time:
    location:
    provider:
    confirmation:

    Email:
    {subject}\n{body[:2000]}
    """

    try:
        res = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content
    except:
        return None

# =============================
# UI
# =============================
st.title("✈️ AI Travel Planner (Outlook)")

# OAuth Login
if "token" not in st.session_state:
    auth_url = get_auth_url()
    st.markdown(f"[🔐 Login with Outlook]({auth_url})")

    token_input = st.text_input("Paste Access Token After Login")

    if token_input:
        st.session_state.token = token_input
        st.rerun()

# =============================
# MAIN APP
# =============================
if "token" in st.session_state:
    st.success("Connected to Outlook ✅")

    if st.button("📥 Import Emails"):
        emails = fetch_emails(st.session_state.token)

        st.write(f"Fetched {len(emails)} emails")

        structured = []

        for email in emails:
            parsed = extract_travel(email)
            if parsed:
                structured.append(parsed)

        if structured:
            df = pd.DataFrame(structured, columns=["AI Output"])
            st.dataframe(df, use_container_width=True)

            # Timeline UI
            st.subheader("🗓 Timeline View")
            for item in structured:
                st.markdown(f"- {item}")

            # Download
            csv = df.to_csv(index=False)
            st.download_button("Download CSV", csv, "travel.csv")

# =============================
# STRIPE MONETIZATION (PLACEHOLDER)
# =============================
st.divider()
st.subheader("💰 Upgrade to Premium")
st.write("Unlock unlimited email parsing + PDF export")
st.markdown("👉 Integrate Stripe Checkout here")
