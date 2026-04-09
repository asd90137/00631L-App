import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# ==========================================
# 賴賴投資戰情室 V8.0 - 完美戰神版
# ==========================================

st.set_page_config(page_title="賴賴終極戰情室", page_icon="📈", layout="wide")
st.title("🛡️ 賴賴投資戰情室 V8.0")

if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

# --- 🏦 核心引擎：貸款自動計算 ---
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

with st.sidebar.expander("🏦 貸款細項設定 (自動連動)", expanded=False):
    l1_p = st.number_input("信貸一總額", value=2200000); l1_r = st.number_input("年利率1(%)", value=2.5); l1_d = st.date_input("首次扣款日1", datetime(2024, 1, 15))
    loan1, pmt1 = calculate_loan_remaining(l1_p, l1_r, 7, l1_d)
    st.info(f"貸1剩餘：{loan1/10000:.1f}萬")
    st.divider()
    l2_p = st.number_input("信貸二總額", value=950000); l2_r = st.number_input("年利率2(%)", value=2.72); l2_d = st.date_input("首次扣款日2", datetime(2026, 3, 5))
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
    st.sidebar.error(f"❌ 帳本連結失敗 (請確認權限或略過此錯誤)：{e}")
    df_tw_raw = pd.DataFrame(); df_us_raw = pd.DataFrame()

if st.button("🚀 啟動戰略掃描", use_container_width=True):
    st.session_state.analyzed = True

if st.session_state.analyzed:
    # --- 核心運算模組 ---
    TICKER_TW = "00631L.TW"
    split_cutoff = pd.to_datetime('2026-03-23')
    
    # 1. 台股計算
    tkr_tw = yf.Ticker(TICKER_TW)
    p_tw_raw = tkr_tw.fast_info.last_price
    p_tw_yest_raw = tkr_tw.fast_info.previous_close
    p_tw_curr = round(p_tw_raw / (22.0 if p_tw_raw > 100 else 1.0), 2)
    p_tw_yest = round(p_tw_yest_raw / (22.0 if p_tw_yest_raw > 100 else 1.0), 2)
    
    temp_tw = df_tw_raw.copy()
    if not temp_tw.empty:
        temp_tw['成交日期'] = pd.to_datetime(temp_tw['成交日期'])
        temp_tw.loc[temp_tw['交易類型'].str.contains('賣出', na=False), ['庫存股數', '持有成本']] *= -1
        actual_shares_tw = temp_tw['庫存股數'].sum()
        actual_cost_tw = temp_tw['持有成本'].sum()
        min_date_tw = temp_tw['成交日期'].min()
    else:
        actual_shares_tw, actual_cost_tw, min_date_tw = 0, 0, pd.to_datetime('2024-01-01')
    cur_val_tw = actual_shares_tw * p_tw_curr
    
    # 2. 美股計算
    us_tickers = ["SOXX", "SOXL", "TMF", "BITX"]
    us_data = yf.download(us_tickers, period="200d", progress=False)
    us_live = {}
    total_us_val_usd = 0.0; total_us_cost_usd = 0.0
    
    for t in ["SOXL", "TMF", "BITX"]:
        t_data = df_us_raw[df_us_raw['股票代號'] == t].copy() if not df_us_raw.empty and '股票代號' in df_us_raw.columns else pd.DataFrame()
        if not t_data.empty:
            t_data['成交日期'] = pd.to_datetime(t_data['成交日期'])
            t_data.loc[t_data['交易類型'].str.contains('賣出', na=False), ['庫存股數', '持有成本']] *= -1
            shares = t_data['庫存股數'].sum()
            cost = t_data['持有成本'].sum()
            first_d = t_data['成交日期'].min()
        else:
            shares, cost, first_d = 0, 0, pd.NaT
            
        curr_p = float(us_data['Close'][t].dropna().iloc[-1])
        yest_p = float(us_data['Close'][t].dropna().iloc[-2])
        us_live[t] = {'shares': shares, 'cost': cost, 'curr': curr_p, 'yest': yest_p, 'first_date': first_d}
        total_us_val_usd += shares * curr_p
        total_us_cost_usd += cost
        
    total_us_val_twd = total_us_val_usd * usd_twd
    FC = cur_val_tw + total_us_val_twd + cash - (loan1 + loan2)

    tab1, tab2, tab3 = st.tabs(["🇹🇼 TW台股", "🇺🇸 US美股", "🛬 生命周期 & 退休"])

    # ------------------------------------------
    # 🇹🇼 Tab 1: 台股
    # ------------------------------------------
    with tab1:
        roi_tw = (cur_val_tw / actual_cost_tw - 1) if actual_cost_tw > 0 else 0
        days_tw = max((datetime.today() - min_date_tw).days, 1) if pd.notnull(min_date_tw) else 1
        ann_roi_tw = ((1+roi_tw)**(365/days_tw) - 1) * 100
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("總市值", f"NT$ {cur_val_tw:,.0f}")
        c2.metric("總投入成本", f"NT$ {actual_cost_tw:,.0f}")
        c3.metric("未實現總損益", f"{cur_val_tw-actual_cost_tw:+,.0f}", f"{roi_tw*100:+.2f}%")
        c4.metric("年化報酬率", f"{ann_roi_tw:+.2f}%")
        
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("庫存總股數", f"{actual_shares_tw:,.0f} 股")
        c6.metric("持有均價", f"{actual_cost_tw/actual_shares_tw:.2f}" if actual_shares_tw>0 else "0")
        c7.metric("昨日還原收盤", f"{p_tw_yest:.2f}")
        c8.metric("目前現價", f"{p_tw_curr:.2f}", f"{(p_tw_curr/p_tw_yest-1)*100:+.2f}%")
        
        c9, c10, c11, _ = st.columns(4)
        c9.metric("今日損益", f"NT$ {(p_tw_curr-p_tw_yest)*actual_shares_tw:+,.0f}", f"{(p_tw_curr/p_tw_yest-1)*100:+.2f}%")
        c10.metric("實際曝險度", f"{(cur_val_tw*2/FC*100):.1f}%")
        c11.metric("投資組合佔比", f"{(cur_val_tw/(cur_val_tw+total_us_val_twd)*100):.1f}%", "台股佔比")

        # --- 圓餅圖：加入貨幣顯示 ---
        st.write("---")
        col_p, col_d = st.columns([2, 1])
        with col_p:
            st.write("📈 **台股與現金分佈**")
            fig_p = go.Figure(data=[go.Pie(
                labels=['00631L 市值', '可用現金'], 
                values=[cur_val_tw, cash], 
                hole=.4, 
                texttemplate='%{label}<br>NT$ %{value:,.0f}<br>%{percent}',
                marker_colors=['#E71D36', '#2EC4B6']
            )])
            fig_p.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig_p, use_container_width=True)
        with col_d:
            st.write("⚠️ **目前債務水位**")
            st.error(f"信貸總餘額：\n\n**NT$ {(loan1+loan2)/10000:,.1f} 萬**")
            st.caption("上述曝險度與淨資產 (FC) 皆已自動扣除此負債。")

        # --- 戰績表：改回股數 ---
        with st.expander("📜 逐筆投資戰績表", expanded=False):
            if not df_tw_raw.empty:
                buy_tw = df_tw_raw[df_tw_raw['交易類型'].str.contains('買入', na=False)].copy()
                buy_tw['成交日期'] = pd.to_datetime(buy_tw['成交日期'])
                recs_tw = []
                for _, r in buy_tw.sort_values('成交日期', ascending=False).iterrows():
                    adj_p = r['成交價格']/22 if r['成交日期']<split_cutoff and r['成交價格']>100 else r['成交價格']
                    adj_s = r['庫存股數']*22 if r['成交日期']<split_cutoff and r['成交價格']>100 else r['庫存股數']
                    l_pnl = adj_s*p_tw_curr - r['持有成本']
                    l_roi = l_pnl / r['持有成本'] if r['持有成本'] > 0 else 0
                    l_ann = ((1+l_roi)**(365/max((datetime.today()-r['成交日期']).days,1))-1)*100
                    recs_tw.append({
                        '日期': r['成交日期'].strftime('%Y-%m-%d'), '買價': f"{adj_p:.2f}", 
                        '股數': f"{adj_s:,.0f}", '今日損益': f"{(p_tw_curr-p_tw_yest)*adj_s:+,.0f}", 
                        '總損益': f"{l_pnl:+,.0f}", '年化報酬': f"{l_ann:+.1f}%", '總報酬': f"{l_roi*100:+.1f}%"
                    })
                st.dataframe(pd.DataFrame(recs_tw), use_container_width=True, hide_index=True)

        with st.expander("🛒 新增台股交易紀錄", expanded=False):
            st.warning("⚠️ **Google API 限制提醒：** 若您未在 Streamlit 後台設定 Google 權限金鑰 (secrets.toml)，即使試算表是公開的，程式也無法寫入。若寫入失敗，請使用下方的「匯出」按鈕自行貼上。")
            col_a, col_b = st.columns(2); tw_date = col_a.date_input("成交日期", key='tw_d'); tw_type = col_b.selectbox("交易類型", ["現股買入", "現股賣出"], key='tw_t')
            col_c, col_d = st.columns(2); tw_price = col_c.number_input("成交價格", key='tw_p', min_value=0.0); tw_shares = col_d.number_input("股數", key='tw_s', min_value=0)
            tw_fee = st.number_input("手續費", value=0, key='tw_f')
            pre_cost = (tw_price * tw_shares) + tw_fee
            st.info(f"💰 本次交易總成本：**NT$ {pre_cost:,.0f}**")
            
            if st.button("🚀 嘗試寫入雲端", use_container_width=True) and tw_shares > 0:
                try:
                    new_data = pd.DataFrame([{"成交日期": tw_date.strftime("%Y-%m-%d"), "交易類型": tw_type, "成交價格": tw_price, "庫存股數": tw_shares, "手續費": tw_fee, "持有成本": pre_cost}])
                    updated_tw = pd.concat([df_tw_raw, new_data], ignore_index=True)
                    conn.update(spreadsheet=SHEET_TW, data=updated_tw)
                    st.success("✅ 寫入成功！")
                except Exception as e:
                    st.error(f"寫入失敗，請確認 API 金鑰。您可將下方資料直接貼入表單：\n\n`{tw_date.strftime('%Y-%m-%d')}	{tw_type}	{tw_price}	{tw_shares}	{tw_fee}	{pre_cost}`")

        st.subheader("🌐 戰術圖表分析 (已自動還原)")
        hist_tw_data = yf.download(TICKER_TW, period="max", progress=False)['Close']
        if isinstance(hist_tw_data, pd.DataFrame): hist_tw_data = hist_tw_data.iloc[:,0]
        adj_h = hist_tw_data.copy()
        adj_h.loc[adj_h.index < split_cutoff] /= 22.0
        
        # 從投資第一天開始
        start_date = min_date_tw if pd.notnull(min_date_tw) else pd.to_datetime('2024-01-01')
        rp = adj_h[adj_h.index >= start_date]
        
        if not rp.dropna().empty:
            # 圖 A：價格與均價
            st.write("📈 **A. 價格走勢與還原均價**")
            fig1 = go.Figure(); fig1.add_trace(go.Scatter(x=rp.index, y=rp.values, name="還原價", line=dict(color='#E71D36')))
            if actual_shares_tw > 0: fig1.add_hline(y=actual_cost_tw/actual_shares_tw, line_dash="dash", line_color="#00A86B", annotation_text="🟢 您的持有均價")
            mx, mi = rp.max(), rp.min(); fig1.add_annotation(x=rp.idxmax(), y=mx, text=f"最高:{mx:.2f}", showarrow=True, ay=-30); fig1.add_annotation(x=rp.idxmin(), y=mi, text=f"最低:{mi:.2f}", showarrow=True, ay=30); fig1.add_annotation(x=rp.index[-1], y=rp.iloc[-1], text=f"最新:{rp.iloc[-1]:.2f}", showarrow=True, ax=40, ay=0)
            fig1.update_layout(height=300, margin=dict(l=0,r=0,t=20,b=0)); st.plotly_chart(fig1, use_container_width=True)
            
            # 圖 B：乖離率
            st.write("📊 **B. 多空戰術乖離率**")
            bias = (rp - rp.rolling(20).mean())/rp.rolling(20).mean()*100
            fig2 = go.Figure(); fig2.add_trace(go.Scatter(x=bias.index, y=bias.values, name="乖離%", fill='tozeroy', line=dict(color='#F4A261')))
            for v, c, t in [(-5,"gray","標準 (-5)"), (-10,"orange","恐慌 (-10)"), (-15,"red","重壓 (-15)")]: fig2.add_hline(y=v, line_dash="dot", line_color=c, annotation_text=t)
            bc = bias.dropna()
            if not bc.empty:
                bx, bi = bc.max(), bc.min(); fig2.add_annotation(x=bc.idxmax(), y=bx, text=f"最高:{bx:.1f}%", showarrow=True, ay=-30); fig2.add_annotation(x=bc.idxmin(), y=bi, text=f"最低:{bi:.1f}%", showarrow=True, ay=30); fig2.add_annotation(x=bc.index[-1], y=bc.iloc[-1], text=f"最新:{bc.iloc[-1]:.1f}%", showarrow=True, ax=40, ay=0)
                fig2.update_yaxes(range=[min(bi,-16)-2, max(bx,10)+2]) # 修復 Y 軸凸出
            fig2.update_layout(height=300, margin=dict(l=0,r=0,t=20,b=0)); st.plotly_chart(fig2, use_container_width=True)

            # 圖 C：損益軌跡
            st.write("💰 **C. 庫存真實損益軌跡**")
            if not temp_tw.empty:
                th = temp_tw.groupby('成交日期')[['庫存股數', '持有成本']].sum().reset_index().set_index('成交日期')
                dh = th.reindex(rp.index).fillna(0); ds = dh['庫存股數'].cumsum(); dc = dh['持有成本'].cumsum()
                dv = ds * rp; dp = np.where(dc > 0, (dv - dc) / dc * 100, 0)
                dp_s = pd.Series(dp, index=rp.index)
                fig3 = go.Figure(); fig3.add_trace(go.Scatter(x=dp_s.index, y=dp_s.values, name='損益%', line=dict(color='#247BA0')))
                fig3.add_hline(y=0, line_width=2, line_color="black")
                dc_cl = dp_s.dropna()
                if not dc_cl.empty:
                    px, pi = dc_cl.max(), dc_cl.min()
                    fig3.add_annotation(x=dc_cl.idxmax(), y=px, text=f"最高:{px:.1f}%", showarrow=True, ay=-30); fig3.add_annotation(x=dc_cl.idxmin(), y=pi, text=f"最低:{pi:.1f}%", showarrow=True, ay=30); fig3.add_annotation(x=dc_cl.index[-1], y=dc_cl.iloc[-1], text=f"最新:{dc_cl.iloc[-1]:.1f}%", showarrow=True, ax=40, ay=0)
                    fig3.update_yaxes(range=[min(pi,-10)-5, max(px,10)+5]) # 修復 Y 軸凸出
                    fig3.add_hrect(y0=0, y1=max(px, 10)+10, fillcolor="green", opacity=0.1, layer="below", line_width=0)
                    fig3.add_hrect(y0=min(pi, -10)-10, y1=0, fillcolor="red", opacity=0.1, layer="below", line_width=0)
                fig3.update_layout(height=300, margin=dict(l=0,r=0,t=20,b=0)); st.plotly_chart(fig3, use_container_width=True)

    # ------------------------------------------
    # 🇺🇸 Tab 2: 美股 
    # ------------------------------------------
    with tab2:
        s_c = float(us_data['Close']['SOXX'].iloc[-1]); s_d = us_data['Close']['SOXX'].rolling(100).mean().iloc[-1]
        soxl_c = us_live['SOXL']['curr']
        soxl_pred = soxl_c * (1 + (s_d/s_c - 1)*3)
        st.markdown(f"### **SOXX 多頭續抱 | 現價:{s_c:.2f} (100DMA:{s_d:.2f} | 差距: {s_c-s_d:+.2f} / {(s_c/s_d-1)*100:+.2f}%)**")
        st.info(f"💡 **SOXL 壓力預測：** 若 SOXX 跌回 100DMA，SOXL 預估來到 **${soxl_pred:.2f}** (距現值 {((soxl_pred/soxl_c-1)*100):.1f}%)")
        cols = st.columns(3)
        for i, (l, t) in enumerate(zip([3,4,5], [30.14, 21.09, 14.77])):
            cols[i].metric(f"階梯 {l} 目標", f"${t}", f"距 {((soxl_c/t-1)*100):.1f}%", delta_color="inverse")
        st.divider()
        
        us_roi = (total_us_val_usd / total_us_cost_usd - 1) if total_us_cost_usd > 0 else 0
        valid_dates = [v['first_date'] for v in us_live.values() if pd.notnull(v['first_date'])]
        min_date_us = min(valid_dates) if valid_dates else pd.to_datetime('2024-01-01')
        ann_roi_us = ((1+us_roi)**(365/max((datetime.today()-min_date_us).days, 1)) - 1) * 100
        
        u1, u2, u3, u4 = st.columns(4)
        u1.metric("總市值 (USD)", f"${total_us_val_usd:,.0f}"); u2.metric("總投入成本", f"${total_us_cost_usd:,.0f}"); u3.metric("未實現損益", f"{(total_us_val_usd-total_us_cost_usd):+,.0f}", f"{us_roi*100:+.2f}%"); u4.metric("年化報酬", f"{ann_roi_us:+.2f}%")
        
        st.write("---")
        st.write("📈 **美股資產配置比例**")
        if total_us_val_usd > 0:
            us_labels = list(us_live.keys())
            us_values = [info['curr'] * info['shares'] for info in us_live.values()]
            fig_us_pie = go.Figure(data=[go.Pie(labels=us_labels, values=us_values, hole=.4, texttemplate='%{label}<br>$%{value:,.0f}<br>%{percent}')])
            fig_us_pie.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig_us_pie, use_container_width=True)

        st.subheader("📦 個股明細")
        us_table = []
        for t, info in us_live.items():
            avg = info['cost']/info['shares'] if info['shares']>0 else 0
            l_roi = (info['curr']/avg - 1) if avg>0 else 0
            days = (datetime.today()-info['first_date']).days if pd.notnull(info['first_date']) else 1
            l_ann = ((1+l_roi)**(365/max(days,1))-1)*100
            us_table.append({'代號': t, '股數': f"{info['shares']:,.0f}", '均價': f"${avg:.2f}", '成本': f"${info['cost']:,.0f}", '昨日收盤': f"${info['yest']:.2f}", '現價': f"${info['curr']:.2f}", '今日損益': f"{(info['curr']/info['yest']-1)*100:+.2f}%" if info['yest']>0 else "0%", '總損益': f"{l_roi*100:+.1f}%", '年化報酬': f"{l_ann:+.1f}%"})
        st.dataframe(pd.DataFrame(us_table), use_container_width=True, hide_index=True)

        st.write(f"🔹 **實際曝險度：** {((us_live['SOXL']['curr']*us_live['SOXL']['shares']*3 + us_live['BITX']['curr']*us_live['BITX']['shares']*2)*usd_twd/FC*100):.1f}% ｜ **美股佔持股比：** {(total_us_val_twd/(cur_val_tw+total_us_val_twd)*100):.1f}%")

        with st.expander("🛒 新增美股交易紀錄", expanded=False):
            st.warning("⚠️ **Google API 限制：** 若未綁定系統金鑰將無法寫入，請使用下方顯示之格式手動貼入試算表。")
            c_ua, c_ub = st.columns(2); us_date = c_ua.date_input("成交日期", key='u_d'); us_type = c_ub.selectbox("交易類型", ["現股買入", "現股賣出"], key='u_t')
            c_uc, c_ud = st.columns(2); us_tk = c_uc.text_input("股票代號", key='u_tk'); us_pr = c_ud.number_input("成交價格", key='u_p')
            c_ue, c_uf = st.columns(2); us_sh = c_ue.number_input("股數", key='u_s', min_value=0); us_fe = c_uf.number_input("手續費(USD)", key='u_f')
            pre_cost_us = (us_pr*us_sh)+us_fe
            st.info(f"💰 預估美股成本：**US$ {pre_cost_us:,.2f}**")
            if st.button("🚀 嘗試寫入美股", use_container_width=True) and us_sh > 0:
                try:
                    new_us = pd.DataFrame([{"成交日期": us_date.strftime("%Y-%m-%d"), "股票代號": us_tk.upper(), "交易類型": us_type, "成交價格": us_pr, "庫存股數": us_sh, "手續費": us_fe, "持有成本": pre_cost_us}])
                    updated_us = pd.concat([df_us_raw, new_us], ignore_index=True)
                    conn.update(spreadsheet=SHEET_US, data=updated_us)
                    st.success("✅ 美股紀錄上傳成功！")
                except:
                    st.error(f"寫入失敗，請直接貼入表單：\n\n`{us_date.strftime('%Y-%m-%d')}	{us_tk.upper()}	{us_type}	{us_pr}	{us_sh}	{us_fe}	{pre_cost_us}`")

    # ------------------------------------------
    # 🛬 Tab 3: 生命周期 & 退休
    # ------------------------------------------
    with tab3:
        st.subheader("⚖️ 生命周期曝險透視")
        exp_tw = cur_val_tw * 2
        exp_us_usd = us_live['SOXL']['curr']*us_live['SOXL']['shares']*3 + us_live['BITX']['curr']*us_live['BITX']['shares']*2
        exp_us = exp_us_usd * usd_twd
        st.markdown(f"""
        | 戰區 | 曝險金額 (台幣) | 淨資產 (FC) | 實際曝險度 | 美金原值對照 |
        | :--- | :--- | :--- | :--- | :--- |
        | 🇹🇼 台股 | NT$ {exp_tw/10000:,.0f} 萬 | NT$ {(cur_val_tw+cash/2-(loan1+loan2)/2)/10000:,.0f} 萬 | **{(exp_tw/FC*100):.1f}%** | - |
        | 🇺🇸 美股 | NT$ {exp_us/10000:,.0f} 萬 | NT$ {(total_us_val_twd+cash/2-(loan1+loan2)/2)/10000:,.0f} 萬 | **{(exp_us/FC*100):.1f}%** | 曝險: **${exp_us_usd:,.0f}** <br> 淨資產: **${total_us_val_usd:,.0f}** |
        | 🔥 **總計** | **NT$ {(exp_tw+exp_us)/10000:,.0f} 萬** | **NT$ {FC/10000:,.0f} 萬** | **{((exp_tw+exp_us)/FC*100):.1f}%** | (匯率: {usd_twd}) |
        """)
        W = FC + (base_m * 12 * hc_years); target_val = W * (target_k/100)
        c_tgt, c_act = st.columns(2); c_tgt.metric("🎯 生命周期目標曝險度", f"{target_val/FC*100:.1f}%"); c_act.metric("🔥 現在總曝險度", f"{(exp_tw+exp_us)/FC*100:.1f}%", f"差距: {(exp_tw+exp_us)/FC*100 - target_val/FC*100:+.1f}%")
        st.divider(); st.subheader("☕ 退休終局與提領反推")
        f_a = FC
        for _ in range(hc_years): f_a = f_a*1.08 + (base_m*12)
        m_a = (f_a*withdrawal_rate)/12; m_a_now = m_a/((1+inflation_rate)**hc_years)
        st.markdown(f"**📈 情境 A：若工作 {hc_years} 年後退休**")
        ca1, ca2, ca3 = st.columns(3); ca1.metric("屆時滾出資產", f"NT$ {f_a/10000:,.0f} 萬"); ca2.metric("未來每月可領", f"NT$ {m_a:,.0f}"); ca3.metric("約等同現在每月可領", f"NT$ {m_a_now:,.0f}")
        st.write(""); st.markdown(f"**🎯 情境 B：反推我想要月領 {target_monthly_now/10000:.0f} 萬(現值) 的退休金**")
        found_y = None; t_f = FC
        for y in range(1, 41):
            t_f = t_f*1.08 + (base_m*12)
            req_m = target_monthly_now*((1+inflation_rate)**y)
            if t_f >= (req_m*12)/withdrawal_rate: found_y = y; final_f = t_f; final_m = req_m; break
        if found_y:
            cb1, cb2, cb3 = st.columns(3); cb1.metric("需滾出資產", f"NT$ {final_f/10000:,.0f} 萬"); cb2.metric("未來每月可領", f"NT$ {final_m:,.0f}"); cb3.metric("剩餘年限", f"{found_y} 年")
        with st.expander("🛬 降落時程推演表 (Glide Path)", expanded=False):
            gp = []; curr_f = FC
            for y in range(hc_years+1):
                if y>0: curr_f = curr_f*1.08 + (base_m*12)
                h_r = max(0, (base_m*12*hc_years) - (base_m*12*y))
                e_g = ((curr_f + h_r)*target_k/100)/curr_f*100
                gp.append({"年": f"第 {y} 年", "預估資產(萬)": f"{curr_f/10000:,.0f}", "應有曝險": f"{e_g:.1f}%"})
            st.table(pd.DataFrame(gp))

st.caption("📱 提示：版面已升級為極值標註與資產圓餅圖，請安心享用。")
