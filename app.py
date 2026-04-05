import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# 1. 設定 App 頁面
st.set_page_config(page_title="00631L 實戰大腦", page_icon="🤖", layout="centered")
st.title("🤖 00631L 實戰大腦 V3")

# 初始化記憶體，讓圖表不會因為輸入數字而消失
if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

# 2. 側邊欄參數設定
st.sidebar.header("⚙️ 參數設定")
loan1 = st.sidebar.number_input("1. 信貸一剩餘本金", value=2056231)
loan2 = st.sidebar.number_input("2. 信貸二剩餘本金", value=935907)
base_m = st.sidebar.number_input("3. 基準每月定期定額", value=100000)
cash = st.sidebar.number_input("4. 目前帳戶可用現金", value=0)
target_exp_pct = st.sidebar.number_input("5. 設定目標曝險度 (%)", value=200)

# 3. 雲端資料庫連動 (Google Sheets)
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_trades_raw = conn.read(ttl=0) 
    
    temp_df = df_trades_raw.copy()
    temp_df['成交日期'] = pd.to_datetime(temp_df['成交日期'])
    
    temp_df.loc[temp_df['交易類型'].str.contains('賣出', na=False), '庫存股數'] = -temp_df['庫存股數'].abs()
    temp_df.loc[temp_df['交易類型'].str.contains('賣出', na=False), '持有成本'] = -temp_df['持有成本'].abs()
    
    actual_shares = temp_df['庫存股數'].sum()
    actual_cost = temp_df['持有成本'].sum()
    
    st.sidebar.success("✅ 雲端資料庫同步成功！")
except Exception as e:
    st.sidebar.error("❌ 雲端庫存讀取失敗，改為0股代入計算。")
    df_trades_raw = pd.DataFrame()
    actual_shares, actual_cost = 0, 0

# 4. 核心運算按鈕
if st.button("🚀 啟動最新盤中決策與分析", use_container_width=True):
    st.session_state.analyzed = True

# 如果已經按下過分析按鈕，就保持顯示以下內容
if st.session_state.analyzed:
    with st.spinner('📡 正在抓取即時行情並還原歷史股價...'):
        TICKER = "00631L.TW"
        data = yf.download(TICKER, period="max", progress=False, auto_adjust=False)
        
        if isinstance(data.columns, pd.MultiIndex):
            if 'Adj Close' in data.columns.get_level_values(0):
                raw_prices = data['Adj Close'][TICKER].dropna()
            else:
                raw_prices = data['Close'][TICKER].dropna()
        else:
            if 'Adj Close' in data.columns:
                raw_prices = data['Adj Close'].dropna()
            else:
                raw_prices = data['Close'].dropna()
                
        raw_prices.index = pd.to_datetime(raw_prices.index).tz_localize(None)

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
        
        if pnl_real > 0:
            v3_dynamic_base = base_m * (1 - min(pnl_real, 0.20))
        else:
            v3_dynamic_base = base_m * (1 + min(abs(pnl_real) * 2, 1.00))
            
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
            suggest_buy_action = f"⚠️ 觸發大跌加碼！級別：{level_str}\n\n🛒 應投入：NT$ {suggest_buy_amount:,.0f}"
        
        net_asset = cur_val + cash - (loan1 + loan2)
        current_exposure = (cur_val * 2) / net_asset if net_asset > 0 else 0
        target_stock_value = ((target_exp_pct / 100.0) * net_asset) / 2
        rebalance_diff = cur_val - target_stock_value
        
        st.subheader("📋 1. 詳細庫存與損益明細")
        c1, c2 = st.columns(2)
        c1.metric("總市值 (元)", f"NT$ {cur_val:,.0f}")
        c2.metric("總投入成本", f"NT$ {actual_cost:,.0f}")
        
        c3, c4 = st.columns(2)
        c3.metric("未實現總損益", f"NT$ {abs_pnl:,.0f}", f"{pnl_real*100:+.2f}%")
        c4.metric("今日損益", f"NT$ {today_pnl:,.0f}", f"{intraday_drop*100:+.2f}%")
        
        c5, c6 = st.columns(2)
        c5.metric("庫存總股數", f"{actual_shares:,.0f} 股")
        c6.metric("持有均價", f"NT$ {avg_cost:,.2f}")
        
        c7, c8 = st.columns(2)
        c7.metric("今日還原現價", f"NT$ {current_p:.2f}")
        c8.metric("昨日還原收盤", f"NT$ {yest_close:.2f}")

        st.divider()
        st.subheader("📈 2. 即時盤中決策台")
        st.write(f"🔹 **當前動態基準金額：** NT$ {v3_dynamic_base:,.0f}")
        
        if intraday_drop <= -0.03:
            st.error(f"💡 **盤中行動指令**：\n\n{suggest_buy_action}")
        else:
            st.info(f"💡 **盤中行動指令**：\n\n{suggest_buy_action}")
        
        st.divider()
        st.subheader("⚖️ 3. 資產再平衡詳細檢視")
        st.write(f"🔹 **總淨資產 (股+現-債):** NT$ {net_asset:,.0f}")
        st.write(f"🔹 **目前實際曝險度:** **{current_exposure*100:.2f}%** (目標: {target_exp_pct}%)")
        
        if rebalance_diff > 0:
            st.warning(f"🚨 【曝險過高】若要嚴格再平衡，應減碼賣出市值： **NT$ {rebalance_diff:,.0f}**")
        elif rebalance_diff < 0:
            st.success(f"🟢 【曝險過低】若資金允許，可加碼買進市值： **NT$ {abs(rebalance_diff):,.0f}**")
        else:
            st.success("✅ 目前曝險完美符合目標，不需調整。")

        st.divider()
        st.subheader("🌐 4. 00631L 歷史還原走勢圖")
        fig = go.Figure()
        recent_prices = adj_prices[adj_prices.index >= pd.to_datetime('2024-01-01')]
        fig.add_trace(go.Scatter(x=recent_prices.index, y=recent_prices.values, mode='lines', name='還原股價', line=dict(color='#E71D36', width=2)))
        fig.update_layout(template='plotly_white', margin=dict(l=0, r=0, t=30, b=0), hovermode='x unified', height=300)
        st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 📝 雲端寫入區塊 (即時連動試算版)
# ==========================================
st.divider()
st.subheader("📝 5. 新增交易紀錄")
st.write("輸入數值後，系統會即時試算成本，確認無誤後再送出！")

# 拔除 st.form，改成即時讀取輸入值的欄位
col_a, col_b = st.columns(2)
trade_date = col_a.date_input("成交日期", datetime.today())
trade_type = col_b.selectbox("交易類型", ["現股買入", "現股賣出"])

col_c, col_d = st.columns(2)
trade_price = col_c.number_input("成交價格", min_value=0.0, step=0.1)
trade_shares = col_d.number_input("庫存股數 (股)", min_value=0, step=1)

trade_fee = st.number_input("手續費 (元)", min_value=0, step=1)

# 即時自動試算成本 (只要上面數字有改動，這裡就會瞬間重算)
preview_cost = (trade_price * trade_shares) + trade_fee

# 顯示明顯的確認試算框
st.info(f"💡 【系統試算】本次交易總成本為： **NT$ {preview_cost:,.0f}**")

# 送出按鈕 (加上防呆：股數必須大於0才能送出)
if trade_shares > 0:
    if st.button("🚀 確認無誤，寫入雲端", use_container_width=True):
        if not df_trades_raw.empty:
            new_data = pd.DataFrame([{
                "成交日期": trade_date.strftime("%Y-%m-%d"),
                "交易類型": trade_type,
                "成交價格": trade_price,
                "庫存股數": trade_shares,
                "手續費": trade_fee,
                "持有成本": preview_cost,
                "損益試算": 0,  
                "報酬率": "0.00%" 
            }])
            
            updated_df = pd.concat([df_trades_raw, new_data], ignore_index=True)
            
            try:
                conn.update(data=updated_df)
                st.cache_data.clear() 
                st.success("✅ 交易紀錄已成功寫入 Google 試算表！請點擊上方「啟動分析」按鈕重新抓取資料。")
            except Exception as e:
                st.error(f"❌ 寫入失敗，請檢查權限設定。({e})")
        else:
            st.error("❌ 無法取得原始資料表，無法寫入。")
else:
    st.button("🚀 請先輸入股數", disabled=True, use_container_width=True)
