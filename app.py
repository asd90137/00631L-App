import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# ==========================================
# 賴賴投資戰情室 V5.2 - 退休終局統一排版版
# ==========================================

st.set_page_config(page_title="賴賴終極戰情室", page_icon="📈", layout="centered")
st.title("🛡️ 賴賴投資戰情室 V5.2")

# --- 初始化 Analyzed 狀態 ---
if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

# --- 側邊欄：資金與曝險參數 ---
st.sidebar.header("⚙️ 資金與曝險參數")
loan1 = st.sidebar.number_input("1. 信貸一剩餘本金", value=2056231)
loan2 = st.sidebar.number_input("2. 信貸二剩餘本金", value=935907)
base_m = st.sidebar.number_input("3. 基準每月定期定額", value=100000)
cash = st.sidebar.number_input("4. 目前帳戶可用現金", value=2000000)
target_exp_pct = st.sidebar.number_input("5. 設定目標曝險度 (%)", value=200)

# --- 側邊欄：生命週期與退休規劃 ---
st.sidebar.divider()
st.sidebar.header("⚙️ 生命周期與退休規劃")
usd_twd = st.sidebar.number_input("6. 目前美元匯率", value=32.0)
hc_years = st.sidebar.number_input("7. 預計剩餘投入年限", value=10, step=1)
target_k = st.sidebar.number_input("8. 一生目標曝險度 (%)", value=83)
st.sidebar.caption("--- 以下為退休反推參數 ---")
target_monthly_now = st.sidebar.number_input("9. 目標月領金額 (現值)", value=100000, step=10000)
inflation_rate_in = st.sidebar.number_input("10. 預估年化通膨 (%)", value=2.0)
withdrawal_rate_in = st.sidebar.number_input("11. 安全提領率 (%)", value=4.0)

# 轉換趴數為小數
inflation_rate = inflation_rate_in / 100.0
withdrawal_rate = withdrawal_rate_in / 100.0

# --- 初始化美股美金數據，供給 Lifecycle 運算預設值 ---
# 定義在 analyzed 區塊外，確保不管哪個 Tab 被點擊，變數都存在
total_us_val_twd_for_lifecycle = 0.0
usd_live_for_lifecycle = {}
us_positions_for_lifecycle = {"SOXL": {"shares": 545, "cost": 50.99}, "BITX": {"shares": 11, "cost": 29.67}}

# --- Google Sheets 資料同步與計算核心均價股數 (優化效能) ---
@st.cache_data(ttl=0) # 0 代表不快取，每次強制同步
def get_stock_data():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_trades_raw = conn.read(ttl=0)
        temp_df = df_trades_raw.copy()
        temp_df['成交日期'] = pd.to_datetime(temp_df['成交日期'])
        temp_df.loc[temp_df['交易類型'].str.contains('賣出', na=False), '庫存股數'] = -temp_df['庫存股數'].abs()
        temp_df.loc[temp_df['交易類型'].str.contains('賣出', na=False), '持有成本'] = -temp_df['持有成本'].abs()
        actual_shares = temp_df['庫存股數'].sum()
        actual_cost = temp_df['持有成本'].sum()
        return df_trades_raw, temp_df, actual_shares, actual_cost
    except:
        return pd.DataFrame(), pd.DataFrame(), 0, 0

df_trades_raw, temp_df, actual_shares, actual_cost = get_stock_data()

if not df_trades_raw.empty:
    st.sidebar.success("✅ 台股資料同步成功！")
else:
    st.sidebar.error("❌ 台股資料讀取失敗。")

# --- 啟動按鈕 ---
if st.button("🚀 啟動戰情室全面掃描", use_container_width=True):
    st.session_state.analyzed = True
    st.cache_data.clear() # 清除 yfinance 快取

# ==========================================
# 📊Analyzed 區塊：只有按鈕按下後才顯示
# ==========================================
if st.session_state.analyzed:
    
    # --- 🌟 集中在最上方計算所需的基礎即時報價，確保 Lifecycle 運算準確 ---
    TICKER = "00631L.TW"
    split_cutoff = pd.to_datetime('2026-03-23')
    tickers_us = ["SOXX", "SOXL", "TMF", "BITX"]
    
    # 台股即時價格
    tkr_tw = yf.Ticker(TICKER)
    try:
        raw_curr_tw = float(tkr_tw.fast_info.last_price)
    except:
        # 備援機制
        hist_tw = yf.download(TICKER, period="1d", interval="1m", progress=False)
        raw_curr_tw = float(hist_tw['Adj Close'].dropna().iloc[-1])
    current_p = round(raw_curr_tw / 22.0, 2) if raw_curr_tw > 100 else raw_curr_tw
    cur_val = actual_shares * current_p

    # 美股即時價格與美金總市值
    total_us_val = 0.0
    us_positions = {
        "SOXL": {"shares": 545, "cost": 50.99},
        "TMF": {"shares": 1050, "cost": 52.94},
        "BITX": {"shares": 11, "cost": 29.67}
    }
    for t, info in us_positions.items():
        try:
            tkr_us_live = yf.Ticker(t)
            price_us_live = float(tkr_us_live.fast_info.last_price)
        except:
            hist_us_live = yf.download(t, period="1d", interval="1m", progress=False)
            price_us_live = float(hist_us_live['Adj Close'].dropna().iloc[-1])
        usd_live_for_lifecycle[t] = {'curr': price_us_live}
        total_us_val += price_us_live * info['shares']
    total_us_val_twd = total_us_val * usd_twd

    # ==========================================
    # 開闢三個分頁
    # ==========================================
    tab1, tab2, tab3 = st.tabs(["🇹🇼 台股 00631L", "🇺🇸 美股狙擊系統", "🛬 生命周期與退休"])

    # ------------------------------------------
    # 🇹🇼 分頁一：台股 00631L 詳細戰情 (找回來了！)
    # ------------------------------------------
    with tab1:
        with st.spinner('📡 抓取即時數據與歷史運算中...'):
            data = yf.download(TICKER, period="max", progress=False, auto_adjust=False)
            if isinstance(data.columns, pd.MultiIndex):
                raw_prices = data['Adj Close'][TICKER].dropna() if 'Adj Close' in data.columns.get_level_values(0) else data['Close'][TICKER].dropna()
            else:
                raw_prices = data['Adj Close'].dropna() if 'Adj Close' in data.columns else data['Close'].dropna()
            raw_prices.index = pd.to_datetime(raw_prices.index).tz_localize(None)

            # 3/23 股價還原 (歷史圖表用)
            adj_prices = raw_prices.copy()
            mask = (adj_prices.index < split_cutoff) & (adj_prices > 100)
            if mask.any():
                adj_prices.loc[mask] = round(adj_prices.loc[mask] / 22.0, 2)
            
            # 再抓昨日收盤與漲跌幅
            tkr_details = yf.Ticker(TICKER)
            try:
                raw_yest_tw = float(tkr_details.fast_info.previous_close)
            except:
                hist_tw_yest = yf.download(TICKER, period="2d", progress=False)
                raw_yest_tw = float(hist_tw_yest['Adj Close'].dropna().iloc[-2])
            yest_close = round(raw_yest_tw / 22.0, 2) if raw_yest_tw > 100 else raw_yest_tw
            
            abs_pnl = cur_val - actual_cost
            pnl_real = abs_pnl / actual_cost if actual_cost > 0 else 0
            avg_cost = actual_cost / actual_shares if actual_shares > 0 else 0
            intraday_drop = (current_p - yest_close) / yest_close if yest_close > 0 else 0
            today_pnl = (current_p - yest_close) * actual_shares
            
            st.subheader("📊 詳細庫存與損益明細")
            c1, c2 = st.columns(2)
            c1.metric("總市值 (元)", f"NT$ {cur_val:,.0f}")
            c2.metric("總投入成本", f"NT$ {actual_cost:,.0f}")
            c3, c4 = st.columns(2)
            c3.metric("未實現總損益", f"NT$ {abs_pnl:,.0f}", f"{pnl_real*100:+.2f}%")
            c4.metric("今日還原現價", f"NT$ {current_p:.2f}", f"{intraday_drop*100:+.2f}%")
            c5, c6 = st.columns(2)
            c5.metric("今日損益", f"NT$ {today_pnl:,.0f}")
            c6.metric("持有均價", f"NT$ {avg_cost:,.2f}")
            st.divider()

            # --- 📜 逐筆明细表 ---
            st.subheader("📜 逐筆投資戰績表")
            with st.expander("點擊展開：檢視每筆子彈的獨立作戰績效", expanded=False):
                if not df_trades_raw.empty:
                    buy_df = df_trades_raw[df_trades_raw['交易類型'].str.contains('買入', na=False)].copy()
                    if not buy_df.empty:
                        buy_df['成交日期'] = pd.to_datetime(buy_df['成交日期'])
                        buy_df = buy_df.sort_values(by='成交日期', ascending=False)
                        today_date = pd.to_datetime(datetime.today().date())
                        
                        records = []
                        for idx, row in buy_df.iterrows():
                            trade_d = row['成交日期']
                            r_price = float(row['成交價格'])
                            r_shares = float(row['庫存股數'])
                            t_cost = float(row['持有成本'])
                            if trade_d < split_cutoff and r_price > 100:
                                adj_p = r_price / 22.0; adj_s = r_shares * 22.0
                            else:
                                adj_p = r_price; adj_s = r_shares
                            
                            lot_cur_val = adj_s * current_p
                            lot_pnl = lot_cur_val - t_cost
                            lot_roi = lot_pnl / t_cost if t_cost > 0 else 0
                            days_held = max((today_date - trade_d).days, 1)
                            ann_roi = (1 + lot_roi) ** (365.0 / days_held) - 1
                            
                            records.append({'📅 日期': trade_d.strftime('%Y-%m-%d'),'🛒 買價': f"{adj_p:.2f}",'📦 股數': f"{adj_s:,.0f}",'💰 成本': f"{t_cost:,.0f}",'📈 總損益': f"{lot_pnl:+,.0f}",'🎯 總報酬': f"{lot_roi*100:+.2f}%",'🚀 年化報酬': f"{ann_roi*100:+.2f}%"})
                        st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)
            st.divider()

            # --- 📊 戰術圖表 ---
            st.subheader("🌐 戰術圖表分析")
            recent_prices = adj_prices[adj_prices.index >= pd.to_datetime('2024-01-01')]
            st.write("📈 **A. 價格走勢與當前均價防線**")
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=recent_prices.index, y=recent_prices.values, mode='lines', name='還原股價', line=dict(color='#E71D36', width=2)))
            if avg_cost > 0:
                fig1.add_hline(y=avg_cost, line_dash="dash", line_color="#00A86B", annotation_text=f"均價: {avg_cost:.2f}")
            fig1.update_layout(template='plotly_white', margin=dict(l=0, r=0, t=35, b=0), height=200)
            st.plotly_chart(fig1, use_container_width=True)

            st.write("📊 **B. 多空戰略乖離率**")
            ma20 = recent_prices.rolling(window=20).mean()
            bias = (recent_prices - ma20) / ma20 * 100
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=bias.index, y=bias.values, fill='tozeroy', mode='lines', name='乖離率%', line=dict(color='#F4A261')))
            fig2.add_hline(y=0, line_width=1, line_color="black") 
            fig2.update_layout(template='plotly_white', margin=dict(l=0, r=0, t=10, b=0), height=200)
            st.plotly_chart(fig2, use_container_width=True)

            st.write("💰 **C. 庫存真實損益率軌跡**")
            if not temp_df.empty:
                trade_hist = temp_df.copy(); trade_hist = trade_hist.groupby('成交日期')[['庫存股數', '持有成本']].sum().reset_index(); trade_hist.set_index('成交日期', inplace=True); trade_hist.index = pd.to_datetime(trade_hist.index).tz_localize(None)
                daily_hist = trade_hist.reindex(adj_prices.index).fillna(0); daily_shares = daily_hist['庫存股數'].cumsum(); daily_cost = daily_hist['持有成本'].cumsum()
                daily_mv = daily_shares * adj_prices; daily_pnl_pct = np.where(daily_cost > 0, (daily_mv - daily_cost) / daily_cost * 100, 0); daily_pnl_pct_series = pd.Series(daily_pnl_pct, index=adj_prices.index); recent_pnl_pct = daily_pnl_pct_series[daily_pnl_pct_series.index >= pd.to_datetime('2024-01-01')]
                fig3 = go.Figure(); fig3.add_trace(go.Scatter(x=recent_pnl_pct.index, y=recent_pnl_pct.values, mode='lines', name='真實損益%', line=dict(color='#247BA0'))); fig3.add_hline(y=0, line_width=2, line_color="black"); fig3.update_layout(template='plotly_white', margin=dict(l=0, r=0, t=10, b=0), height=200)
                st.plotly_chart(fig3, use_container_width=True)

    # ------------------------------------------
    # 🇺🇸 分頁二：美股狙擊系統 (找回來了！)
    # ------------------------------------------
    with tab2:
        with st.spinner('📡 抓取美股數據中...'):
            us_data = yf.download(tickers_us, period="200d", progress=False)
            us_live = {}
            for t in us_positions.keys():
                tkr_us_det = yf.Ticker(t)
                try:
                    curr = float(tkr_us_det.fast_info.last_price)
                    yest = float(tkr_us_det.fast_info.previous_close)
                except:
                    curr = float(us_data['Close'][t].dropna().iloc[-1]); yest = float(us_data['Close'][t].dropna().iloc[-2])
                us_live[t] = {'curr': curr, 'yest': yest}
            
            st.subheader("🎯 1. 大盤趨勢與輪動階梯")
            soxx_close = us_data['Close']['SOXX'].dropna()
            soxx_100dma = soxx_close.rolling(window=100).mean(); curr_soxx = soxx_close.iloc[-1]; curr_dma = soxx_100dma.iloc[-1]
            if curr_soxx > curr_dma: st.success(f"🟢 **SOXX 多頭續抱** | 現價:{curr_soxx:.2f} (100DMA:{curr_dma:.2f})")
            else: st.error(f"🔴 **停利訊號觸發！** | 現價:{curr_soxx:.2f} 跌破 100DMA ({curr_dma:.2f})")
            
            steps = [30.14, 21.09, 14.77]; cols = st.columns(3); curr_soxl = us_live['SOXL']['curr']
            for i, target in enumerate(steps):
                if curr_soxl <= target: cols[i].warning(f"✅ 階梯 {i+3}\n已達標\n${target}")
                else: cols[i].info(f"⏳ 階梯 {i+3}\n目标 ${target}")
            
            st.divider()
            total_us_val_det = 0.0; total_us_cost_det = 0.0; total_today_pnl_det = 0.0
            for t, info in us_positions.items():
                p_c = us_live[t]['curr']; p_y = us_live[t]['yest']; shr = info['shares']
                total_us_val_det += p_c * shr; total_us_cost_det += info['cost'] * shr; total_today_pnl_det += (p_c - p_y) * shr
            total_abs_pnl_det = total_us_val_det - total_us_cost_det; total_pnl_pct_det = total_abs_pnl_det / total_us_cost_det if total_us_cost_det > 0 else 0

            st.subheader("📋 2. 美股總資產身價")
            cu1, cu2 = st.columns(2)
            cu1.metric("美股總市值 (USD)", f"${total_us_val_det:,.2f}")
            cu2.metric("美股總投入成本 (USD)", f"${total_us_cost_det:,.2f}")
            cu3, cu4 = st.columns(2)
            cu3.metric("未實現總損益", f"${total_abs_pnl_det:,.2f}", f"{total_pnl_pct_det*100:+.2f}%")
            cu4.metric("今日總損益", f"${total_today_pnl_det:,.2f}")
            st.divider()

            st.subheader("📦 3. 個股明細快報")
            for t, info in us_positions.items():
                p_c = us_live[t]['curr']; p_y = us_live[t]['yest']; shr = info['shares']; avg = info['cost']
                cur_v = p_c * shr; tot_c = avg * shr; pnl_a = cur_v - tot_c; pnl_p = pnl_a / tot_c if tot_c > 0 else 0
                today_v = (p_c - p_y) * shr; today_p = (p_c / p_y - 1)
                st.markdown(f"#### 📌 **{t}** | 今日: ${p_c:.2f} ({today_p*100:+.2f}%)")
                st.write(f"🔹 **持倉:** {shr:,.0f} 股 / **成本:** ${avg:.2f} / **市值:** ${cur_v:,.2f}")
                st.write(f"🔹 **總損益:** ${pnl_a:,.2f} ({pnl_p*100:+.2f}%) / **今日損益:** ${today_v:,.2f}")
                st.markdown("---")

    # ------------------------------------------
    # 🛬 分頁三：生命週期與退休規劃 (排版更新重點！)
    # ------------------------------------------
    with tab3:
        st.subheader("🛬 生命週期投資法 & 退休終局導航")
        st.write("系統已自動抓取你當前的台美股真實市值、現金與信貸，為你推演未來的最佳化降落軌跡。")
        
        # --- Lifecycle 數值運算 ---
        FC_TW = cur_val + cash - (loan1 + loan2) # 台股帳戶實質淨值
        FC_US = total_us_val_twd_for_lifecycle # 美股帳戶實質淨值
        FC = FC_TW + FC_US
        annual_inv = base_m * 12
        HC = annual_inv * hc_years
        W = FC + HC
        target_stock_val = W * (target_k / 100.0)
        current_E_lifecycle = (target_stock_val / FC * 100) if FC > 0 else 0
        
        # 算出分子 (實質跳動曝險金額，使用 Lifecycle 專用預先計算的數據)
        twd_exposure_val = cur_val * 2 # 台股 00631L 是 2倍
        soxl_val_twd_lf = usd_live_for_lifecycle['SOXL']['curr'] * us_positions_for_lifecycle['SOXL']['shares'] * usd_twd
        bitx_val_twd_lf = usd_live_for_lifecycle['BITX']['curr'] * us_positions_for_lifecycle['BITX']['shares'] * usd_twd
        usd_exposure_val = (soxl_val_twd_lf * 3) + (bitx_val_twd_lf * 2) # TMF 避險債券不列入
        total_exposure_val = twd_exposure_val + usd_exposure_val
        
        # 算出實際曝險度
        actual_twd_E = (twd_exposure_val / FC_TW * 100) if FC_TW > 0 else 0
        actual_usd_E = (usd_exposure_val / FC_US * 100) if FC_US > 0 else 0
        actual_total_E = (total_exposure_val / FC * 100) if FC > 0 else 0

        st.divider()
        
        # --- ⚖️ 1. 曝險公式透視表 (去掉大分子、大分母) ---
        st.markdown("### ⚖️ 1. 當前實際曝險度透視 (槓桿乘開計算)")
        st.markdown(f"""
        | 戰區 | 曝險金額 | 淨資產 (FC) | 實際曝險度 |
        | :--- | :--- | :--- | :--- |
        | **🇹🇼 台股 (00631L市值x2)** | NT$ {twd_exposure_val:,.0f} | NT$ {FC_TW:,.0f} | **{actual_twd_E:.1f}%** |
        | **🇺🇸 美股 (攻擊標的依槓桿還原)** | NT$ {usd_exposure_val:,.0f} | NT$ {FC_US:,.0f} | **{actual_usd_E:.1f}%** |
        | **🔥 總計** | **NT$ {total_exposure_val:,.0f}** | **NT$ {FC:,.0f}** | **{actual_total_E:.1f}%** |
        """)

        # 大Metric 並排 (目標 vs 現在)
        c_tgt, c_act = st.columns(2)
        c_tgt.metric("🎯 生命週期目標曝險度", f"{current_E_lifecycle:.1f}%")
        c_act.metric("🔥 現在總曝險度", f"{actual_total_E:.1f}%", f"差距: {actual_total_E - current_E_lifecycle:+.1f}%")

        # --- 智能降落指南 ---
        target_exp_val_from_lf = FC * (current_E_lifecycle / 100.0)
        excess_exposure_val = total_exposure_val - target_exp_val_from_lf
        
        if excess_exposure_val > 0:
            st.error(f"🚨 **目前【高於】目標曝險度！** (總曝險超標金額：NT$ {excess_exposure_val:,.0f})")
            st.markdown(f"""
            **💡 降落操作指南（依此進行再平衡即可）：**
            * 【方案 A】🇹🇼 賣出市值 **NT$ {excess_exposure_val / 2:,.0f}** 的 00631L (2倍)，**轉存為現金**。
            * 【方案 B】🇹🇼 賣出市值 **NT$ {excess_exposure_val / 1:,.0f}** 的 00631L (2倍)，全數**買入 0050** (1倍)。
            * 【方案 C】🇺🇸 賣出市值 **NT$ {excess_exposure_val / 3:,.0f}** 的 SOXL (3倍)，**轉存為美金現金**。
            """)
        else:
            st.success(f"🟢 **目前【低於】目標曝險度！** (尚可加碼空間：NT$ {abs(excess_exposure_val):,.0f})")

        st.divider()

        # --- ☕ 2. 退休終局導航 (排版統一升級！) ---
        st.markdown("### ☕ 2. 退休終局與提領反推")
        
        # --- 情境 A：現況預測 ---
        st.markdown(f"**📈 情境 A：依照目前每年 {annual_inv/10000:,.0f} 萬投入，於 {hc_years} 年後投入期結束時退休**")
        # 假設以 8% 正常情境計算 {hc_years} 年後的 FC (資產母體)
        fc_future_a = FC
        for _ in range(hc_years): fc_future_a = fc_future_a * 1.08 + annual_inv
        annual_withdraw_a_fut = fc_future_a * withdrawal_rate
        monthly_withdraw_a_fut = annual_withdraw_a_fut / 12
        monthly_withdraw_a_now = monthly_withdraw_a_fut / ((1 + inflation_rate)**hc_years)

        # A 的大看板 (統一排版)
        col_ra1, col_ra2, col_ra3 = st.columns(3)
        col_ra1.metric("屆時滾出資產", f"NT$ {fc_future_a:,.0f}")
        col_ra2.metric("屆時未來需月領", f"NT$ {monthly_withdraw_a_fut:,.0f}")
        col_ra3.metric("約等同現在月薪", f"NT$ {monthly_withdraw_a_now:,.0f}", f"扣除通膨")
        st.info("💡 屆時總資產配置：83% 控制市場 (例如用 41.5% 正2，其餘約 6 成資金放現金/美債安全提領)。")
        st.divider()

        # --- 情境 B：目標反推 (幫你統一排版了！) ---
        st.markdown(f"**🎯 情境 B：反推我想要在退休時，擁有現在領 {target_monthly_now:,.0f} 元月薪的體感**")
        found_year = None; temp_fc = FC
        for y in range(1, 41): # 最多推算 40 年
            temp_fc = temp_fc * 1.08 + annual_inv
            req_monthly_fut = target_monthly_now * ((1 + inflation_rate)**y)
            req_fc_total = (req_monthly_fut * 12) / withdrawal_rate
            if temp_fc >= req_fc_total:
                found_year = y; final_req_fc = req_fc_total; final_monthly_fut = req_monthly_fut; break
        
        # B 的大看板 (這就是你要的統一模樣！在 Metric 先顯示數字)
        if found_year:
            col_rb1, col_rb2, col_rb3 = st.columns(3)
            col_rb1.metric("需滾出退休資產", f"NT$ {final_req_fc:,.0f}")
            col_rb2.metric("屆時未來需月領", f"NT$ {final_monthly_fut:,.0f}", f"現值 {target_monthly_now:,.0f}")
            col_rb3.metric("工作剩餘年限", f"{found_year} 年")
            st.success(f"🎉 **目標達成！** 依照目前投入速度與正常市況，還要工作 **{found_year}** 年即可完美降落。")
        else:
            # 沒達到的 Metric 排版
            col_rb1, col_rb2, col_rb3 = st.columns(3)
            col_rb1.metric("需滾出退休資產", f"NT$ {target_monthly_now * 12 / withdrawal_rate * ((1 + inflation_rate)**40):,.0f}")
            col_rb2.metric("工作剩餘年限", f"> 40 年")
            st.warning("⚠️ **火力不足！** 依目前投入速度，40 年內難以達成體感 10 萬的目標，建議增加投入金額或降低退休目標。")
            
        st.divider()
        
        # --- 🛬 3. 降落時程推演表 ---
        st.markdown("### 🛬 3. 降落時程推演表 (Glide Path)")
        st.caption("以下推演在保守(6%)、正常(8%)、樂觀(10%)三種年化報酬情境下，你的FC成長與應有曝險度變化。")
        records_gp = []
        f6, f8, f10 = FC, FC, FC
        drop_year = None
        for y in range(0, hc_years + 1):
            if y == 0: e6 = e8 = e10 = current_E_lifecycle
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
