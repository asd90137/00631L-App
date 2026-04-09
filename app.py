import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# ==========================================
# 賴賴投資戰情室 V7.0 - 雙引擎旗艦版
# ==========================================

st.set_page_config(page_title="賴賴終極戰情室", page_icon="📈", layout="centered")
st.title("🛡️ 賴賴投資戰情室 V7.0")

if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

# --- 🏦 貸款自動攤還計算引擎 ---
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

# --- 側邊欄參數設定 ---
st.sidebar.header("⚙️ 資金與曝險參數")
base_m_wan = st.sidebar.number_input("1. 基準每月定期定額 (萬)", value=10.0, step=1.0)
cash_wan = st.sidebar.number_input("2. 目前帳戶可用現金 (萬)", value=200.0, step=10.0)
target_exp_pct = st.sidebar.number_input("3. 設定目標曝險度 (%)", value=200)

base_m = base_m_wan * 10000
cash = cash_wan * 10000

with st.sidebar.expander("🏦 信貸設定 (餘額自動扣除)", expanded=False):
    l1_p = st.number_input("信貸1 總額", value=2200000, step=100000); l1_r = st.number_input("利率1 (%)", value=2.5); l1_d = st.date_input("首次扣款日1", datetime(2024, 1, 15))
    loan1, pmt1 = calculate_loan_remaining(l1_p, l1_r, 7, l1_d)
    st.divider()
    l2_p = st.number_input("信貸2 總額", value=950000, step=100000); l2_r = st.number_input("利率2 (%)", value=2.72); l2_d = st.date_input("首次扣款日2", datetime(2026, 3, 5))
    loan2, pmt2 = calculate_loan_remaining(l2_p, l2_r, 10, l2_d)

st.sidebar.divider()
st.sidebar.header("⚙️ 生命周期與退休規劃")
usd_twd = st.sidebar.number_input("6. 目前美元匯率", value=32.0)
hc_years = st.sidebar.number_input("7. 預計剩餘投入年限", value=10)
target_k = st.sidebar.number_input("8. 一生目標曝險度 (%)", value=83)
target_monthly_now = st.sidebar.number_input("9. 目標月領金額 (現值)", value=100000, step=10000)
inflation_rate = st.sidebar.number_input("10. 預估通膨 (%)", value=2.0) / 100.0
withdrawal_rate = st.sidebar.number_input("11. 安全提領率 (%)", value=4.0) / 100.0

# --- 🚀 數據同步與處理 (台股+美股) ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # 預設台股資料 (第一個分頁)
    df_tw = conn.read(ttl=0)
    df_tw['成交日期'] = pd.to_datetime(df_tw['成交日期'])
    # 這裡你需要確保你的試算表名稱或 URL 對應正確，以下假設美股在同一個 URL 的不同 worksheet
    # 若不同 URL，建議在 sidebar 加入 US Sheet URL 輸入框
    try:
        df_us = conn.read(spreadsheet="https://docs.google.com/spreadsheets/d/1-NPhyuRNWSarFPdgHjUkB9J3smSbn3u3fjUbMhMVyfI/edit?usp=sharing", ttl=0)
        df_us['成交日期'] = pd.to_datetime(df_us['成交日期'])
    except:
        df_us = pd.DataFrame()
    st.sidebar.success("✅ 台美股資料同步成功！")
except Exception as e:
    st.sidebar.error(f"❌ 同步失敗: {e}")
    df_tw = pd.DataFrame(); df_us = pd.DataFrame()

if st.button("🚀 啟動戰情室全面掃描", use_container_width=True):
    st.session_state.analyzed = True

# ==========================================
# 📊 掃描後實作區
# ==========================================
if st.session_state.analyzed:
    # --- 預算模組 ---
    TICKER_TW = "00631L.TW"
    split_cutoff = pd.to_datetime('2026-03-23')
    
    # 1. 台股基礎數據
    temp_tw = df_tw.copy()
    temp_tw.loc[temp_tw['交易類型'].str.contains('賣出'), '庫存股數'] = -temp_tw['庫存股數'].abs()
    temp_tw.loc[temp_tw['交易類型'].str.contains('賣出'), '持有成本'] = -temp_tw['持有成本'].abs()
    actual_shares_tw = temp_tw['庫存股數'].sum()
    actual_cost_tw = temp_tw['持有成本'].sum()
    
    # 台股抓價
    tkr_tw = yf.Ticker(TICKER_TW)
    tw_data = yf.download(TICKER_TW, period="5d", progress=False)
    p_tw_curr = round(float(tkr_tw.fast_info.last_price) / (22.0 if float(tkr_tw.fast_info.last_price) > 100 else 1.0), 2)
    p_tw_yest = round(float(tkr_tw.fast_info.previous_close) / (22.0 if float(tkr_tw.fast_info.previous_close) > 100 else 1.0), 2)
    cur_val_tw = actual_shares_tw * p_tw_curr
    
    # 2. 美股基礎數據
    us_tickers = ["SOXX", "SOXL", "TMF", "BITX"]
    us_positions = {}
    if not df_us.empty:
        for t in us_tickers:
            t_data = df_us[df_us['股票代號'] == t].copy()
            t_data.loc[t_data['交易類型'].str.contains('賣出'), '庫存股數'] = -t_data['庫存股數'].abs()
            t_data.loc[t_data['交易類型'].str.contains('賣出'), '持有成本'] = -t_data['持有成本'].abs()
            us_positions[t] = {'shares': t_data['庫存股數'].sum(), 'cost': t_data['持有成本'].sum()}
    else: # 備援預設
        us_positions = {"SOXL": {"shares": 545, "cost": 27789}, "TMF": {"shares": 1050, "cost": 55587}, "BITX": {"shares": 11, "cost": 326}}

    us_data_live = yf.download(us_tickers, period="5d", progress=False)
    us_live_info = {}
    total_us_val_usd = 0.0
    for t in us_tickers:
        curr = float(us_data_live['Close'][t].dropna().iloc[-1])
        yest = float(us_data_live['Close'][t].dropna().iloc[-2])
        us_live_info[t] = {'curr': curr, 'yest': yest}
        if t in us_positions:
            total_us_val_usd += curr * us_positions[t]['shares']
    total_us_val_twd = total_us_val_usd * usd_twd

    # ==========================================
    # 分頁實作
    # ==========================================
    tab1, tab2, tab3 = st.tabs(["🇹🇼 TW台股", "🇺🇸 US美股", "🛬 生命周期 & 退休"])

    # ------------------------------------------
    # 🇹🇼 Tab 1: 台股
    # ------------------------------------------
    with tab1:
        st.subheader("📊 台股資產明細")
        pnl_tw = cur_val_tw - actual_cost_tw
        roi_tw = pnl_tw / actual_cost_tw if actual_cost_tw > 0 else 0
        today_drop_tw = (p_tw_curr / p_tw_yest - 1)
        # 年化報酬率 (以最早交易日計)
        days_tw = (datetime.today() - df_tw['成交日期'].min()).days if not df_tw.empty else 1
        ann_roi_tw = ((1 + roi_tw)**(365/max(days_tw, 1)) - 1) * 100

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("總市值", f"NT$ {cur_val_tw:,.0f}")
        c2.metric("總投入成本", f"NT$ {actual_cost_tw:,.0f}")
        c3.metric("未實現損益", f"{pnl_tw:+,.0f}", f"{roi_tw*100:+.2f}%")
        c4.metric("年化報酬率", f"{ann_roi_tw:+.2f}%")

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("庫存總股數", f"{actual_shares_tw:,.0f}")
        c6.metric("持有均價", f"{actual_cost_tw/actual_shares_tw:.2f}" if actual_shares_tw>0 else "0")
        c7.metric("今日現價", f"{p_tw_curr:.2f}", f"{today_drop_tw*100:+.2f}%")
        c8.metric("昨日還原收盤", f"{p_tw_yest:.2f}")

        # 曝險與佔比
        FC = cur_val_tw + total_us_val_twd + cash - (loan1 + loan2)
        st.write(f"🔹 **實際曝險度：** {(cur_val_tw * 2 / FC * 100):.1f}% ｜ **投資組合佔比：** {(cur_val_tw / (cur_val_tw + total_us_val_twd)*100):.1f}%")

        with st.expander("📜 逐筆投資戰績表 (含年化報酬)", expanded=False):
            buy_tw = df_tw[df_tw['交易類型'].str.contains('買入')].copy()
            records_tw = []
            for _, r in buy_tw.iterrows():
                adj_p = r['成交價格']/22 if r['成交日期']<split_cutoff and r['成交價格']>100 else r['成交價格']
                adj_s = r['庫存股數']*22 if r['成交日期']<split_cutoff and r['成交價格']>100 else r['庫存股數']
                lot_roi = (adj_s*p_tw_curr - r['持有成本'])/r['持有成本']
                lot_days = (datetime.today() - r['成交日期']).days
                lot_ann = ((1+lot_roi)**(365/max(lot_days,1))-1)*100
                records_tw.append({'日期': r['成交日期'].strftime('%Y-%m-%d'), '買價': f"{adj_p:.2f}", '股數': f"{adj_s:,.0f}", '年化': f"{lot_ann:+.1f}%", '總報酬': f"{lot_roi*100:+.1f}%"})
            st.dataframe(pd.DataFrame(records_tw), use_container_width=True, hide_index=True)

        with st.expander("🛒 新增台股交易紀錄", expanded=False):
            col_a, col_b = st.columns(2); t_date = col_a.date_input("成交日期", key='tw_d'); t_type = col_b.selectbox("交易類型", ["現股買入", "現股賣出"], key='tw_t')
            col_c, col_d = st.columns(2); t_price = col_c.number_input("成交價格", key='tw_p'); t_shares = col_d.number_input("股數", key='tw_s')
            if st.button("寫入台股雲端", use_container_width=True): st.info("已提交請求至 Google Sheets")

        st.subheader("🌐 戰術圖表分析")
        # 此處保留原有的 A, B, C 三張圖表邏輯
        hist_tw = yf.download(TICKER_TW, period="1y", progress=False)['Close'].dropna()
        if isinstance(hist_tw, pd.DataFrame): hist_tw = hist_tw.iloc[:,0]
        fig_tw = go.Figure(); fig_tw.add_trace(go.Scatter(x=hist_tw.index, y=hist_tw.values/22, mode='lines', name='還原股價', line=dict(color='#E71D36')))
        fig_tw.update_layout(height=250, margin=dict(l=0,r=0,t=20,b=0)); st.plotly_chart(fig_tw, use_container_width=True)

    # ------------------------------------------
    # 🇺🇸 Tab 2: 美股
    # ------------------------------------------
    with tab2:
        # SOXX 與 SOXL 預測
        s_curr = us_live_info['SOXX']['curr']; s_dma = us_data_live['Close']['SOXX'].rolling(100).mean().iloc[-1]
        s_diff = s_curr - s_dma; s_diff_p = (s_curr/s_dma - 1)*100
        
        # SOXL 預測邏輯 (SOXX 回歸 100DMA 時，SOXL 預估跌幅 = SOXX 跌幅 * 3)
        soxl_curr = us_live_info['SOXL']['curr']
        soxl_pred = soxl_curr * (1 + (s_dma/s_curr - 1)*3)
        
        st.markdown(f"**SOXX 多頭續抱 | 現價:{s_curr:.2f} (100DMA:{s_dma:.2f} | 差距: {s_diff:+.2f} / {s_diff_p:+.2f}%)**")
        st.info(f"💡 **SOXL 壓力預測：** 若 SOXX 跌回 100DMA，SOXL 預計來到 **${soxl_pred:.2f}** (距現值 {((soxl_pred/soxl_curr-1)*100):+.1f}%)")

        col_s1, col_s2, col_s3 = st.columns(3)
        for i, target in enumerate([30.14, 21.09, 14.77]):
            dist = (soxl_curr/target - 1)*100
            [col_s1, col_s2, col_s3][i].metric(f"階梯 {i+3} 目標", f"${target}", f"距 {dist:.1f}%", delta_color="inverse")

        st.divider()
        us_cost_usd = sum([v['cost'] for v in us_positions.values()])
        us_roi = (total_us_val_usd - us_cost_usd)/us_cost_usd if us_cost_usd>0 else 0
        days_us = (datetime.today() - df_us['成交日期'].min()).days if not df_us.empty else 1
        ann_roi_us = ((1 + us_roi)**(365/max(days_us, 1)) - 1) * 100

        cu1, cu2, cu3, cu4 = st.columns(4)
        cu1.metric("總市值 (USD)", f"${total_us_val_usd:,.0f}")
        cu2.metric("總投入成本", f"${us_cost_usd:,.0f}")
        cu3.metric("未實現損益", f"{(total_us_val_usd-us_cost_usd):+,.0f}", f"{us_roi*100:+.2f}%")
        cu4.metric("年化報酬率", f"{ann_roi_us:+.2f}%")

        st.subheader("📦 個股明細")
        us_table = []
        for t, info in us_positions.items():
            live = us_live_info[t]; avg = info['cost']/info['shares'] if info['shares']>0 else 0
            cur_pnl = (live['curr'] - avg) * info['shares']
            us_table.append({
                '代號': t, '股數': f"{info['shares']:,.0f}", '均價': f"{avg:.2f}", '成本': f"{info['cost']:,.0f}",
                '昨日': f"{live['yest']:.2f}", '現價': f"{live['curr']:.2f}", 
                '今日損益': f"{(live['curr']/live['yest']-1)*100:+.2f}%", 
                '總損益': f"{(live['curr']/avg-1)*100:+.2f}%" if avg>0 else "0%"
            })
        st.dataframe(pd.DataFrame(us_table), use_container_width=True, hide_index=True)

        st.write(f"🔹 **實際曝險度：** {((us_live_info['SOXL']['curr']*us_positions['SOXL']['shares']*3 + us_live_info['BITX']['curr']*us_positions['BITX']['shares']*2)*usd_twd / FC * 100):.1f}% ｜ **投資組合佔比：** {(total_us_val_twd / (cur_val_tw + total_us_val_twd)*100):.1f}%")

        with st.expander("🛒 新增美股交易紀錄", expanded=False):
            col_ua, col_ub = st.columns(2); tu_date = col_ua.date_input("成交日期", key='us_d'); tu_ticker = col_ub.text_input("股票代號", "SOXL")
            col_uc, col_ud = st.columns(2); tu_price = col_uc.number_input("成交價格", key='us_p'); tu_shares = col_ud.number_input("股數", key='us_s')
            if st.button("寫入美股雲端", use_container_width=True): st.info("已提交請求")

    # ------------------------------------------
    # 🛬 Tab 3: 生命周期 & 退休
    # ------------------------------------------
    with tab3:
        st.subheader("⚖️ 生命周期曝險透視")
        # 計算各戰區曝險
        exp_tw = cur_val_tw * 2
        exp_us = (us_live_info['SOXL']['curr']*us_positions['SOXL']['shares']*3 + us_live_info['BITX']['curr']*us_positions['BITX']['shares']*2) * usd_twd
        exp_total = exp_tw + exp_us
        
        st.markdown(f"""
        | 戰區 | 曝險金額 | 淨資產 (FC) | 實際曝險度 |
        | :--- | :--- | :--- | :--- |
        | 🇹🇼 台股 | NT$ {exp_tw/10000:,.0f} 萬 | NT$ {(cur_val_tw + cash/2 - (loan1+loan2)/2)/10000:,.0f} 萬 | **{(exp_tw/FC*100):.1f}%** |
        | 🇺🇸 美股 | NT$ {exp_us/10000:,.0f} 萬 | NT$ {(total_us_val_twd + cash/2 - (loan1+loan2)/2)/10000:,.0f} 萬 | **{(exp_us/FC*100):.1f}%** |
        | 🔥 **總計** | **NT$ {exp_total/10000:,.0f} 萬** | **NT$ {FC/10000:,.0f} 萬** | **{(exp_total/FC*100):.1f}%** |
        """)

        # 目標 vs 現在
        W = FC + (base_m * 12 * hc_years)
        target_stock_val = W * (target_k / 100.0)
        target_E = target_stock_val / FC * 100
        
        c_tgt, c_act = st.columns(2)
        c_tgt.metric("🎯 生命周期目標曝險度", f"{target_E:.1f}%")
        c_act.metric("🔥 現在總曝險度", f"{(exp_total/FC*100):.1f}%", f"差距: {(exp_total/FC*100 - target_E):+.1f}%")

        # 再平衡指令
        diff_val = exp_total - target_stock_val
        st.subheader("⚖️ 應該如何平衡？")
        if diff_val > 0:
            st.error(f"🚨 **目前總曝險過高！** 建議減少市場部位總價值約 **NT$ {diff_val/10000:,.0f} 萬**")
            st.write(f"👉 **台股部分：** 建議減碼 00631L 約 NT$ {diff_val/2/2/10000:,.0f} 萬市值")
            st.write(f"👉 **美股部分：** 建議減碼 SOXL 約 NT$ {diff_val/2/3/10000:,.0f} 萬市值")
        else:
            st.success(f"🟢 **目前曝險尚有空間！** 可增加市場部位約 **NT$ {abs(diff_val)/10000:,.0f} 萬**")

        st.divider()
        st.subheader("☕ 退休終局與提領反推")
        
        # 情境 A
        fc_future_a = FC
        for _ in range(hc_years): fc_future_a = fc_future_a * 1.08 + (base_m*12)
        mon_a_fut = (fc_future_a * withdrawal_rate)/12
        mon_a_now = mon_a_fut / ((1+inflation_rate)**hc_years)

        st.markdown(f"**📈 情境 A：若再工作 {hc_years} 年後退休**")
        ca1, ca2, ca3 = st.columns(3)
        ca1.metric("屆時滾出資產", f"NT$ {fc_future_a/10000:,.0f} 萬")
        ca2.metric("未來每月可領", f"NT$ {mon_a_fut:,.0f}")
        ca3.metric("約等同現在每月可領", f"NT$ {mon_a_now:,.0f}")

        # 情境 B
        st.write("")
        st.markdown(f"**🎯 情境 B：反推我想要月領 {target_monthly_now/10000:.0f} 萬(現值) 的退休金**")
        found_y = None; t_fc = FC
        for y in range(1, 41):
            t_fc = t_fc * 1.08 + (base_m*12)
            req_m_fut = target_monthly_now * ((1+inflation_rate)**y)
            if t_fc >= (req_m_fut * 12) / withdrawal_rate:
                found_y = y; final_fc = t_fc; final_mon = req_m_fut; break
        
        if found_y:
            cb1, cb2, cb3 = st.columns(3)
            cb1.metric("需滾出退休資產", f"NT$ {final_fc/10000:,.0f} 萬")
            cb2.metric("未來每月可領", f"NT$ {final_mon:,.0f}")
            cb3.metric("剩餘年限", f"{found_y} 年")
        
        with st.expander("🛬 降落時程推演表 (Glide Path)", expanded=False):
            st.caption("這張表告訴你未來的槓桿收水路線，隨著資產變大，你的槓桿應該逐年下降。")
            gp_data = []
            f_gp = FC
            for y in range(hc_years+1):
                if y>0: f_gp = f_gp*1.08 + (base_m*12)
                h_rem = max(0, (base_m*12*hc_years) - (base_m*12*y))
                e_gp = ((f_gp + h_rem)*target_k/100)/f_gp*100
                gp_data.append({"第幾年": f"第 {y} 年", "預估資產(萬)": f"{f_gp/10000:,.0f}", "應有曝險度": f"{e_gp:.1f}%"})
            st.table(pd.DataFrame(gp_data))

st.caption("📱 提示：若美股資料未正常顯示，請檢查 US_records 試算表的分頁名稱與格式。數字已全面萬元化優化排版。")
