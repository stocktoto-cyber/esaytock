import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import ta

# --- 頁面設定 (手機版面優化) ---
st.set_page_config(page_title="台股量價分析 (Mobile)", layout="wide", initial_sidebar_state="collapsed")

# --- CSS 樣式表 (擬物化 + 手機優化) ---
st.markdown("""
<style>
    /* --- 1. 全域變數 --- */
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

    /* 隱藏側邊欄 (因為我們要把控制項移到主畫面) */
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
    ul[data-baseweb="menu"] li[aria-selected="false"]:hover {
        background-color: #b2bec3 !important;
    }
    ul[data-baseweb="menu"] li[aria-selected="true"] {
        background-color: #2d3436 !important;
        color: #FF9F43 !important;
    }

    /* --- 擬物化元件 --- */
    .stTextInput input, .stDateInput input, div[data-baseweb="select"] > div:first-child {
        background-color: var(--bg-color) !important;
        border: none !important;
        border-radius: 12px !important;
        box-shadow: inset 4px 4px 8px var(--shadow-dark), 
                    inset -4px -4px 8px var(--shadow-light) !important;
        padding: 5px 10px !important;
    }
    
    input { color: #000000 !important; }

    div[data-testid="stMetric"] {
        background-color: var(--bg-color);
        border-radius: 20px;
        padding: 15px; /* 手機版稍微縮小 padding */
        box-shadow: 6px 6px 12px var(--shadow-dark), 
                   -6px -6px 12px var(--shadow-light);
        margin-bottom: 10px;
    }
    
    div[data-testid="stMetricValue"] > div {
        color: #0984e3 !important;
        font-weight: 700;
        font-size: 24px !important; /* 手機版字體微調 */
    }

    /* 按鈕優化 (全寬、好按) */
    .stButton button {
        background: linear-gradient(145deg, #ffab57, #e68f3c) !important;
        color: white !important; 
        border: none !important;
        border-radius: 15px !important; /* 手機版圓角稍微小一點比較好排 */
        box-shadow: 4px 4px 8px #cc7f36, -4px -4px 8px #ffbf60 !important;
        font-weight: bold;
        font-size: 18px !important;
        padding: 15px 0 !important; /* 增加高度，方便手指點擊 */
    }
    .stButton button:active {
        box-shadow: inset 3px 3px 6px #cc7f36, inset -3px -3px 6px #ffbf60 !important;
    }
    
    /* Expander 優化 (讓設定區塊明顯) */
    .streamlit-expanderHeader {
        background-color: var(--bg-color);
        border-radius: 10px;
        box-shadow: 5px 5px 10px var(--shadow-dark), -5px -5px 10px var(--shadow-light);
        color: #000000 !important;
        font-weight: bold;
    }
    
    div[data-testid="stDataFrame"] {
        padding: 10px;
        border-radius: 15px;
        background-color: var(--bg-color);
        box-shadow: inset 4px 4px 8px var(--shadow-dark), inset -4px -4px 8px var(--shadow-light);
    }
    
    .js-plotly-plot .plotly .main-svg {
        background: transparent !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 標題 ---
st.markdown("<h2 style='text-align: center; margin-bottom: 20px; letter-spacing: 1px;'>📈 台股量價分析</h2>", unsafe_allow_html=True)

# --- 初始化 Session State ---
if 'run_analysis' not in st.session_state:
    st.session_state.run_analysis = False

# ==========================================
#  📱 手機版控制面板 (使用 Expander 取代 Sidebar)
# ==========================================
with st.expander("🛠️ 點擊展開/收合 設定面板", expanded=not st.session_state.run_analysis):
    
    # 第一列：股票代碼 + 強制更新
    c1, c2 = st.columns([2, 1]) 
    with c1:
        stock_id = st.text_input("股票代碼 (例: 2330)", value="2330")
    with c2:
        st.write("") # 為了排版對齊
        st.write("") 
        if st.button("🔄 更新", use_container_width=True):
            st.cache_data.clear()
            st.session_state.run_analysis = True

    # 處理代碼後綴
    if stock_id and not stock_id.endswith('.TW') and not stock_id.endswith('.TWO'):
        ticker = f"{stock_id}.TW"
    else:
        ticker = stock_id

    # 第二列：期間選擇
    period_option = st.selectbox(
        "選擇回測區間",
        ["近一年", "近三年", "近五年", "AI爆發期 (2023-至今)", "疫情期間 (2020-2022)", "美中貿易戰 (2018-2019)", "自訂日期"]
    )

    # 日期邏輯
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    start_date = today - timedelta(days=365)
    end_date = tomorrow

    if period_option == "近一年":
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
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            start_date = st.date_input("開始日期", today - timedelta(days=365))
        with col_d2:
            user_end_date = st.date_input("結束日期", today)
            if user_end_date == today:
                end_date = tomorrow
            else:
                end_date = user_end_date

    st.markdown("---") # 分隔線

    # 第三列：策略設定
    st.write("📊 **策略條件設定**")
    
    # 使用 columns 讓手機版也不會太長
    c_strat1, c_strat2 = st.columns(2)
    with c_strat1:
        vol_multiplier = st.slider("成交量倍數", 1.0, 3.0, 1.5, 0.1)
    with c_strat2:
        bb_tolerance = st.slider("寬容度 (%)", 0.0, 10.0, 1.0, 0.1)

    bb_strategy = st.radio(
        "布林篩選條件",
        ("不限 (僅看成交量)", "爆量 + 站上布林上緣 (強勢)", "爆量 + 跌破布林下緣 (弱勢/反彈)")
    )
    
    bb_window = 20
    bb_std = 2

    st.markdown("<br>", unsafe_allow_html=True)
    
    # 執行按鈕 (全寬)
    def start_click():
        st.session_state.run_analysis = True
        
    run_btn = st.button("🚀 開始執行分析", on_click=start_click, use_container_width=True)


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
        data = load_data(ticker, start_date, end_date)

    if data is not None and not data.empty:
        data['Volume'] = data['Volume'] / 1000

        # 指標計算
        indicator_bb = ta.volatility.BollingerBands(close=data["Close"], window=bb_window, window_dev=bb_std)
        data["BB_High"] = indicator_bb.bollinger_hband()
        data["BB_Low"] = indicator_bb.bollinger_lband()
        data["BB_Mid"] = indicator_bb.bollinger_mavg() 
        data["BB_Width"] = data["BB_High"] - data["BB_Low"]
        data["Vol_MA20"] = data["Volume"].rolling(window=20).mean()

        # ----------------------------------
        # 最新行情 (手機版適合用 2x2 排列)
        latest = data.iloc[-1]
        prev = data.iloc[-2] if len(data) > 1 else latest
        latest_date_str = latest.name.strftime('%Y-%m-%d')
        
        st.markdown(f"#### 🎫 最新行情 ({latest_date_str})")
        
        diff = latest['Close'] - prev['Close']
        diff_pct = (diff / prev['Close']) * 100
        
        # 使用 columns 讓 metrics 在手機上不會變成一條長龍
        m_row1_1, m_row1_2 = st.columns(2)
        with m_row1_1:
            st.metric("目前股價", f"{latest['Close']:.2f}", f"{diff:.2f} ({diff_pct:.2f}%)")
        with m_row1_2:
            st.metric("最新成交量", f"{latest['Volume']:,.0f} 張")
            
        m_row2_1, m_row2_2 = st.columns(2)
        with m_row2_1:
            st.metric("布林上緣", f"{latest['BB_High']:.2f}")
        with m_row2_2:
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
            signal_name = f"爆量近上緣 (寬容度{bb_tolerance}%)"
            marker_symbol = "triangle-down"
            signal_y_position = data['High'] * 1.005 

        elif bb_strategy == "爆量 + 跌破布林下緣 (弱勢/反彈)":
            trigger_price = data["BB_Low"] * (1 + tolerance_factor)
            condition_strategy = condition_vol & (data["Close"] <= trigger_price)
            signal_color = "green"
            signal_name = f"爆量近下緣 (寬容度{bb_tolerance}%)"
            marker_symbol = "triangle-up"
            signal_y_position = data['Low'] * 0.995 

        else:
            condition_strategy = condition_vol
            signal_color = "orange"
            signal_name = "爆量訊號"
            marker_symbol = "triangle-down"
            signal_y_position = data['High'] * 1.005

        signals = data[condition_strategy]
        
        # 回測結果
        st.markdown(f"#### 📊 策略分析: {bb_strategy}")
        
        c1, c2, c3 = st.columns(3)
        if len(data) > 0:
            roi = ((data['Close'].iloc[-1] - data['Close'].iloc[0]) / data['Close'].iloc[0] * 100)
            c1.metric("區間漲跌幅", f"{roi:.2f}%")
            c2.metric("符合天數", f"{len(signals)} 天")
            c3.metric("最新通道寬", f"{data['BB_Width'].iloc[-1]:.2f}")

        # 繪圖
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=data.index,
            open=data['Open'], high=data['High'],
            low=data['Low'], close=data['Close'],
            name='K線'
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
            title=f"走勢圖 (已還原權值)", 
            xaxis_rangeslider_visible=False, 
            height=500, # 手機版圖表高度稍微縮小一點方便瀏覽
            margin=dict(l=10, r=10, t=40, b=10) # 減少邊界，利用手機螢幕寬度
        )
        st.plotly_chart(fig, use_container_width=True)

        # 詳細數據
        st.markdown("#### 🔎 詳細數據")
        if not signals.empty:
            display_df = signals[['Close', 'Volume', 'Vol_MA20', 'BB_High', 'BB_Low', 'BB_Width']].copy()
            display_df['Volume_Ratio'] = display_df['Volume'] / display_df['Vol_MA20']

            display_df.columns = ['收盤', '成交量', '月均量', '上緣', '下緣', '寬度', '量倍數'] # 縮短欄位名稱以適應手機
            display_df.index.name = '日期'

            formatted_df = display_df.style.format({
                '收盤': '{:.2f}', '成交量': '{:,.0f}', '月均量': '{:,.0f}',
                '上緣': '{:.2f}', '下緣': '{:.2f}', '寬度': '{:.2f}', '量倍數': '{:.2f}倍'
            })
            
            st.dataframe(formatted_df, use_container_width=True)
        else:
            st.warning("此區間無符合策略之交易日。")
    else:
        st.error(f"找不到代碼 {ticker} 或資料未更新。")
else:
    st.info("👆 請點擊上方展開設定，並按下「🚀 開始執行分析」。")
