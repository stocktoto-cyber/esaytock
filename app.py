import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import ta

# --- 頁面設定 ---
st.set_page_config(page_title="台股量價分析 (Neumorphism)", layout="wide")

# --- 【關鍵修改】強力 CSS 注入 (全亮色高對比方案) ---
st.markdown("""
<style>
    /* --- 1. 全域變數 --- */
    :root {
        --bg-color: #EBECF0;        /* 淺灰藍背景 */
        --text-color: #000000;      /* 純黑文字 (最安全) */
        --shadow-light: #FFFFFF;    
        --shadow-dark: #b2bec3;     
    }

    .stApp {
        background-color: var(--bg-color);
        font-family: 'Segoe UI', sans-serif;
        color: var(--text-color);
    }

    /* 側邊欄背景 */
    section[data-testid="stSidebar"] {
        background-color: var(--bg-color);
        box-shadow: inset -5px 0 10px var(--shadow-dark);
    }

    /* 強制所有基本文字為黑色 */
    h1, h2, h3, p, label, span, div, li {
        color: var(--text-color);
    }

    /* --- 【修正核心】下拉選單 (Selectbox) --- */
    
    /* 1. 修正「選單容器 (Popover)」背景 -> 強制白色 */
    div[data-baseweb="popover"],
    ul[data-baseweb="menu"] {
        background-color: #FFFFFF !important;
    }

    /* 2. 修正「選單內的所有選項」文字 -> 強制黑色 */
    ul[data-baseweb="menu"] li div,
    ul[data-baseweb="menu"] li span {
        color: #000000 !important;
    }

    /* 3. 修正「已選擇的項目 (顯示在框框內)」文字 -> 強制黑色 */
    div[data-baseweb="select"] div {
        color: #000000 !important;
    }
    
    /* 4. 修正「輸入框」文字 -> 強制黑色 */
    input {
        color: #000000 !important;
    }

    /* --- 2. 擬物化元件樣式 --- */
    
    /* 輸入框與選單外框 (凹陷效果) */
    .stTextInput input, .stDateInput input, div[data-baseweb="select"] > div {
        background-color: var(--bg-color) !important;
        border: none !important;
        border-radius: 12px !important;
        box-shadow: inset 4px 4px 8px var(--shadow-dark), 
                    inset -4px -4px 8px var(--shadow-light) !important;
        padding: 10px 15px !important;
    }

    /* Metric 卡片 (浮出效果) */
    div[data-testid="stMetric"] {
        background-color: var(--bg-color);
        border-radius: 20px;
        padding: 20px;
        box-shadow: 8px 8px 16px var(--shadow-dark), 
                   -8px -8px 16px var(--shadow-light);
    }
    
    /* 數據顏色 (藍色) */
    div[data-testid="stMetricValue"] > div {
        color: #0984e3 !important;
        font-weight: 700;
        font-size: 28px !important;
    }

    /* 按鈕 (亮橘色浮出) */
    .stButton button {
        background: linear-gradient(145deg, #ffab57, #e68f3c) !important;
        color: white !important; /* 按鈕文字維持白色 */
        border: none !important;
        border-radius: 30px !important;
        box-shadow: 5px 5px 10px #cc7f36, -5px -5px 10px #ffbf60 !important;
        font-weight: bold;
    }
    .stButton button:active {
        box-shadow: inset 3px 3px 6px #cc7f36, inset -3px -3px 6px #ffbf60 !important;
    }
    
    /* 表格與圖表容器 */
    div[data-testid="stDataFrame"] {
        padding: 15px;
        border-radius: 20px;
        background-color: var(--bg-color);
        box-shadow: inset 5px 5px 10px var(--shadow-dark), inset -5px -5px 10px var(--shadow-light);
    }
    
    /* Plotly 背景透明 */
    .js-plotly-plot .plotly .main-svg {
        background: transparent !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 標題 ---
st.markdown("<h1 style='text-align: center; margin-bottom: 30px; letter-spacing: 2px;'>📈 台股量價分析</h1>", unsafe_allow_html=True)

# --- 初始化 Session State ---
if 'run_analysis' not in st.session_state:
    st.session_state.run_analysis = False

# --- 側邊欄 ---
st.sidebar.markdown("### 🔍 搜尋與設定")
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

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ 策略參數")
vol_multiplier = st.sidebar.slider("成交量爆發倍數 (vs 20日均量)", 1.0, 3.0, 1.5, 0.1)

st.sidebar.markdown("### 📉 布林策略")
bb_strategy = st.sidebar.radio(
    "訊號過濾條件",
    ("不限 (僅看成交量)", "爆量 + 站上布林上緣 (強勢)", "爆量 + 跌破布林下緣 (弱勢/反彈)")
)

bb_window = 20
bb_std = 2

st.sidebar.markdown("<br>", unsafe_allow_html=True)

def start_click():
    st.session_state.run_analysis = True

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
            
            color_red = "#FF5252"
            color_green = "#26de81"
            color_orange = "#FF9F43"
            color_blue = "#0984e3"

            signal_color = color_orange
            signal_name = "爆量訊號"
            marker_symbol = "triangle-down"
            signal_y_position = data['High'] * 1.005 
            
            if bb_strategy == "爆量 + 站上布林上緣 (強勢)":
                condition_strategy = condition_vol & (data["Close"] >= data["BB_High"])
                signal_color = color_red
                signal_name = "爆量突破上緣"
                marker_symbol = "triangle-down"
                signal_y_position = data['High'] * 1.005 
            elif bb_strategy == "爆量 + 跌破布林下緣 (弱勢/反彈)":
                condition_strategy = condition_vol & (data["Close"] <= data["BB_Low"])
                signal_color = color_green
                signal_name = "爆量跌破下緣"
                marker_symbol = "triangle-up"
                signal_y_position = data['Low'] * 0.995 
            else:
                condition_strategy = condition_vol

            signals = data[condition_strategy]
            
            # --- 顯示結果 ---
            st.markdown(f"<h3 style='margin-left: 10px;'>📊 {ticker} 分析結果</h3>", unsafe_allow_html=True)
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
            fig.add_trace(go.Candlestick(
                x=data.index,
                open=data['Open'], high=data['High'],
                low=data['Low'], close=data['Close'],
                name='K線'
            ))
            fig.add_trace(go.Scatter(x=data.index, y=data['BB_Mid'], line=dict(color=color_blue, width=2), name='月線 (20MA)'))
            fig.add_trace(go.Scatter(x=data.index, y=data['BB_High'], line=dict(color='#A0A0A0', width=1, dash='dot'), name='布林上緣'))
            fig.add_trace(go.Scatter(x=data.index, y=data['BB_Low'], line=dict(color='#A0A0A0', width=1, dash='dot'), name='布林下緣', fill='tonexty'))

            if not signals.empty:
                plot_y = signal_y_position[signals.index]
                fig.add_trace(go.Scatter(
                    x=signals.index, y=plot_y, mode='markers',
                    marker=dict(symbol=marker_symbol, size=14, color=signal_color, line=dict(width=1, color='white')),
                    name=signal_name
                ))

            fig.update_layout(
                title=dict(text=f"股價走勢圖 ({signal_name})", font=dict(color="#000000", size=20)),
                xaxis_rangeslider_visible=False, 
                height=600,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=20, r=20, t=50, b=20),
                font=dict(family="Segoe UI, sans-serif", color="#000000"),
                xaxis=dict(showgrid=True, gridcolor='#dfe6e9'),
                yaxis=dict(showgrid=True, gridcolor='#dfe6e9')
            )
            
            st.markdown("""
            <div style="background-color: #EBECF0; padding: 20px; border-radius: 20px; box-shadow: 8px 8px 16px #b2bec3, -8px -8px 16px #FFFFFF;">
            """, unsafe_allow_html=True)
            st.plotly_chart(fig, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

            # --- 詳細數據 ---
            st.markdown("<br><h3 style='margin-left: 10px;'>🔎 詳細數據</h3>", unsafe_allow_html=True)
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
    st.markdown("<br><br><div style='text-align: center; color: #636e72;'>👈 請在左側輸入代碼，並按下「🚀 開始執行分析」</div>", unsafe_allow_html=True)
