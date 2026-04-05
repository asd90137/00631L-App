import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# 1. 設定 App 頁面
st.set_page_config(page_title="賴賴終極戰情室", page_icon="📈", layout="centered")

# --- 資料讀取與前處理 ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_trades_raw = conn.read(ttl=0) 
    
    # 台股庫存計算 (00631L)
    temp_df = df_trades_raw.copy()
    temp_df['成交日期'] = pd.to_datetime(temp_df['成交日期'])
    temp_df.loc[temp_df['交易類型'].str.contains('賣出', na=False), '庫存股數'] = -temp_df['庫存股數'].abs()
    temp_df.loc[temp_df['交易類型'].str.contains('賣出', na=False), '持有成本'] = -temp_df['持有成本'].abs()
    actual_shares = temp_df['庫存股數'].sum()
    actual_cost = temp_df['持有成本'].sum()
except:
    actual_shares, actual_cost = 0, 0

# --- App 標題與側邊欄 ---
st.title("🛡️ 賴賴投資戰情室 V3.5")

# 分頁功能
tab1, tab2 = st.tabs(["🇹🇼 台股 00631L", "🇺🇸 美股狙擊系統"])

# ==========================================
# 🇹🇼 分頁一：台股 00631L 核心
# ==========================================
with tab1:
    st.sidebar.header("⚙️ 台股參數")
    loan1 = st.sidebar.number_input("信貸一剩餘", value=2056231)
    loan2 = st.sidebar.number_input("信貸二剩餘", value=935907)
    base_m = st.sidebar.number_input("每月基準扣款", value=100000)
    cash = st.sidebar.number_input("台股帳戶可用現金", value=2000000)
    target_exp_pct = st.sidebar.number_input("目標曝險度 (%)", value=200)

    if st.button("🚀 啟動台股即時分析", use_container_width=True):
        with st.spinner('抓取 00631L 數據...'):
            data = yf.download("00631L.TW", period="max", progress=False, auto_adjust=False)
            # 還原股價邏輯 (簡化處理)
            close_prices = data['Close']['00631L.TW'] if isinstance(data.columns, pd.MultiIndex) else data['Close']
            adj_prices = close_prices.copy()
            mask = (adj_prices.index < '2026-03-23') & (adj_prices > 100)
            adj_prices.loc[mask] = round(adj_prices.loc[mask] / 22.0, 2)
            
            current_p = float(adj_prices.iloc[-1])
            yest_close = float(adj_prices.iloc[-2])
            
            cur_val = actual_shares * current_p
            abs_pnl = cur_val - actual_cost
            pnl_pct = abs_pnl / actual_cost if actual_cost > 0 else 0
            today_pnl = (current_p - yest_close) * actual_shares

            # V3 動態基準
            v3_dynamic_base = base_m * (1 - min(pnl_pct, 0.20)) if pnl_pct > 0 else base_m * (1 + min(abs(pnl_pct) * 2, 1.00))

            # 顯示 00631L 八宮格
            st.subheader("📊 庫存明細")
            c1, c2 = st.columns(2)
            c1.metric("總市值", f"NT$ {cur_val:,.0f}")
            c2.metric("總投入成本", f"NT$ {actual_cost:,.0f}")
            c3, c4 = st.columns(2)
            c3.metric("未實現損益", f"NT$ {abs_pnl:,.0f}", f"{pnl_pct*100:+.2f}%")
            c4.metric("今日損益", f"NT$ {today_pnl:,.0f}", f"{(current_p/yest_close-1)*100:+.2f}%")
            
            st.divider()
            st.info(f"💡 本月動態基準金額：**NT$ {v3_dynamic_base:,.0f}**")

# ==========================================
# 🇺🇸 分頁二：美股狙擊系統
# ==========================================
with tab2:
    st.subheader("🎯 SOXX 趨勢監測 (100 DMA)")
    
    with st.spinner('📡 抓取美股數據中...'):
        # 抓取 SOXX (監控用) 與 核心持倉
        tickers = ["SOXX", "SOXL", "TMF", "BITX"]
        us_data = yf.download(tickers, period="200d", progress=False)
        
        # 1. SOXX 趨勢判斷
        soxx_close = us_data['Close']['SOXX'].dropna()
        soxx_100dma = soxx_close.rolling(window=100).mean()
        curr_soxx = soxx_close.iloc[-1]
        curr_dma = soxx_100dma.iloc[-1]
        
        if curr_soxx > curr_dma:
            st.success(f"🟢 SOXX 目前在 100 DMA 之上 (現價:{curr_soxx:.2f} / DMA:{curr_dma:.2f})\n\n**指令：趨勢向上，SOXL 持續獲利。**")
        else:
            st.error(f"🔴 SOXX 跌破 100 DMA (現價:{curr_soxx:.2f} / DMA:{curr_dma:.2f})\n\n**指令：停利訊號觸發！請考慮全數賣出轉入 TLT。**")
        
        st.divider()
        
        # 2. SOXL 階梯買入追蹤
        st.subheader("⏳ TMF ➔ SOXL 輪動階梯")
        curr_soxl = float(us_data['Close']['SOXL'].iloc[-1])
        steps = [30.14, 21.09, 14.77]
        
        col_s1, col_s2, col_s3 = st.columns(3)
        cols = [col_s1, col_s2, col_s3]
        
        for i, target in enumerate(steps):
            if curr_soxl <= target:
                cols[i].warning(f"✅ 階梯 {i+3}\n已達標\n{target}")
            else:
                cols[i].info(f"⏳ 階梯 {i+3}\n目標 {target}\n距: {((curr_soxl/target)-1)*100:.1f}%")
        
        st.write(f"🔹 **SOXL 目前現價：${curr_soxl:.2f}**")
        
        st.divider()
        
        # 3. 美股資產現況 (手動輸入部分資訊暫代，之後可存 Sheets)
        st.subheader("📦 美股持倉快報")
        # 這裡根據你提供的 2026/04 數據
        us_positions = {
            "TMF": {"shares": 1050, "cost": 52.94},
            "SOXL": {"shares": 545, "cost": 50.99},
            "BITX": {"shares": 11, "cost": 29.67}
        }
        
        total_us_val = 0
        for t, info in us_positions.items():
            price = float(us_data['Close'][t].iloc[-1])
            val = price * info['shares']
            total_us_val += val
            pnl = (price - info['cost']) / info['cost'] * 100
            st.write(f"**{t}**: ${price:.2f} (損益: {pnl:+.2f}%) | 市值: ${val:,.2f}")
        
        st.metric("美股總估計市值", f"${total_us_val:,.2f}")

# ==========================================
# 📝 共同底部：新增紀錄
# ==========================================
st.divider()
st.subheader("📝 新增交易紀錄 (同步至 Google)")
# (這裡保留你原本的寫入 Google 試算表代碼...)
st.caption("📱 提示：美股資料延遲約 15 分鐘。")
