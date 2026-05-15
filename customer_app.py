import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import date
import base64
import os
import math
import json

# --- 1. 連接 Google Sheets (雲端安全版) ---
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    
    client = gspread.authorize(creds)
    db = client.open("ShiYu_Booking_DB")
    sheet_bookings = db.worksheet("bookings")
    sheet_customers = db.worksheet("customers")
    sheet_services = db.worksheet("services") 
except Exception as e:
    st.error(f"❌ 系統連線維護中，請稍後再試。 ({e})")
    st.stop()

# --- 2. 初始化狀態 ---
if "selected_times" not in st.session_state: st.session_state.selected_times = []
if "current_date" not in st.session_state: st.session_state.current_date = str(date.today())
for k in ["phone_input", "name_input", "line_input", "birth_input"]:
    if k not in st.session_state: st.session_state[k] = ""

# --- 3. UI 視覺與 CSS 設定 ---
st.set_page_config(page_title="時嶼 Shi.Yu studio | 預約", page_icon="🤎", layout="centered")

def get_base64(bin_file):
    try:
        with open(bin_file, 'rb') as f: return base64.b64encode(f.read()).decode()
    except: return ""

logo_base64 = get_base64("shiyu_logo.png")

st.markdown(f"""
    <style>
    .stApp {{ background-color: #FDFBF7; }}
    #MainMenu {{visibility: hidden;}} footer {{visibility: hidden;}} header {{visibility: hidden;}}
    .block-container {{ padding-top: 1.0rem !important; }}
    .logo-container {{ display: flex; justify-content: center; padding-top: 0px; margin-bottom: 1px; }}
    .logo-mask {{ width: 140px; height: 140px; border-radius: 50%; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 2px solid #FFFFFF; }}
    .logo-mask img {{ width: 100%; height: 100%; object-fit: cover; }}
    .brand-subtitle {{ text-align: center; font-size: 16px; color: #8C7565 !important; margin-top: 5px; margin-bottom: 35px; font-family: 'Courier New', Courier, monospace; letter-spacing: 2px; }}
    h1, h2, h3, p, span, label {{ color: #5C4B41 !important; }}
    div.stButton > button {{ border-radius: 12px; width: 100%; transition: all 0.3s; font-weight: bold; }}
    div.stButton > button:disabled {{ background-color: #E2E2E2 !important; color: #AAAAAA !important; border: 1px solid #CCCCCC !important; opacity: 1 !important; text-decoration: line-through !important; }}
    div.stButton > button[kind="primary"] {{ background-color: #C4A484 !important; color: #FFFFFF !important; border: 1px solid #C4A484 !important; box-shadow: none !important; }}
    div[data-testid="stColumn"] div.stButton > button[kind="secondary"] {{ background-color: #FDFBF7 !important; color: #7A6353 !important; border: 1px solid #EAE0D5 !important; }}
    </style>
""", unsafe_allow_html=True)

if logo_base64:
    st.markdown(f'<div class="logo-container"><div class="logo-mask"><img src="data:image/png;base64,{logo_base64}"></div></div>', unsafe_allow_html=True)
st.markdown('<div class="brand-subtitle">Shi.Yu studio</div>', unsafe_allow_html=True)

# --- 4. 讀取與顯示 ---
def read_f(f):
    if os.path.exists(f): 
        with open(f, "r", encoding="utf-8") as file: return file.read().strip()
    return ""

with st.expander("📋 預約須知 (必讀)"): st.write(read_f("notice.txt"))
with st.expander("📖 查看價目表 (展開)"): 
    try:
        col_p1, col_p2, col_p3 = st.columns([1,2,1])
        with col_p2:
            st.image("price1.png", use_container_width=True)
            st.image("price2.png", use_container_width=True)
            st.image("price3.png", use_container_width=True)
    except: st.warning("⚠️ 價目表圖片讀取中...")

st.markdown("### 顧客資料")
phone = st.text_input("聯絡電話", placeholder="09xxxxxxxx", key="phone_input")
if st.button("🔍 自動查詢資料", use_container_width=True):
    input_phone = st.session_state.phone_input.strip()
    if input_phone:
        try:
            cust_records = sheet_customers.get_all_records()
            found = False
            for r in cust_records:
                sp = str(r.get("Phone","")).replace("'", "").strip()
                if len(sp)==9 and sp.startswith("9"): sp="0"+sp
                if sp == input_phone:
                    st.session_state.name_input = str(r.get("Name",""))
                    st.session_state.line_input = str(r.get("LineID",""))
                    st.session_state.birth_input = str(r.get("Birthday",""))
                    found = True
                    break
            if found:
                st.success("✅ 已成功載入老朋友資料！")
                st.rerun()
            else:
                st.warning("查無此電話，歡迎新朋友填寫資料！")
        except: pass

col1, col2 = st.columns(2)
with col1: name = st.text_input("姓名", key="name_input")
with col2: line_id = st.text_input("LineID", key="line_input")
birthday = st.text_input("生日", key="birth_input")

# --- 5. 服務項目與時間邏輯 ---
st.markdown("### 預約內容")
services_lines = [s.strip() for s in read_f("services.txt").split('\n') if s.strip()]
selected_services = []

if services_lines:
    services_dict = {}
    curr_cat = "✨ 項目"
    for line in services_lines:
        if line.startswith("[") and line.endswith("]"): curr_cat = line[1:-1]
        else:
            if curr_cat not in services_dict: services_dict[curr_cat] = []
            services_dict[curr_cat].append(line)
    for cat, items in services_dict.items():
        with st.expander(cat, expanded=False):
            for itm in items:
                if st.checkbox(itm, key=f"svc_{itm}"): selected_services.append(itm)

duration_db, price_db = {}, {}
try:
    s_recs = sheet_services.get_all_records()
    for r in s_recs:
        item_name = str(r.get('Item', '')).strip()
        if item_name:
            duration_db[item_name] = int(r.get('Duration_mins', 60))
            price_db[item_name] = int(r.get('Price', 0))
except: pass

# 🌟 核心修改 1：改為除以 20 分鐘來計算所需格子
total_mins = sum(duration_db.get(s, 60) for s in selected_services)
total_price = sum(price_db.get(s, 0) for s in selected_services)
slots_needed = math.ceil(total_mins / 20.0) if total_mins > 0 else 1

st.markdown("### 選擇時間")
booking_date = st.date_input("選擇日期", date.today(), label_visibility="collapsed")
if str(booking_date) != st.session_state.current_date:
    st.session_state.current_date, st.session_state.selected_times = str(booking_date), []

# 🌟 核心修改 2：動態產出 20 分鐘單位的時間表，並根據平假日決定打烊時間
def get_time_slots(target_date):
    is_weekend = target_date.weekday() >= 5
    end_hour = 19 if is_weekend else 16
    slots = []
    for h in range(9, end_hour + 1):
        for m in (0, 20, 40):
            slots.append(f"{h:02d}:{m:02d}")
    return slots

time_slots = get_time_slots(booking_date)

booked_times = []
try:
    recs = sheet_bookings.get_all_records()
    for r in recs:
        if str(r.get("Date")) == str(booking_date):
            clean_time_str = str(r.get("Time")).replace("'", "")
            booked_times.extend([t.strip() for t in clean_time_str.split(",")])
except: pass

if total_mins > 0: st.caption(f"💡 您選取的項目需約 {total_mins} 分鐘 (需預留 {slots_needed} 個連續時段)")

def select_start(t): st.session_state.selected_times = [t]

valid_slots = []
conflicts = {}
for i, t in enumerate(time_slots):
    conflict = False
    for j in range(slots_needed):
        if i + j >= len(time_slots) or time_slots[i+j] in booked_times:
            conflict = True
            break
    conflicts[t] = conflict
    if not conflict: valid_slots.append(t)

# 依序橫向排版：因為一小時有 00, 20, 40 三個時段，3 欄排版剛剛好等於一行一小時！
for i in range(0, len(time_slots), 3):
    cols = st.columns(3)
    for j in range(3):
        if i + j < len(time_slots):
            t = time_slots[i + j]
            is_sel = (len(st.session_state.selected_times) > 0 and t == st.session_state.selected_times[0])
            with cols[j]:
                st.button(
                    t, 
                    key=f"t_{t}", 
                    disabled=conflicts[t], 
                    type="primary" if is_sel else "secondary", 
                    use_container_width=True, 
                    on_click=select_start, 
                    args=(t,)
                )

if st.session_state.selected_times and st.session_state.selected_times[0] not in valid_slots:
    st.session_state.selected_times = []

# --- 6. 送出 ---
st.markdown("### 預約確認")
c1 = st.checkbox("加入官方LINE收到預約通知", key="c1")
c2 = st.checkbox("更改時間限1次，需3天前告知", key="c2")

if st.button("送出確認預約", type="primary", use_container_width=True):
    if not name or not phone or not selected_services or not st.session_state.selected_times or not (c1 and c2):
        st.warning("⚠️ 請確認資料、服務項目、時段均已填寫並勾選同意事項。")
    else:
        start_t = st.session_state.selected_times[0]
        start_idx = time_slots.index(start_t)
        final_times = ", ".join(time_slots[start_idx : start_idx + slots_needed])
        clean_phone = phone.strip()
        
        sheet_bookings.append_row([str(date.today()), str(booking_date), "'" + final_times, name, "'" + clean_phone, line_id, "Christine", ", ".join(selected_services), total_price, "已預約", ""])
        
        try:
            cust_records = sheet_customers.get_all_records()
            existing_phones = []
            found_row_idx = -1
            current_visits = 0
            for idx, r in enumerate(cust_records):
                p = str(r.get("Phone", "")).replace("'", "").strip()
                if len(p) == 9 and p.startswith("9"): p = "0" + p
                existing_phones.append(p)
                if p == clean_phone:
                    found_row_idx = idx + 2
                    current_visits = int(r.get("Total_Visits", 0)) if str(r.get("Total_Visits", "")).isdigit() else 0
                    
            if clean_phone not in existing_phones:
                sheet_customers.append_row(["'" + clean_phone, name, line_id, birthday, "", 1])
            else:
                sheet_customers.update_cell(found_row_idx, 6, current_visits + 1)
        except: pass 
        
        summary = f"【時嶼預約成功】\n姓名：{name}\n日期：{booking_date}\n時間：{final_times.split(',')[0]} (總時長 {total_mins} 分鐘)\n項目：{', '.join(selected_services)}"
        st.success("🎉 預約成功！內容已備妥。")
        st.code(summary, language=None)
        st.markdown(f'<a href="https://lin.ee/VPHMiO8" target="_blank"><button style="width:100%; background-color:#06C755; color:white; border:none; padding:12px; border-radius:10px; font-weight:bold;">點此跳轉官方 LINE (完成預約)</button></a>', unsafe_allow_html=True)
        st.balloons()
