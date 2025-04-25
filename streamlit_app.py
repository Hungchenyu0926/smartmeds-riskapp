
import streamlit as st
import gspread
from openai import OpenAI
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

st.set_page_config(page_title="SmartMeds-AI", page_icon="💊", layout="wide")
st.title("💊 SmartMeds-AI 交互作用與風險分層")

# ---------- Google Sheets 認證 ----------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    st.secrets["GSPREAD_CREDENTIALS"], scope
)
gs_client = gspread.authorize(creds)
sheet = gs_client.open("SmartMeds_DB").sheet1

# ---------- OpenAI client ----------
openai_client = OpenAI(api_key=st.secrets["OPENAI"]["api_key"])

# ---------- GPT 助理函式 ----------
def gpt_risk_label(drug_list:str)->str:
    """回傳 '紅' '黃' '綠'"""
    prompt = (
        "你是一位資深臨床藥師，僅依下列用藥組合判斷整體風險："
        "若高風險輸出'紅'，中等風險輸出'黃'，低風險輸出'綠'，不要加其他文字。\n"
        f"用藥: {drug_list}"
    )
    resp = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"user","content":prompt}],
        temperature=0
    )
    ans = resp.choices[0].message.content.strip()
    return "紅" if "紅" in ans else "黃" if "黃" in ans else "綠"

# ---------- UI ----------
st.subheader("📋 SmartMeds_DB 現況")
df = st.session_state.get("df_cache")
if df is None:
    import pandas as pd
    df = pd.DataFrame(sheet.get_all_records())
    if "藥師風險判讀" not in df.columns:
        df["藥師風險判讀"] = ""
    st.session_state["df_cache"] = df
st.dataframe(df, use_container_width=True)

# ---------- 一鍵風險判讀 ----------
if st.button("🔴🟡🟢 風險判讀", type="primary"):
    with st.spinner("GPT 判讀中..."):
        updated_vals=[]
        for idx, row in df.iterrows():
            meds = row.get("目前用藥", "")
            label = gpt_risk_label(meds) if meds else ""
            df.at[idx, "藥師風險判讀"] = label
            updated_vals.append(label)
        # 寫回 Google Sheet
        col_idx = df.columns.get_loc("藥師風險判讀") + 1
        rng = f"{gspread.utils.rowcol_to_a1(2,col_idx)}:{gspread.utils.rowcol_to_a1(len(df)+1,col_idx)}"
        cell_list = sheet.range(rng)
        for c,val in zip(cell_list, updated_vals):
            c.value=val
        sheet.update_cells(cell_list, value_input_option="USER_ENTERED")
    st.success("已完成 GPT 風險判讀並回寫 Google Sheet ✔️")
    st.dataframe(df, use_container_width=True)

# ---------- 個案即時建議 ----------
st.subheader("📝 AI 用藥安全建議 (單筆)")
drug_input = st.text_input("🔎 請輸入藥品名稱（逗號分隔）")
age = st.number_input("👤 年齡",1,120,65)
cond_input = st.text_input("🩺 病史或慢性疾病（逗號分隔，可空白）")

def get_drug_advice(drug_list, age, conditions):
    prompt = (
        "你是一位資深臨床藥師，依 2023 Beers Criteria 與 2022 STOPP/START v3，" 
        "格式: 1.潛在問題 2.機制/風險 3.建議替代方案/監測 4.參考來源(Beers/STOPP)。\n"
        f"年齡:{age} 歲\n病史:{', '.join(conditions) if conditions else '無'}\n"
        f"藥品:{', '.join(drug_list)}\n回答請用繁體中文並分段。" )
    r = openai_client.chat.completions.create(
        model="gpt-3.5-turbo", messages=[{"role":"user","content":prompt}], temperature=0.4)
    return r.choices[0].message.content

if st.button("📋 生成用藥建議"):
    drugs=[d.strip() for d in drug_input.split(',') if d.strip()]
    conditions=[c.strip() for c in cond_input.split(',') if c.strip()]
    if not drugs:
        st.warning("請輸入至少一個藥品名稱")
        st.stop()
    with st.spinner("AI 分析中..."):
        try:
            advice = get_drug_advice(drugs, age, conditions)
            st.markdown(advice)
        except Exception as e:
            st.error(f"🛑 發生錯誤：{e}")
