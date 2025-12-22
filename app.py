import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import ta

# --- 頁面設定 ---
st.set_page_config(page_title="台股量價分析 (iOS Style)", layout="wide", initial_sidebar_state="expanded")

# --- 【關鍵修改】強力 iOS 風格 CSS 注入 (修復對比度問題) ---
st.markdown("""
<style>
    /* --- 全域變數定義 (強制淺色主題色票) --- */
    :root {
        --ios-bg-main: #F2F2F7;       /* iOS 系統背景灰 */
        --ios-bg-secondary: #FFFFFF;  /* iOS 卡片白 */
        --ios-text-primary: #000000;  /* 深黑文字 */
        --ios-text-secondary: #8E8E93;/* 淺灰說明文字 */
        --ios-blue: #007AFF;          /* iOS 系統藍 */
        --ios-red: #FF3B30;           /* iOS 系統紅 */
        --ios-green: #34C759;         /* iOS 系統綠 */
        --ios-orange: #FF9500;        /* iOS 系統橘 */
        --font-stack: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    /* 強制全域字體與背景色 */
    html, body, .stApp {
        font-family: var(--font-stack) !important;
        background-color: var(--ios-bg-main) !important;
        color: var(--ios-text-primary) !important;
    }

    /* --- 側邊欄優化 --- */
    section[data-testid="stSidebar"] {
        background-color: var(--ios-bg-secondary) !important;
        border-right: 1px solid #E5E5EA;
        box-shadow: none !important;
    }
    
    /* 強制側邊欄所有文字為深色 */
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3, 
    section[data-testid="stSidebar"] label, 
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] div {
        color: var(--ios-text-primary) !important;
    }

    /* --- 輸入元件優化 (圓角 + 白底黑字) --- */
    /* 文字輸入框、日期選擇器 */
    .stTextInput input, .stDateInput input {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 1px solid #D1D1D6 !important;
        border-radius: 12px !important;
        padding: 10px !important;
    }
    /* 下拉選單與 Radio 按鈕 */
    div[data-baseweb="select"] > div, div[role="radiogroup"] {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border-radius: 12px !important;
        border: 1px solid #D1D1D6 !important;
    }
    /* 滑桿文字顏色 */
    div[data-testid="stSlider"] label {
        color: var(--ios-text-primary) !important;
    }

    /* --- 主畫面元件優化 --- */
    /* 標題強制深色 */
    h1, h2, h3, .plotly-graph-div title {
        color: var(--ios-text-primary) !important;
        font-weight: 700 !important;
    }

    /* Metric 卡片化設計 (關鍵修復) */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF !important;
        padding: 20px !important;
        border-radius: 20px !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08) !important;
        border: none !important;
        text-align: center;
    }
    /* Metric 標籤 (淺灰) */
    div[data-testid="stMetricLabel"] > label {
        color: var(--ios-text-secondary) !important;
        font-size: 14px !important;
        font-weight: 500 !important;
    }
    /* Metric 數值 (深黑大字) */
    div[data-testid="stMetricValue"] > div {
        color: var(--ios-text-primary) !important;
        font-size: 32px !important;
        font-weight: 700 !important;
        padding-top: 5px;
    }

    /* 按鈕樣式 (iOS 藍) */
    .stButton button {
        background-color: var(--ios-blue) !important;
        color: white !important;
        border-radius: 16px !important;
        border: none !important;
        padding: 12px 28px !important;
        font-weight: 600 !important;
        font-size: 17px !important;
        width: 100%; /* 按鈕填滿寬度 */
        box-shadow: 0 4px 10px rgba(0, 122, 255, 0.3);
    }
    .stButton button:hover { box-shadow: 0 6px 15px rgba(0, 122, 255, 0.4); }
    .stButton button:active { transform: scale(0.98); }

    /* 表格樣式優化 (白底黑字) */
    div[data-testid="stDataFrame"] {
        background-color: #FFFFFF;
        padding: 15px;
        border-radius: 20px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    }
    div[data-testid="stDataFrame"] * {
        color: var(--ios-text-primary) !important;
        font-family: var(--font-stack) !important;
    }
    
    /* Plotly 圖表背景修正 */
    .js-plotly-plot .plotly .main-svg {
        background-color: rgba(0,0,0,0) !important; /* 讓圖表背景透明，透出網頁背景 */
    }
</style>
""", unsafe_allow_html=True)

# --- 主標題 (使用 HTML 讓它更像 App 標題) ---
st.markdown(f"<h1 style='text-align: center; color: #000000; margin-bottom: 30px;'>📈 台股量價分析</h1>", unsafe_allow_html=True)

# --- 初始化 Session State ---
if 'run_analysis' not in st.session_state:
    st.session_state.run_analysis = False

# --- 側邊欄 ---
st.sidebar.header("1. 股票與期間")
stock_id = st.sidebar.text_input("輸入股票代碼", value="2330")

if stock_id and not stock_id.endswith('.TW') and not stock_id.endswith('.TWO'):
    ticker = f"{stock_id}.TW"
else:
    ticker = stock_id

period_option = st.sidebar.selectbox(
    "選擇回測區間",
    ["近一年", "近三年", "近五年", "AI爆發期 (2023-至今)", "疫情期間 (2020-2022)", "美中貿易戰 (2018-2019)", "自訂日期"]
)

today = datetime.now().date()
start_date = today - timedelta(days=365)
end_date = today

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
    col_d1, col_d2 = st.sidebar.columns(2)
    with col_d1:
        start_date = st.date_input("開始日期", today - timedelta(days=365))
    with col_d2:
        end_date = st.date_input("結束日期", today)

st.sidebar.header("2. 策略參數設定")
vol_multiplier = st.sidebar.slider("成交量爆發倍數 (vs 20日均量)", 1.0, 3.0, 1.5, 0.1)

st.sidebar.subheader("布林通道位置篩選")
bb_strategy = st.sidebar.radio(
    "選擇訊號過濾條件",
    ("不限 (僅看成交量)", "爆量 + 站上布林上緣 (強勢)", "爆量 + 跌破布林下緣 (弱勢/反彈)")
)

bb_window = 20
bb_std = 2

st.sidebar.markdown("---")
def start_click():
    st.session_state.run_analysis = True

# 按鈕 (CSS 會自動套用 iOS 藍色樣式)
run_btn = st.sidebar.button("🚀 開始執行分析", on_click=start_click)

# --- 數據處理 ---
@st.cache_data
def load_data(ticker, start, end):
    try:
        df = yf.download(ticker, start=str(start), end=str(end))
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
        return df
    except Exception: return None

# --- 主程式邏輯 ---
if st.session_state.run_analysis:
    if start_date > end_date:
        st.error("錯誤：開始日期不能晚於結束日期。")
    else:
        with st.spinner(f"正在分析 {ticker} ..."):
            data = load_data(ticker, start_date, end_date)

        if data is not None and not data.empty:
            data['Volume'] = data['Volume'] / 1000

            # 計算指標
            indicator_bb = ta.volatility.BollingerBands(close=data["Close"], window=bb_window, window_dev=bb_std)
            data["BB_High"] = indicator_bb.bollinger_hband()
            data["BB_Low"] = indicator_bb.bollinger_lband()
            data["BB_Mid"] = indicator_bb.bollinger_mavg() 
            data["BB_Width"] = data["BB_High"] - data["BB_Low"]
            data["Vol_MA20"] = data["Volume"].rolling(window=20).mean()

            # 篩選訊號
            condition_vol = data["Volume"] > (data["Vol_MA20"] * vol_multiplier)
            
            # iOS 色票定義
            ios_red = "#FF3B30"
            ios_green = "#34C759"
            ios_orange = "#FF9500"
            ios_blue = "#007AFF"

            signal_color = ios_orange
            signal_name = "爆量訊號"
            marker_symbol = "triangle-down"
            signal_y_position = data['High'] * 1.005 
            
            if bb_strategy == "爆量 + 站上布林上緣 (強勢)":
                condition_strategy = condition_vol & (data["Close"] >= data["BB_High"])
                signal_color = ios_red
                signal_name = "爆量突破上緣"
                marker_symbol = "triangle-down"
                signal_y_position = data['High'] * 1.005 
            elif bb_strategy == "爆量 + 跌破布林下緣 (弱勢/反彈)":
                condition_strategy = condition_vol & (data["Close"] <= data["BB_Low"])
                signal_color = ios_green
                signal_name = "爆量跌破下緣"
                marker_symbol = "triangle-up"
                signal_y_position = data['Low'] * 0.995 
            else:
                condition_strategy = condition_vol

            signals = data[condition_strategy]
            
            # --- 顯示結果 (iOS 卡片風格) ---
            st.markdown(f"<h3 style='color: black;'>📊 {ticker} 分析結果 | 策略: {bb_strategy}</h3>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
            if len(data) > 0:
                roi = ((data['Close'].iloc[-1] - data['Close'].iloc[0]) / data['Close'].iloc[0] * 100)
                col1.metric("區間漲跌幅", f"{roi:.2f}%")
                col2.metric("符合策略天數", f"{len(signals)} 天")
                col3.metric("最新布林寬度", f"{data['BB_Width'].iloc[-1]:.2f}")

            st.markdown("<br>", unsafe_allow_html=True)

            # --- 繪圖 ---
            fig = go.Figure()

            # K線
            fig.add_trace(go.Candlestick(
                x=data.index,
                open=data['Open'], high=data['High'],
                low=data['Low'], close=data['Close'],
                name='K線'
            ))

            # 月線 (20MA) - 使用 iOS 藍
            fig.add_trace(go.Scatter(x=data.index, y=data['BB_Mid'], line=dict(color=ios_blue, width=1.5), name='月線 (20MA)'))

            # 布林通道
            fig.add_trace(go.Scatter(x=data.index, y=data['BB_High'], line=dict(color='gray', width=1, dash='dot'), name='布林上緣'))
            fig.add_trace(go.Scatter(x=data.index, y=data['BB_Low'], line=dict(color='gray', width=1, dash='dot'), name='布林下緣', fill='tonexty'))

            # 標記訊號
            if not signals.empty:
                plot_y = signal_y_position[signals.index]
                fig.add_trace(go.Scatter(
                    x=signals.index, y=plot_y, mode='markers',
                    marker=dict(symbol=marker_symbol, size=12, color=signal_color),
                    name=signal_name
                ))

            fig.update_layout(
                title=dict(text=f"股價走勢圖 ({signal_name})", font=dict(color="black", size=20)),
                xaxis_rangeslider_visible=False, 
                height=600,
                paper_bgcolor='rgba(0,0,0,0)', # 讓圖表外框透明
                plot_bgcolor='#FFFFFF',        # 繪圖區維持白色
                margin=dict(l=20, r=20, t=50, b=20),
                font=dict(family="-apple-system, BlinkMacSystemFont, sans-serif", color="black"), # 強制圖表文字黑色
                xaxis=dict(showgrid=True, gridcolor='#E5E5EA'), # 網格線改淺灰
                yaxis=dict(showgrid=True, gridcolor='#E5E5EA')
            )
            st.plotly_chart(fig, use_container_width=True)

            # --- 詳細數據表格 (白底黑字) ---
            st.markdown("<h3 style='color: black; margin-top: 30px;'>🔎 策略訊號詳細數據</h3>", unsafe_allow_html=True)
            if not signals.empty:
                display_df = signals[['Close', 'Volume', 'Vol_MA20', 'BB_High', 'BB_Low', 'BB_Width']].copy()
                display_df['Volume_Ratio'] = display_df['Volume'] / display_df['Vol_MA20']
                display_df.columns = ['收盤價', '成交量 (張)', '月均量', '布林上緣', '布林下緣', '通道寬度', '量增倍數']
                display_df.index.name = '日期'
                formatted_df = display_df.style.format({
                    '收盤價': '{:.2f}', '成交量 (張)': '{:,.0f}', '月均量': '{:,.0f}',
                    '布林上緣': '{:.2f}', '布林下緣': '{:.2f}', '通道寬度': '{:.2f}', '量增倍數': '{:.2f}倍'
                })
                st.dataframe(formatted_df)
            else:
                st.warning("在此區間內，沒有發現符合「策略條件」的交易日。")
        else:
            st.error(f"找不到代碼 {ticker} 的資料。")
else:
    # 初始畫面提示 (深色文字)
    st.markdown("<div style='text-align: center; color: #8E8E93; padding: 50px;'>👈 請在左側設定參數，並按下「🚀 開始執行分析」按鈕。</div>", unsafe_allow_html=True)
