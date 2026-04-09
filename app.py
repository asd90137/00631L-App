import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# ==========================================
# 賴賴投資戰情室 V6.2 - 信貸期數精準校正版
# ==========================================

st.set_page_config(page_title="賴賴終極戰情室", page_icon="📈", layout="centered")
st.title("🛡️ 賴賴投資戰情室 V6.2")

if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

# --- 🏦 定義信貸自動攤還計算函數 (精準期數修復) ---
def calculate_loan_remaining(principal, annual_rate, years, start_date):
    if principal <= 0 or years <= 0:
        return 0, 0
    r = annual_rate / 100 / 12
    N = years * 12
    # 計算每月應繳本息金額 (PMT)
    pmt = principal * r * (1+r)**N / ((1+r)**N - 1) if r > 0 else principal / N
    
    today = datetime.today().date()
    
    # 計算跨越的月份差
    passed_months = (today.year - start_date.year) * 12 + (today.month - start_date.month)
    
    # 🌟 關鍵修復：只要今天的號碼 ≥ 扣款日，代表本月已扣款，期數直接 +1 (包含首次扣款那個月)
    if today.day >= start_date.day:
        passed_months += 1
        
    # 防呆機制：若今天還沒到首次扣款日，期數歸零
    if today < start_date:
        passed_months = 0
        
    passed_months = max(0, min(passed_months, int(N))) # 確保期數在合理範圍內
    
    # 計算剩餘本金餘額
    if r > 0:
        rem_balance = principal * ((1+r)**N - (1+r)**passed_months) / ((1+r)**N - 1)
    else:
        rem_balance = principal - (pmt * passed_months)
        
    return max(0, rem_balance), pmt

# --- 側邊欄參數設定 ---
st.sidebar.header("⚙️ 資金與曝險參數")

# 單位優化：改為「萬」
base_m_wan = st.sidebar.number_input("1. 基準每月定期定額 (萬)", value=10.0, step=1.0)
cash_wan = st.sidebar.number_input("2. 目前帳戶可用現金 (萬)", value=200.0, step=10.0)
target_exp_pct = st.sidebar.number_input("3. 設定目標曝險度 (%)", value=200)

base_m = base_m_wan * 10000
cash = cash_wan * 10000

# 信貸自動扣款設定器
with st.sidebar.expander("🏦 信貸自動扣款設定 (自動計算餘額)", expanded=False):
    st.caption("設定一次，系統將每月自動扣除你的本金欠款！")
    
    st.markdown("**🔹 信貸一**")
    l1_p = st.number_input("原始貸款總額", value=2200000, step=100000, key='l1p')
    l1_r = st.number_input("年利率 (%)", value=2.5, step=0.1, key='l1r')
    l1_y = st.number_input("貸款期數 (年)", value=7, step=1, key='l1y')
    l1_d = st.date_input("首次扣款日", datetime(2024, 1, 15), key='l1d')
    loan1, pmt1 = calculate_loan_remaining(l1_p, l1_r, l1_y, l1_d)
    st.info(f"💡 目前剩餘本金：**NT$ {loan1:,.0f}**\n\n(每月扣繳 NT$ {pmt1:,.0f})")

    st.divider()
    
    st.markdown("**🔹 信貸二**")
    l2_p = st.number_input("原始貸款總額", value=950000, step=100000, key='l2p')
    l2_r = st.number_input("年利率 (%)", value=2.72, step=0.1, key='l2r')
    l2_y = st.number_input("貸款期數 (年)", value=10, step=1, key='l2y')
    l2_d = st.date_input("首次扣款日", datetime(2026, 3, 5), key='l2d')
    loan2, pmt2 = calculate_loan_remaining(l2_p, l2_r, l2_y, l2_d)
    st.info(f"💡 目前剩餘本金：**NT$ {loan2:,.0f}**\n\n(每月扣繳 NT$ {pmt2:,.0f})")

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
# 核心計算區
# ==========================================
if st.session_state.analyzed:
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

    us_positions = {"SOXL": {"shares": 545, "cost": 50.99}, "TMF": {"shares": 1050, "cost": 52.94}, "BITX": {"shares": 11, "cost": 29.67}}
    tickers_us = ["SOXX", "SOXL", "TMF", "BITX"]
    us_data_hist = yf.download(tickers_us, period="5d", progress=False)
    us_live = {}
    total_us_val = 0.0
    
    for t, info in us_positions.items():
        try:
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

    with tab1:
        st.subheader("📊 詳細庫存與損益明細")
        abs_pnl = cur_val - actual_cost
        pnl_real = abs_pnl / actual_cost if actual_cost > 0 else 0
        intraday_drop = (current_p - yest_close) / yest_close
        today_pnl = (current_p - yest_close) * actual_shares
        avg_cost = actual_cost / actual_shares if actual_shares > 0 else 0
        
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
        
        for title, series, color in [("📈 A. 價格走勢與均價防線", recent_prices, '#E71D36'), ("📊 B. 乖離率動能圖", (recent_prices - recent_prices.rolling(20).mean())/recent_prices.rolling(20).mean()*100, '#F4A261')]:
            st.write(title)
            fig = go.Figure(); fig.add_trace(go.Scatter(x=series.index, y=series.values, mode='lines', line=dict(color=color, width=2)))
            if "均價" in title and avg_cost > 0: fig.add_hline(y=avg_cost, line_dash="dash", line_color="#00A86B")
            if not series.dropna().empty:
                m_idx, m_val = series.idxmax(), series.max(); l_idx, l_val = series.idxmin(), series.min()
                fig.add_annotation(x=m_idx, y=m_val, text=f"高: {m_val:.2f}", showarrow=True, ay=-30)
                fig.add_annotation(x=l_idx, y=l_val, text=f"低: {l_val:.2f}", showarrow=True, ay=30)
            fig.update_layout(template='plotly_white', margin=dict(l=0, r=0, t=30, b=0), height=230); st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("🎯 1. 大盤趨勢與輪動階梯")
        soxx_data = yf.download("SOXX", period="200d", progress=False)
        soxx_c = soxx_data['Close'].dropna(); dma100 = soxx_c.rolling(100).mean()
        curr_soxx = float(yf.Ticker("SOXX").fast_info.last_price)
        diff = curr_soxx - dma100.iloc[-1]; diff_p = (curr_soxx/dma100.iloc[-1]-1)*100
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

    with tab3:
        st.subheader("🛬 生命周期投資法 & 退休終局")
        FC_TW = cur_val + cash - (loan1 + loan2); FC_US = total_us_val_twd; FC = FC_TW + FC_US
        twd_exp = cur_val * 2; usd_exp = (us_live['SOXL']['curr']*us_positions['SOXL']['shares']*usd_twd*3) + (us_live['BITX']['curr']*us_positions['BITX']['shares']*usd_twd*2)
        total_exp = twd_exp + usd_exp
        
        st.markdown("### ⚖️ 1. 實際曝險 vs 應有曝險")
        st.markdown(f"| 戰區 | 曝險金額 | 淨資產 | 實際曝險度 |\n| :--- | :--- | :--- | :--- |\n| **🇹🇼 台股** | NT$ {twd_exp/10000:,.0f} 萬 | NT$ {FC_TW/10000:,.0f} 萬 | **{twd_exp/FC_TW*100:.1f}%** |\n| **🇺🇸 美股** | NT$ {usd_exp/10000:,.0f} 萬 | NT$ {FC_US/10000:,.0f} 萬 | **{usd_exp/FC_US*100:.1f}%** |\n| **🔥 總計** | **NT$ {total_exp/10000:,.0f} 萬** | **NT$ {FC/10000:,.0f} 萬** | **{total_exp/FC*100:.1f}%** |")
        
        W = FC + (base_m*12*hc_years); target_stock = W * (target_k/100.0); target_E = target_stock/FC*100
        c_tgt, c_act = st.columns(2); c_tgt.metric("🎯 生命週期目標曝險度", f"{target_E:.1f}%"); c_act.metric("🔥 現在總曝險度", f"{total_exp/FC*100:.1f}%", f"差距: {total_exp/FC*100 - target_E:+.1f}%")

        st.divider(); st.markdown("### ☕ 2. 退休終局與提領反推")
        fc_future_a = FC
        for _ in range(hc_years): fc_future_a = fc_future_a * 1.08 + (base_m*12)
        mon_a_fut = (fc_future_a * withdrawal_rate)/12; mon_a_now = mon_a_fut / ((1+inflation_rate)**hc_years)
        st.markdown(f"**📈 情境 A：若工作 {hc_years} 年後退休**")
        col_ra1, col_ra2, col_ra3 = st.columns(3); col_ra1.metric("屆時滾出資產", f"NT$ {fc_future_a/10000:,.0f} 萬"); col_ra2.metric("未來每月可領", f"NT$ {mon_a_fut:,.0f}"); col_ra3.metric("約等同現在每月可領", f"NT$ {mon_a_now:,.0f}", "扣除通膨")
        
        st.write(""); st.markdown(f"**🎯 情境 B：反推我想要月領 {target_monthly_now/10000:.0f} 萬(現值) 的退休金**")
        found_y = None; t_fc = FC
        for y in range(1, 41):
            t_fc = t_fc * 1.08 + (base_m*12)
            req_m = target_monthly_now * ((1+inflation_rate)**y)
            if t_fc >= (req_m*12)/withdrawal_rate: found_y = y; break
        
        if found_y:
            col_rb1, col_rb2, col_rb3 = st.columns(3); col_rb1.metric("需滾出資產", f"NT$ {((target_monthly_now*((1+inflation_rate)**found_y)*12)/withdrawal_rate)/10000:,.0f} 萬"); col_rb2.metric("未來每月可領", f"NT$ {target_monthly_now*((1+inflation_rate)**found_y):,.0f}"); col_rb3.metric("剩餘年限", f"{found_y} 年")
            st.success(f"🎊 只要再拼 **{found_y}** 年即可達標！")

        st.divider()
        st.markdown("### 🛬 3. 降落時程推演表 (Glide Path)")
        st.info("💡 **這張表怎麼看？** 這是你未來的【槓桿降落路線圖】。它推算隨著你持續投入與資產成長，你的「應有曝險度」會如何逐年下降。保守(6%)與樂觀(10%)是模擬市場好壞的情境，幫你抓出最差與最好的降落時間點。")

        records_gp = []
        f6, f8, f10 = FC, FC, FC
        for y in range(0, hc_years + 1):
            if y == 0: e6 = e8 = e10 = target_E
            else:
                f6 = f6*1.06 + (base_m*12); f8 = f8*1.08 + (base_m*12); f10 = f10*1.10 + (base_m*12)
                hc_rem = max((base_m*12*hc_years) - (base_m*12) * y, 0)
                e6 = ((f6 + hc_rem) * (target_k/100)) / f6 * 100
                e8 = ((f8 + hc_rem) * (target_k/100)) / f8 * 100
                e10 = ((f10 + hc_rem) * (target_k/100)) / f10 * 100
            records_gp.append({"第幾年": f"第 {y} 年" if y > 0 else "現在 (第0年)","預估 FC (8%)": f"{f8/10000:,.0f} 萬","應有曝險(8%)": f"{e8:.1f}%","保守(6%)": f"{e6:.1f}%","樂觀(10%)": f"{e10:.1f}%"})
        st.dataframe(pd.DataFrame(records_gp), use_container_width=True, hide_index=True)

st.caption("📱 提示：信貸期數引擎已修正。台美雙引擎透視表現以「萬」為單位顯示，版面更直覺乾淨。")
