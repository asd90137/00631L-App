import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection

# 1. 設定 App 頁面
st.set_page_config(page_title="00631L 實戰大腦", page_icon="🤖", layout="centered")
st.title("🤖 00631L 實戰大腦 (雲端連動版)")

# 2. 側邊欄參數設定
st.sidebar.header("⚙️ 參數設定")
loan1 = st.sidebar.number_input("1. 信貸一剩餘本金", value=2056231)
loan2 = st.sidebar.number_input("2. 信貸二剩餘本金", value=935907)
base_m = st.sidebar.number_input("3. 基準每月定期定額", value=100000)
cash = st.sidebar.number_input("4. 目前帳戶可用現金", value=0)
target_exp_pct = st.sidebar.number_input("5. 設定目標曝險度 (%)", value=200)

# 3. 雲端資料庫連動 (Google Sheets)
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_trades = conn.read()
    
    # 計算即時庫存與成本
    df_trades['成交日期'] = pd.to_datetime(df_trades['成交日期'])
    # 處理賣出為負值
    temp_df = df_trades.copy()
    temp_df.loc[temp_df['交易類型'].str.contains('賣出', na=False), '庫存股數'] = -temp_df['庫存股數'].abs()
    temp_df.loc[temp_df['交易類型'].str.contains('賣出', na=False), '持有成本'] = -temp_df['持有成本'].abs()
    
    actual_shares = temp_df['庫存股數'].sum()
    actual_cost = temp_df['持有成本'].sum()
    
    st.sidebar.success(f"✅ 雲端同步成功！\n目前庫存：{actual_shares:,.0f} 股")
except:
    st.sidebar.error("❌ 雲端資料庫連線失敗，請檢查 Secrets 設定")
    actual_shares, actual_cost = 0, 0

# 4. 核心運算按鈕
if st.button("🚀 啟動最新盤中決策", use_container_width=True):
    with st.spinner('📡 正在抓取即時行情並運算中...'):
        TICKER = "00631L.TW"
        data = yf.download(TICKER, period="5d", progress=False)
        # 取得最新還原價 (簡化版處理)
        current_p = float(data['Close'].iloc[-1])
        yest_close = float(data['Close'].iloc[-2])
        
        # V3 加碼邏輯
        cur_val = actual_shares * current_p
        pnl_real = (cur_val - actual_cost) / actual_cost if actual_cost > 0 else 0
        intraday_drop = (current_p - yest_close) / yest_close
        
        # 計算曝險
        net_asset = cur_val + cash - (loan1 + loan2)
        current_exposure = (cur_val * 2) / net_asset if net_asset > 0 else 0
        
        # 顯示結果
        st.subheader("📈 即時盤中決策台")
        c1, c2 = st.columns(2)
        c1.metric("今日現價", f"{current_p:.2f}", f"{intraday_drop*100:.2f}%")
        c2.metric("總市值", f"{cur_val:,.0f}")
        
        st.divider()
        st.subheader("⚖️ 曝險檢視")
        st.write(f"🔹 目前實際曝險度：**{current_exposure*100:.2f}%**")
        
        if current_exposure > (target_exp_pct/100 + 0.2):
            st.warning("🚨 曝險過高，建議年度再平衡時考慮減碼。")
        else:
            st.success("✅ 曝險狀況良好，請維持紀律扣款。")

st.caption("📱 提示：將此網頁「加入主畫面」，它就是你的專屬實戰 App！")
