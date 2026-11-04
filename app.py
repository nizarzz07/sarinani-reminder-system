import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import urllib.parse
import xml.etree.ElementTree as ET
import os

st.set_page_config(page_title="Sarinani Motors - Service Reminder System", layout="wide")

st.title("🚗 Sarinani Motors - Service Reminder System")
st.caption("Target: 10 Reminders / Day with Auto-Save Status Tracking")

DB_FILE = "saved_service_data.csv"

# Function to parse Perodua / Sarinani export files (XML / Excel)
def parse_uploaded_file(file):
    try:
        df = pd.read_excel(file)
        return df
    except Exception:
        file.seek(0)
        tree = ET.parse(file)
        root = tree.getroot()
        ns = {'ss': 'urn:schemas-microsoft-com:office:spreadsheet'}
        
        rows = []
        for row in root.findall('.//ss:Row', ns):
            row_data = []
            for cell in row.findall('./ss:Cell', ns):
                data = cell.find('./ss:Data', ns)
                row_data.append(data.text if data is not None else "")
            rows.append(row_data)
        
        if len(rows) > 8:
            header = rows[8]
            data_rows = rows[9:]
            df = pd.DataFrame(data_rows, columns=header)
            return df
        return pd.DataFrame()

# 1. Check if local database already exists
if os.path.exists(DB_FILE):
    df = pd.read_csv(DB_FILE)
    st.sidebar.success("✅ Loaded existing data from local database!")
else:
    df = pd.DataFrame()

# Expandable Upload section in case a new file needs to be imported
with st.expander("📁 Import New Excel File (Only needed if updating the master list)", expanded=(not os.path.exists(DB_FILE))):
    uploaded_file = st.file_uploader("Upload Excel File (svcReListEx(2).xls)", type=["xls", "xlsx"])
    if uploaded_file is not None:
        if st.button("📥 Process & Save New Data"):
            parsed_df = parse_uploaded_file(uploaded_file)
            if not parsed_df.empty:
                parsed_df.columns = [str(col).strip() for col in parsed_df.columns]
                if 'Reminder Status' not in parsed_df.columns:
                    parsed_df['Reminder Status'] = 'INCOMPLETE'
                else:
                    parsed_df['Reminder Status'] = parsed_df['Reminder Status'].fillna('INCOMPLETE')
                
                # Save to local CSV
                parsed_df.to_csv(DB_FILE, index=False)
                st.success("Data successfully saved to system database! Refreshing page...")
                st.rerun()

if not df.empty:
    st.sidebar.header("⚙️ Target Controls & Filters")

    # Main columns
    target_date_col = 'Service Reminder/ Target Date'
    next_service_col = 'Next Service Estimated Date'
    phone_col = 'Customer Contact No'
    name_col = 'Customer Name'
    plate_col = 'Vehicle No'

    # Date formatting
    if target_date_col in df.columns:
        df[target_date_col] = pd.to_datetime(df[target_date_col], errors='coerce')
    if next_service_col in df.columns:
        df[next_service_col] = pd.to_datetime(df[next_service_col], errors='coerce')

    show_all = st.sidebar.checkbox("Show All Customers (Ignore Date Filter)", value=False)
    default_target_date = datetime(2026, 12, 2).date()
    selected_date = st.sidebar.date_input("Filter Target / Service Date", value=default_target_date)
    daily_limit = st.sidebar.number_input("Daily Target Limit", min_value=1, max_value=100, value=10)
    status_filter = st.sidebar.radio("View Status", ["All", "INCOMPLETE Only", "COMPLETE Only"], index=1)

    # Phone Number Formatter
    def format_phone(phone):
        p = str(phone).replace(".0", "").strip()
        digits = "".join(filter(str.isdigit, p))
        if digits.startswith("0"):
            digits = "60" + digits[1:]
        elif not digits.startswith("60") and len(digits) > 0:
            digits = "60" + digits
        return digits

    # WhatsApp Message Template
    def build_whatsapp_url(phone_num, customer_name, due_date, car_plate):
        clean_phone = format_phone(phone_num)
        script_text = (
            f"Hello {customer_name},\n\n"
            f"I am Nizar, your Service Advisor at Sarinani Motors Sdn Bhd.\n\n"
            f"Your next service is due on {due_date}.\n\n"
            f"We look forward to your next appointment.\n\n"
            f"If you have already serviced your vehicle at our service centre or any other service centre, please disregard this message.\n\n"
            f"If you would like to make a service booking with us, kindly fill in the details below:\n\n"
            f"NAME: {customer_name}\n"
            f"CONTACT NO.: {phone_num}\n"
            f"REG NO / PLATE NO.: {car_plate}\n"
            f"SERVICE BOOKING DATE:\n"
            f"TIME:\n"
            f"CURRENT MILEAGE:\n\n"
            f"You may also contact us at 011-21502920.\n\n"
            f"Thank you for choosing Sarinani Motors Sdn Bhd. We look forward to serving you again."
        )
        encoded_msg = urllib.parse.quote(script_text)
        return f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_msg}"

    # Data Filtering
    if not show_all and target_date_col in df.columns:
        filtered_df = df[df[target_date_col].dt.date == selected_date]
        if filtered_df.empty:
            filtered_df = df.copy()
    else:
        filtered_df = df.copy()

    if status_filter == "INCOMPLETE Only":
        filtered_df = filtered_df[filtered_df['Reminder Status'] == 'INCOMPLETE']
    elif status_filter == "COMPLETE Only":
        filtered_df = filtered_df[filtered_df['Reminder Status'] == 'COMPLETE']

    target_batch = filtered_df.head(daily_limit)

    total_complete = (df['Reminder Status'] == 'COMPLETE').sum()
    st.subheader(f"📋 Target Customer List ({len(target_batch)} Displayed / Limit: {daily_limit})")
    st.progress(min(total_complete / daily_limit, 1.0), text=f"Total Completed Today: {total_complete} customers")

    for idx, row in target_batch.iterrows():
        cust_name = str(row.get(name_col, '')).strip()
        car_plate = str(row.get(plate_col, '')).strip()
        phone_no = str(row.get(phone_col, '')).strip()
        current_status = str(row.get('Reminder Status', 'INCOMPLETE')).strip()
        
        raw_date = row.get(next_service_col)
        if pd.notnull(raw_date) and hasattr(raw_date, 'strftime'):
            due_date_str = raw_date.strftime('%d/%m/%Y')
        else:
            due_date_str = str(selected_date.strftime('%d/%m/%Y'))

        wa_link = build_whatsapp_url(phone_no, cust_name, due_date_str, car_plate)

        with st.container():
            c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 2, 2, 2.5, 2.5])
            
            c1.markdown(f"**{cust_name}**")
            c2.markdown(f"🚘 **{car_plate}**")
            c3.markdown(f"📞 `{phone_no}`")
            c4.markdown(f"📅 **{due_date_str}**")
            
            c5.link_button("💬 Send WhatsApp", wa_link, type="primary")
            
            new_status = c6.selectbox(
                "Status",
                ["INCOMPLETE", "COMPLETE"],
                index=0 if current_status == "INCOMPLETE" else 1,
                key=f"status_{idx}"
            )
            
            # Auto-save changes to local database immediately
            if new_status != current_status:
                df.at[idx, 'Reminder Status'] = new_status
                df.to_csv(DB_FILE, index=False)
                st.rerun()

            st.divider()

    st.sidebar.markdown("---")
    st.sidebar.subheader("📥 Backup & Download")
    csv_data = df.to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(
        label="Download Latest CSV Backup",
        data=csv_data,
        file_name=f"service_reminders_backup_{selected_date}.csv",
        mime="text/csv"
    )
