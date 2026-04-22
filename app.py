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
# 賴賴投資戰情室 V10.1 - 單頁整合極速版
# ==========================================

st.set_page_config(page_title="賴賴終極戰情室", page_icon="💰", layout="wide")
st.title("🛡️ 賴賴投資戰情室 V10.1")

if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

# ==========================================
# 🔑 Fugle API Key 設定
# ==========================================
FUGLE_API_KEY = st.secrets.get("FUGLE_API_KEY", "")

# ==========================================
# 📡 Fugle 即時報價函式 (含 yfinance 備援)
# ==========================================
@st.cache_data(ttl=60)  
def get_tw_price(ticker_symbol: str):
    tw_tz = pytz.timezone("Asia/Taipei")
    
    try:
        from fugle_marketdata import RestClient
        client = RestClient(api_key=FUGLE_API_KEY)
        quote = client.stock.intraday.quote(symbol=ticker_symbol)
        
        curr_price = quote.get("closePrice") or quote.get("lastPrice") or quote.get("referencePrice", 0)
        prev_close = quote.get("referencePrice", curr_price)
        
        update_time_raw = quote.get("lastUpdated") or quote.get("lastTrade", {}).get("time")
        if update_time_raw:
            try:
                # 🚀 修正時間戳判定（解決 1970 年 Bug 與 8 小時時區差）
                if isinstance(update_time_raw, (int, float)):
                    # 加入 utc=True，讓系統知道這是 UTC 時間
                    if update_time_raw > 1e14:
                        dt_obj = pd.to_datetime(update_time_raw, unit='us', utc=True)
                    elif update_time_raw > 1e11:
                        dt_obj = pd.to_datetime(update_time_raw, unit='ms', utc=True)
                    else:
                        dt_obj = pd.to_datetime(update_time_raw, unit='s', utc=True)
                    
                    # 確實將 UTC 時間轉換為台灣時間 (+8)
                    update_dt = dt_obj.astimezone(tw_tz)
                else:
                    # 如果是字串格式
                    dt_obj = pd.to_datetime(update_time_raw)
                    update_dt = dt_obj.tz_localize("Asia/Taipei") if dt_obj.tzinfo is None else dt_obj.astimezone(tw_tz)

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
        pass  
    except Exception as fugle_err:
        st.sidebar.warning(f"⚠️ Fugle API 失敗：{fugle_err}，改用 yfinance")
    
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
    
    try:
        yf_ticker = ticker_symbol + ".TW" if not ticker_symbol.endswith(".TW") else ticker_symbol
        hist = yf.download(yf_ticker, period="5d", progress=False)
        
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
st.sidebar.header("🏦 資金與貸款設定")
# (已移除介面手動輸入：基準每月定期定額、帳戶可用現金、目標曝險度，改為由下方 Google Sheets 自動讀取)

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
usd_twd = st.sidebar.number_input("4. 目前美元匯率", value=32.0)
hc_years = st.sidebar.number_input("5. 預計剩餘投入年限", value=11)
target_k = st.sidebar.number_input("6. 一生目標曝險度 (%)", value=83)
target_monthly_now = st.sidebar.number_input("7. 目標月領金額 (現值)", value=100000, step=10000)
inflation_rate = st.sidebar.number_input("8. 預估通膨 (%)", value=2.0) / 100.0
withdrawal_rate = st.sidebar.number_input("9. 安全提領率 (%)", value=4.0) / 100.0

# --- 🚀 雙帳本雲端同步 (合併讀取，大幅加速) ---
SHEET_TW = "https://docs.google.com/spreadsheets/d/1yYs-JIW4-8jr8EoyyWlydNrE5Gtd_frWdlMQVdn1VYk/edit?usp=sharing"
SHEET_US = "https://docs.google.com/spreadsheets/d/1-NPhyuRNWSarFPdgHjUkB9J3smSbn3u3fjUbMhMVyfI/edit?usp=sharing"

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.sidebar.error(f"連線初始化失敗: {e}")

# 1. 讀取台股 (並同步抓取 J2, K2 參數)
base_m_wan = 10.0  # 預設值防呆
cash_wan = 200.0   # 預設值防呆

try:
    df_tw_raw = conn.read(spreadsheet=SHEET_TW, ttl=0)
    st.sidebar.success("✅ 台股帳本同步成功！")
    
    # 🚀 修正版：直接從已經下載的 df_tw_raw 提取 J2 (第10欄) 與 K2 (第11欄)
    if not df_tw_raw.empty:
        try:
            # 確保欄位寬度足夠，避免抓不到 K 欄報錯
            while len(df_tw_raw.columns) < 11:
                df_tw_raw[f"Unnamed_{len(df_tw_raw.columns)}"] = np.nan
                
            # iloc[0, 9] 代表第一筆資料的 J 欄、iloc[0, 10] 代表 K 欄
            v_j = str(df_tw_raw.iloc[0, 9]).replace(',', '').replace('$', '').strip()
            v_k = str(df_tw_raw.iloc[0, 10]).replace(',', '').replace('$', '').strip()
            
            parsed_j = float(pd.to_numeric(v_j, errors='coerce'))
            parsed_k = float(pd.to_numeric(v_k, errors='coerce'))
            
            if not np.isnan(parsed_j): base_m_wan = parsed_j
            if not np.isnan(parsed_k): cash_wan = parsed_k
            
        except Exception as parse_e:
            st.sidebar.warning(f"⚠️ 參數欄位解析失敗，改用預設值。({parse_e})")
        
    st.sidebar.info(f"🏦 自動載入台股參數：\n基準定額 **{base_m_wan:,.0f} 萬** | 現金 **{cash_wan:,.0f} 萬**")

except Exception as e:
    st.sidebar.error(f"❌ 台股帳本讀取失敗: {e}")
    df_tw_raw = pd.DataFrame()

# 根據試算表取得的參數計算實際金額
base_m = base_m_wan * 10000
cash = cash_wan * 10000


# 2. 讀取美股 (包含自動抓取 I7 可用現金)
us_cash_usd = 0.0 # 預先宣告全域變數
try:
    df_us_raw_no_header = conn.read(spreadsheet=SHEET_US, ttl=0, header=None)
    
    df_us_raw = df_us_raw_no_header.copy()
    if not df_us_raw.empty:
        df_us_raw.columns = df_us_raw.iloc[0]
        df_us_raw = df_us_raw[1:].reset_index(drop=True)
    
    st.sidebar.success("✅ 美股資料庫同步成功！(含交易與SOXL網格)")
    
    try:
        if len(df_us_raw_no_header) >= 7 and len(df_us_raw_no_header.columns) >= 9:
            val = str(df_us_raw_no_header.iloc[6, 8]).replace(',', '').replace('$', '').strip()
            us_cash_usd = float(pd.to_numeric(val, errors='coerce'))
            if np.isnan(us_cash_usd):
                us_cash_usd = 0.0
        else:
            us_cash_usd = 0.0
        st.sidebar.info(f"💵 自動讀取美股可用現金 (I7): ${us_cash_usd:,.2f}")
    except Exception as e:
        st.sidebar.warning(f"⚠️ 無法解析 I7 現金欄位: {e}")
        us_cash_usd = 0.0
        
except Exception as e:
    st.sidebar.error(f"❌ 美股讀取失敗: {e}")
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

    TICKER_TW = "00631L"  
    TICKER_TW_YF = "00631L.TW"  
    split_cutoff = pd.to_datetime('2026-03-23')

    # ==========================================
    # 1. 台股報價 
    # ==========================================
    raw_curr, raw_yest, price_source, price_time, price_age = get_tw_price(TICKER_TW)

    p_tw_curr = round(raw_curr / (22.0 if raw_curr > 100 else 1.0), 2)
    p_tw_yest = round(raw_yest / (22.0 if raw_yest > 100 else 1.0), 2)

    if price_age < 60:
        st.caption(f"{price_source} 報價正常｜最後更新：{price_time}（{price_age:.0f} 分鐘前）")
    elif price_age < 480:
        st.caption(f"{price_source} 報價略舊｜最後更新：{price_time}（{price_age/60:.1f} 小時前）")
    elif price_age < 9999:
        st.caption(f"{price_source} 報價可能異常｜最後更新：{price_time}（{price_age/60:.1f} 小時前）")
    else:
        st.caption(f"{price_source}｜使用歷史收盤價，非即時（最後資料時間：{price_time}）")

    temp_tw = df_tw_raw.copy()
    if not temp_tw.empty and '交易類型' in temp_tw.columns:
        temp_tw['成交日期'] = pd.to_datetime(temp_tw['成交日期'])
        # 防呆轉數值
        temp_tw['庫存股數'] = pd.to_numeric(temp_tw['庫存股數'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        temp_tw['持有成本'] = pd.to_numeric(temp_tw['持有成本'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        temp_tw.loc[temp_tw['交易類型'].str.contains('賣出', na=False), ['庫存股數', '持有成本']] *= -1
        actual_shares_tw = temp_tw['庫存股數'].sum()
        actual_cost_tw = temp_tw['持有成本'].sum()
        min_date_tw = temp_tw['成交日期'].min()

    cur_val_tw = actual_shares_tw * p_tw_curr

    # ==========================================
    # 2. 美股報價與交易紀錄
    # ==========================================
    us_tickers = ["SOXL", "TMF", "BITX"]
    us_live = {}

    for t in us_tickers:
        t_data = df_us_raw[df_us_raw['股票代號'] == t].copy() if not df_us_raw.empty and '股票代號' in df_us_raw.columns else pd.DataFrame()
        if not t_data.empty and '交易類型' in t_data.columns:
            t_data['成交日期'] = pd.to_datetime(t_data['成交日期'])
            
            # 🌟 修復錯誤核心：強制將股數與成本從字串轉為浮點數，過濾掉任何逗號
            t_data['庫存股數'] = pd.to_numeric(t_data['庫存股數'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            t_data['持有成本'] = pd.to_numeric(t_data['持有成本'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            
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
    # ⚖️ 淨資產與曝險計算
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

    tab1, tab2, tab3 = st.tabs(["💰 台股 ", "💵 美股 ", "🛬 生命周期 & 退休 "])

    # ------------------------------------------
    # 📈 Tab 1: 台股
    # ------------------------------------------
    with tab1:
        roi_tw = (cur_val_tw / actual_cost_tw - 1) if actual_cost_tw > 0 else 0
        days_tw = max((datetime.today() - min_date_tw).days, 1) if pd.notnull(min_date_tw) else 1
        ann_roi_tw = ((1 + roi_tw) ** (365 / days_tw) - 1) * 100

        c1, c2, c3, c4, c5 = st.columns(5)
        # 除以 10000 並加上「萬」，保留兩位小數
        c1.metric("市值", f"{cur_val_tw / 10000:,.0f} 萬")
        c2.metric("成本", f"{actual_cost_tw / 10000:,.0f} 萬")
        c3.metric("未實現損益", f"{(cur_val_tw - actual_cost_tw) / 10000:+,.0f} 萬", f"{roi_tw * 100:+.0f}%")
        
        tw_daily_pct = (p_tw_curr / p_tw_yest - 1) * 100 if p_tw_yest > 0 else 0
        c4.metric("今日損益", f"{(p_tw_curr - p_tw_yest) * actual_shares_tw:+,.0f}", f"{tw_daily_pct:+.2f}%")
        c5.metric("曝險度", f"{pct_tw:.1f}%")

        c6, c7, c8, c9, c10 = st.columns(5)
        c6.metric("庫存張數", f"{actual_shares_tw / 1000.0:,.0f} 張")
        c7.metric("均價", f"{actual_cost_tw / actual_shares_tw:.2f}" if actual_shares_tw > 0 else "0")
        c8.metric("昨日收盤", f"{p_tw_yest:.2f}")
        c9.metric("目前現價", f"{p_tw_curr:.2f}")
        c10.metric("年化報酬率", f"{ann_roi_tw:+.2f}%")

        st.write("---")

        st.subheader("🚨 雙引擎戰略")
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
            st.write("📊 **台幣資產與淨值變動 (瀑布圖)**")
            
            # 這裡將負債轉為負值，以便在瀑布圖中向下扣除
            total_loan = -(loan1 + loan2)
            
            # 先計算出最終淨額，交給 y 陣列讓標籤去讀取
            net_total = cur_val_tw + cash + total_loan
            
            fig_w = go.Figure(go.Waterfall(
                name = "淨值分析",
                orientation = "v",
                x = ["00631L 市值", "可用現金", "信貸總餘額", "台股獨立淨資產"],
                measure = ["relative", "relative", "relative", "total"],
                # 將最後一個值換成 net_total，解決顯示為 0 的問題
                y = [cur_val_tw, cash, total_loan, net_total],
                
                # 設定數字顯示在柱子內部
                textposition = "inside",
                texttemplate = "NT$ %{y:,.0f}",
                # 將字體改為白色並放大，在有顏色的柱狀圖內更易讀
                textfont = dict(color="black", size=14),
                
                # 調整顏色，讓「總淨值」的顏色與「資產」明顯分開
                increasing = {"marker":{"color":"#2EC4B6"}}, # 湖水綠 (資產增加)
                decreasing = {"marker":{"color":"#E71D36"}}, # 警示紅 (負債減少)
                totals = {"marker":{"color":"#FF9F1C"}},     # 亮橘黃 (總計淨額)
                connector = {"line":{"color":"#5C5C5C", "width":1, "dash":"dot"}}
            ))

            fig_w.update_layout(
                height=400,
                margin=dict(l=10, r=10, t=10, b=10),
                showlegend=False,
                yaxis=dict(title="金額 (NT$)")
            )
            
            st.plotly_chart(fig_w, use_container_width=True)

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
    # 💵 Tab 2: 美股 (純淨網格版)
    # ------------------------------------------
    with tab2:
        us_roi = (total_us_val_usd / total_us_cost_usd - 1) if total_us_cost_usd > 0 else 0
        valid_dates = [v['first_date'] for v in us_live.values() if pd.notnull(v['first_date'])]
        min_date_us = min(valid_dates) if valid_dates else pd.to_datetime('2024-01-01')
        ann_roi_us = ((1+us_roi)**(365/max((datetime.today()-min_date_us).days, 1)) - 1) * 100

        total_today_pnl_usd = sum([(info['curr'] - info['yest']) * info['shares'] for info in us_live.values()])
        total_yest_val_usd = sum([info['yest'] * info['shares'] for info in us_live.values()])
        today_pct_us = (total_today_pnl_usd / total_yest_val_usd) if total_yest_val_usd > 0 else 0

        st.subheader("🎯 SOXL 網格進出戰略 ")
        soxl_c = us_live.get('SOXL', {}).get('curr', 0)

        st.markdown("""
        * **🅿️ 資金停泊：** 閒置資金請優先停泊於 **1、2、3 個月期美國國債**，等待大跌機會。
        """)

        cur_tranche_name = "第 0 份"
        avg_p = 0.0
        tot_s = 0
        tp_pct = 0.0
        tp_price = 0.0
        add_p = 0.0
        add_s = 0

        # 防呆機制：直接從第一頁的海量資料中找出 SOXL 規則的欄位
        if not df_us_raw.empty:
            soxl_df = df_us_raw.copy()
            
            # 動態尋找標題 (即使你貼在 Z 欄，只要標題對就抓得到)
            col_k = next((c for c in soxl_df.columns if '實際股數' in str(c)), None)
            col_l = next((c for c in soxl_df.columns if '實際成本價' in str(c)), None)
            col_m = next((c for c in soxl_df.columns if '實際停利股價' in str(c)), None)
            col_d = next((c for c in soxl_df.columns if '預估股價' in str(c)), None)
            col_e = next((c for c in soxl_df.columns if '預估股數' in str(c)), None)
            col_g = next((c for c in soxl_df.columns if '停利%' in str(c)), None)
            
            if col_k is None:
                st.info("⚠️ 尚未在第一頁讀取到 SOXL 規則！請確認你已經把『SOXL規則』的整張表貼到了第一頁的空白處，並且標題放在第一列 (Row 1)。")
            else:
                try:
                    # 1. 抓出實際股數，並清理為數字
                    k_series = soxl_df[col_k].astype(str).str.replace(r'[^\d.]', '', regex=True)
                    soxl_df['clean_K'] = pd.to_numeric(k_series, errors='coerce').fillna(0)
                    
                    # 2. 為了避免讀到合併表單底下的空白列，我們用「預估股價」來確保這是有效的一列
                    if col_d:
                        d_series = soxl_df[col_d].astype(str).str.replace(r'[^\d.]', '', regex=True)
                        soxl_df['clean_D'] = pd.to_numeric(d_series, errors='coerce').fillna(0)
                        valid_grid_df = soxl_df[soxl_df['clean_D'] > 0].reset_index(drop=True)
                    else:
                        valid_grid_df = soxl_df.reset_index(drop=True)
                    
                    # 3. 篩選出已經有投入實際股數的列
                    active_df = valid_grid_df[valid_grid_df['clean_K'] > 0]
                    
                    if not active_df.empty:
                        last_idx = active_df.index[-1]
                        last_row = valid_grid_df.iloc[last_idx]
                        
                        # 靠資料筆數自動推算第幾份
                        cur_tranche_name = f"第 {len(active_df)} 份"
                        tot_s = active_df['clean_K'].sum()
                        
                        if col_l:
                            l_val = str(last_row[col_l]).replace(',', '').replace('%', '')
                            avg_p = float(pd.to_numeric(l_val, errors='coerce'))
                            if np.isnan(avg_p): avg_p = 0.0
                            
                        if col_m:
                            m_val = str(last_row[col_m]).replace(',', '').replace('%', '')
                            tp_price = float(pd.to_numeric(m_val, errors='coerce'))
                            if np.isnan(tp_price): tp_price = 0.0
                            
                        if col_g:
                            g_val = str(last_row[col_g]).replace(',', '').replace('%', '')
                            tp_pct_raw = float(pd.to_numeric(g_val, errors='coerce'))
                            if np.isnan(tp_pct_raw): tp_pct_raw = 0.0
                            tp_pct = tp_pct_raw * 100 if tp_pct_raw < 10 else tp_pct_raw
                            
                        # 下一階加碼 (D、E欄)
                        next_idx = last_idx + 1
                        if next_idx < len(valid_grid_df):
                            next_row = valid_grid_df.iloc[next_idx]
                            if col_d:
                                add_p = float(pd.to_numeric(str(next_row[col_d]).replace(',', ''), errors='coerce'))
                                if np.isnan(add_p): add_p = 0.0
                            if col_e:
                                add_s = float(pd.to_numeric(str(next_row[col_e]).replace(',', ''), errors='coerce'))
                                if np.isnan(add_s): add_s = 0.0
                    else:
                        # 庫存為 0 時，抓第一列預估當加碼
                        if not valid_grid_df.empty:
                            first_row = valid_grid_df.iloc[0]
                            if col_d:
                                add_p = float(pd.to_numeric(str(first_row[col_d]).replace(',', ''), errors='coerce'))
                                if np.isnan(add_p): add_p = 0.0
                            if col_e:
                                add_s = float(pd.to_numeric(str(first_row[col_e]).replace(',', ''), errors='coerce'))
                                if np.isnan(add_s): add_s = 0.0
                except Exception as parse_e:
                    st.error(f"⚠️ 資料解析異常: {parse_e}")

        tp_dist = (tp_price / soxl_c - 1) * 100 if soxl_c > 0 and tp_price > 0 else 0
        add_dist = (add_p / soxl_c - 1) * 100 if soxl_c > 0 and add_p > 0 else 0

        # ========== 🌟 新增的報酬與股價計算 ==========
        soxl_y = us_live.get('SOXL', {}).get('yest', 0)
        soxl_daily_pct = (soxl_c / soxl_y - 1) * 100 if soxl_y > 0 else 0
        cur_roi_pct = (soxl_c / avg_p - 1) * 100 if avg_p > 0 else 0
        est_profit = (tp_price - avg_p) * tot_s if avg_p > 0 and tot_s > 0 else 0

        # ========== 🌟 擴充為 5 個區塊 ==========
        c_g1, c_g2, c_g3, c_g4, c_g5 = st.columns(5)
        
        c_g1.metric("目前進度", f"{cur_tranche_name}")
        c_g2.metric("目前股價", f"${soxl_c:.2f}", f"今日報酬 {soxl_daily_pct:+.2f}%")
        c_g3.metric(f"平均股價 ({tot_s:,.0f} 股)", f"${avg_p:.2f}", f"報酬 {cur_roi_pct:+.2f}% ")
        c_g4.metric(f"目標停利 ({tp_pct:.0f}%, 預估 +${est_profit:,.0f})", f"${tp_price:.2f}", f"差距 {tp_dist:+.2f}%" if soxl_c > 0 and tp_price > 0 else "N/A")

        if add_p > 0:
            c_g5.metric(f"加碼股價 ({add_s:,.0f} 股)", f"${add_p:.2f}", f"差距 {add_dist:+.2f}%" if soxl_c > 0 else "N/A")
        else:
            c_g5.metric("加碼股價", "已滿倉", "無加碼空間")

        st.divider()

        u1, u2, u3, u4, u5 = st.columns(5)
        u1.metric("總市值 (USD)", f"${total_us_val_usd:,.0f}")
        u2.metric("總投入成本", f"${total_us_cost_usd:,.0f}")
        u3.metric("未實現總損益", f"{(total_us_val_usd-total_us_cost_usd):+,.0f}", f"{us_roi*100:+.2f}%")
        u4.metric("今日損益", f"${total_today_pnl_usd:+,.2f}", f"{today_pct_us*100:+.2f}%")
        u5.metric("曝險度", f"{pct_us:.1f}%")

        st.write("---")
        col_up, col_ud = st.columns([2, 1])
        with col_up:
            st.write("📈 **美金資產配置比例 (USD)**")
            us_labels = list(us_live.keys()) + ['美股可用現金']
            us_values = [info['curr']*info['shares'] for info in us_live.values()] + [us_cash_usd]
            fig_u = go.Figure(data=[go.Pie(labels=us_labels, values=us_values, hole=.4, texttemplate='%{label}<br>$%{value:,.0f}<br>%{percent}')])
            fig_u.update_layout(height=350, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig_u, use_container_width=True)
        with col_ud:
            st.info(f"💡 **美股獨立淨資產 (FC_US)：**\n\nUS$ {FC_US_USD:,.0f}\n\n*(公式：美股市值 + 美股現金)*")

        st.subheader("📦 個股明細")
        us_table = []
        for t, info in us_live.items():
            avg = info['cost']/info['shares'] if info['shares']>0 else 0
            l_roi = (info['curr']/avg - 1) if avg>0 else 0
            days = (datetime.today()-info['first_date']).days if pd.notnull(info['first_date']) else 1
            l_ann = ((1+l_roi)**(365/max(days,1))-1)*100

            today_pnl_abs = (info['curr'] - info['yest']) * info['shares']
            total_pnl_abs = (info['curr'] - avg) * info['shares']

            us_table.append({
                '代號': t, '股數': f"{info['shares']:,.0f}", '均價': f"${avg:.2f}", '成本': f"${info['cost']:,.0f}",
                '昨日收盤': f"${info['yest']:.2f}", '目前現價': f"${info['curr']:.2f}", 
                '今日損益': f"${today_pnl_abs:+,.2f} ({(info['curr']/info['yest']-1)*100:+.2f}%)" if info['yest']>0 else "$0 (0.00%)", 
                '總損益': f"${total_pnl_abs:+,.2f} ({l_roi*100:+.2f}%)", '年化報酬': f"{l_ann:+.2f}%"
            })
        st.dataframe(pd.DataFrame(us_table), use_container_width=True, hide_index=True)

        st.write("---")
        st.link_button("🛒 新增美股交易紀錄 (直接開啟 Google Sheets 手動填寫)", SHEET_US, use_container_width=True)

    # ------------------------------------------
    # 🛬 Tab 3: 生命周期 & 退休
    # ------------------------------------------
    with tab3:
        st.subheader("⚖️ 生命周期曝險透視")

        total_port_val = cur_val_tw + (total_us_val_usd * usd_twd)
        tw_port_pct = (cur_val_tw / total_port_val * 100) if total_port_val > 0 else 0
        us_port_pct = ((total_us_val_usd * usd_twd) / total_port_val * 100) if total_port_val > 0 else 0

        col_p1, col_p2 = st.columns(2)
        col_p1.metric("💰 台股投資組合佔比", f"{tw_port_pct:.1f}%")
        col_p2.metric("💵 美股投資組合佔比", f"{us_port_pct:.1f}%")

        st.markdown(f"""
| 戰區 | 曝險金額 (台幣) | 淨資產 (FC) | 獨立曝險度 |
| :--- | :--- | :--- | :--- |
| 💰 台股 | NT$ {exp_tw/10000:,.0f} 萬 | NT$ {FC_TW/10000:,.0f} 萬 | **{pct_tw:.1f}%** |
| 💵 美股 | NT$ {exp_us_twd/10000:,.0f} 萬<br/><span style="font-size: 0.85em; color: gray;"> {exp_us_usd:,.0f}</span> | NT$ {(FC_US_USD*usd_twd)/10000:,.0f} 萬<br/><span style="font-size: 0.85em; color: gray;"> {FC_US_USD:,.0f}</span> | **{pct_us:.1f}%** |
| 🔥 綜合 | **NT$ {exp_total/10000:,.0f} 萬** | **NT$ {FC_TOTAL/10000:,.0f} 萬** | **{pct_total:.1f}%** |
""", unsafe_allow_html=True)


        W = FC_TOTAL + (base_m * 12 * hc_years); target_val = W * (target_k/100)
        target_E = (target_val/FC_TOTAL*100) if FC_TOTAL > 0 else 0

        c_tgt, c_act = st.columns(2); c_tgt.metric("🎯 綜合目標曝險度", f"{target_E:.1f}%"); c_act.metric("🔥 綜合實際曝險度", f"{pct_total:.1f}%", f"差距: {(pct_total - target_E):+.1f}%")

        st.subheader("⚖️ 應該如何平衡？")
        diff_val = exp_total - target_val
        if diff_val > 0:
            st.error(f"🚨 **目前總曝險過高！** 建議減少市場部位總價值約 **NT$ {diff_val/10000:,.0f} 萬**")
            st.write(f"👉 **台股部分：** 若由台股調整，需減碼 00631L 約 NT$ {diff_val/2/10000:,.1f} 萬市值")
            st.write(f"👉 **美股部分：** 若由美股調整，需減碼 SOXL 約 NT$ {diff_val/3/10000:,.1f} 萬市值")
        else:
            st.success(f"🟢 **目前曝險尚有空間！** 可增加市場部位約 **NT$ {abs(diff_val)/10000:,.0f} 萬**")

        st.divider(); st.subheader("☕ 退休終局與提領反推")
        f_a = FC_TOTAL
        for _ in range(hc_years): f_a = f_a*1.08 + (base_m*12)
        m_a = (f_a*withdrawal_rate)/12; m_a_now = m_a/((1+inflation_rate)**hc_years)
        st.markdown(f"**📈 情境 A：若工作 {hc_years} 年後退休**")
        ca1, ca2, ca3 = st.columns(3); ca1.metric("屆時滾出資產", f"NT$ {f_a/10000:,.0f} 萬"); ca2.metric("未來每月可領", f"NT$ {m_a:,.0f}"); ca3.metric("約等同現在每月可領", f"NT$ {m_a_now:,.0f}")

        st.write(""); st.markdown(f"**🎯 情境 B：反推我想要月領 {target_monthly_now/10000:.0f} 萬(現值) 的退休金**")
        found_y = None; t_f = FC_TOTAL
        for y in range(1, 41):
            t_f = t_f*1.08 + (base_m*12)
            req_m = target_monthly_now*((1+inflation_rate)**y)
            if t_f >= (req_m*12)/withdrawal_rate: found_y = y; final_f = t_f; final_m = req_m; break
        if found_y:
            cb1, cb2, cb3 = st.columns(3); cb1.metric("需滾出資產", f"NT$ {final_f/10000:,.0f} 萬"); cb2.metric("未來每月可領", f"NT$ {final_m:,.0f}"); cb3.metric("剩餘年限", f"{found_y} 年")

        with st.expander("🛬 降落時程推演表 (Glide Path)", expanded=False):
            gp = []; curr_f = FC_TOTAL
            for y in range(hc_years+1):
                if y>0: curr_f = curr_f*1.08 + (base_m*12)
                h_r = max(0, (base_m*12*hc_years) - (base_m*12*y))
                e_g = ((curr_f + h_r)*target_k/100)/curr_f*100 if curr_f>0 else 0
                gp.append({"年": f"第 {y} 年", "預估資產(萬)": f"{curr_f/10000:,.0f}", "應有曝險": f"{e_g:.1f}%"})
            st.table(pd.DataFrame(gp))

st.caption("📱 提示：V10.1 單頁整合極速版，美股資料讀取只需一次 API 請求，防呆抗快取干擾。")
