import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# ==========================================
# 賴賴投資戰情室 V5.0 - 戰略全能版 (含生命週期降落)
# ==========================================

st.set_page_config(page_title="賴賴終極戰情室", page_icon="📈", layout="centered")
st.title("🛡️ 賴賴投資戰情室 V5.0")

if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

st.sidebar.header("⚙️ 資金與曝險參數")
loan1 = st.sidebar.number_input("1. 信貸一剩餘本金", value=2056231)
loan2 = st.sidebar.number_input("2. 信貸二剩餘本金", value=935907)
base_m = st.sidebar.number_input("3. 基準每月定期定額", value=100000)
cash = st.sidebar.number_input("4. 目前帳戶可用現金", value=2000000)
target_exp_pct = st.sidebar.number_input("5. 設定目標曝險度 (%)", value=200)

st.sidebar.divider()
st.sidebar.header("⚙️ 生命週期規劃參數")
usd_twd = st.sidebar.number_input("6. 目前美元匯率", value=32.0)
hc_years = st.sidebar.number_input("7. 預計剩餘投入年限", value=10)
target_k = st.sidebar.number_input("8. 一生目標曝險度 (%)", value=83)

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

# 🌟 新增第三個標籤頁
tab1, tab2, tab3 = st.tabs(["🇹🇼 台股 00631L", "🇺🇸 美股狙擊系統", "🛬 生命週期軌跡"])

if st.session_state.analyzed:
    # 預先宣告總市值變數，供給生命週期計算使用
    cur_val = 0
    total_us_val = 0

    # ==========================================
    # 🇹🇼 分頁一：台股 00631L
    # ==========================================
    with tab1:
        with st.spinner('📡 抓取即時數據與歷史運算中...'):
            TICKER = "00631L.TW"
            data = yf.download(TICKER, period="max", progress=False, auto_adjust=False)
            
            if isinstance(data.columns, pd.MultiIndex):
                raw_prices = data['Adj Close'][TICKER].dropna() if 'Adj Close' in data.columns.get_level_values(0) else data['Close'][TICKER].dropna()
            else:
                raw_prices = data['Adj Close'].dropna() if 'Adj Close' in data.columns else data['Close'].dropna()
                    
            raw_prices.index = pd.to_datetime(raw_prices.index).tz_localize(None)

            # 3/23 股價還原
            adj_prices = raw_prices.copy()
            split_cutoff = pd.to_datetime('2026-03-23')
            mask = (adj_prices.index < split_cutoff) & (adj_prices > 100)
            if mask.any():
                adj_prices.loc[mask] = round(adj_prices.loc[mask] / 22.0, 2)
                
            # V4.9 精準即時報價核心
            tkr = yf.Ticker(TICKER)
            try:
                raw_curr = float(tkr.fast_info.last_price)
                raw_yest = float(tkr.fast_info.previous_close)
            except:
                tw_date = (datetime.utcnow() + timedelta(hours=8)).date()
                if raw_prices.index[-1].date() == tw_date:
                    raw_curr = float(raw_prices.iloc[-1])
                    raw_yest = float(raw_prices.iloc[-2])
                else:
                    raw_yest = float(raw_prices.iloc[-1])
                    try:
                        intra = yf.download(TICKER, period="1d", interval="1m", progress=False)
                        raw_curr = float(intra['Close'][TICKER].dropna().iloc[-1]) if isinstance(intra.columns, pd.MultiIndex) else float(intra['Close'].dropna().iloc[-1])
                    except:
                        raw_curr = raw_yest

            current_p = round(raw_curr / 22.0, 2) if raw_curr > 100 else raw_curr
            yest_close = round(raw_yest / 22.0, 2) if raw_yest > 100 else raw_yest
            
            cur_val = actual_shares * current_p
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
            c4.metric("今日損益", f"NT$ {today_pnl:,.0f}", f"{intraday_drop*100:+.2f}%")
            
            c5, c6 = st.columns(2)
            c5.metric("庫存總股數", f"{actual_shares:,.0f} 股")
            c6.metric("持有均價", f"NT$ {avg_cost:,.2f}")
            
            c7, c8 = st.columns(2)
            c7.metric("今日還原現價", f"NT$ {current_p:.2f}")
            c8.metric("昨日還原收盤", f"NT$ {yest_close:.2f}")

            st.divider()

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
                                adj_p = r_price / 22.0
                                adj_s = r_shares * 22.0
                            else:
                                adj_p = r_price
                                adj_s = r_shares
                            
                            lot_cur_val = adj_s * current_p
                            lot_pnl = lot_cur_val - t_cost
                            lot_roi = lot_pnl / t_cost if t_cost > 0 else 0
                            lot_today_pnl = (current_p - yest_close) * adj_s
                            
                            days_held = max((today_date - trade_d).days, 1)
                            if days_held < 30:
                                ann_roi_str = "-"
                            else:
                                ann_roi = (1 + lot_roi) ** (365.0 / days_held) - 1
                                ann_roi_str = f"{ann_roi*100:+.2f}%"
                            
                            records.append({
                                '📅 日期': trade_d.strftime('%Y-%m-%d'),
                                '🛒 買價': f"{adj_p:.2f}",
                                '📦 股數': f"{adj_s:,.0f}",
                                '💰 總成本': f"{t_cost:,.0f}",
                                '🔥 今日損益': f"{lot_today_pnl:+,.0f}",
                                '📈 總損益': f"{lot_pnl:+,.0f}",
                                '🎯 總報酬': f"{lot_roi*100:+.2f}%",
                                '🚀 年化報酬': ann_roi_str
                            })
                        st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)
                    else:
                        st.write("目前尚無買入紀錄。")
                else:
                    st.write("無法讀取資料。")

            st.divider()

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

            st.subheader("📈 即時盤中決策台")
            st.write(f"🔹 **當前動態基準金額：** NT$ {v3_dynamic_base:,.0f}")
            if intraday_drop <= -0.03:
                st.error(f"💡 **盤中行動指令**：\n\n{suggest_buy_action}")
            else:
                st.info(f"💡 **盤中行動指令**：\n\n{suggest_buy_action}")
            
            st.divider()
            
            st.subheader("⚖️ 資產再平衡詳細檢視")
            st.write(f"🔹 **總淨資產 (股+現-債):** NT$ {net_asset:,.0f}")
            st.write(f"🔹 **目前實際曝險度:** **{current_exposure*100:.2f}%** (目標: {target_exp_pct}%)")
            
            if rebalance_diff > 0:
                st.warning(f"🚨 【曝險過高】應減碼賣出市值： **NT$ {rebalance_diff:,.0f}**")
            elif rebalance_diff < 0:
                st.success(f"🟢 【曝險過低】可加碼買進市值： **NT$ {abs(rebalance_diff):,.0f}**")
            else:
                st.success("✅ 目前曝險完美符合目標，不需調整。")

            st.divider()

            st.subheader("🌐 戰術圖表分析")
            recent_prices = adj_prices[adj_prices.index >= pd.to_datetime('2024-01-01')]
            
            st.write("📈 **A. 價格走勢與當前均價防線**")
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=recent_prices.index, y=recent_prices.values, mode='lines', name='還原股價', line=dict(color='#E71D36', width=2)))
            if avg_cost > 0:
                fig1.add_hline(y=avg_cost, line_dash="dash", line_color="#00A86B", annotation_text=f"你的均價: {avg_cost:.2f}")
            if not recent_prices.empty:
                max_idx, max_val = recent_prices.idxmax(), recent_prices.max()
                min_idx, min_val = recent_prices.idxmin(), recent_prices.min()
                fig1.add_annotation(x=max_idx, y=max_val, text=f"高: {max_val:.2f}", showarrow=True, arrowhead=1, ax=0, ay=-30)
                fig1.add_annotation(x=min_idx, y=min_val, text=f"低: {min_val:.2f}", showarrow=True, arrowhead=1, ax=0, ay=30)
            fig1.update_layout(template='plotly_white', margin=dict(l=0, r=0, t=35, b=0), height=250)
            st.plotly_chart(fig1, use_container_width=True)

            st.write("📊 **B. 多空戰略動能圖 (乖離率雙向動能)**")
            ma20 = recent_prices.rolling(window=20).mean()
            bias = (recent_prices - ma20) / ma20 * 100
            
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=bias.index, y=bias.values, fill='tozeroy', mode='lines', name='乖離率%', line=dict(color='#F4A261')))
            fig2.add_hline(y=0, line_width=1, line_color="black") 
            for val, color, txt in [(-5, "gray", "標準"), (-10, "orange", "恐慌"), (-15, "red", "重壓")]:
                fig2.add_hline(y=val, line_dash="dot", line_color=color, annotation_text=txt)
            bias_clean = bias.dropna()
            if not bias_clean.empty:
                b_max_idx, b_max_val = bias_clean.idxmax(), bias_clean.max()
                b_min_idx, b_min_val = bias_clean.idxmin(), bias_clean.min()
                fig2.add_annotation(x=b_max_idx, y=b_max_val, text=f"最高: {b_max_val:.1f}%", showarrow=True, arrowhead=1, ax=0, ay=-30)
                fig2.add_annotation(x=b_min_idx, y=b_min_val, text=f"最低: {b_min_val:.1f}%", showarrow=True, arrowhead=1, ax=0, ay=30)
            fig2.update_layout(template='plotly_white', margin=dict(l=0, r=0, t=35, b=0), height=250, yaxis_title="乖離率 %")
            st.plotly_chart(fig2, use_container_width=True)

            st.write("💰 **C. 庫存損益率歷史真實軌跡**")
            if not temp_df.empty:
                trade_history = temp_df.copy()
                trade_history = trade_history.groupby('成交日期')[['庫存股數', '持有成本']].sum().reset_index()
                trade_history.set_index('成交日期', inplace=True)
                trade_history.index = pd.to_datetime(trade_history.index).tz_localize(None)

                daily_history = trade_history.reindex(adj_prices.index).fillna(0)
                daily_shares = daily_history['庫存股數'].cumsum()
                daily_cost = daily_history['持有成本'].cumsum()

                daily_mv = daily_shares * adj_prices
                daily_pnl_pct = np.where(daily_cost > 0, (daily_mv - daily_cost) / daily_cost * 100, 0)
                daily_pnl_pct_series = pd.Series(daily_pnl_pct, index=adj_prices.index)

                recent_pnl_pct = daily_pnl_pct_series[daily_pnl_pct_series.index >= pd.to_datetime('2024-01-01')]
                
                max_val = recent_pnl_pct.max() if not recent_pnl_pct.empty and not pd.isna(recent_pnl_pct.max()) else 0
                min_val = recent_pnl_pct.min() if not recent_pnl_pct.empty and not pd.isna(recent_pnl_pct.min()) else 0

                fig3 = go.Figure()
                fig3.add_trace(go.Scatter(x=recent_pnl_pct.index, y=recent_pnl_pct.values, mode='lines', name='真實損益率%', line=dict(color='#247BA0')))
                fig3.add_hline(y=0, line_width=2, line_color="black") 
                fig3.add_hrect(y0=0, y1=max(max_val, 10)+5, fillcolor="green", opacity=0.1, layer="below", line_width=0)
                fig3.add_hrect(y0=min(min_val, -10)-5, y1=0, fillcolor="red", opacity=0.1, layer="below", line_width=0)
                pnl_clean = recent_pnl_pct.dropna()
                if not pnl_clean.empty and (max_val != 0 or min_val != 0):
                    p_max_idx, p_max_val = pnl_clean.idxmax(), pnl_clean.max()
                    p_min_idx, p_min_val = pnl_clean.idxmin(), pnl_clean.min()
                    fig3.add_annotation(x=p_max_idx, y=p_max_val, text=f"最高: {p_max_val:.1f}%", showarrow=True, arrowhead=1, ax=0, ay=-30)
                    fig3.add_annotation(x=p_min_idx, y=p_min_val, text=f"最低: {p_min_val:.1f}%", showarrow=True, arrowhead=1, ax=0, ay=30)
                fig3.update_layout(template='plotly_white', margin=dict(l=0, r=0, t=35, b=0), height=250, yaxis_title="真實損益 %")
                st.plotly_chart(fig3, use_container_width=True)
            else:
                st.info("尚無足夠的歷史交易紀錄，無法繪製真實損益軌跡。")

        st.divider()
        st.subheader("📝 新增交易紀錄 (同步至 Google 試算表)")
        col_a, col_b = st.columns(2)
        trade_date = col_a.date_input("成交日期", datetime.today())
        trade_type = col_b.selectbox("交易類型", ["現股買入", "現股賣出"])
        col_c, col_d = st.columns(2)
        trade_price = col_c.number_input("成交價格", min_value=0.0, step=0.1)
        trade_shares = col_d.number_input("庫存股數 (股)", min_value=0, step=1)
        trade_fee = st.number_input("手續費 (元)", min_value=0, step=1)

        preview_cost = (trade_price * trade_shares) + trade_fee
        st.info(f"💡 【系統試算】本次交易總成本為： **NT$ {preview_cost:,.0f}**")

        if trade_shares > 0:
            if st.button("🚀 確認無誤，寫入雲端", use_container_width=True):
                if not df_trades_raw.empty:
                    new_data = pd.DataFrame([{
                        "成交日期": trade_date.strftime("%Y-%m-%d"),
                        "交易類型": trade_type, "成交價格": trade_price,
                        "庫存股數": trade_shares, "手續費": trade_fee,
                        "持有成本": preview_cost, "損益試算": 0, "報酬率": "0.00%" 
                    }])
                    updated_df = pd.concat([df_trades_raw, new_data], ignore_index=True)
                    try:
                        conn.update(data=updated_df)
                        st.cache_data.clear() 
                        st.success("✅ 交易紀錄已寫入！請點擊上方「啟動全面掃描」按鈕重新讀取。")
                    except Exception as e:
                        st.error(f"❌ 寫入失敗。({e})")

    # ==========================================
    # 🇺🇸 分頁二：美股狙擊系統
    # ==========================================
    with tab2:
        with st.spinner('📡 抓取美股數據中...'):
            tickers = ["SOXX", "SOXL", "TMF", "BITX"]
            us_data = yf.download(tickers, period="200d", progress=False)
            
            us_positions = {
                "SOXL": {"shares": 545, "cost": 50.99},
                "TMF": {"shares": 1050, "cost": 52.94},
                "BITX": {"shares": 11, "cost": 29.67}
            }
            
            us_live = {}
            for t in us_positions.keys():
                try:
                    tkr_us = yf.Ticker(t)
                    us_live[t] = {'curr': float(tkr_us.fast_info.last_price), 'yest': float(tkr_us.fast_info.previous_close)}
                except:
                    us_live[t] = {'curr': float(us_data['Close'][t].dropna().iloc[-1]), 'yest': float(us_data['Close'][t].dropna().iloc[-2])}
            
            st.subheader("🎯 1. 大盤趨勢與輪動階梯")
            soxx_close = us_data['Close']['SOXX'].dropna()
            soxx_100dma = soxx_close.rolling(window=100).mean()
            curr_soxx = soxx_close.iloc[-1]
            curr_dma = soxx_100dma.iloc[-1]
            
            soxx_diff = curr_soxx - curr_dma
            soxx_diff_pct = (curr_soxx / curr_dma - 1) * 100
            
            if curr_soxx > curr_dma:
                st.success(f"🟢 **SOXX 多頭續抱** | 現價:{curr_soxx:.2f} (100DMA:{curr_dma:.2f} | 差距: +{soxx_diff:.2f} / +{soxx_diff_pct:.2f}%)\n\n**指令：趨勢向上，SOXL 持續抱牢。**")
            else:
                st.error(f"🔴 **停利訊號觸發！** | 現價:{curr_soxx:.2f} 跌破 100DMA ({curr_dma:.2f} | 差距: {soxx_diff:.2f} / {soxx_diff_pct:.2f}%)\n\n**指令：全數賣出 SOXL 轉入 TLT。**")
            
            curr_soxl = us_live['SOXL']['curr']
            steps = [30.14, 21.09, 14.77]
            col_s1, col_s2, col_s3 = st.columns(3)
            cols = [col_s1, col_s2, col_s3]
            for i, target in enumerate(steps):
                if curr_soxl <= target:
                    cols[i].warning(f"✅ 階梯 {i+3}\n已達標\n${target}")
                else:
                    cols[i].info(f"⏳ 階梯 {i+3}\n目標 ${target}\n距 {((curr_soxl/target)-1)*100:.1f}%")
            st.caption(f"🔹 **SOXL 目前現價：${curr_soxl:.2f}**")
            
            st.divider()

            total_us_val = 0
            total_us_cost = 0
            total_today_pnl = 0
            total_yest_val = 0
            
            for t, info in us_positions.items():
                p_curr = us_live[t]['curr']
                p_yest = us_live[t]['yest']
                shares = info['shares']
                
                total_us_val += p_curr * shares
                total_yest_val += p_yest * shares
                total_us_cost += info['cost'] * shares
                total_today_pnl += (p_curr - p_yest) * shares
                
            total_us_val_twd = total_us_val * usd_twd # 傳遞給分頁三使用

            total_abs_pnl = total_us_val - total_us_cost
            total_pnl_pct = total_abs_pnl / total_us_cost if total_us_cost > 0 else 0
            total_today_pct = total_today_pnl / total_yest_val if total_yest_val > 0 else 0

            st.subheader("📋 2. 美股總資產詳細身價")
            cu1, cu2 = st.columns(2)
            cu1.metric("美股總市值 (USD)", f"${total_us_val:,.2f}")
            cu2.metric("美股總投入成本 (USD)", f"${total_us_cost:,.2f}")
            
            cu3, cu4 = st.columns(2)
            cu3.metric("未實現總損益", f"${total_abs_pnl:,.2f}", f"{total_pnl_pct*100:+.2f}%")
            cu4.metric("今日總損益", f"${total_today_pnl:,.2f}", f"{total_today_pct*100:+.2f}%")

            st.divider()

            st.subheader("📦 3. 個股明細快報")
            for t, info in us_positions.items():
                p_curr = us_live[t]['curr']
                p_yest = us_live[t]['yest']
                shares = info['shares']
                avg_cost = info['cost']
                
                cur_val_us = p_curr * shares
                tot_cost_us = avg_cost * shares
                abs_pnl_us = cur_val_us - tot_cost_us
                pnl_pct_us = abs_pnl_us / tot_cost_us if tot_cost_us > 0 else 0
                today_pnl_val_us = (p_curr - p_yest) * shares
                today_pnl_pct_us = (p_curr / p_yest - 1)
                
                st.markdown(f"#### 📌 **{t}**")
                st.write(f"🔹 **今日現價:** ${p_curr:.2f} ({today_pnl_pct_us*100:+.2f}%) ｜ **今日損益:** ${today_pnl_val_us:,.2f}")
                st.write(f"🔹 **持有均價:** ${avg_cost:.2f} ｜ **未實現損益:** ${abs_pnl_us:,.2f} ({pnl_pct_us*100:+.2f}%)")
                st.write(f"🔹 **庫存股數:** {shares:,.0f} 股 ｜ **總市值:** ${cur_val_us:,.2f}")
                st.markdown("---")

    # ==========================================
    # 🛬 分頁三：生命週期降落軌跡 (Lifecycle Investing)
    # ==========================================
    with tab3:
        st.subheader("🛬 生命週期投資法 (Lifecycle Investing)")
        st.write("系統已自動抓取你當前的台美股真實市值、現金與信貸，為你推演未來的最佳化降落軌跡 (Glide Path)。")
        
        # 1. 數值運算
        FC = cur_val + total_us_val_twd + cash - (loan1 + loan2)
        annual_inv = base_m * 12
        HC = annual_inv * hc_years
        W = FC + HC
        target_stock = W * (target_k / 100.0)
        current_E = (target_stock / FC * 100) if FC > 0 else 0
        
        # 2. 當前戰況總結
        st.markdown("### 📊 1. 當前戰況總結")
        c_l1, c_l2 = st.columns(2)
        c_l1.metric("當前總金融資本 (FC)", f"NT$ {FC:,.0f}", "台股+美股+現-債")
        c_l2.metric("未來人力資本 (HC)", f"NT$ {HC:,.0f}", f"未來 {hc_years} 年")
        
        c_l3, c_l4 = st.columns(2)
        c_l3.metric("一生總財富 (W)", f"NT$ {W:,.0f}", "FC + HC")
        c_l4.metric("目標股票部位", f"NT$ {target_stock:,.0f}", f"目標曝險 {target_k}%")
        
        st.info(f"💡 **當前應有曝險度 (E) = {current_E:.1f}%**\n\n目前你的總資產規模，對應你未來的人力資本，最佳化的曝險水位為 **{current_E:.1f}%**。若大於 200%，代表你目前處於完全可以承受高槓桿的黃金期！")
        
        st.divider()
        
        # 3. 降落時程推演表
        st.markdown("### 🛬 2. 降落時程推演表 (Glide Path)")
        st.caption("以下推演在保守(6%)、正常(8%)、樂觀(10%)三種年化報酬情境下，你的FC成長與應有曝險度變化。")
        
        records_gp = []
        fc_6, fc_8, fc_10 = FC, FC, FC
        drop_year_6, drop_year_8, drop_year_10 = None, None, None
        
        for y in range(0, hc_years + 1):
            if y == 0:
                e_6 = e_8 = e_10 = current_E
            else:
                fc_6 = fc_6 * 1.06 + annual_inv
                fc_8 = fc_8 * 1.08 + annual_inv
                fc_10 = fc_10 * 1.10 + annual_inv
                
                hc_rem = max(HC - annual_inv * y, 0)
                e_6 = ((fc_6 + hc_rem) * (target_k / 100.0)) / fc_6 * 100
                e_8 = ((fc_8 + hc_rem) * (target_k / 100.0)) / fc_8 * 100
                e_10 = ((fc_10 + hc_rem) * (target_k / 100.0)) / fc_10 * 100
                
            if e_6 < 200 and drop_year_6 is None: drop_year_6 = y
            if e_8 < 200 and drop_year_8 is None: drop_year_8 = y
            if e_10 < 200 and drop_year_10 is None: drop_year_10 = y
            
            records_gp.append({
                "第幾年": f"第 {y} 年" if y > 0 else "現在 (第0年)",
                "剩餘 HC": f"{max(HC - annual_inv * y, 0):,.0f}",
                "預估 FC (8%)": f"{fc_8 if y>0 else FC:,.0f}",
                "應有曝險(8%)": f"{e_8:.1f}%",
                "保守曝險(6%)": f"{e_6:.1f}%",
                "樂觀曝險(10%)": f"{e_10:.1f}%"
            })
            
        st.dataframe(pd.DataFrame(records_gp), use_container_width=True, hide_index=True)
        
        st.divider()
        
        # 4. 具體行動指南
        st.markdown("### 🎯 3. 具體行動指南")
        st.write(f"根據推算，你的最佳曝險度大約會在以下時間點 **正式跌破 200% (啟動降落)**：")
        st.markdown(f"""
        * 🟢 **樂觀情境 (10%)：** 第 **{drop_year_10 if drop_year_10 else '>10'}** 年
        * 🟡 **正常情境 (8%)：** 第 **{drop_year_8 if drop_year_8 else '>10'}** 年
        * 🔴 **保守情境 (6%)：** 第 **{drop_year_6 if drop_year_6 else '>10'}** 年
        """)
        
        st.warning("⚠️ **降槓桿操盤提醒：**\n\n計算總曝險時是「台股 + 美股」合併計算的。未來若需要降槓桿（例如從 200% 降到 150%），你可以自由決定要賣出台股的 00631L 或是美股的 SOXL 換回 1 倍原型部位，**不需要將美金匯回台灣**，只要在各自的券商內切換標的即可！")

st.caption("📱 提示：將此網頁「加入主畫面」，它就是你的專屬實戰 App！")
