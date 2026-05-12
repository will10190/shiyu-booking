import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import date, timedelta
import math
import calendar
import json

# --- 1. UI 風格與 CSS 設定 ---
st.set_page_config(page_title="時嶼 Shi.Yu studio | 管家後台", page_icon="🤎", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #FDFBF7; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    h1, h2, h3, p, span { color: #5C4B41 !important; }
    .brand-title { text-align: center; font-size: 28px; font-weight: 700; color: #7A6353 !important; margin-top: 10px; margin-bottom: 20px; }
    
    .booking-card { background-color: #FFFFFF; border-radius: 15px; padding: 20px 24px; margin-top: 15px; margin-bottom: 8px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05); border: 1px solid #F0EBE1; }
    .booking-card h4 { margin: 0 0 10px 0; color: #5C4B41 !important; font-size: 17px; }
    .booking-card h2 { margin: 0 0 12px 0; display: flex; align-items: center; gap: 10px; font-size: 22px; }
    .booking-card p  { margin: 4px 0; font-size: 15px; }
    .status-pill { font-size: 13px; background-color: #EAE0D5; color: #5C4B41; padding: 3px 12px; border-radius: 20px; font-weight: normal; }
    div.stButton > button { background-color: #EDE0D4; color: #5C4B41; border-radius: 10px; border: none; width: 100%; font-weight: 600; font-size: 14px; padding: 10px 6px; transition: all 0.2s; line-height: 1.5; }
    div.stButton > button:hover { background-color: #DCC8B4; }
    .action-panel { background-color: #FAF6F1; border-radius: 12px; padding: 16px 20px; margin-bottom: 16px; border: 1px solid #EAE0D5; }
    
    /* 🌟 核心修復：強制加上 !important 與 table-cell 鎖死網格，抵抗雲端的響應式干擾 */
    .calendar-table { width: 100% !important; border-collapse: collapse !important; background-color: white !important; border-radius: 10px !important; overflow: hidden !important; box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important; table-layout: fixed !important; display: table !important; }
    .calendar-table tbody { display: table-row-group !important; }
    .calendar-table tr { display: table-row !important; }
    .calendar-table th { display: table-cell !important; width: 14.28% !important; background-color: #FAF6F1 !important; color: #7A6353 !important; padding: 10px !important; text-align: center !important; border: 1px solid #F0EBE1 !important; font-weight: 600 !important; font-size: 13px !important; }
    .calendar-table td { display: table-cell !important; width: 14.28% !important; border: 1px solid #F0EBE1 !important; height: 130px !important; vertical-align: top !important; padding: 4px !important; position: relative !important; }
    .calendar-day-num { font-weight: bold !important; color: #5C4B41 !important; margin-bottom: 5px !important; font-size: 12px !important; padding-left: 2px !important; }
    .calendar-other-month { background-color: #F9F9F9 !important; color: #CCC !important; }
    
    .cal-event { background-color: #E6D5C3; color: #5C4B41; font-size: 10px; padding: 3px 5px; border-radius: 4px; margin-bottom: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; border-left: 3px solid #C4A484; line-height: 1.2; }
    .cal-event-off { background-color: #E2E2E2; color: #666; border-left: 3px solid #999; } 
    .cal-scroll { max-height: 105px; overflow-y: auto; scrollbar-width: none; }
    .cal-scroll::-webkit-scrollbar { display: none; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 密碼驗證 ---
if "admin_auth" not in st.session_state: st.session_state.admin_auth = False
if not st.session_state.admin_auth:
    st.markdown("<div class='brand-title'>時嶼 管家後台</div>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        pwd = st.text_input("密碼", type="password", placeholder="請輸入密碼", label_visibility="collapsed")
        if st.button("登入"):
            if pwd == st.secrets["admin_password"]:
                st.session_state.admin_auth = True; st.rerun()
            else: st.error("❌ 密碼錯誤")
    st.stop()

# --- 3. 連接 Google Sheets ---
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    db = client.open("ShiYu_Booking_DB")
    sheet_bookings = db.worksheet("bookings")
    sheet_services = db.worksheet("services")
    sheet_customers = db.worksheet("customers")
except Exception as e:
    st.error(f"❌ 系統連線維護中。 ({e})")
    st.stop()

PRICE_MAP, DURATION_MAP = {}, {}
try:
    services_records = sheet_services.get_all_records()
    for r in services_records:
        item = str(r.get('Item', '')).strip()
        if item:
            PRICE_MAP[item] = int(r.get('Price', 0))
            DURATION_MAP[item] = int(r.get('Duration_mins', 60))
except: pass

CUST_MAP = {}
try:
    cust_records = sheet_customers.get_all_records()
    CUST_MAP = {str(r['Phone']).replace("'", ""): str(r.get('Skin_Type / Notes', '')) for r in cust_records if 'Phone' in r}
except: pass

if "active_panel" not in st.session_state: st.session_state.active_panel = None
st.markdown("<div class='brand-title'>時嶼 管家後台</div>", unsafe_allow_html=True)

time_slots = ["09:00","10:00","11:00","12:00","13:00","14:00","15:00","16:00"]
records = sheet_bookings.get_all_records()
df = pd.DataFrame(records) if records else pd.DataFrame()
if not df.empty: df['Sheet_Row'] = df.index + 2

# === 排休系統 ===
with st.expander("🏖️ 新增排休 / 鎖定時段", expanded=False):
    col_off1, col_off2 = st.columns([1, 2])
    with col_off1:
        off_date = st.date_input("選擇排休日期", date.today())
        is_all_day = st.checkbox("✅ 全天休假 (鎖定整天)")
    with col_off2:
        off_times = []
        if not is_all_day: off_times = st.multiselect("選擇要鎖定的時段", options=time_slots)
        else:
            off_times = time_slots 
            st.info("已選擇全天，所有時段將被鎖定。")
    if st.button("確認新增排休", type="primary"):
        if not off_times: st.warning("請至少選擇一個時段。")
        else:
            sheet_bookings.append_row([str(date.today()), str(off_date), "'" + ", ".join(off_times), "[店休/排休]", "系統排休", "", "Christine", "店休", 0, "已排休", ""])
            st.success(f"已成功設定排休！"); st.rerun()

st.write("---")

# === 月曆總覽 ===
st.markdown("### 📅 當月預約總覽")
if "cal_year" not in st.session_state: st.session_state.cal_year = date.today().year
if "cal_month" not in st.session_state: st.session_state.cal_month = date.today().month

col_m1, col_m2, col_m3 = st.columns([1, 2, 1])
with col_m1:
    if st.button("◀ 上個月", use_container_width=True):
        st.session_state.cal_month -= 1
        if st.session_state.cal_month < 1: st.session_state.cal_month, st.session_state.cal_year = 12, st.session_state.cal_year - 1
        st.rerun()
with col_m2: st.markdown(f"<h3 style='text-align: center; margin-top:0;'>{st.session_state.cal_year} 年 {st.session_state.cal_month} 月</h3>", unsafe_allow_html=True)
with col_m3:
    if st.button("下個月 ▶", use_container_width=True):
        st.session_state.cal_month += 1
        if st.session_state.cal_month > 12: st.session_state.cal_month, st.session_state.cal_year = 1, st.session_state.cal_year + 1
        st.rerun()

cal = calendar.Calendar(firstweekday=6) 
month_days = cal.monthdatescalendar(st.session_state.cal_year, st.session_state.cal_month)
html_cal = "<table class='calendar-table'><tr><th>日</th><th>一</th><th>二</th><th>三</th><th>四</th><th>五</th><th>六</th></tr>"

for week in month_days:
    html_cal += "<tr>"
    for d in week:
        td_class = "" if d.month == st.session_state.cal_month else "calendar-other-month"
        html_cal += f"<td class='{td_class}'><div class='calendar-day-num'>{d.day}</div><div class='cal-scroll'>"
        if not df.empty:
            day_bookings = df[df['Date'] == str(d)].sort_values(by=['Time'])
            for _, rb in day_bookings.iterrows():
                b_name, b_svc = str(rb['Name']), str(rb['Service'])
                time_list = [t.strip() for t in str(rb['Time']).replace("'", "").split(",") if t.strip()]
                if b_name == "[店休/排休]":
                    if len(time_list) >= len(time_slots): html_cal += f"<div class='cal-event cal-event-off' style='font-weight:bold;'>🚫 全天休假</div>"
                    else:
                        for t in time_list: html_cal += f"<div class='cal-event cal-event-off'>🚫 {t} 休</div>"
                else:
                    start_t = time_list[0] if time_list else ""
                    html_cal += f"<div class='cal-event' title='{b_svc}'>🤎 {start_t} {b_name}<br/><span style='font-size:9px; opacity:0.8;'>{b_svc}</span></div>"
        html_cal += "</div></td></tr>"
html_cal += "</table>"

st.markdown(html_cal, unsafe_allow_html=True)
st.write("---")

# === 單日詳細管理 ===
st.markdown("### 📝 單日詳細管理")
selected_date = st.date_input("選擇日期", date.today())
day_df = df[df['Date'] == str(selected_date)].sort_values(by=['Time']) if not df.empty else pd.DataFrame()

if day_df.empty: st.info("這天沒有預約或排休。")
else:
    for _, row in day_df.iterrows():
        real_row, uid = int(row['Sheet_Row']), int(row['Sheet_Row'])
        paid_icon = "✅" if str(row.get('Paid','0')) == "1" else "⏳"
        clean_phone = str(row['Phone']).replace("'", "")
        cust_note = CUST_MAP.get(clean_phone, "")
        cust_note_html = f"<p>📝 老客備註：<span style='color:#A85A32;'>{cust_note}</span></p>" if cust_note else ""
        display_time = str(row['Time']).replace("'", "")
        
        if row['Name'] == "[店休/排休]":
            st.markdown(f'<div class="booking-card" style="background-color: #F5F5F5; border: 1px dashed #CCC;"><h4>🚫 {display_time} | 系統排休</h4><h2>[店休 / 鎖定時段]</h2></div>', unsafe_allow_html=True)
            if st.button("🗑️ 刪除排休", key=f"del_off_{uid}"):
                sheet_bookings.delete_rows(real_row); st.success("已解除鎖定"); st.rerun()
        else:
            st.markdown(f'<div class="booking-card"><h4>{display_time} | {row["Staff"]}</h4><h2>{row["Name"]} <span class="status-pill">{row["Status"]}</span></h2><p>📋 項目：{row["Service"]}</p><p>📞 {clean_phone} | LINE：{row.get("LineID","—")}</p>{cust_note_html}<p>{paid_icon} {"已付款" if str(row.get("Paid","0"))=="1" else "未付款"}</p></div>', unsafe_allow_html=True)
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("💰 計價", key=f"price_{uid}"): st.session_state.active_panel = ("price", uid); st.rerun()
            with col2:
                if st.button("💬 提醒", key=f"remind_{uid}"): st.session_state.active_panel = ("remind", uid); st.rerun()
            with col3:
                if st.button("⏱️ 改時", key=f"time_{uid}"): st.session_state.active_panel = ("time", uid); st.rerun()
            with col4:
                if st.button("❌ 取消", key=f"cancel_{uid}"): st.session_state.active_panel = ("cancel", uid); st.rerun()

            panel = st.session_state.active_panel
            if panel == ("price", uid):
                st.markdown("<div class='action-panel'>", unsafe_allow_html=True)
                service_list = [s.strip() for s in str(row['Service']).split(",")]
                suggested = sum(PRICE_MAP.get(s, 0) for s in service_list)
                amount = st.number_input("實收金額", value=suggested, key=f"amt_{uid}")
                paid = st.checkbox("標記付款", value=(str(row.get('Paid','0'))=="1"), key=f"p_{uid}")
                note = st.text_input("備註", value=str(row.get('Note','')), key=f"n_{uid}")
                if st.button("✅ 儲存", key=f"s_p_{uid}"):
                    sheet_bookings.update_cell(real_row, 9, "1" if paid else "0"); sheet_bookings.update_cell(real_row, 11, note)
                    st.session_state.active_panel = None; st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            if panel == ("remind", uid):
                st.markdown("<div class='action-panel'>", unsafe_allow_html=True)
                st.text_area("複製訊息", value=f"【時嶼預約提醒】\n{row['Name']}您好！明天 {row['Date']} {display_time} 有預約 🤎\n項目：{row['Service']}", height=120)
                st.markdown("</div>", unsafe_allow_html=True)

            if panel == ("time", uid):
                st.markdown("<div class='action-panel'>", unsafe_allow_html=True)
                new_date = st.date_input("新日期", value=selected_date, key=f"nd_{uid}")
                svc_list = [s.strip() for s in str(row['Service']).split(",")]
                tot_mins = sum(DURATION_MAP.get(s, 60) for s in svc_list)
                s_needed = math.ceil(tot_mins / 60.0) if tot_mins > 0 else 1
                
                booked_new = []
                for _, r_row in df[df['Date'] == str(new_date)].iterrows():
                    if int(r_row['Sheet_Row']) != real_row:
                        booked_new.extend([t.strip() for t in str(r_row['Time']).replace("'", "").split(",")])
                
                valid_starts = []
                for i, t in enumerate(time_slots):
                    conflict = False
                    for j in range(s_needed):
                        if i + j >= len(time_slots) or time_slots[i+j] in booked_new:
                            conflict = True; break
                    if not conflict: valid_starts.append(t)
                        
                new_start = st.selectbox("新開始時段", options=["請選擇..."]+valid_starts, key=f"ns_{uid}") if valid_starts else None
                if not valid_starts: st.warning("⚠️ 該日期已無足夠時段。")
                if st.button("✅ 確認改時", key=f"st_{uid}"):
                    if valid_starts and new_start != "請選擇...":
                        start_idx = time_slots.index(new_start)
                        sheet_bookings.update_cell(real_row, 2, str(new_date))
                        sheet_bookings.update_cell(real_row, 3, "'" + ", ".join(time_slots[start_idx : start_idx + s_needed]))
                        st.session_state.active_panel = None; st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            if panel == ("cancel", uid):
                st.markdown("<div class='action-panel'>", unsafe_allow_html=True)
                st.write(f"確定取消 {row['Name']}？")
                if st.button("🗑️ 確定取消", key=f"cc_{uid}"):
                    sheet_bookings.delete_rows(real_row); st.session_state.active_panel = None; st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
