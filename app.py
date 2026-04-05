import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# 1. 設定 App 頁面與標題 (手機上看起來的樣子)
st.set_page_config(page_title="00631L 實戰大腦", page_icon="🤖", layout="centered")
st.title("🤖 00631L 實戰大腦 V3")

# 2. 側邊欄 (Sidebar) - 取代你原本的 input()
st.sidebar.header("⚙️ 參數設定")
loan1 = st.sidebar.number_input("1. 信貸一剩餘本金", value=2056231, step=10000)
loan2 = st.sidebar.number_input("2. 信貸二剩餘本金", value=935907, step=10000)
base_m = st.sidebar.number_input("3. 基準每月定期定額", value=100000, step=10000)
cash = st.sidebar.number_input("4. 目前股票帳戶可用現金", value=0, step=10000)
target_exp_pct = st.sidebar.number_input("5. 設定目標曝險度 (%)", value=200)

# 加入一個按鈕，按下去才開始運算
if st.button("🚀 啟動盤中決策與分析"):
    with st.spinner('系統正在抓取最新股價並運算中...'):
        
        # ==========================================
        # 這裡之後會貼上你完整的 Python 運算邏輯
        # (現在先放個骨架讓你測試手機畫面長怎樣)
        # ==========================================
        current_p = 200.50 
        yest_close = 205.00
        intraday_drop = (current_p - yest_close) / yest_close
        
        suggest_buy_action = "無須動作 (維持紀律等待)"
        if intraday_drop <= -0.03:
            suggest_buy_action = "⚠️ 觸發大跌加碼！" 

        # 3. 畫面呈現：盤中決策台
        st.subheader("📈 即時盤中決策台")
        
        col1, col2 = st.columns(2)
        col1.metric(label="今日現價", value=f"{current_p:.2f}", delta=f"{intraday_drop*100:.2f}%")
        col2.metric(label="昨日收盤", value=f"{yest_close:.2f}")
        
        st.info(f"💡 **盤中行動指令**：{suggest_buy_action}")
        
        st.divider() 
        
        # 4. 畫面呈現：資產再平衡區塊
        st.subheader("⚖️ 資產再平衡檢視")
        st.write("🔹 **總淨資產 (股+現-債):** 這裡放計算結果 元")
        st.write("🔹 **目前實際曝險度:** 這裡放計算結果 %")
        st.success("✅ 目前曝險完美符合目標，不需調整。") 
        
        st.divider()

        # 5. 畫面呈現：圖表區塊
        st.subheader("🌐 歷史與未來宇宙模擬圖")
        st.caption("👈 (之後將會在此顯示互動圖表，手機可左右滑動)")
