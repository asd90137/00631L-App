import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# ==========================================
# 賴賴投資戰情室 V5.1 - 退休終局導航版
# ==========================================

st.set_page_config(page_title="賴賴終極戰情室", page_icon="📈", layout="centered")
st.title("🛡️ 賴賴投資戰情室 V5.1")

if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

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
st.sidebar.caption("--- 以下為退休反推參數 ---")
target_monthly_now = st.sidebar.number_input("9. 目標月領金額 (現值)", value=100000)
inflation_rate = st.sidebar.number_input("10. 預估年化通膨 (%)", value=2.0) / 100
withdrawal_rate = st.sidebar.number_input("11. 安全提領率 (%)", value=4.0) / 100

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
    df_trades_raw = pd.DataFrame()
    actual_shares, actual_cost = 0, 0

if st.button("🚀 啟動戰情室全面掃描", use_container_width=True):
    st.session_state.analyzed = True

tab1, tab2, tab3 = st.tabs(["🇹🇼 台股 00631L", "🇺🇸 美股狙擊系統", "🛬 生命週期與退休"])

if st.session_state.analyzed:
    cur_val = 0
    total_us_val_twd = 0

    # --- [台股與美股邏輯保持不變，略過以減少篇幅，直接進入分頁三] ---
    # (此處包含原有的台美股運算代碼...)
    with tab1:
        TICKER = "00631L.TW"
        data = yf.download(TICKER, period="max", progress=False, auto_adjust=False)
        raw_prices = data['Adj Close'][TICKER].dropna() if isinstance(data.columns, pd.MultiIndex) else data['Adj Close'].dropna()
        raw_prices.index = pd.to_datetime(raw_prices.index).tz_localize(None)
        adj_prices = raw_prices.copy()
        split_cutoff = pd.to_datetime('2026-03-23')
        mask = (adj_prices.index < split_cutoff) & (adj_prices > 100)
        if mask.any(): adj_prices.loc[mask] = round(adj_prices.loc[mask] / 22.0, 2)
        tkr = yf.Ticker(TICKER)
        try:
            raw_curr = float(tkr.fast_info.last_price)
            raw_yest = float(tkr.fast_info.previous_close)
        except:
            raw_curr = float(raw_prices.iloc[-1]); raw_yest = float(raw_prices.iloc[-2])
        current_p = round(raw_curr / 22.0, 2) if raw_curr > 100 else raw_curr
        yest_close = round(raw_yest / 22.0, 2) if raw_yest > 100 else raw_yest
        cur_val = actual_shares * current_p
        abs_pnl = cur_val - actual_cost
        pnl_real = abs_pnl / actual_cost if actual_cost > 0 else 0
        avg_cost = actual_cost / actual_shares if actual_shares > 0 else 0
        intraday_drop = (current_p - yest_close) / yest_close if yest_close > 0 else 0
        st.subheader("📊 詳細庫存與損益明細")
        c1, c2 = st.columns(2)
        c1.metric("總市值 (元)", f"NT$ {cur_val:,.0f}")
        c2.metric("總投入成本", f"NT$ {actual_cost:,.0f}")
        c3, c4 = st.columns(2)
        c3.metric("未實現總損益", f"NT$ {abs_pnl:,.0f}", f"{pnl_real*100:+.2f}%")
        c4.metric("今日還原現價", f"NT$ {current_p:.2f}", f"{intraday_drop*100:+.2f}%")
        st.divider()

    with tab2:
        tickers = ["SOXX", "SOXL", "TMF", "BITX"]
        us_data = yf.download(tickers, period="200d", progress=False)
        us_positions = {"SOXL": {"shares": 545, "cost": 50.99}, "TMF": {"shares": 1050, "cost": 52.94}, "BITX": {"shares": 11, "cost": 29.67}}
        us_live = {}
        for t in us_positions.keys():
            tkr_us = yf.Ticker(t)
            us_live[t] = {'curr': float(tkr_us.fast_info.last_price), 'yest': float(tkr_us.fast_info.previous_close)}
        total_us_val = sum([us_live[t]['curr'] * info['shares'] for t, info in us_positions.items()])
        total_us_val_twd = total_us_val * usd_twd
        st.subheader("📋 美股總資產")
        cu1, cu2 = st.columns(2)
        cu1.metric("美股總市值 (USD)", f"${total_us_val:,.2f}")
        cu2.metric("美股台幣估值", f"NT$ {total_us_val_twd:,.0f}")

    # ==========================================
    # 🛬 分頁三：生命週期與退休規劃 
    # ==========================================
    with tab3:
        st.subheader("🛬 生命週期投資法 & 退休導航")
        
        # 1. 核心數值運算
        FC_TW = cur_val + cash - (loan1 + loan2)
        FC_US = total_us_val_twd
        FC = FC_TW + FC_US
        annual_inv = base_m * 12
        HC = annual_inv * hc_years
        W = FC + HC
        target_stock_val = W * (target_k / 100.0)
        current_E = (target_stock_val / FC * 100) if FC > 0 else 0
        
        twd_exposure_val = cur_val * 2
        soxl_val_twd = us_live['SOXL']['curr'] * us_positions['SOXL']['shares'] * usd_twd
        bitx_val_twd = us_live['BITX']['curr'] * us_positions['BITX']['shares'] * usd_twd
        usd_exposure_val = (soxl_val_twd * 3) + (bitx_val_twd * 2) 
        total_exposure_val = twd_exposure_val + usd_exposure_val
        actual_total_E = (total_exposure_val / FC * 100) if FC > 0 else 0

        # --- 📊 第一區：當前戰況總結 ---
        st.markdown("### 📊 1. 曝險公式透視表")
        st.markdown(f"""
        | 戰區 | 曝險金額 (分子) | 淨資產 (分母) | 實際曝險度 |
        | :--- | :--- | :--- | :--- |
        | **🇹🇼 台股** | NT$ {twd_exposure_val:,.0f} | NT$ {FC_TW:,.0f} | **{(twd_exposure_val/FC_TW*100):.1f}%** |
        | **🇺🇸 美股** | NT$ {usd_exposure_val:,.0f} | NT$ {FC_US:,.0f} | **{(usd_exposure_val/FC_US*100):.1f}%** |
        | **🔥 總計** | **NT$ {total_exposure_val:,.0f}** | **NT$ {FC:,.0f}** | **{actual_total_E:.1f}%** |
        """)
        c_tgt, c_act = st.columns(2)
        c_tgt.metric("🎯 生命週期目標曝險度", f"{current_k:.1f}%" if 'current_k' in locals() else f"{current_E:.1f}%")
        c_act.metric("🔥 現在總曝險度", f"{actual_total_E:.1f}%", f"差距: {actual_total_E - current_E:+.1f}%")

        st.divider()

        # --- ☕ 第二區：退休終局導航 ---
        st.markdown("### ☕ 2. 退休反推與進度導航")
        
        # A. 根據目前的 HC 結束點 (例如10年後) 預估退休收入
        # 假設以 8% 正常情境計算 10 年後的 FC
        fc_future_10 = FC
        for _ in range(hc_years): fc_future_10 = fc_future_10 * 1.08 + annual_inv
        
        annual_withdraw_future = fc_future_10 * withdrawal_rate
        monthly_withdraw_future = annual_withdraw_future / 12
        # 反推回現在的價值 (扣除通膨)
        monthly_withdraw_now_equiv = monthly_withdraw_future / ((1 + inflation_rate)**hc_years)

        st.markdown(f"**📈 情境 A：若工作 {hc_years} 年後退休**")
        col_ra1, col_ra2 = st.columns(2)
        col_ra1.metric(f"{hc_years}年後每月可領", f"NT$ {monthly_withdraw_future:,.0f}", "未來名目價值")
        col_ra2.metric("約等同現在月薪", f"NT$ {monthly_withdraw_now_equiv:,.0f}", f"扣除 {inflation_rate*100:.1f}% 通膨")
        
        # B. 根據目標月薪，反推還要工作多久
        # 先算出目標月薪在未來的名目金額，再算出需要多少總資產 (4%原則)
        st.markdown(f"**🎯 情境 B：為了達到現在體感的「月領 {target_monthly_now/10000:.0f} 萬」退休金**")
        
        found_year = None
        temp_fc = FC
        for y in range(1, 41): # 最多推算 40 年
            temp_fc = temp_fc * 1.08 + annual_inv
            # 第 y 年需要的未來月領額 (考慮通膨)
            req_monthly_future = target_monthly_now * ((1 + inflation_rate)**y)
            # 需要的總資產 (根據 4% 提領率)
            req_fc_total = (req_monthly_future * 12) / withdrawal_rate
            
            if temp_fc >= req_fc_total:
                found_year = y
                final_req_fc = req_fc_total
                break
        
        if found_year:
            st.success(f"🎊 **目標達成預測：還要工作 {found_year} 年**")
            st.write(f"🔹 屆時總資產需達：**NT$ {final_req_fc:,.0f}**")
            st.write(f"🔹 屆時每月提領：**NT$ {target_monthly_now * ((1 + inflation_rate)**found_year):,.0f}** (等於現在的 {target_monthly_now:,.0f} 元)")
        else:
            st.warning("⚠️ 依目前投入速度，40 年內難以達成此目標月薪，建議增加投入或調整目標。")

        st.divider()
        
        # --- 🛬 第三區：降落時程表 ---
        st.markdown("### 🛬 3. 降落時程推演表 (Glide Path)")
        records_gp = []
        f6, f8, f10 = FC, FC, FC
        drop_year = None
        for y in range(0, hc_years + 1):
            if y == 0: e6 = e8 = e10 = current_E
            else:
                f6 = f6*1.06 + annual_inv; f8 = f8*1.08 + annual_inv; f10 = f10*1.10 + annual_inv
                hc_rem = max(HC - annual_inv * y, 0)
                e6 = ((f6 + hc_rem) * (target_k/100)) / f6 * 100
                e8 = ((f8 + hc_rem) * (target_k/100)) / f8 * 100
                e10 = ((f10 + hc_rem) * (target_k/100)) / f10 * 100
            if e8 < 200 and drop_year is None: drop_year = y
            records_gp.append({"第幾年": f"第 {y} 年","預估 FC (8%)": f"{f8:,.0f}","應有曝險(8%)": f"{e8:.1f}%","保守(6%)": f"{e6:.1f}%","樂觀(10%)": f"{e10:.1f}%"})
        st.dataframe(pd.DataFrame(records_gp), use_container_width=True, hide_index=True)

st.caption("📱 提示：將此網頁「加入主畫面」，它就是你的專屬實戰 App！")
