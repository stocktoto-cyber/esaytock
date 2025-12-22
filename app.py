import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import ta

# --- 1. 頁面設定 ---
st.set_page_config(
    page_title="台股量價回測(手機觸控版)", 
    page_icon="📈",
    layout="centered", 
    initial_sidebar_state="collapsed"
)

# 自訂 CSS 以優化手機版間距
st.markdown("""
    <style>
    .stMetricLabel {font-size: 14px !important;}
    .stMetricValue {font-size: 20px !important;}
    .stPlotlyChart {
        margin-left: -10px; margin-right: -10px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📈 台股量價回測 (觸控優化)")

# --- 初始化 Session State ---
if 'run_analysis' not in st.session_state:
    st.session_state.run_analysis = False

# --- 2. 輸入區塊 ---
col_input, col_btn = st.columns([2.5, 1])
with col_input:
    stock_input = st.text_input("股票代碼", value="00663L", label_visibility="collapsed", placeholder="輸入台股代碼")

if stock_input and not stock_input.endswith('.TW') and not stock_input.endswith('.TWO'):
    ticker = f"{stock_input}.TW"
else:
    ticker = stock_input

# --- 3. 摺疊式設定選單 ---
with st.expander("⚙️ 點此設定日期與策略參數", expanded=False):
    
    st.caption("📅 日期設定")
    period_option = st.selectbox(
        "選擇回測區間",
        ["近一年", "近三年", "近五年", "AI爆發期 (2023-至今)", "疫情期間 (2020-2022)", "自訂日期"]
    )

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
    elif period_option == "自訂日期":
        c_d1, c_d2 = st.columns(2)
        with c_d1:
            start_date = st.date_input("開始", today - timedelta(days=365))
        with c_d2:
            user_end_date = st.date_input("結束", today)
            if user_end_date == today:
                end_date = tomorrow
            else:
                end_date = user_end_date

    st.markdown("---")
    st.caption("📊 策略參數")
    vol_multiplier = st.slider("爆量倍數 (vs 20MA)", 1.0, 3.0, 1.5, 0.1)
    
    bb_strategy = st.radio(
        "訊號過濾條件",
        ("不限 (僅看成交量)", "爆量 + 站上布林上緣", "爆量 + 跌破布林下緣")
    )
    
    bb_tolerance = st.slider("訊號寬容度 (%)", 0.0, 10.0, 1.0, 0.1)
    bb_window = 20
    bb_std = 2

    if st.button("🔄 清除快取並強制更新", use_container_width=True):
        st.cache_data.clear()
        st.session_state.run_analysis = True

# 執行按鈕
with col_btn:
    def start_click():
        st.session_state.run_analysis = True
    st.button("🚀 分析", on_click=start_click, type="primary", use_container_width=True)


# --- 數據處理函數 ---
@st.cache_data(ttl=60, show_spinner=False)
def load_data(ticker, start, end):
    try:
        df = yf.download(ticker, start=str(start), end=str(end), auto_adjust=True, progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex):
            if 'Close' in df.columns.get_level_values(1):
                 df.columns = df.columns.droplevel(0)
            elif 'Close' in df.columns.get_level_values(0):
                 df.columns = df.columns.droplevel(1)
        return df
    except Exception as e:
        st.error(f"資料下載失敗: {e}")
        return None

# --- 主程式邏輯 ---
if st.session_state.run_analysis:
    
    with st.spinner(f"正在分析 {ticker}..."):
        data = load_data(ticker, start_date, end_date)
        
        if data is not None and not data.empty and 'Close' in data.columns:
            data = data.copy()
            data['Volume'] = data['Volume'] / 1000 

            # 指標計算
            indicator_bb = ta.volatility.BollingerBands(close=data["Close"], window=bb_window, window_dev=bb_std)
            data["BB_High"] = indicator_bb.bollinger_hband()
            data["BB_Low"] = indicator_bb.bollinger_lband()
            data["BB_Mid"] = indicator_bb.bollinger_mavg() 
            data["BB_Width"] = data["BB_High"] - data["BB_Low"]
            data["Vol_MA20"] = data["Volume"].rolling(window=20).mean()
        else:
            st.error(f"無法取得 {ticker} 資料，請檢查代碼是否正確。")
            st.stop()

    # --- 4. 最新行情顯示 ---
    latest = data.iloc[-1]
    prev = data.iloc[-2] if len(data) > 1 else latest
    
    diff = latest['Close'] - prev['Close']
    diff_pct = (diff / prev['Close']) * 100
    
    # 【修正點】移除 anchor=False 以相容舊版 Streamlit
    st.subheader(f"🎫 {ticker} 行情") 
    st.caption(f"最新資料日期: {latest.name.strftime('%Y-%m-%d')}")

    m_col1, m_col2 = st.columns(2)
    with m_col1:
        st.metric("收盤價", f"{latest['Close']:.2f}", f"{diff:.2f} ({diff_pct:.2f}%)")
        st.metric("布林上緣", f"{latest['BB_High']:.2f}")
    with m_col2:
        st.metric("成交量 (張)", f"{latest['Volume']:,.0f}")
        st.metric("布林下緣", f"{latest['BB_Low']:.2f}")

    # --- 策略邏輯 ---
    condition_vol = data["Volume"] > (data["Vol_MA20"] * vol_multiplier)
    tolerance_factor = bb_tolerance / 100.0

    if bb_strategy == "爆量 + 站上布林上緣":
        trigger_price = data["BB_High"] * (1 - tolerance_factor)
        condition_strategy = condition_vol & (data["Close"] >= trigger_price)
        signal_color, marker_symbol = "red", "triangle-down"
        signal_y_position = data['High'] * 1.01 
        signal_name = "強勢訊號"
    elif bb_strategy == "爆量 + 跌破布林下緣":
        trigger_price = data["BB_Low"] * (1 + tolerance_factor)
        condition_strategy = condition_vol & (data["Close"] <= trigger_price)
        signal_color, marker_symbol = "green", "triangle-up"
        signal_y_position = data['Low'] * 0.99 
        signal_name = "弱勢訊號"
    else:
        condition_strategy = condition_vol
        signal_color, marker_symbol = "orange", "triangle-down"
        signal_y_position = data['High'] * 1.01
        signal_name = "爆量訊號"

    signals = data[condition_strategy]

    # --- 5. 回測統計 ---
    # 【修正點】移除 anchor=False 以相容舊版 Streamlit
    st.markdown("### 📊 回測績效") 
    roi = ((data['Close'].iloc[-1] - data['Close'].iloc[0]) / data['Close'].iloc[0] * 100)
    
    s1, s2, s3 = st.columns(3)
    s1.metric("區間漲跌", f"{roi:.1f}%")
    s2.metric("觸發次數", f"{len(signals)}")
    s3.metric("目前頻寬", f"{data['BB_Width'].iloc[-1]:.2f}")

    # --- 6. 圖表優化 (含手機觸控功能) ---
    fig = go.Figure()

    # K線
    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data['Open'], high=data['High'],
        low=data['Low'], close=data['Close'],
        name='K線', visible=True
    ))

    # 布林帶
    fig.add_trace(go.Scatter(x=data.index, y=data['BB_High'], line=dict(color='rgba(128,128,128,0.5)', width=1), name='BB Upper', legendgroup="BB"))
    fig.add_trace(go.Scatter(x=data.index, y=data['BB_Low'], line=dict(color='rgba(128,128,128,0.5)', width=1), name='BB Lower', fill='tonexty', fillcolor='rgba(128,128,128,0.1)', legendgroup="BB"))
    fig.add_trace(go.Scatter(x=data.index, y=data['BB_Mid'], line=dict(color='blue', width=1.5), name='MA20', legendgroup="BB"))

    # 訊號
    if not signals.empty:
        plot_y = signal_y_position[signals.index]
        fig.add_trace(go.Scatter(
            x=signals.index, y=plot_y,
            mode='markers',
            marker=dict(symbol=marker_symbol, size=12, color=signal_color, line=dict(width=1, color='white')),
            name=signal_name
        ))

    fig.update_layout(
        title="股價走勢圖 (單指平移/雙指縮放)",
        title_font_size=16,
        height=550,
        margin=dict(l=10, r=10, t=60, b=20),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1,
            bgcolor="rgba(255,255,255,0.6)",
            font=dict(size=11)
        ),
        xaxis=dict(
            rangeslider=dict(visible=True, thickness=0.12),
            type="date",
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1月", step="month", stepmode="backward"),
                    dict(count=3, label="3月", step="month", stepmode="backward"),
                    dict(count=6, label="半年", step="month", stepmode="backward"),
                    dict(step="all", label="全部")
                ]),
                x=0, y=1.01, xanchor='left', yanchor='bottom',
                font=dict(size=11),
                bgcolor="rgba(240,240,240,0.8)"
            )
        ),
        yaxis=dict(
            autorange=True,
            fixedrange=False,
            side="right"
        ),
        dragmode='pan',
        hovermode='x unified',
        hoverlabel=dict(bgcolor="rgba(255,255,255,0.9)", font_size=12)
    )

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': True})

    # --- 7. 詳細數據 ---
    with st.expander("🔎 查看詳細訊號表格"):
        if not signals.empty:
            display_df = signals[['Close', 'Volume', 'BB_High', 'BB_Low']].copy()
            display_df.columns = ['收盤', '量(張)', 'BB上', 'BB下']
            display_df.index = display_df.index.strftime('%Y-%m-%d')
            st.dataframe(display_df.style.format("{:,.0f}", subset=['量(張)']).format("{:.2f}", subset=['收盤', 'BB上', 'BB下']))
        else:
            st.info("此區間內無觸發訊號")

else:
    st.info("👆 請在上方輸入代碼並點擊「🚀 分析」")
