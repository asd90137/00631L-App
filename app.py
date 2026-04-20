import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import calendar
import pytz

# ==========================================
# 賴賴投資戰情室 V9.7 - 終極雙引擎版 (Fugle 即時報價)
# ==========================================

st.set_page_config(page_title="賴賴終極戰情室", page_icon="💰", layout="wide")
st.title("🛡️ 賴賴投資戰情室 V9.7 (終極雙引擎)")

if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

# ==========================================
# 🔑 Fugle API Key 設定
# ==========================================
FUGLE_API_KEY = "NGMwZjg5NjctNTdjOS00NTY1LTkwZGUtMGZhNTFlZjIwYjBkIGQ1NWQ2ZGQ3LTljMTQtNDExYi1hZDE3LTNiYTIyNmM2NDA2Yw=="

# ==========================================
# 📡 Fugle 即時報價函式 (含 yfinance 備援)
# ==========================================
@st.cache_data(ttl=60)  # 每 60 秒才重新呼叫一次，避免超過頻率限制
def get_tw_price(ticker_symbol: str):
    """
    優先使用 Fugle MarketData API 取得台股即時報價。
    若 Fugle 失敗，自動降級使用 yfinance 備援。
    
    回傳: (curr_price, prev_close, source_label, update_time_str, age_minutes)
    """
    tw_tz = pytz.timezone("Asia/Taipei")
    
    # --- 嘗試 Fugle API ---
    try:
        from fugle_marketdata import RestClient
        client = RestClient(api_key=FUGLE_API_KEY)
        
        # 取得即時報價
        quote = client.stock.intraday.quote(symbol=ticker_symbol)
        
        curr_price = quote.get("closePrice") or quote.get("lastPrice") or quote.get("referencePrice", 0)
        prev_close = quote.get("referencePrice", curr_price)
        
        # 解析更新時間
        update_time_raw = quote.get("lastUpdated") or quote.get("lastTrade", {}).get("time")
        if update_time_raw:
            try:
                update_dt = pd.to_datetime(update_time_raw).tz_localize("Asia/Taipei") if pd.to_datetime(update_time_raw).tzinfo is None else pd.to_datetime(update_time_raw).astimezone(tw_tz)
                now_tw = datetime.now(tz=tw_tz)
                age_min = (now_tw - update_dt).total_seconds() / 60
                time_str = update_dt.strftime("%Y-%m-%d %H:%M")
            except:
                age_min = 0
                time_str = "未知"
        else:
            age_min = 0
            time_str = "未知"
        
        return float(curr_price), float(prev_close), "🟢 Fugle 即時", time_str, age_min
    
    except ImportError:
        pass  # fugle_marketdata 未安裝，降級
    except Exception as fugle_err:
        st.sidebar.warning(f"⚠️ Fugle API 失敗：{fugle_err}，改用 yfinance")
    
    # --- Fugle 失敗：yfinance fast_info 備援 ---
    try:
        yf_ticker = ticker_symbol + ".TW" if not ticker_symbol.endswith(".TW") else ticker_symbol
        tkr = yf.Ticker(yf_ticker)
        fi = tkr.fast_info
        curr_price = float(fi.last_price)
        prev_close = float(fi.previous_close)
        
        try:
            last_ts = fi.regular_market_time
            if isinstance(last_ts, (int, float)):
                update_dt = datetime.fromtimestamp(last_ts, tz=tw_tz)
            else:
                update_dt = last_ts.astimezone(tw_tz)
            now_tw = datetime.now(tz=tw_tz)
            age_min = (now_tw - update_dt).total_seconds() / 60
            time_str = update_dt.strftime("%Y-%m-%d %H:%M")
        except:
            age_min = 999
            time_str = "無法取得"
        
        return curr_price, prev_close, "🟡 yfinance fast_info", time_str, age_min
    
    except Exception:
        pass
    
    # --- 最終備援：yfinance download 歷史資料 ---
    try:
        yf_ticker = ticker_symbol + ".TW" if not ticker_symbol.endswith(".TW") else ticker_symbol
        hist = yf.download(yf_ticker, period="5d", progress=False)
        
        # 相容新版 yfinance MultiIndex
        if isinstance(hist.columns, pd.MultiIndex):
            closes = hist["Close"][yf_ticker].dropna()
        else:
            closes = hist["Close"].dropna()
        
        curr_price = float(closes.iloc[-1])
        prev_close = float(closes.iloc[-2]) if len(closes) >= 2 else curr_price
        return curr_price, prev_close, "🔴 yfinance 歷史備援", "歷史資料", 9999
    
    except Exception:
        return 1.0, 1.0, "❌ 完全失敗", "N/A", 99999


@st.cache_data(ttl=60)
def get_us_price(ticker_symbol: str):
    """
    取得美股即時報價（yfinance，含 MultiIndex 修正）
    回傳: (curr_price, prev_close)
    """
    try:
        tkr = yf.Ticker(ticker_symbol)
        curr_p = float(tkr.fast_info.last_price)
        yest_p = float(tkr.fast_info.previous_close)
        return curr_p, yest_p
    except:
        pass
    
    try:
        hist = yf.download(ticker_symbol, period="5d", progress=False)
        if isinstance(hist.columns, pd.MultiIndex):
            closes = hist["Close"][ticker_symbol].dropna()
        else:
            closes = hist["Close"].dropna()
        curr_p = float(closes.iloc[-1])
        yest_p = float(closes.iloc[-2]) if len(closes) >= 2 else curr_p
        return curr_p, yest_p
    except:
        return 0.0, 0.0


# --- 🏦 核心引擎：貸款自動計算 ---
def calculate_loan_remaining(principal, annual_rate, years, start_date):
    if principal <= 0 or years <= 0:
        return 0, 0
    r = annual_rate / 100 / 12
    N = years * 12
    pmt = principal * r * (1+r)**N / ((1+r)**N - 1) if r > 0 else principal / N
    today = datetime.today().date()
    passed_months = (today.year - start_date.year) * 12 + (today.month - start_date.month)
    if today.day >= start_date.day:
        passed_months += 1
    passed_months = max(0, min(passed_months, int(N)))
    rem_balance = principal * ((1+r)**N - (1+r)**passed_months) / ((1+r)**N - 1) if r > 0 else principal - (pmt * passed_months)
    return max(0, rem_balance), pmt


# --- 側邊欄：全局參數 ---
st.sidebar.header("⚙️ 資金與曝險參數")
base_m_wan = st.sidebar.number_input("1. 基準每月定期定額 (萬)", value=10.0, step=1.0)
cash_wan = st.sidebar.number_input("2. 目前帳戶可用現金 (萬)", value=200.0, step=10.0)
us_cash_usd = st.sidebar.number_input("3. 美股可用現金 (USD)", value=345.0, step=10.0)
target_exp_pct = st.sidebar.number_input("4. 設定目標曝險度 (%)", value=200)

base_m = base_m_wan * 10000
cash = cash_wan * 10000

with st.sidebar.expander("🏦 貸款細項設定 (自動連動)", expanded=False):
    l1_p = st.number_input("信貸一總額", value=2830000)
    l1_r = st.number_input("年利率1(%)", value=2.28)
    l1_d = st.date_input("首次扣款日1", datetime(2024, 1, 15))
    loan1, pmt1 = calculate_loan_remaining(l1_p, l1_r, 7, l1_d)
    st.info(f"貸1剩餘：{loan1/10000:.1f}萬")
    st.divider()
    l2_p = st.number_input("信貸二總額", value=950000)
    l2_r = st.number_input("年利率2(%)", value=2.72)
    l2_d = st.date_input("首次扣款日2", datetime(2026, 3, 5))
    loan2, pmt2 = calculate_loan_remaining(l2_p, l2_r, 10, l2_d)
    st.info(f"貸2剩餘：{loan2/10000:.1f}萬")

st.sidebar.divider()
st.sidebar.header("⚙️ 生命周期與退休規劃")
usd_twd = st.sidebar.number_input("6. 目前美元匯率", value=32.0)
hc_years = st.sidebar.number_input("7. 預計剩餘投入年限", value=11)
target_k = st.sidebar.number_input("8. 一生目標曝險度 (%)", value=83)
target_monthly_now = st.sidebar.number_input("9. 目標月領金額 (現值)", value=100000, step=10000)
inflation_rate = st.sidebar.number_input("10. 預估通膨 (%)", value=2.0) / 100.0
withdrawal_rate = st.sidebar.number_input("11. 安全提領率 (%)", value=4.0) / 100.0

# --- 🚀 雙帳本雲端同步 ---
SHEET_TW = "https://docs.google.com/spreadsheets/d/1yYs-JIW4-8jr8EoyyWlydNrE5Gtd_frWdlMQVdn1VYk/edit?usp=sharing"
SHEET_US = "https://docs.google.com/spreadsheets/d/1-NPhyuRNWSarFPdgHjUkB9J3smSbn3u3fjUbMhMVyfI/edit?usp=sharing"

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_tw_raw = conn.read(spreadsheet=SHEET_TW, ttl=0)
    df_us_raw = conn.read(spreadsheet=SHEET_US, ttl=0)
    st.sidebar.success("✅ 台美股雙帳本同步成功！")
except Exception as e:
    st.sidebar.error("❌ 帳本連結失敗 (請確認權限或略過此錯誤)")
    df_tw_raw = pd.DataFrame()
    df_us_raw = pd.DataFrame()

if st.button("🚀 啟動戰略掃描", use_container_width=True):
    st.session_state.analyzed = True

if st.session_state.analyzed:
    # 🛡️ 預先宣告所有關鍵變數
    cur_val_tw = 0.0
    actual_shares_tw = 0
    actual_cost_tw = 0.0
    p_tw_curr = 0.0
    p_tw_yest = 0.0
    min_date_tw = pd.to_datetime('2024-01-01')
    total_us_val_usd = 0.0
    total_us_cost_usd = 0.0
    total_us_val_twd = 0.0
    FC = 0.0

    TICKER_TW = "00631L"  # Fugle 用不帶 .TW 的代號
    TICKER_TW_YF = "00631L.TW"  # yfinance 備援用
    split_cutoff = pd.to_datetime('2026-03-23')

    # ==========================================
    # 1. 台股報價 - Fugle 優先 + 自動除權還原
    # ==========================================
    raw_curr, raw_yest, price_source, price_time, price_age = get_tw_price(TICKER_TW)

    p_tw_curr = round(raw_curr / (22.0 if raw_curr > 100 else 1.0), 2)
    p_tw_yest = round(raw_yest / (22.0 if raw_yest > 100 else 1.0), 2)

    # 顯示報價來源與新鮮度
    if price_age < 60:
        st.caption(f"{price_source} 報價正常｜最後更新：{price_time}（{price_age:.0f} 分鐘前）")
    elif price_age < 480:
        st.caption(f"{price_source} 報價略舊｜最後更新：{price_time}（{price_age/60:.1f} 小時前）")
    elif price_age < 9999:
        st.caption(f"{price_source} 報價可能異常｜最後更新：{price_time}（{price_age/60:.1f} 小時前）")
    else:
        st.caption(f"{price_source}｜使用歷史收盤價，非即時")

    # 台股帳本計算
    temp_tw = df_tw_raw.copy()
    if not temp_tw.empty and '交易類型' in temp_tw.columns:
        temp_tw['成交日期'] = pd.to_datetime(temp_tw['成交日期'])
        temp_tw.loc[temp_tw['交易類型'].str.contains('賣出', na=False), ['庫存股數', '持有成本']] *= -1
        actual_shares_tw = temp_tw['庫存股數'].sum()
        actual_cost_tw = temp_tw['持有成本'].sum()
        min_date_tw = temp_tw['成交日期'].min()

    cur_val_tw = actual_shares_tw * p_tw_curr

    # ==========================================
    # 2. 美股報價（yfinance，含 MultiIndex 修正）
    # ==========================================
    us_tickers = ["SOXL", "TMF", "BITX"]
    us_live = {}

    for t in us_tickers:
        t_data = df_us_raw[df_us_raw['股票代號'] == t].copy() if not df_us_raw.empty and '股票代號' in df_us_raw.columns else pd.DataFrame()
        if not t_data.empty and '交易類型' in t_data.columns:
            t_data['成交日期'] = pd.to_datetime(t_data['成交日期'])
            t_data.loc[t_data['交易類型'].str.contains('賣出', na=False), ['庫存股數', '持有成本']] *= -1
            shares = t_data['庫存股數'].sum()
            cost = t_data['持有成本'].sum()
            first_d = t_data['成交日期'].min()
        else:
            shares, cost, first_d = 0, 0, pd.NaT

        curr_p, yest_p = get_us_price(t)

        us_live[t] = {'shares': shares, 'cost': cost, 'curr': curr_p, 'yest': yest_p, 'first_date': first_d}
        total_us_val_usd += shares * curr_p
        total_us_cost_usd += cost

    # ==========================================
    # ⚖️ 淨資產 (FC) 與曝險計算
    # ==========================================
    FC_TW = cur_val_tw + cash - (loan1 + loan2)
    exp_tw = cur_val_tw * 2
    pct_tw = (exp_tw / FC_TW * 100) if FC_TW > 0 else 0

    FC_US_USD = total_us_val_usd + us_cash_usd
    exp_us_usd = (
        us_live.get('SOXL', {}).get('curr', 0) * us_live.get('SOXL', {}).get('shares', 0) * 3 +
        us_live.get('BITX', {}).get('curr', 0) * us_live.get('BITX', {}).get('shares', 0) * 2
    )
    pct_us = (exp_us_usd / FC_US_USD * 100) if FC_US_USD > 0 else 0

    total_us_val_twd = FC_US_USD * usd_twd
    FC_TOTAL = FC_TW + total_us_val_twd
    exp_us_twd = exp_us_usd * usd_twd
    exp_total = exp_tw + exp_us_twd
    pct_total = (exp_total / FC_TOTAL * 100) if FC_TOTAL > 0 else 0

    tab1, tab2, tab3 = st.tabs(["💰 台股 (雙引擎戰略)", "💵 美股 (網格戰略)", "🛬 生命周期 & 退休"])

    # ------------------------------------------
    # 📈 Tab 1: 台股
    # ------------------------------------------
    with tab1:
        roi_tw = (cur_val_tw / actual_cost_tw - 1) if actual_cost_tw > 0 else 0
        days_tw = max((datetime.today() - min_date_tw).days, 1) if pd.notnull(min_date_tw) else 1
        ann_roi_tw = ((1 + roi_tw) ** (365 / days_tw) - 1) * 100

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("總市值", f"NT$ {cur_val_tw:,.0f}")
        c2.metric("總投入成本", f"NT$ {actual_cost_tw:,.0f}")
        c3.metric("未實現總損益", f"{cur_val_tw - actual_cost_tw:+,.0f}", f"{roi_tw * 100:+.2f}%")
        tw_daily_pct = (p_tw_curr / p_tw_yest - 1) * 100 if p_tw_yest > 0 else 0
        c4.metric("今日損益", f"NT$ {(p_tw_curr - p_tw_yest) * actual_shares_tw:+,.0f}", f"{tw_daily_pct:+.2f}%")
        c5.metric("獨立實際曝險度", f"{pct_tw:.1f}%", "僅視台幣資產負債")

        c6, c7, c8, c9, c10 = st.columns(5)
        c6.metric("庫存總張數", f"{actual_shares_tw / 1000.0:,.1f} 張")
        c7.metric("持有均價", f"{actual_cost_tw / actual_shares_tw:.2f}" if actual_shares_tw > 0 else "0")
        c8.metric("昨日還原收盤", f"{p_tw_yest:.2f}")
        c9.metric("目前現價", f"{p_tw_curr:.2f}")
        c10.metric("年化報酬率", f"{ann_roi_tw:+.2f}%")

        st.write("---")

        # ========================================================
        # 🔥 雙引擎戰略
        # ========================================================
        st.subheader("🚨 雙引擎作略：動態定額 ＋ 階梯狙擊")
        roi_pct = roi_tw * 100

        if roi_pct >= 0:
            adj_pct = min(roi_pct * 1.0, 20.0)
            dynamic_m = max(base_m * (1 - adj_pct / 100.0), base_m * 0.8)
            adj_str = f"降 {adj_pct:.1f}% (獲利調節)"
        else:
            adj_pct = min(abs(roi_pct) * 2.0, 100.0)
            dynamic_m = min(base_m * (1 + adj_pct / 100.0), base_m * 2.0)
            adj_str = f"升 {adj_pct:.1f}% (虧損加碼)"

        today_d = datetime.today().date()
        c_cal = calendar.monthcalendar(today_d.year, today_d.month)
        first_wed = c_cal[0][2] if c_cal[0][2] != 0 else c_cal[1][2]
        dca_date = datetime(today_d.year, today_d.month, first_wed).date()
        if today_d > dca_date:
            next_m = today_d.month + 1 if today_d.month < 12 else 1
            next_y = today_d.year if today_d.month < 12 else today_d.year + 1
            c_cal_next = calendar.monthcalendar(next_y, next_m)
            first_wed_next = c_cal_next[0][2] if c_cal_next[0][2] != 0 else c_cal_next[1][2]
            dca_date = datetime(next_y, next_m, first_wed_next).date()

        is_dca_day = (today_d == dca_date)

        sniper_mult = 0.0
        sniper_label = "保留現金"

        if tw_daily_pct <= -15.0:
            sniper_mult, sniper_label = 4.0, "🔴 重壓 (4.0x)"
        elif tw_daily_pct <= -10.0:
            sniper_mult, sniper_label = 3.0, "🔴 恐慌買 (3.0x)"
        elif tw_daily_pct <= -8.0:
            sniper_mult, sniper_label = 2.0, "🟠 恐慌買 (2.0x)"
        elif tw_daily_pct <= -6.0:
            sniper_mult, sniper_label = 1.5, "🟠 中型修正 (1.5x)"
        elif tw_daily_pct <= -5.0:
            sniper_mult, sniper_label = 1.0, "🟡 標準買點 (1.0x)"
        elif tw_daily_pct <= -4.0:
            sniper_mult, sniper_label = 0.5, "🟡 波段低接 (0.5x)"
        elif tw_daily_pct <= -3.0:
            sniper_mult, sniper_label = 0.25, "🟢 日常試單 (0.25x)"

        sniper_m = dynamic_m * sniper_mult

        final_action_amt = 0
        action_reason = "觀望不動"

        if is_dca_day and sniper_m > 0:
            final_action_amt = max(dynamic_m, sniper_m)
            action_reason = "🔥 定額與狙擊撞日 (擇高投入)"
        elif is_dca_day:
            final_action_amt = dynamic_m
            action_reason = "📅 執行每月動態定額"
        elif sniper_m > 0:
            final_action_amt = sniper_m
            action_reason = f"🎯 執行階梯狙擊 ({sniper_label})"

        st.info("💡 **資金鐵則：** 帳戶請隨時鎖定 6 倍現金流，作為戰略預備金。")
        col_eng1, col_eng2, col_eng3 = st.columns(3)

        with col_eng1:
            st.markdown("#### 📅 引擎一：動態定額")
            st.write(f"**下次回款日：** {dca_date.strftime('%Y-%m-%d')} {'(🟢 今日!)' if is_dca_day else ''}")
            st.write(f"**庫存總損益：** {roi_pct:+.2f}%")
            st.write(f"**調整幅度：** {adj_str}")
            st.metric("當月動態基準", f"NT$ {dynamic_m:,.0f}")

        with col_eng2:
            st.markdown("#### 🎯 引擎二：階梯狙擊")
            st.write(f"**今日漲跌幅：** {tw_daily_pct:+.2f}%")
            st.write(f"**觸發位階：** {sniper_label}")
            st.write("**加碼公式：** 動態基準 × 倍數")
            st.metric("今日狙擊金額", f"NT$ {sniper_m:,.0f}")

        with col_eng3:
            st.markdown("#### 🚀 今日最終行動指示")
            if final_action_amt > 0:
                st.success(f"**{action_reason}**")
                st.metric("建議投入本金", f"NT$ {final_action_amt:,.0f}")
                st.metric("換算購買股數", f"約 {(final_action_amt / p_tw_curr):,.0f} 股" if p_tw_curr > 0 else "0 股")
            else:
                st.warning("☕ 目前未達狙擊標準且非扣款日，請保留現金觀望。")

        st.write("---")

        col_p, col_d = st.columns([2, 1])
        with col_p:
            st.write("📈 **台幣資產配置比例 (含負債對照)**")
            fig_p = go.Figure(data=[go.Pie(
                labels=['00631L 市值', '可用現金', '信貸總餘額 (負債)'],
                values=[cur_val_tw, cash, loan1 + loan2],
                hole=.4,
                texttemplate='%{label}<br>NT$ %{value:,.0f}<br>%{percent}',
                marker_colors=['#E71D36', '#2EC4B6', '#5C5C5C']
            )])
            fig_p.update_layout(height=350, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig_p, use_container_width=True)
        with col_d:
            st.info(f"💡 **台股獨立淨資產 (FC_TW)：**\n\nNT$ {FC_TW / 10000:,.1f} 萬\n\n*(公式：台股市值 + 台幣現金 - 總信貸)*")

        with st.expander(f"📜 逐筆投資戰績表 (目前現價: {p_tw_curr:.2f})", expanded=False):
            if not df_tw_raw.empty and '交易類型' in df_tw_raw.columns:
                buy_tw = df_tw_raw[df_tw_raw['交易類型'].str.contains('買入', na=False)].copy()
                buy_tw['成交日期'] = pd.to_datetime(buy_tw['成交日期'])
                recs_tw = []
                for _, r in buy_tw.sort_values('成交日期', ascending=False).iterrows():
                    adj_p = r['成交價格'] / 22 if r['成交日期'] < split_cutoff and r['成交價格'] > 100 else r['成交價格']
                    adj_s = r['庫存股數'] * 22 if r['成交日期'] < split_cutoff and r['成交價格'] > 100 else r['庫存股數']
                    l_pnl = adj_s * p_tw_curr - r['持有成本']
                    l_roi = l_pnl / r['持有成本'] if r['持有成本'] > 0 else 0
                    l_ann = ((1 + l_roi) ** (365 / max((datetime.today() - r['成交日期']).days, 1)) - 1) * 100
                    recs_tw.append({
                        '日期': r['成交日期'].strftime('%Y-%m-%d'),
                        '買價': f"{adj_p:.2f}",
                        '股數': f"{adj_s:,.0f}",
                        '目前現價': f"{p_tw_curr:.2f}",
                        '今日損益': f"{(p_tw_curr - p_tw_yest) * adj_s:+,.0f}",
                        '總損益': f"{l_pnl:+,.0f}",
                        '年化報酬': f"{l_ann:+.1f}%",
                        '總報酬': f"{l_roi * 100:+.1f}%"
                    })
                st.dataframe(pd.DataFrame(recs_tw), use_container_width=True, hide_index=True)

        st.subheader("🌐 戰術圖表分析")
        try:
            hist_tw_data = yf.download(TICKER_TW_YF, period="max", progress=False)
            # 相容新版 MultiIndex
            if isinstance(hist_tw_data.columns, pd.MultiIndex):
                hist_tw_data = hist_tw_data["Close"][TICKER_TW_YF]
            else:
                hist_tw_data = hist_tw_data["Close"]

            adj_h = hist_tw_data.copy()
            adj_h.loc[adj_h.index < split_cutoff] /= 22.0

            start_date = min_date_tw if pd.notnull(min_date_tw) else pd.to_datetime('2024-01-01')
            rp = adj_h[adj_h.index >= start_date]

            if not rp.dropna().empty:
                avg_cost = actual_cost_tw / actual_shares_tw if actual_shares_tw > 0 else 0

                # 圖 A
                st.write("📈 **A. 價格走勢與還原均價**")
                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(x=rp.index, y=rp.values, name="還原價", line=dict(color='#E71D36')))
                mx, mi, lt = rp.max(), rp.min(), rp.dropna().iloc[-1]
                if avg_cost > 0:
                    fig1.add_hline(y=avg_cost, line_dash="dash", line_color="#00A86B", annotation_text=f"🟢 均價線: {avg_cost:.2f}")
                    fig1.add_hrect(y0=avg_cost, y1=max(mx * 1.1, avg_cost * 1.1), fillcolor="green", opacity=0.1, layer="below", line_width=0)
                    fig1.add_hrect(y0=min(mi * 0.9, avg_cost * 0.9), y1=avg_cost, fillcolor="red", opacity=0.1, layer="below", line_width=0)
                fig1.add_annotation(x=rp.idxmax(), y=mx, text=f"高:{mx:.2f}", showarrow=True, ay=-30)
                fig1.add_annotation(x=rp.idxmin(), y=mi, text=f"低:{mi:.2f}", showarrow=True, ay=30)
                fig1.add_annotation(x=rp.index[-1], y=lt, text=f"最新:{lt:.2f}", showarrow=True, ax=40)
                fig1.update_yaxes(range=[
                    min(mi * 0.9, avg_cost * 0.9) if avg_cost > 0 else mi * 0.9,
                    max(mx * 1.1, avg_cost * 1.1) if avg_cost > 0 else mx * 1.1
                ])
                st.plotly_chart(fig1, use_container_width=True)

                # 圖 B
                st.write("📊 **B. 多空戰術乖離率**")
                bias = (rp - rp.rolling(20).mean()) / rp.rolling(20).mean() * 100
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=bias.index, y=bias.values, name="乖離%", line=dict(color='#F4A261')))
                for v, c, t in [(-5, "gray", "標準 (-5)"), (-10, "orange", "恐慌 (-10)"), (-15, "red", "重壓 (-15)")]:
                    fig2.add_hline(y=v, line_dash="dot", line_color=c, annotation_text=t)
                bc = bias.dropna()
                if not bc.empty:
                    bx, bi, bl = bc.max(), bc.min(), bc.iloc[-1]
                    fig2.add_hrect(y0=0, y1=max(bx * 1.2, 10), fillcolor="green", opacity=0.1, layer="below", line_width=0)
                    fig2.add_hrect(y0=min(bi * 1.2, -20), y1=0, fillcolor="red", opacity=0.1, layer="below", line_width=0)
                    fig2.add_annotation(x=bc.idxmax(), y=bx, text=f"最高:{bx:.1f}%", showarrow=True, ay=-30)
                    fig2.add_annotation(x=bc.idxmin(), y=bi, text=f"最低:{bi:.1f}%", showarrow=True, ay=30)
                    fig2.add_annotation(x=bc.index[-1], y=bl, text=f"最新:{bl:.1f}%", showarrow=True, ax=40)
                    fig2.update_yaxes(range=[min(bi * 1.2, -20), max(bx * 1.2, 15)])
                    st.plotly_chart(fig2, use_container_width=True)

                # 圖 C
                st.write("💰 **C. 庫存真實損益軌跡**")
                if not temp_tw.empty and '交易類型' in temp_tw.columns:
                    th = temp_tw.groupby('成交日期')[['庫存股數', '持有成本']].sum().reset_index().set_index('成交日期')
                    dh = th.reindex(rp.index).fillna(0)
                    ds = dh['庫存股數'].cumsum()
                    dc = dh['持有成本'].cumsum()
                    dp = np.where(dc > 0, (ds * rp - dc) / dc * 100, 0)
                    dp_s = pd.Series(dp, index=rp.index)
                    fig3 = go.Figure()
                    fig3.add_trace(go.Scatter(x=dp_s.index, y=dp_s.values, line=dict(color='#247BA0')))
                    dc_cl = dp_s.dropna()
                    if not dc_cl.empty:
                        px, pi, pl = dc_cl.max(), dc_cl.min(), dc_cl.iloc[-1]
                        fig3.add_hrect(y0=0, y1=max(px * 1.2, 10), fillcolor="green", opacity=0.1, layer="below", line_width=0)
                        fig3.add_hrect(y0=min(pi * 1.2, -10), y1=0, fillcolor="red", opacity=0.1, layer="below", line_width=0)
                        fig3.add_annotation(x=dc_cl.idxmax(), y=px, text=f"最高:{px:.1f}%", showarrow=True, ay=-30)
                        fig3.add_annotation(x=dc_cl.idxmin(), y=pi, text=f"最低:{pi:.1f}%", showarrow=True, ay=30)
                        fig3.add_annotation(x=dc_cl.index[-1], y=pl, text=f"最新:{pl:.1f}%", showarrow=True, ax=40)
                        fig3.update_yaxes(range=[min(pi * 1.2, -15), max(px * 1.2, 20)])
                        st.plotly_chart(fig3, use_container_width=True)
        except Exception as e:
            st.error(f"圖表載入中，等待下次網路重試。({e})")

        st.divider()
        st.link_button("🛒 新增台股交易紀錄 (直接開啟 Google Sheets 手動填寫)", SHEET_TW, use_container_width=True)

    # ------------------------------------------
    # 💵 Tab 2: 美股
    # ------------------------------------------
    with tab2:
        st.subheader("💵 美股持倉總覽")
        us_cols = st.columns(len(us_tickers))
        for i, t in enumerate(us_tickers):
            d = us_live[t]
            val = d['shares'] * d['curr']
            pnl = val - d['cost']
            roi = pnl / d['cost'] * 100 if d['cost'] > 0 else 0
            daily_pct = (d['curr'] / d['yest'] - 1) * 100 if d['yest'] > 0 else 0
            with us_cols[i]:
                st.metric(f"{t}", f"${d['curr']:.2f}", f"{daily_pct:+.2f}%")
                st.write(f"持股：{d['shares']:.0f} 股")
                st.write(f"市值：${val:,.0f}")
                st.write(f"損益：{pnl:+,.0f} ({roi:+.1f}%)")

        st.divider()
        c_us1, c_us2, c_us3 = st.columns(3)
        c_us1.metric("美股總市值 (USD)", f"${total_us_val_usd:,.0f}")
        c_us2.metric("美股淨資產 FC_US (USD)", f"${FC_US_USD:,.0f}")
        c_us3.metric("美股曝險度", f"{pct_us:.1f}%")
        st.link_button("🛒 新增美股交易紀錄", SHEET_US, use_container_width=True)

    # ------------------------------------------
    # 🛬 Tab 3: 生命周期
    # ------------------------------------------
    with tab3:
        st.subheader("🛬 生命周期 & 退休規劃")
        years_to_retirement = hc_years
        future_monthly_need = target_monthly_now * ((1 + inflation_rate) ** years_to_retirement)
        required_nest_egg = future_monthly_need * 12 / withdrawal_rate

        c_r1, c_r2, c_r3 = st.columns(3)
        c_r1.metric("退休後月需 (未來值)", f"NT$ {future_monthly_need:,.0f}")
        c_r2.metric("所需退休金規模", f"NT$ {required_nest_egg/10000:,.0f} 萬")
        c_r3.metric("目前總淨資產 (FC)", f"NT$ {FC_TOTAL/10000:,.0f} 萬")

        st.write(f"**距離目標缺口：** NT$ {max(0, required_nest_egg - FC_TOTAL)/10000:,.0f} 萬")
        st.write(f"**目前整體曝險度：** {pct_total:.1f}%（目標 {target_exp_pct}%）")
