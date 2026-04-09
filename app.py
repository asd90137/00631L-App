import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# ==========================================
# 賴賴投資戰情室 V7.1 - 終極實戰旗艦版
# ==========================================

st.set_page_config(page_title="賴賴終極戰情室", page_icon="📈", layout="wide")
st.title("🛡️ 賴賴投資戰情室 V7.1")

if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

# --- 🏦 核心：貸款自動計算引擎 ---
def calculate_loan_remaining(principal, annual_rate, years, start_date):
    if principal <= 0 or years <= 0: return 0, 0
    r = annual_rate / 100 / 12
    N = years * 12
    pmt = principal * r * (1+r)**N / ((1+r)**N - 1) if r > 0 else principal / N
    today = datetime.today().date()
    passed_months = (today.year - start_date.year) * 12 + (today.month - start_date.month)
    if today.day >= start_date.day: passed_months += 1
    passed_months = max(0, min(passed_months, int(N))) 
    rem_balance = principal * ((1+r)**N - (1+r)**passed_months) / ((1+r)**N - 1) if r > 0 else principal - (pmt * passed_months)
    return max(0, rem_balance), pmt

# --- 側邊欄：全局參數 ---
st.sidebar.header("⚙️ 資金與曝險參數")
base_m_wan = st.sidebar.number_input("1. 基準每月定期定額 (萬)", value=10.0, step=1.0)
cash_wan = st.sidebar.number_input("2. 目前帳戶可用現金 (萬)", value=200.0, step=10.0)
target_exp_pct = st.sidebar.number_input("3. 設定目標曝險度 (%)", value=200)

base_m = base_m_wan * 10000
cash = cash_wan * 10000

with st.sidebar.expander("🏦 貸款細項設定", expanded=False):
    l1_p = st.number_input("信貸一總額", value=2200000); l1_r = st.number_input("年利率1(%)", value=2.5); l1_d = st.date_input("首次扣款日1", datetime(2024, 1, 15))
    loan1, _ = calculate_loan_remaining(l1_p, l1_r, 7, l1_d)
    st.divider()
    l2_p = st.number_input("信貸二總額", value=950000); l2_r = st.number_input("年利率2(%)", value=2.72); l2_d = st.date_input("首次扣款日2", datetime(2026, 3, 5))
    loan2, _ = calculate_loan_remaining(l2_p, l2_r, 10, l2_d)

st.sidebar.divider()
st.sidebar.header("⚙️ 生命周期與退休規劃")
usd_twd = st.sidebar.number_input("6. 目前美元匯率", value=32.0)
hc_years = st.sidebar.number_input("7. 預計剩餘投入年限", value=10)
target_k = st.sidebar.number_input("8. 一生目標曝險度 (%)", value=83)
target_monthly_now = st.sidebar.number_input("9. 目標月領金額 (現值)", value=100000, step=10000)
inflation_rate = st.sidebar.number_input("10. 預估通膨 (%)", value=2.0) / 100.0
withdrawal_rate = st.sidebar.number_input("11. 安全提領率 (%)", value=4.0) / 100.0

# --- 🚀 雲端數據同步 ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_tw = conn.read(ttl=0) # 台股
    df_us = conn.read(spreadsheet="https://docs.google.com/spreadsheets/d/1-NPhyuRNWSarFPdgHjUkB9J3smSbn3u3fjUbMhMVyfI/edit?usp=sharing", ttl=0) # 美股
    st.sidebar.success("✅ 台美股帳本同步成功！")
except Exception as e:
    st.sidebar.error("❌ 帳本讀取失敗，請檢查 URL。")
    df_tw = pd.DataFrame(); df_us = pd.DataFrame()

if st.button("🚀 啟動戰術掃描", use_container_width=True):
    st.session_state.analyzed = True

if st.session_state.analyzed:
    # 核心預算模組
    TICKER_TW = "00631L.TW"
    split_cutoff = pd.to_datetime('2026-03-23')
    
    # 台股計算
    tkr_tw = yf.Ticker(TICKER_TW)
    raw_tw = tkr_tw.fast_info
    p_tw_curr = round(float(raw_tw.last_price) / (22.0 if float(raw_tw.last_price) > 100 else 1.0), 2)
    p_tw_yest = round(float(raw_tw.previous_close) / (22.0 if float(raw_tw.previous_close) > 100 else 1.0), 2)
    
    temp_tw = df_tw.copy()
    temp_tw['成交日期'] = pd.to_datetime(temp_tw['成交日期'])
    temp_tw.loc[temp_tw['交易類型'].str.contains('賣出'), ['庫存股數', '持有成本']] *= -1
    actual_shares_tw = temp_tw['庫存股數'].sum()
    actual_cost_tw = temp_tw['持有成本'].sum()
    cur_val_tw = actual_shares_tw * p_tw_curr
    
    # 美股計算
    us_tickers = ["SOXX", "SOXL", "TMF", "BITX"]
    us_data = yf.download(us_tickers, period="200d", progress=False)
    us_live = {}
    total_us_val_usd = 0.0
    total_us_cost_usd = 0.0
    
    for t in ["SOXL", "TMF", "BITX"]:
        t_data = df_us[df_us['股票代號'] == t].copy()
        t_data['成交日期'] = pd.to_datetime(t_data['成交日期'])
        t_data.loc[t_data['交易類型'].str.contains('賣出'), ['庫存股數', '持有成本']] *= -1
        shares = t_data['庫存股數'].sum()
        cost = t_data['持有成本'].sum()
        curr_p = float(us_data['Close'][t].dropna().iloc[-1])
        yest_p = float(us_data['Close'][t].dropna().iloc[-2])
        us_live[t] = {'shares': shares, 'cost': cost, 'curr': curr_p, 'yest': yest_p, 'first_date': t_data['成交日期'].min()}
        total_us_val_usd += shares * curr_p
        total_us_cost_usd += cost
        
    total_us_val_twd = total_us_val_usd * usd_twd
    FC = cur_val_tw + total_us_val_twd + cash - (loan1 + loan2)

    # ==========================================
    # 分頁顯示
    # ==========================================
    tab1, tab2, tab3 = st.tabs(["🇹🇼 TW台股", "🇺🇸 US美股", "🛬 生命周期 & 退休"])

    # --- Tab 1: 台股 ---
    with tab1:
        st.subheader("📊 台股資產明細 (00631L)")
        roi_tw = (cur_val_tw / actual_cost_tw - 1) if actual_cost_tw > 0 else 0
        days_tw = (datetime.today() - temp_tw['成交日期'].min()).days
        ann_roi_tw = ((1+roi_tw)**(365/max(days_tw,1)) - 1) * 100
        
        # 11大指標排版
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("總市值", f"NT$ {cur_val_tw:,.0f}")
        m2.metric("總投入成本", f"NT$ {actual_cost_tw:,.0f}")
        m3.metric("未實現總損益", f"{cur_val_tw-actual_cost_tw:+,.0f}", f"{roi_tw*100:+.2f}%")
        m4.metric("年化報酬率", f"{ann_roi_tw:+.2f}%")
        
        m5, m6, m7, m8 = st.columns(4)
        m5.metric("庫存總張數", f"{actual_shares_tw/1000:,.1f} 張", f"{actual_shares_tw:,.0f} 股")
        m6.metric("持有均價", f"{actual_cost_tw/actual_shares_tw:.2f}" if actual_shares_tw>0 else "0")
        m7.metric("貸款剩餘本金", f"NT$ {(loan1+loan2)/10000:,.0f} 萬", "信貸1+2")
        m8.metric("目前現價", f"{p_tw_curr:.2f}", f"{(p_tw_curr/p_tw_yest-1)*100:+.2f}%")
        
        m9, m10, m11, _ = st.columns(4)
        m9.metric("昨日還原收盤", f"{p_tw_yest:.2f}")
        m10.metric("實際曝險度", f"{(cur_val_tw*2/FC*100):.1f}%")
        m11.metric("投資組合佔比", f"{(cur_val_tw/(cur_val_tw+total_us_val_twd)*100):.1f}%")

        with st.expander("📜 逐筆投資戰績表", expanded=False):
            buy_tw = df_tw[df_tw['交易類型'].str.contains('買入')].copy()
            buy_tw['成交日期'] = pd.to_datetime(buy_tw['成交日期'])
            recs_tw = []
            for _, r in buy_tw.sort_values('成交日期', ascending=False).iterrows():
                adj_p = r['成交價格']/22 if r['成交日期']<split_cutoff and r['成交價格']>100 else r['成交價格']
                adj_s = r['庫存股數']*22 if r['成交日期']<split_cutoff and r['成交價格']>100 else r['庫存股數']
                l_roi = (adj_s*p_tw_curr - r['持有成本'])/r['持有成本']
                l_ann = ((1+l_roi)**(365/max((datetime.today()-r['成交日期']).days,1))-1)*100
                recs_tw.append({'日期': r['成交日期'].strftime('%Y-%m-%d'), '買價': f"{adj_p:.2f}", '張數': f"{adj_s/1000:.1f}", '今日損益': f"{(p_tw_curr-p_tw_yest)*adj_s:+,.0f}", '年化': f"{l_ann:+.1f}%", '總報酬': f"{l_roi*100:+.2f}%"})
            st.dataframe(pd.DataFrame(recs_tw), use_container_width=True, hide_index=True)

        with st.expander("🛒 新增台股交易紀錄", expanded=False):
            st.write("此按鈕將連動 Google Sheets...")
            if st.button("點擊前往台股帳本"): st.write("請手動開啟原始連結進行編輯")

        st.subheader("🌐 戰術圖表分析")
        hist_tw = yf.download(TICKER_TW, period="1y", progress=False)['Close']
        if isinstance(hist_tw, pd.DataFrame): hist_tw = hist_tw.iloc[:,0]
        adj_h = hist_tw.copy() / 22.0
        fig = go.Figure(); fig.add_trace(go.Scatter(x=adj_h.index, y=adj_h.values, name="還原股價", line=dict(color='#E71D36')))
        st.plotly_chart(fig, use_container_width=True)

    # --- Tab 2: 美股 ---
    with tab2:
        s_c = float(us_data['Close']['SOXX'].iloc[-1]); s_d = us_data['Close']['SOXX'].rolling(100).mean().iloc[-1]
        s_gap = s_c - s_d; s_gap_p = (s_c/s_d - 1)*100
        soxl_c = us_live['SOXL']['curr']
        # SOXL 預估價：SOXX 回歸 100DMA (跌幅x3)
        soxl_pred = soxl_c * (1 + (s_d/s_c - 1)*3)
        
        st.markdown(f"### **SOXX 多頭續抱 | 現價:{s_c:.2f} (100DMA:{s_d:.2f} | 差距: {s_gap:+.2f} / {s_gap_p:+.2f}%)**")
        st.info(f"💡 **SOXL 壓力預測：** 若 SOXX 跌回 100DMA，SOXL 預計來到 **${soxl_pred:.2f}** (距現值 {((soxl_pred/soxl_c-1)*100):.1f}%)")

        col_st = st.columns(3)
        for i, (lvl, tgt) in enumerate(zip([3,4,5], [30.14, 21.09, 14.77])):
            col_st[i].metric(f"階梯 {lvl} 目標", f"${tgt}", f"距 {((soxl_c/tgt-1)*100):.1f}%", delta_color="inverse")

        st.divider()
        us_roi = (total_us_val_usd / total_us_cost_usd - 1) if total_us_cost_usd > 0 else 0
        min_date_us = min([v['first_date'] for v in us_live.values()])
        ann_roi_us = ((1+us_roi)**(365/max((datetime.today()-min_date_us).days,1)) - 1) * 100
        
        u1, u2, u3, u4 = st.columns(4)
        u1.metric("總市值 (USD)", f"${total_us_val_usd:,.0f}")
        u2.metric("總投入成本 (USD)", f"${total_us_cost_usd:,.0f}")
        u3.metric("未實現總損益", f"${(total_us_val_usd-total_us_cost_usd):+,.0f}", f"{us_roi*100:+.2f}%")
        u4.metric("年化報酬率", f"{ann_roi_us:+.2f}%")

        st.subheader("📦 個股明細")
        us_table = []
        for t, info in us_live.items():
            avg = info['cost']/info['shares'] if info['shares']>0 else 0
            l_roi = (info['curr']/avg - 1) if avg>0 else 0
            l_ann = ((1+l_roi)**(365/max((datetime.today()-info['first_date']).days,1))-1)*100
            us_table.append({
                '代號': t, '股數': f"{info['shares']:,.0f}", '均價': f"{avg:.2f}", '成本': f"{info['cost']:,.0f}",
                '昨日': f"{info['yest']:.2f}", '現價': f"{info['curr']:.2f}", 
                '今日損益': f"{(info['curr']/info['yest']-1)*100:+.2f}%", 
                '總損益': f"{l_roi*100:+.1f}%", '年化': f"{l_ann:+.1f}%"
            })
        st.dataframe(pd.DataFrame(us_table), use_container_width=True, hide_index=True)

        st.write(f"🔹 **實際曝險度：** {((us_live['SOXL']['curr']*us_live['SOXL']['shares']*3 + us_live['BITX']['curr']*us_live['BITX']['shares']*2)*usd_twd/FC*100):.1f}% ｜ **投資組合佔比：** {(total_us_val_twd/(cur_val_tw+total_us_val_twd)*100):.1f}%")

        with st.expander("🛒 新增美股交易紀錄", expanded=False):
            st.write("連動美股帳本： [US_records](https://docs.google.com/spreadsheets/d/1-NPhyuRNWSarFPdgHjUkB9J3smSbn3u3fjUbMhMVyfI/edit?usp=sharing)")

    # --- Tab 3: 生命周期 ---
    with tab3:
        st.subheader("⚖️ 生命周期投資法 & 退休終局")
        exp_tw = cur_val_tw * 2
        exp_us = (us_live['SOXL']['curr']*us_live['SOXL']['shares']*3 + us_live['BITX']['curr']*us_live['BITX']['shares']*2) * usd_twd
        
        st.markdown(f"""
        | 戰區 | 曝險金額 | 淨資產 (FC) | 實際曝險度 |
        | :--- | :--- | :--- | :--- |
        | 🇹🇼 台股 | NT$ {exp_tw/10000:,.0f} 萬 | NT$ {(cur_val_tw+cash/2-loan1/2-loan2/2)/10000:,.0f} 萬 | **{(exp_tw/FC*100):.1f}%** |
        | 🇺🇸 美股 | NT$ {exp_us/10000:,.0f} 萬 | NT$ {(total_us_val_twd+cash/2-loan1/2-loan2/2)/10000:,.0f} 萬 | **{(exp_us/FC*100):.1f}%** |
        | 🔥 **總計** | **NT$ {(exp_tw+exp_us)/10000:,.0f} 萬** | **NT$ {FC/10000:,.0f} 萬** | **{((exp_tw+exp_us)/FC*100):.1f}%** |
        """)
        
        W = FC + (base_m * 12 * hc_years); target_val = W * (target_k/100)
        st.write(f"🔹 **生命週期目標曝險度：** {(target_val/FC*100):.1f}% ｜ **現在總曝險度：** {((exp_tw+exp_us)/FC*100):.1f}% (差距: {((exp_tw+exp_us)/FC*100 - target_val/FC*100):+.1f}%)")

        st.divider(); st.subheader("☕ 退休終局與提領反推")
        # 情境 A
        f_a = FC
        for _ in range(hc_years): f_a = f_a*1.08 + (base_m*12)
        m_a = (f_a*withdrawal_rate)/12; m_a_now = m_a/((1+inflation_rate)**hc_years)
        st.markdown(f"**📈 情境 A：若工作 {hc_years} 年後退休**")
        ca1, ca2, ca3 = st.columns(3); ca1.metric("屆時滾出資產", f"NT$ {f_a/10000:,.0f} 萬"); ca2.metric("未來每月可領", f"NT$ {m_a:,.0f}"); ca3.metric("約等同現在每月可領", f"NT$ {m_a_now:,.0f}")
        
        # 情境 B
        st.write(""); st.markdown(f"**🎯 情境 B：反推我想要月領 {target_monthly_now/10000:.0f} 萬(現值) 的退休金**")
        found_y = None; t_f = FC
        for y in range(1, 41):
            t_f = t_f*1.08 + (base_m*12)
            req_m = target_monthly_now*((1+inflation_rate)**y)
            if t_f >= (req_m*12)/withdrawal_rate: found_y = y; break
        if found_y:
            cb1, cb2, cb3 = st.columns(3); cb1.metric("需滾出資產", f"NT$ {(target_monthly_now*((1+inflation_rate)**found_y)*12/withdrawal_rate)/10000:,.0f} 萬"); cb2.metric("未來每月可領", f"NT$ {target_monthly_now*((1+inflation_rate)**found_y):,.0f}"); cb3.metric("剩餘年限", f"{found_y} 年")

        with st.expander("🛬 降落時程推演表 (Glide Path)", expanded=False):
            gp = []
            curr_f = FC
            for y in range(hc_years+1):
                if y>0: curr_f = curr_f*1.08 + (base_m*12)
                h_r = max(0, (base_m*12*hc_years) - (base_m*12*y))
                e_g = ((curr_f + h_r)*target_k/100)/curr_f*100
                gp.append({"年": f"第 {y} 年", "預估資產(萬)": f"{curr_f/10000:,.0f}", "應有曝險": f"{e_g:.1f}%"})
            st.table(pd.DataFrame(gp))

st.caption("📱 提示：美股資訊由 US_records 連結驅動。所有金額已轉換為「萬」顯示，確保閱讀體驗。")
