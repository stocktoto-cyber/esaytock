import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import ta

# --- 頁面設定 (手機優先) ---
st.set_page_config(page_title="台股量價分析 (Mobile)", layout="wide", initial_sidebar_state="collapsed")

# --- CSS 樣式表 (手機版優化 + 高對比配色) ---
st.markdown("""
<style>
    /* --- 全域設定 --- */
    :root {
        --bg-color: #EBECF0;
        --text-color: #000000;
        --shadow-light: #FFFFFF;
        --shadow-dark: #b2bec3;
    }

    .stApp {
        background-color: var(--bg-color);
        font-family: 'Segoe UI', sans-serif;
        color: var(--text-color);
    }

    /* 隱藏側邊欄 (手機版改用 Expander) */
    [data-testid="stSidebar"] {
        display: none;
    }

    /* 全域文字預設黑色 */
    h1, h2, h3, p, label, span, div {
        color: var(--text-color);
    }

    /* --- 下拉選單顏色修正 --- */
    div[data-baseweb="select"] > div {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        background-color: transparent !important;
    }
    ul[data-baseweb="menu"] {
        background-color: #636e72 !important;
    }
    ul[data-baseweb="menu"] li div,
    ul[data-baseweb="menu"] li span {
        color: #FFFFFF !important;
    }
    
    /* --- 元件擬物化風格 --- */
    .stTextInput input, .stDateInput input, div[data-baseweb="select"] > div:first-child {
        background-color: var(--bg-color) !important;
        border: none !important;
        border-radius: 12px !important;
        box-shadow: inset 3px 3px 6px var(--shadow-dark), 
                    inset -3px -3px 6px var(--shadow-light) !important;
        padding: 8px 10px !important;
    }
    input { color: #000000 !important; }

    /* Metric 卡片 */
    div[data-testid="stMetric"] {
        background-color: var(--bg-color);
        border-radius: 15px;
        padding: 10px;
        box-shadow: 5px 5px 10px var(--shadow-dark), 
                   -5px -5px 10px var(--shadow-light);
        margin-bottom: 8px;
    }
    div[data-testid="stMetricValue"] > div {
        color: #0984e3 !important;
        font-weight: 700;
        font-size: 22px !important;
    }

    /* 按鈕優化 */
    .stButton button {
        background: linear-gradient(145deg, #ffab57, #e68f3c) !important;
        color: white !important; 
        border: none !important;
        border-radius: 12px !important;
        box-shadow: 4px 4px 8px #cc7f36, -4px -4px 8px #ffbf60 !important;
        font-weight: bold;
        font-size: 18px !important;
        padding: 12px 0 !important;
        width: 100%;
    }
    .stButton button:active {
        box-shadow: inset 3px 3px 6px #cc7f36, inset -3px -3px 6px #ffbf60 !important;
    }

    .streamlit-expanderHeader {
        background-color: var(--bg-color);
        border-radius: 10px;
        box-shadow: 3px 3px 6px var(--shadow-dark), -3px -3px 6px var(--shadow-light);
        color: #000000 !important;
        font-weight: bold;
        margin-bottom: 10px;
    }
    
    .js-plotly-plot .plotly .main-svg {
        background: transparent !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 標題 ---
st.markdown("<h3 style='text-align: center; margin-bottom: 15px;'>📈 台股量價分析 (Mobile)</h3>", unsafe_allow_html=True)

# --- 初始化 Session State ---
if 'run_analysis' not in st.session_state:
    st.session_state.run_analysis = False

# ==========================================
#  📱 手機版控制面板 (Expander)
# ==========================================
with st.expander("🛠️ 點擊展開設定 (股票/日期/策略)", expanded=not st.session_state.run_analysis):
    
    # Row 1: 股票代碼 + 強制更新
    c1, c2 = st.columns([2, 1])
    with c1:
        stock_id = st.text_input("股票代碼", value="00663L")
    with c2:
        st.write("") 
        st.write("") 
        if st.button("🔄 更新", key="update_btn"):
            st.cache_data.clear()
            st.session_state.run_analysis = True

    if stock_id and not stock_id.endswith('.TW') and not stock_id.endswith('.TWO'):
        ticker = f"{stock_id}.TW"
    else:
        ticker = stock_id

    # Row 2: 回測區間 (加入 "近一週")
    period_option = st.selectbox(
        "選擇回測區間",
        ["近一週", "近一年", "近三年", "近五年", "AI爆發期 (2023-至今)", "疫情期間 (2020-2022)", "美中貿易戰 (2018-2019)", "自訂日期"]
    )

    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    
    # 預設結束時間為明天 (確保 yfinance 能抓到今天)
    end_date = tomorrow
    
    # 設定開始時間
    if period_option == "近一週":
        start_date = today - timedelta(days=7)
    elif period_option == "近一年":
        start_date = today - timedelta(days=365)
    elif period_option == "近三年":
        start_date = today - timedelta(days=365*3)
    elif period_option == "近五年":
        start_date = today - timedelta(days=365*5)
    elif period_option == "AI爆發期 (2023-至今)":
        start_date = date(2023, 1, 1)
    elif period_option == "疫情期間 (2020-2022)":
        start_date = date(2020, 1, 1)
        end_date = date(2022, 12, 31)
    elif period_option == "美中貿易戰 (2018-2019)":
        start_date = date(2018, 1, 1)
        end_date = date(2020, 1, 15)
    elif period_option == "自訂日期":
        d_col1, d_col2 = st.columns(2)
        with d_col1:
            start_date = st.date_input("開始", today - timedelta(days=365))
        with d_col2:
            user_end_date = st.date_input("結束", today)
            if user_end_date == today:
                end_date = tomorrow
            else:
                end_date = user_end_date

    st.markdown("---")

    # Row 3: 策略參數
    st.write("📊 **策略參數**")
    s_col1, s_col2 = st.columns(2)
    with s_col1:
        vol_multiplier = st.slider("量增倍數", 1.0, 3.0, 1.5, 0.1)
    with s_col2:
        bb_tolerance = st.slider("寬容度(%)", 0.0, 10.0, 1.0, 0.1)

    bb_strategy = st.radio(
        "訊號條件",
        ("不限 (僅看成交量)", "爆量 + 站上布林上緣 (強勢)", "爆量 + 跌破布林下緣 (弱勢/反彈)")
    )
    
    bb_window = 20
    bb_std = 2

    st.markdown("<br>", unsafe_allow_html=True)
    
    def start_click():
        st.session_state.run_analysis = True
    
    st.button("🚀 開始執行分析", on_click=start_click, type="primary", use_container_width=True)


# --- 數據處理函數 ---
@st.cache_data(ttl=60)
def load_data(ticker, start, end):
    try:
        df = yf.download(ticker, start=str(start), end=str(end), auto_adjust=True)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
        return df
    except Exception: return None

# --- 主程式邏輯 ---
if st.session_state.run_analysis:
    if start_date >= end_date:
         pass 

    with st.spinner(f"正在分析 {ticker} ..."):
        # 【關鍵技巧】多抓 30 天資料 (Buffer) 讓布林通道能算出，否則短天期會沒指標
        fetch_start = start_date - timedelta(days=30)
        data = load_data(ticker, fetch_start, end_date)

    if data is not None and not data.empty:
        data['Volume'] = data['Volume'] / 1000

        # 指標計算 (使用包含 Buffer 的資料計算，數值才會準)
        indicator_bb = ta.volatility.BollingerBands(close=data["Close"], window=bb_window, window_dev=bb_std)
        data["BB_High"] = indicator_bb.bollinger_hband()
        data["BB_Low"] = indicator_bb.bollinger_lband()
        data["BB_Mid"] = indicator_bb.bollinger_mavg() 
        data["BB_Width"] = data["BB_High"] - data["BB_Low"]
        data["Vol_MA20"] = data["Volume"].rolling(window=20).mean()

        # 【關鍵裁切】算完指標後，裁切回使用者想看的日期
        # 轉換 date 格式以進行比較
        data = data[data.index.date >= start_date]

        # 如果裁切後沒資料 (例如使用者選的區間剛好休市)
        if data.empty:
            st.error("選定區間無交易資料，請調整日期。")
        else:
            # ----------------------------------
            # 最新行情儀表板
            latest = data.iloc[-1]
            # 嘗試抓前一筆 (若資料只有一筆，就用自己)
            prev = data.iloc[-2] if len(data) > 1 else latest
            
            latest_date_str = latest.name.strftime('%Y-%m-%d')
            diff = latest['Close'] - prev['Close']
            diff_pct = (diff / prev['Close']) * 100 if prev['Close'] != 0 else 0

            st.markdown(f"**🎫 最新行情: {latest_date_str}**")
            
            m1, m2 = st.columns(2)
            with m1:
                st.metric("收盤價", f"{latest['Close']:.2f}", f"{diff:.2f} ({diff_pct:.2f}%)")
            with m2:
                st.metric("成交量", f"{latest['Volume']:,.0f} 張")
                
            m3, m4 = st.columns(2)
            with m3:
                st.metric("布林上緣", f"{latest['BB_High']:.2f}")
            with m4:
                st.metric("布林下緣", f"{latest['BB_Low']:.2f}")

            st.markdown("---")
            # ----------------------------------

            # 策略篩選
            condition_vol = data["Volume"] > (data["Vol_MA20"] * vol_multiplier)
            signal_color = "orange"
            signal_name = "爆量訊號"
            marker_symbol = "triangle-down"
            signal_y_position = data['High'] * 1.005 
            
            tolerance_factor = bb_tolerance / 100.0

            if bb_strategy == "爆量 + 站上布林上緣 (強勢)":
                trigger_price = data["BB_High"] * (1 - tolerance_factor)
                condition_strategy = condition_vol & (data["Close"] >= trigger_price)
                signal_color = "red"
                signal_name = f"爆量近上緣({bb_tolerance}%)"
                marker_symbol = "triangle-down"
                signal_y_position = data['High'] * 1.005 
            elif bb_strategy == "爆量 + 跌破布林下緣 (弱勢/反彈)":
                trigger_price = data["BB_Low"] * (1 + tolerance_factor)
                condition_strategy = condition_vol & (data["Close"] <= trigger_price)
                signal_color = "green"
                signal_name = f"爆量近下緣({bb_tolerance}%)"
                marker_symbol = "triangle-up"
                signal_y_position = data['Low'] * 0.995 
            else:
                condition_strategy = condition_vol
                signal_color = "orange"
                signal_name = "爆量訊號"
                marker_symbol = "triangle-down"
                signal_y_position = data['High'] * 1.005

            signals = data[condition_strategy]
            
            # ----------------------------------
            # 📊 歷史回測結果
            # ----------------------------------
            st.markdown(f"**📊 回測結果: {bb_strategy}**")
            
            # 計算平均買價
            if not signals.empty:
                avg_buy_price = signals['Close'].mean()
                avg_price_str = f"{avg_buy_price:.2f}"
            else:
                avg_price_str = "N/A"

            if len(data) > 0:
                roi = ((data['Close'].iloc[-1] - data['Close'].iloc[0]) / data['Close'].iloc[0] * 100)
                
                # 第一排：漲跌幅 & 平均買價
                r1, r2 = st.columns(2)
                with r1:
                    st.metric("區間漲跌", f"{roi:.1f}%")
                with r2:
                    st.metric("策略平均買價", avg_price_str)
                
                # 第二排：訊號天數 & 通道寬度
                r3, r4 = st.columns(2)
                with r3:
                    st.metric("符合天數", f"{len(signals)}")
                with r4:
                    st.metric("通道寬", f"{data['BB_Width'].iloc[-1]:.1f}")

            # 繪圖
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=data.index, open=data['Open'], high=data['High'],
                low=data['Low'], close=data['Close'], name='K線'
            ))
            fig.add_trace(go.Scatter(x=data.index, y=data['BB_Mid'], line=dict(color='blue', width=1.5), name='20MA'))
            fig.add_trace(go.Scatter(x=data.index, y=data['BB_High'], line=dict(color='gray', width=1, dash='dot'), name='上緣'))
            fig.add_trace(go.Scatter(x=data.index, y=data['BB_Low'], line=dict(color='gray', width=1, dash='dot'), name='下緣', fill='tonexty'))

            if not signals.empty:
                plot_y = signal_y_position[signals.index]
                fig.add_trace(go.Scatter(
                    x=signals.index, y=plot_y, mode='markers',
                    marker=dict(symbol=marker_symbol, size=12, color=signal_color),
                    name=signal_name
                ))

            fig.update_layout(
                title=f"股價走勢 ({ticker})", 
                xaxis_rangeslider_visible=False, 
                height=500, 
                margin=dict(l=10, r=10, t=30, b=10), 
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1) 
            )
            st.plotly_chart(fig, use_container_width=True)

            # 詳細數據
            st.markdown("**🔎 詳細數據**")
            if not signals.empty:
                display_df = signals[['Close', 'Volume', 'Vol_MA20', 'BB_High', 'BB_Low', 'BB_Width']].copy()
                display_df['Volume_Ratio'] = display_df['Volume'] / display_df['Vol_MA20']
                
                display_df.columns = ['收盤', '成交量', '月均量', '上緣', '下緣', '寬度', '量倍數']
                display_df.index.name = '日期'

                formatted_df = display_df.style.format({
                    '收盤': '{:.2f}', '成交量': '{:,.0f}', '月均量': '{:,.0f}',
                    '上緣': '{:.2f}', '下緣': '{:.2f}', '寬度': '{:.2f}', '量倍數': '{:.2f}'
                })
                
                st.dataframe(formatted_df, use_container_width=True)
            else:
                st.warning("此區間無符合條件交易日")
    else:
        st.error(f"無法取得資料: {ticker} (請確認代碼或更新)")
else:
    st.info("👆 請點擊上方展開設定，並按下「🚀 開始執行分析」")
