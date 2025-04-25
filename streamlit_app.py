
# streamlit_app.py  ─ 完整範例
import streamlit as st
import pandas as pd
import gspread
import pickle
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="SmartMeds 風險分層", page_icon="💊", layout="wide")
st.title("💊 長者多重用藥風險分層系統")

# -------------------------------#
# 1. Google Sheets 認證與載入
# -------------------------------#
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    st.secrets["GSPREAD_CREDENTIALS"], scope
)
client = gspread.authorize(creds)

SHEET_NAME = "SmartMeds_DB"
worksheet = client.open(SHEET_NAME).sheet1

# 將整表轉 DataFrame
df = pd.DataFrame(worksheet.get_all_records())
if "藥師風險判讀" not in df.columns:
    # 若尚未建欄位則補上
    df["藥師風險判讀"] = ""

st.subheader("📋 最新照護用藥資料")
st.dataframe(df, use_container_width=True)

# -------------------------------#
# 2. 風險判讀模型（可替換）
# -------------------------------#
HIGH_RISK_LIST = ["Warfarin", "Digoxin", "Diazepam", "Insulin"]  # 示範用
MED_RISK_LIST = ["Aspirin", "Metformin", "Furosemide"]

def rule_based_risk(med_str: str) -> str:
    """簡化規則：含高風險→紅；中風險→黃；否則綠"""
    meds = [m.strip().title() for m in med_str.split(",")]
    if any(m in meds for m in HIGH_RISK_LIST):
        return "紅"
    if any(m in meds for m in MED_RISK_LIST):
        return "黃"
    return "綠"

# 主選擇開關（此示範用 rule_based）
predict_risk = rule_based_risk

# -------------------------------#
# 3. 一鍵風險判讀按鈕
# -------------------------------#
if st.button("🔴🟡🟢 風險判讀", type="primary"):
    with st.spinner("AI 風險分析中…"):
        updated_rows = []
        for idx, row in df.iterrows():
            meds = row.get("目前用藥", "")
            if not meds:
                risk = ""
            else:
                risk = predict_risk(meds)
            df.at[idx, "藥師風險判讀"] = risk
            updated_rows.append(risk)

        # 寫回 Google Sheet「藥師風險判讀」欄
        col_index = df.columns.get_loc("藥師風險判讀") + 1  # gspread 1-based
        cell_range = f"{gspread.utils.rowcol_to_a1(2, col_index)}:" \
                     f"{gspread.utils.rowcol_to_a1(len(df) + 1, col_index)}"
        cell_list = worksheet.range(cell_range)
        for cell, risk in zip(cell_list, updated_rows):
            cell.value = risk
        worksheet.update_cells(cell_list, value_input_option="USER_ENTERED")

    st.success("判讀完成！表格已更新。")
    st.dataframe(df, use_container_width=True)

# -------------------------------#
# 4. 搜尋功能
# -------------------------------#
st.divider()
query = st.text_input("🔍 依藥品名稱搜尋（多品項以逗號分隔）")
if query:
    keywords = [q.strip().title() for q in query.split(",")]
    mask = df["目前用藥"].apply(
        lambda x: any(k in x.title() for k in keywords) if isinstance(x, str) else False
    )
    st.dataframe(df[mask], use_container_width=True)
