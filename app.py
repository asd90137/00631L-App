import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# ==========================================
# 賴賴投資戰情室 V4.2 - 戰術圖表全能版
# ==========================================

st.set_page_config(page_title="賴賴終極戰情室", page_icon="📈", layout="centered")
st.title("🛡️ 賴賴投資戰情室 V4.2")

if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

st.sidebar.header("⚙️ 台股參數")
loan1 = st.sidebar.number_input("1. 信貸一剩餘本金", value=2056231)
loan2 = st.sidebar.number_input("2. 信貸二剩餘本金", value=935907)
base_m = st.sidebar.number_input("3. 基準每月定期定額", value=100000)
cash = st.sidebar.number_input("4. 目前帳戶可用現金", value=2000000)
target_exp_pct = st.sidebar.number_input("5. 設定目標曝險度 (%)", value=200)

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_trades_raw = conn.read(ttl=0) 
    
    temp_df = df_trades_raw.copy()
    temp_df['成交日期'] = pd.to_datetime(temp_df['成交日期'])
    temp_df.loc[temp_df['交易類型'].str.contains('賣出', na=False), '庫存股數'] = -temp_df['庫存股數'].abs()
    temp_df.loc[temp_df['交易類型'].str.contains('賣出', na=False), '持有成本'] = -temp_df['持有成本'].abs()
    
    actual_shares = temp_df['庫存股數'].sum()
    actual_cost = temp_df['持有成本'].sum()
    st.sidebar.success("✅ 台股資料同步成功！")
except Exception as e:
    st.sidebar.error("❌ 台股資料讀取失敗。")
    actual_shares, actual_cost = 0, 0

if st.button("🚀 啟動戰情室全面掃描", use_container_width=True):
    st.session_state.analyzed = True

tab1, tab2 = st.tabs(["🇹🇼 台股 00631L", "🇺🇸 美股狙擊系統"])

if st.session_state.analyzed:
    with tab1:
        with st.spinner('📡 掃描中...'):
            TICKER = "00631L.TW"
            data = yf.download(TICKER, period="max", progress=False, auto_adjust=False)
            
            if isinstance(data.columns, pd.MultiIndex):
                raw_prices = data['Adj Close'][TICKER].dropna() if 'Adj Close' in data.columns.get_level_values(0) else data['Close'][TICKER].dropna()
            else:
                raw_prices = data['Adj Close'].dropna() if 'Adj Close' in data.columns else data['Close'].dropna()
                    
            raw_prices.index = pd.to_datetime(raw_prices.index).tz_localize(None)

            # 3/23 股價還原
            adj_prices = raw_prices.copy()
            split_cutoff = pd.to_datetime('2026-03-23')
            mask = (adj_prices.index < split_cutoff) & (adj_prices > 100)
            if mask.any():
                adj_prices.loc[mask] = round(adj_prices.loc[mask] / 22.0, 2)
                
            current_p = float(adj_prices.iloc[-1])
            yest_close = float(adj_prices.iloc[-2])
            
            cur_val = actual_shares * current_p
            abs_pnl = cur_val - actual_cost
            pnl_real = abs_pnl / actual_cost if actual_cost > 0 else 0
            avg_cost = actual_cost / actual_shares if actual_shares > 0 else 0
            
            intraday_drop = (current_p - yest_close) / yest_close
            today_pnl = (current_p - yest_close) * actual_shares
            
            # --- 儀表板數據 ---
            st.subheader("📊 詳細庫存與損益明細")
            c1, c2 = st.columns(2)
            c1.metric("總市值 (元)", f"NT$ {cur_val:,.0f}")
            c2.metric("總投入成本", f"NT$ {actual_cost:,.0f}")
            c3, c4 = st.columns(2)
            c3.metric("未實現總損益", f"NT$ {abs_pnl:,.0f}", f"{pnl_real*100:+.2f}%")
            c4.metric("今日損益", f"NT$ {today_pnl:,.0f}", f"{intraday_drop*100:+.2f}%")
            c5, c6 = st.columns(2)
            c5.metric("庫存總股數", f"{actual_shares:,.0f} 股")
            c6.metric("持有均價", f"NT$ {avg_cost:,.2f}")

            st.divider()

            # --- 戰術圖表區 ---
            st.subheader("🌐 戰術圖表分析")
            recent_prices = adj_prices[adj_prices.index >= pd.to_datetime('2024-01-01')]
            
            # A. 走勢與成本線
            st.write("📈 **A. 價格走勢與均價防線**")
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=recent_prices.index, y=recent_prices.values, mode='lines', name='還原股價', line=dict(color='#E71D36', width=2)))
            if avg_cost > 0:
                fig1.add_hline(y=avg_cost, line_dash="dash", line_color="#00A86B", annotation_text=f"你的均價: {avg_cost:.2f}")
            fig1.update_layout(template='plotly_white', margin=dict(l=0, r=0, t=10, b=0), height=250)
            st.plotly_chart(fig1, use_container_width=True)

            # B. 多空戰略動能圖 (結合漲幅與回檔)
            st.write("📊 **B. 多空戰略動能圖 (創高 vs 回檔)**")
            rolling_max = recent_prices.cummax()
            # 回檔為負，創高時顯示相對於前波高點的增長 (若持平則為0)
            drawdown = (recent_prices - rolling_max) / rolling_max * 100
            
            fig2 = go.Figure()
            # 負向回檔區 (橘色)
            fig2.add_trace(go.Scatter(x=drawdown.index, y=drawdown.values, fill='tozeroy', mode='lines', name='回檔幅度%', line=dict(color='orange')))
            # 繪製觸發線
            for val, color, txt in [(-5, "gray", "標準"), (-10, "orange", "恐慌"), (-15, "red", "重壓")]:
                fig2.add_hline(y=val, line_dash="dot", line_color=color, annotation_text=txt)
            
            fig2.update_layout(template='plotly_white', margin=dict(l=0, r=0, t=10, b=0), height=250, yaxis_title="幅度 %")
            st.plotly_chart(fig2, use_container_width=True)

            # C. 庫存損益率走勢圖
            st.write("💰 **C. 庫存損益率歷史模擬 (以均價為基準)**")
            if avg_cost > 0:
                # 歷史價格相對於目前均價的損益趴數
                pnl_history = (recent_prices - avg_cost) / avg_cost * 100
                fig3 = go.Figure()
                # 填色：賺錢綠色，賠錢紅色
                fig3.add_trace(go.Scatter(x=pnl_history.index, y=pnl_history.values, mode='lines', name='損益率%', line=dict(color='#247BA0')))
                fig3.add_hline(y=0, line_width=2, line_color="black") # 均價平衡線
                # 著色區塊
                fig3.add_hrect(y0=0, y1=max(pnl_history.max(), 10), fillcolor="green", opacity=0.1, layer="below", line_width=0)
                fig3.add_hrect(y0=min(pnl_history.min(), -10), y1=0, fillcolor="red", opacity=0.1, layer="below", line_width=0)
                
                fig3.update_layout(template='plotly_white', margin=dict(l=0, r=0, t=10, b=0), height=250, yaxis_title="損益 %")
                st.plotly_chart(fig3, use_container_width=True)

    with tab2:
        # (美股模組保持 V3.9 俐落版...)
        with st.spinner('📡 抓取美股數據中...'):
            tickers = ["SOXX", "SOXL", "TMF", "BITX"]
            us_data = yf.download(tickers, period="200d", progress=False)
            us_positions = {"SOXL": {"shares": 545, "cost": 50.99}, "TMF": {"shares": 1050, "cost": 52.94}, "BITX": {"shares": 11, "cost": 29.67}}
            st.subheader("🎯 1. 大盤趨勢與輪動階梯")
            soxx_close = us_data['Close']['SOXX'].dropna()
            soxx_100dma = soxx_close.rolling(window=100).mean()
            curr_soxx, curr_dma = soxx_close.iloc[-1], soxx_100dma.iloc[-1]
            if curr_soxx > curr_dma:
                st.success(f"🟢 **SOXX 多頭續抱** | 現價:{curr_soxx:.2f} (100DMA:{curr_dma:.2f})\n\n**指令：趨勢向上，SOXL 持續抱牢。**")
            else:
                st.error(f"🔴 **停利訊號觸發！** | 現價跌破 100DMA ({curr_dma:.2f})\n\n**指令：全數賣出 SOXL 轉入 TLT。**")
            
            curr_soxl = float(us_data['Close']['SOXL'].dropna().iloc[-1])
            steps = [30.14, 21.09, 14.77]
            cols = st.columns(3)
            for i, target in enumerate(steps):
                if curr_soxl <= target: cols[i].warning(f"✅ 階梯 {i+3}\n達標 ${target}")
                else: cols[i].info(f"⏳ 階梯 {i+3}\n目標 ${target}")
            st.divider()
            # (總資產與個股明細...)
            total_us_val = 0
            total_us_cost = 0
            for t, info in us_positions.items():
                p_curr = float(us_data['Close'][t].dropna().iloc[-1])
                total_us_val += p_curr * info['shares']
                total_us_cost += info['cost'] * info['shares']
            st.subheader("📋 2. 美股總資產")
            cu1, cu2 = st.columns(2)
            cu1.metric("總市值 (USD)", f"${total_us_val:,.2f}")
            cu2.metric("總投入成本", f"${total_us_cost:,.2f}")
            st.divider()
            st.subheader("📦 3. 個股明細")
            for t, info in us_positions.items():
                p_curr = float(us_data['Close'][t].dropna().iloc[-1])
                p_yest = float(us_data['Close'][t].dropna().iloc[-2])
                cur_val = p_curr * info['shares']
                abs_pnl = cur_val - (info['cost'] * info['shares'])
                st.markdown(f"#### 📌 **{t}**")
                st.write(f"🔹 **現價:** ${p_curr:.2f} ({(p_curr/p_yest-1)*100:+.2f}%) | **今日損益:** ${(p_curr-p_yest)*info['shares']:,.2f}")
                st.write(f"🔹 **均價:** ${info['cost']:.2f} | **未實現損益:** ${abs_pnl:,.2f} ({abs_pnl/(info['cost']*info['shares'])*100:+.2f}%)")
                st.markdown("---")

st.caption("📱 提示：美股延遲15分。台股圖表顯示 2024 至今。")
