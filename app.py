import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# 1. 設定 App 頁面
st.set_page_config(page_title="00631L 實戰大腦", page_icon="🤖", layout="centered")
st.title("🤖 00631L 實戰大腦 V3")

# 2. 側邊欄 (Sidebar) - 參數設定
st.sidebar.header("⚙️ 參數設定")
loan1 = st.sidebar.number_input("1. 信貸一剩餘本金", value=2056231, step=10000)
loan2 = st.sidebar.number_input("2. 信貸二剩餘本金", value=935907, step=10000)
base_m = st.sidebar.number_input("3. 基準每月定期定額", value=100000, step=10000)
cash = st.sidebar.number_input("4. 目前股票帳戶可用現金", value=0, step=10000)
target_exp_pct = st.sidebar.number_input("5. 設定目標曝險度 (%)", value=200)

st.sidebar.divider()
st.sidebar.subheader("📂 庫存現況 (暫代資料庫)")
actual_shares = st.sidebar.number_input("目前總庫存 (股)", value=10000, step=1000)
actual_cost = st.sidebar.number_input("目前總持有成本 (元)", value=1500000, step=10000)


# 3. 核心運算區塊
if st.button("🚀 啟動盤中決策與分析", use_container_width=True):
    with st.spinner('📡 正在連線抓取 00631L 即時數據...'):
        
        # --- 抓取真實股價 ---
        TICKER = "00631L.TW"
        df_p_all = yf.download(TICKER, period="max", progress=False, auto_adjust=False)
        
        if isinstance(df_p_all.columns, pd.MultiIndex):
            if 'Adj Close' in df_p_all.columns.get_level_values(0):
                raw_prices = df_p_all['Adj Close'][TICKER].dropna()
            else:
                raw_prices = df_p_all['Close'][TICKER].dropna()
        else:
            if 'Adj Close' in df_p_all.columns:
                raw_prices = df_p_all['Adj Close'].dropna()
            else:
                raw_prices = df_p_all['Close'].dropna()
                
        raw_prices.index = pd.to_datetime(raw_prices.index).tz_localize(None)

        # 處理 3/23 還原股價
        adj_prices = raw_prices.copy()
        split_cutoff = pd.to_datetime('2026-03-23')
        mask = (adj_prices.index < split_cutoff) & (adj_prices > 100)
        if mask.any():
            adj_prices.loc[mask] = round(adj_prices.loc[mask] / 22.0, 2)

        # 取得最新與昨日股價
        last_date = adj_prices.index[-1].date()
        today_date = pd.Timestamp.today().date()
        if last_date == today_date and len(adj_prices) > 1:
            yest_close = float(adj_prices.iloc[-2]) 
        else:
            yest_close = float(adj_prices.iloc[-1]) 
            
        current_p = float(adj_prices.iloc[-1])
        
        # --- 執行 V3 決策邏輯 ---
        cur_val = actual_shares * current_p
        pnl_real = (cur_val - actual_cost) / actual_cost if actual_cost > 0 else 0
        
        if pnl_real > 0:
            v3_dynamic_base = base_m * (1 - min(pnl_real, 0.20))
        else:
            v3_dynamic_base = base_m * (1 + min(abs(pnl_real) * 2, 1.00))

        intraday_drop = (current_p - yest_close) / yest_close
        suggest_buy_action = "無須動作 (維持紀律等待)"
        
        if intraday_drop <= -0.03:
            d = abs(intraday_drop)
            if d >= 0.15: mult = 4.0; level_str = "重壓加碼"
            elif d >= 0.10: mult = 3.0; level_str = "恐慌買進"
            elif d >= 0.08: mult = 2.0; level_str = "恐慌買進"
            elif d >= 0.06: mult = 1.5; level_str = "中型修正"
            elif d >= 0.05: mult = 1.0; level_str = "標準買點"
            elif d >= 0.04: mult = 0.5; level_str = "波段低接"
            else: mult = 0.25; level_str = "日常試單"
            
            suggest_buy_amount = v3_dynamic_base * mult
            suggest_buy_action = f"⚠️ 觸發大跌加碼！級別：{level_str} | 應投入：NT$ {suggest_buy_amount:,.0f}"

        # --- 資產再平衡邏輯 ---
        net_asset = cur_val + cash - (loan1 + loan2)
        current_exposure = (cur_val * 2) / net_asset if net_asset > 0 else 0
        target_stock_value = ((target_exp_pct / 100.0) * net_asset) / 2
        rebalance_diff = cur_val - target_stock_value

        # ==========================================
        # 📊 畫面呈現區塊
        # ==========================================
        st.subheader("📈 即時盤中決策台")
        
        col1, col2 = st.columns(2)
        col1.metric(label="今日還原現價", value=f"{current_p:.2f}", delta=f"{intraday_drop*100:+.2f}%")
        col2.metric(label="昨日還原收盤", value=f"{yest_close:.2f}")
        
        if intraday_drop <= -0.03:
            st.error(f"💡 **盤中行動指令**：\n\n{suggest_buy_action}")
        else:
            st.info(f"💡 **盤中行動指令**：\n\n{suggest_buy_action}")
            
        st.divider()
        
        st.subheader("⚖️ 資產再平衡檢視")
        st.write(f"🔹 **目前庫存市值:** NT$ {cur_val:,.0f}")
        st.write(f"🔹 **總淨資產 (股+現-債):** NT$ {net_asset:,.0f}")
        st.write(f"🔹 **目前實際曝險度:** {current_exposure*100:.2f}% (目標: {target_exp_pct}%)")
        
        if rebalance_diff > 0:
            st.warning(f"🚨 【曝險過高】應獲利了結，減碼賣出市值: NT$ {rebalance_diff:,.0f}")
        elif rebalance_diff < 0:
            st.success(f"🟢 【曝險過低】若資金允許，可加碼買進市值: NT$ {abs(rebalance_diff):,.0f}")
        else:
            st.success("✅ 目前曝險完美符合目標，不需調整。")
            
        st.divider()

        st.subheader("🌐 00631L 歷史還原走勢圖")
        
        # 繪製簡單的手機版互動圖表
        fig = go.Figure()
        recent_prices = adj_prices.tail(252) # 只抓近一年資料讓手機跑順一點
        fig.add_trace(go.Scatter(x=recent_prices.index, y=recent_prices.values, mode='lines', name='還原股價', line=dict(color='#E71D36', width=2)))
        fig.update_layout(template='plotly_white', margin=dict(l=20, r=20, t=30, b=20), hovermode='x unified')
        st.plotly_chart(fig, use_container_width=True)

