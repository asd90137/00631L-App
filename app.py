import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# ==========================================
# 賴賴投資戰情室 V5.6 - 終極完美縫合版
# ==========================================

st.set_page_config(page_title="賴賴終極戰情室", page_icon="📈", layout="centered")
st.title("🛡️ 賴賴投資戰情室 V5.6")

if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

# --- 側邊欄參數設定 ---
st.sidebar.header("⚙️ 資金與曝險參數")
loan1 = st.sidebar.number_input("1. 信貸一剩餘本金", value=2056231)
loan2 = st.sidebar.number_input("2. 信貸二剩餘本金", value=935907)
base_m = st.sidebar.number_input("3. 基準每月定期定額", value=100000)
cash = st.sidebar.number_input("4. 目前帳戶可用現金", value=2000000)
target_exp_pct = st.sidebar.number_input("5. 設定目標曝險度 (%)", value=200)

st.sidebar.divider()
st.sidebar.header("⚙️ 生命週期與退休規劃")
usd_twd = st.sidebar.number_input("6. 目前美元匯率", value=32.0)
hc_years = st.sidebar.number_input("7. 預計剩餘投入年限", value=10, step=1)
target_k = st.sidebar.number_input("8. 一生目標曝險度 (%)", value=83)
st.sidebar.caption("--- 退休反推參數 ---")
target_monthly_now = st.sidebar.number_input("9. 目標月領金額 (現值)", value=100000, step=10000)
inflation_rate_in = st.sidebar.number_input("10. 預估年化通膨 (%)", value=2.0)
withdrawal_rate_in = st.sidebar.number_input("11. 安全提領率 (%)", value=4.0)

inflation_rate = inflation_rate_in / 100.0
withdrawal_rate = withdrawal_rate_in / 100.0

# --- 數據同步 ---
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
    df_trades_raw = pd.DataFrame(); actual_shares, actual_cost = 0, 0

if st.button("🚀 啟動戰情室全面掃描", use_container_width=True):
    st.session_state.analyzed = True

# ==========================================
# 核心計算區 (預先算出所有分頁共用數據)
# ==========================================
if st.session_state.analyzed:
    # 1. 抓取台股數據
    TICKER = "00631L.TW"
    split_cutoff = pd.to_datetime('2026-03-23')
    tkr_tw = yf.Ticker(TICKER)
    try:
        raw_curr_tw = float(tkr_tw.fast_info.last_price)
        raw_yest_tw = float(tkr_tw.fast_info.previous_close)
    except:
        hist_tw = yf.download(TICKER, period="2d", progress=False)
        raw_curr_tw = float(hist_tw['Close'].iloc[-1]); raw_yest_tw = float(hist_tw['Close'].iloc[-2])
    
    current_p = round(raw_curr_tw / 22.0, 2) if raw_curr_tw > 100 else raw_curr_tw
    yest_close = round(raw_yest_tw / 22.0, 2) if raw_yest_tw > 100 else raw_yest_tw
    cur_val = actual_shares * current_p

    # 2. 抓取美股數據 (修正盤前誤判 Bug)
    us_positions = {"SOXL": {"shares": 545, "cost": 50.99}, "TMF": {"shares": 1050, "cost": 52.94}, "BITX": {"shares": 11, "cost": 29.67}}
    tickers_us = ["SOXX", "SOXL", "TMF", "BITX"]
    us_data_hist = yf.download(tickers_us, period="5d", progress=False)
    us_live = {}
    total_us_val = 0.0
    
    for t, info in us_positions.items():
        try:
            # 強制抓取當天 1 分鐘線來判斷真正盤前/盤中價格，避開 fast_info Bug
            intra = yf.download(t, period="1d", interval="1m", progress=False)
            curr_price_us = float(intra['Close'].iloc[-1])
            yest_price_us = float(us_data_hist['Close'][t].dropna().iloc[-2]) if t in us_data_hist['Close'] else 0.0
        except:
            curr_price_us = float(us_data_hist['Close'][t].iloc[-1])
            yest_price_us = float(us_data_hist['Close'][t].iloc[-2])
        
        us_live[t] = {'curr': curr_price_us, 'yest': yest_price_us}
        total_us_val += curr_price_us * info['shares']
    total_us_val_twd = total_us_val * usd_twd

    # ==========================================
    # 分頁實作
    # ==========================================
    tab1, tab2, tab3 = st.tabs(["🇹🇼 台股 00631L", "🇺🇸 美股狙擊系統", "🛬 生命周期與退休"])

    # --- Tab 1: 台股 ---
    with tab1:
        st.subheader("📊 詳細庫存與損益明細")
        abs_pnl = cur_val - actual_cost
        pnl_real = abs_pnl / actual_cost if actual_cost > 0 else 0
        intraday_drop = (current_p - yest_close) / yest_close
        today_pnl = (current_p - yest_close) * actual_shares
        avg_cost = actual_cost / actual_shares if actual_shares > 0 else 0
        
        # 🌟 完美 8 宮格回歸
        c1, c2 = st.columns(2); c1.metric("總市值 (元)", f"NT$ {cur_val:,.0f}"); c2.metric("總投入成本", f"NT$ {actual_cost:,.0f}")
        c3, c4 = st.columns(2); c3.metric("未實現總損益", f"NT$ {abs_pnl:,.0f}", f"{pnl_real*100:+.2f}%"); c4.metric("今日損益", f"NT$ {today_pnl:,.0f}", f"{intraday_drop*100:+.2f}%")
        c5, c6 = st.columns(2); c5.metric("庫存總股數", f"{actual_shares:,.0f} 股"); c6.metric("持有均價", f"NT$ {avg_cost:,.2f}")
        c7, c8 = st.columns(2); c7.metric("今日還原現價", f"NT$ {current_p:.2f}"); c8.metric("昨日還原收盤", f"NT$ {yest_close:.2f}")
        
        st.divider()
        st.subheader("📜 逐筆投資戰績表")
        with st.expander("點擊展開：檢視最新日期置頂與今日損益", expanded=False):
            if not df_trades_raw.empty:
                buy_df = df_trades_raw[df_trades_raw['交易類型'].str.contains('買入', na=False)].copy()
                buy_df['成交日期'] = pd.to_datetime(buy_df['成交日期'])
                buy_df = buy_df.sort_values(by='成交日期', ascending=False)
                records = []
                for _, row in buy_df.iterrows():
                    adj_p = row['成交價格']/22.0 if row['成交日期'] < split_cutoff and row['成交價格']>100 else row['成交價格']
                    adj_s = row['庫存股數']*22.0 if row['成交日期'] < split_cutoff and row['成交價格']>100 else row['庫存股數']
                    lot_pnl = (adj_s * current_p) - row['持有成本']
                    lot_roi = lot_pnl / row['持有成本']
                    lot_today = (current_p - yest_close) * adj_s
                    records.append({'📅 日期': row['成交日期'].strftime('%Y-%m-%d'),'🛒 買價': f"{adj_p:.2f}",'📦 股數': f"{adj_s:,.0f}",'💰 成本': f"{row['持有成本']:,.0f}",'🔥 今日損益': f"{lot_today:+,.0f}",'📈 總損益': f"{lot_pnl:+,.0f}",'🎯 報酬': f"{lot_roi*100:+.2f}%"})
                st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("🌐 戰術圖表分析")
        hist_tw = yf.download(TICKER, period="max", progress=False)
        hist_p = hist_tw['Close'].dropna()
        adj_p = hist_p.copy()
        mask = (adj_p.index < split_cutoff) & (adj_p > 100)
        if mask.any(): adj_p.loc[mask] = adj_p.loc[mask] / 22.0
        recent_prices = adj_p[adj_p.index >= '2024-01-01']
        
        # 🌟 找回圖表極值標示 (A, B, C)
        for title, series, color in [("📈 A. 價格走勢與均價防線", recent_prices, '#E71D36'), ("📊 B. 乖離率動能圖", (recent_prices - recent_prices.rolling(20).mean())/recent_prices.rolling(20).mean()*100, '#F4A261')]:
            st.write(title)
            fig = go.Figure(); fig.add_trace(go.Scatter(x=series.index, y=series.values, mode='lines', line=dict(color=color, width=2)))
            if "均價" in title and avg_cost > 0: fig.add_hline(y=avg_cost, line_dash="dash", line_color="#00A86B")
            if not series.dropna().empty:
                m_idx, m_val = series.idxmax(), series.max(); l_idx, l_val = series.idxmin(), series.min()
                fig.add_annotation(x=m_idx, y=m_val, text=f"高: {m_val:.2f}", showarrow=True, ay=-30)
                fig.add_annotation(x=l_idx, y=l_val, text=f"低: {l_val:.2f}", showarrow=True, ay=30)
            fig.update_layout(template='plotly_white', margin=dict(l=0, r=0, t=30, b=0), height=230); st.plotly_chart(fig, use_container_width=True)

    # --- Tab 2: 美股 ---
    with tab2:
        st.subheader("🎯 1. 大盤趨勢與輪動階梯")
        soxx_data = yf.download("SOXX", period="200d", progress=False)
        soxx_c = soxx_data['Close'].dropna(); dma100 = soxx_c.rolling(100).mean()
        curr_soxx = float(yf.Ticker("SOXX").fast_info.last_price)
        diff = curr_soxx - dma100.iloc[-1]; diff_p = (curr_soxx/dma100.iloc[-1]-1)*100
        # 🌟 完美 差距% 數回歸
        if curr_soxx > dma100.iloc[-1]: st.success(f"🟢 **SOXX 多頭續抱** | 現價:{curr_soxx:.2f} (100DMA:{dma100.iloc[-1]:.2f} | 差距: +{diff:.2f} / +{diff_p:.2f}%)")
        else: st.error(f"🔴 **停利訊號觸發** | 現價:{curr_soxx:.2f} (100DMA:{dma100.iloc[-1]:.2f} | 差距: {diff:.2f} / {diff_p:.2f}%)")
        
        st.divider()
        st.subheader("📋 2. 美股總資產身價")
        tot_cost_us = sum([info['cost']*info['shares'] for info in us_positions.values()])
        cu1, cu2 = st.columns(2); cu1.metric("美股總市值 (USD)", f"${total_us_val:,.2f}"); cu2.metric("未實現總損益", f"${total_us_val - tot_cost_us:,.2f}", f"{(total_us_val/tot_cost_us-1)*100:+.2f}%")
        
        st.subheader("📦 3. 個股明細快報")
        for t, info in us_positions.items():
            p_c = us_live[t]['curr']; p_y = us_live[t]['yest']; shr = info['shares']; avg = info['cost']
            st.markdown(f"#### 📌 **{t}** | 今日: ${p_c:.2f} ({(p_c/p_y-1)*100:+.2f}%)")
            st.write(f"🔹 **損益:** ${(p_c-avg)*shr:,.2f} ({(p_c/avg-1)*100:+.2f}%) | **市值:** ${p_c*shr:,.2f}")

    # --- Tab 3: 生命周期與退休 ---
    with tab3:
        st.subheader("🛬 生命周期投資法 & 退休終局")
        # 1. 曝險透視
        FC_TW = cur_val + cash - (loan1 + loan2); FC_US = total_us_val_twd; FC = FC_TW + FC_US
        twd_exp = cur_val * 2; usd_exp = (us_live['SOXL']['curr']*us_positions['SOXL']['shares']*usd_twd*3) + (us_live['BITX']['curr']*us_positions['BITX']['shares']*usd_twd*2)
        total_exp = twd_exp + usd_exp
        
        st.markdown("### ⚖️ 1. 當前實際曝險度透視")
        st.markdown(f"| 戰區 | 曝險金額 | 淨資產 | 實際曝險度 |\n| :--- | :--- | :--- | :--- |\n| **🇹🇼 台股** | NT$ {twd_exp:,.0f} | NT$ {FC_TW:,.0f} | **{twd_exp/FC_TW*100:.1f}%** |\n| **🇺🇸 美股** | NT$ {usd_exp:,.0f} | NT$ {FC_US:,.0f} | **{usd_exp/FC_US*100:.1f}%** |\n| **🔥 總計** | **NT$ {total_exp:,.0f}** | **NT$ {FC:,.0f}** | **{total_exp/FC*100:.1f}%** |")
        
        W = FC + (base_m*12*hc_years); target_stock = W * (target_k/100.0); target_E = target_stock/FC*100
        c_tgt, c_act = st.columns(2); c_tgt.metric("🎯 生命週期目標曝險度", f"{target_E:.1f}%"); c_act.metric("🔥 現在總曝險度", f"{total_exp/FC*100:.1f}%", f"差距: {total_exp/FC*100 - target_E:+.1f}%")

        # 2. 退休導航
        st.divider(); st.markdown("### ☕ 2. 退休終局與提領反推")
        # 情境 A
        fc_future_a = FC
        for _ in range(hc_years): fc_future_a = fc_future_a * 1.08 + (base_m*12)
        mon_a_fut = (fc_future_a * withdrawal_rate)/12; mon_a_now = mon_a_fut / ((1+inflation_rate)**hc_years)
        st.markdown(f"**📈 情境 A：若工作 {hc_years} 年後退休**")
        col_ra1, col_ra2, col_ra3 = st.columns(3); col_ra1.metric("屆時滾出資產", f"NT$ {fc_future_a:,.0f}"); col_ra2.metric("未來需月領", f"NT$ {mon_a_fut:,.0f}"); col_ra3.metric("約等同現在月薪", f"NT$ {mon_a_now:,.0f}", "扣除通膨")
        
        # 情境 B
        st.write(""); st.markdown(f"**🎯 情境 B：反推我想要月領 {target_monthly_now:,.0f} 元(現值) 的退休金**")
        found_y = None; t_fc = FC
        for y in range(1, 41):
            t_fc = t_fc * 1.08 + (base_m*12)
            req_m = target_monthly_now * ((1+inflation_rate)**y)
            if t_fc >= (req_m*12)/withdrawal_rate: found_y = y; break
        
        if found_y:
            col_rb1, col_rb2, col_rb3 = st.columns(3); col_rb1.metric("需滾出資產", f"NT$ {(target_monthly_now*((1+inflation_rate)**found_y)*12)/withdrawal_rate:,.0f}"); col_rb2.metric("未來需月領", f"NT$ {target_monthly_now*((1+inflation_rate)**found_y):,.0f}"); col_rb3.metric("剩餘年限", f"{found_y} 年")
            st.success(f"🎊 只要再拼 **{found_y}** 年即可達標！")
            
st.caption("📱 提示：美股報價已進行暴力修正，確保盤前大漲也能顯示正確。台股 3/23 分割已全自動還原。")
