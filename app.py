import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection

# 1. 設定 App 頁面
st.set_page_config(page_title="00631L 實戰大腦", page_icon="🤖", layout="centered")
st.title("🤖 00631L 實戰大腦 (詳細數據版)")

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
    df_trades = conn.read()
    
    df_trades['成交日期'] = pd.to_datetime(df_trades['成交日期'])
    temp_df = df_trades.copy()
    temp_df.loc[temp_df['交易類型'].str.contains('賣出', na=False), '庫存股數'] = -temp_df['庫存股數'].abs()
    temp_df.loc[temp_df['交易類型'].str.contains('賣出', na=False), '持有成本'] = -temp_df['持有成本'].abs()
    
    actual_shares = temp_df['庫存股數'].sum()
    actual_cost = temp_df['持有成本'].sum()
    
    st.sidebar.success(f"✅ 雲端同步成功！\n庫存：{actual_shares:,.0f} 股\n成本：{actual_cost:,.0f} 元")
except Exception as e:
    st.sidebar.error("❌ 雲端庫存讀取失敗，改為0股代入計算。")
    actual_shares, actual_cost = 0, 0

# 4. 核心運算按鈕
if st.button("🚀 啟動最新盤中決策", use_container_width=True):
    with st.spinner('📡 正在抓取即時行情並深度分析中...'):
        TICKER = "00631L.TW"
        # 多抓一點資料來畫圖 (近一年)
        data = yf.download(TICKER, period="1y", progress=False)
        
        # 修正 yfinance 新版的雙層表格格式問題
        if isinstance(data.columns, pd.MultiIndex):
            close_prices = data['Close'][TICKER].dropna()
        else:
            close_prices = data['Close'].dropna()
            
        current_p = float(close_prices.iloc[-1])
        yest_close = float(close_prices.iloc[-2])
        
        # V3 加碼邏輯
        cur_val = actual_shares * current_p
        pnl_real = (cur_val - actual_cost) / actual_cost if actual_cost > 0 else 0
        intraday_drop = (current_p - yest_close) / yest_close
        
        # 判斷加碼指令與動態基準
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
        
        # 曝險計算
        net_asset = cur_val + cash - (loan1 + loan2)
        current_exposure = (cur_val * 2) / net_asset if net_asset > 0 else 0
        target_stock_value = ((target_exp_pct / 100.0) * net_asset) / 2
        rebalance_diff = cur_val - target_stock_value
        
        # ==========================================
        # 📊 手機版詳細 UI 介面
        # ==========================================
        
        st.subheader("📊 1. 個人庫存與損益現況")
        c1, c2 = st.columns(2)
        c1.metric("總市值 (元)", f"{cur_val:,.0f}")
        c2.metric("未實現損益", f"{pnl_real*100:+.2f}%", f"總成本: {actual_cost:,.0f}")
        
        st.divider()
        
        st.subheader("📈 2. 即時盤中決策台")
        c3, c4 = st.columns(2)
        c3.metric("今日現價", f"{current_p:.2f}", f"{intraday_drop*100:+.2f}%")
        c4.metric("動態基準金額", f"{v3_dynamic_base:,.0f}")
        
        if intraday_drop <= -0.03:
            st.error(f"💡 **盤中行動指令**：\n\n{suggest_buy_action}")
        else:
            st.info(f"💡 **盤中行動指令**：\n\n{suggest_buy_action}")
        
        st.divider()
        
        st.subheader("⚖️ 3. 資產再平衡詳細檢視")
        st.write(f"🔹 **總淨資產 (股+現-債):** NT$ {net_asset:,.0f}")
        st.write(f"🔹 **目前實際曝險度:** **{current_exposure*100:.2f}%** (目標: {target_exp_pct}%)")
        
        # 給出明確的買賣數字
        if rebalance_diff > 0:
            st.warning(f"🚨 【曝險過高】若要嚴格再平衡，應減碼賣出市值： **NT$ {rebalance_diff:,.0f}**")
        elif rebalance_diff < 0:
            st.success(f"🟢 【曝險過低】若資金允許，可加碼買進市值： **NT$ {abs(rebalance_diff):,.0f}**")
        else:
            st.success("✅ 目前曝險完美符合目標，不需調整。")

        st.divider()

        st.subheader("🌐 4. 00631L 近一年走勢圖")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=close_prices.index, y=close_prices.values, mode='lines', name='股價', line=dict(color='#E71D36', width=2)))
        fig.update_layout(template='plotly_white', margin=dict(l=0, r=0, t=30, b=0), hovermode='x unified', height=300)
        st.plotly_chart(fig, use_container_width=True)

st.caption("📱 提示：將此網頁「加入主畫面」，它就是你的專屬實戰 App！")
