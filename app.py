import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import ta

# --- 頁面設定 ---
st.set_page_config(page_title="台股量價回測系統", layout="wide")
st.title("📈 台股量價與布林通道回測工具")

# --- 初始化 Session State (用於控制按鈕狀態) ---
if 'run_analysis' not in st.session_state:
    st.session_state.run_analysis = False

# --- 側邊欄：控制面板 ---
st.sidebar.header("1. 股票與期間")
stock_id = st.sidebar.text_input("輸入股票代碼", value="2330")

# 自動補全 .TW
if stock_id and not stock_id.endswith('.TW') and not stock_id.endswith('.TWO'):
    ticker = f"{stock_id}.TW"
else:
    ticker = stock_id

period_option = st.sidebar.selectbox(
    "選擇回測區間",
    ["近一年", "近三年", "近五年", "AI爆發期 (2023-至今)", "疫情期間 (2020-2022)", "美中貿易戰 (2018-2019)", "自訂日期"]
)

# 日期邏輯
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

# 【新增功能】布林通道篩選策略
st.sidebar.subheader("布林通道位置篩選")
bb_strategy = st.sidebar.radio(
    "選擇訊號過濾條件",
    ("不限 (僅看成交量)", "爆量 + 站上布林上緣 (強勢)", "爆量 + 跌破布林下緣 (弱勢/反彈)")
)

bb_window = 20
bb_std = 2

st.sidebar.markdown("---")
# 【新增功能】執行按鈕 (放在側邊欄最下方)
# 使用 callback 來更新狀態，確保按鈕按下後圖表不會因為互動而消失
def start_click():
    st.session_state.run_analysis = True

run_btn = st.sidebar.button("🚀 開始執行分析", on_click=start_click, type="primary")

# --- 數據處理函數 ---
@st.cache_data
def load_data(ticker, start, end):
    try:
        df = yf.download(ticker, start=str(start), end=str(end))
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        return df
    except Exception:
        return None

# --- 主程式邏輯 (只有當按鈕被按下過，才會執行) ---
if st.session_state.run_analysis:
    
    # 檢查日期
    if start_date > end_date:
        st.error("錯誤：開始日期不能晚於結束日期。")
    else:
        with st.spinner(f"正在分析 {ticker} ..."):
            data = load_data(ticker, start_date, end_date)

        if data is not None and not data.empty:
            # 單位換算：股 -> 張
            data['Volume'] = data['Volume'] / 1000

            # 1. 計算技術指標
            indicator_bb = ta.volatility.BollingerBands(close=data["Close"], window=bb_window, window_dev=bb_std)
            data["BB_High"] = indicator_bb.bollinger_hband()
            data["BB_Low"] = indicator_bb.bollinger_lband()
            data["BB_Mid"] = indicator_bb.bollinger_mavg()
            data["BB_Width"] = data["BB_High"] - data["BB_Low"]
            data["Vol_MA20"] = data["Volume"].rolling(window=20).mean()

            # 2. 篩選策略訊號 (結合 成交量 + 布林位置)
            # 基礎條件：成交量爆發
            condition_vol = data["Volume"] > (data["Vol_MA20"] * vol_multiplier)
            
            # 加上布林條件
            if bb_strategy == "爆量 + 站上布林上緣 (強勢)":
                # 收盤價 >= 上緣
                condition_strategy = condition_vol & (data["Close"] >= data["BB_High"])
                signal_color = "red" # 紅色代表強勢/多方
                signal_name = "爆量突破上緣"
            elif bb_strategy == "爆量 + 跌破布林下緣 (弱勢/反彈)":
                # 收盤價 <= 下緣
                condition_strategy = condition_vol & (data["Close"] <= data["BB_Low"])
                signal_color = "green" # 綠色代表弱勢/空方 (或在此視為抄底訊號)
                signal_name = "爆量跌破下緣"
            else:
                # 不限
                condition_strategy = condition_vol
                signal_color = "orange"
                signal_name = "爆量訊號"

            signals = data[condition_strategy]
            
            # --- 顯示結果 ---
            st.subheader(f"📊 {ticker} 分析結果 | 策略: {bb_strategy}")
            
            col1, col2, col3 = st.columns(3)
            if len(data) > 0:
                roi = ((data['Close'].iloc[-1] - data['Close'].iloc[0]) / data['Close'].iloc[0] * 100)
                col1.metric("區間漲跌幅", f"{roi:.2f}%")
                col2.metric("符合策略天數", f"{len(signals)} 天")
                col3.metric("最新布林寬度", f"{data['BB_Width'].iloc[-1]:.2f}")

            # --- 繪圖 ---
            fig = go.Figure()

            # K線
            fig.add_trace(go.Candlestick(
                x=data.index,
                open=data['Open'], high=data['High'],
                low=data['Low'], close=data['Close'],
                name='K線'
            ))

            # 布林通道
            fig.add_trace(go.Scatter(x=data.index, y=data['BB_High'], line=dict(color='gray', width=1, dash='dot'), name='布林上緣'))
            fig.add_trace(go.Scatter(x=data.index, y=data['BB_Low'], line=dict(color='gray', width=1, dash='dot'), name='布林下緣', fill='tonexty'))

            # 標記訊號
            if not signals.empty:
                fig.add_trace(go.Scatter(
                    x=signals.index, 
                    y=signals['High'] * 1.02,
                    mode='markers',
                    marker=dict(symbol='triangle-down', size=12, color=signal_color),
                    name=signal_name
                ))

            fig.update_layout(
                title=f"股價走勢圖 (標記: {signal_name})", 
                xaxis_rangeslider_visible=False, 
                height=600
            )
            st.plotly_chart(fig, use_container_width=True)

            # --- 詳細數據 ---
            st.subheader("🔎 策略訊號詳細數據")
            if not signals.empty:
                display_df = signals[['Close', 'Volume', 'Vol_MA20', 'BB_High', 'BB_Low', 'BB_Width']].copy()
                display_df['Volume_Ratio'] = display_df['Volume'] / display_df['Vol_MA20']

                # 重新命名欄位 (加入布林上下緣資訊)
                display_df.columns = ['收盤價', '成交量 (張)', '月均量', '布林上緣', '布林下緣', '通道寬度', '量增倍數']
                display_df.index.name = '日期'

                formatted_df = display_df.style.format({
                    '收盤價': '{:.2f}',
                    '成交量 (張)': '{:,.0f}',
                    '月均量': '{:,.0f}',
                    '布林上緣': '{:.2f}',
                    '布林下緣': '{:.2f}',
                    '通道寬度': '{:.2f}',
                    '量增倍數': '{:.2f}倍'
                })
                
                st.dataframe(formatted_df)
            else:
                st.warning("在此區間內，沒有發現符合「策略條件」的交易日。")
        else:
            st.error(f"找不到代碼 {ticker} 的資料。")
else:
    # 這是尚未按下按鈕時的顯示畫面
    st.info("👈 請在左側設定參數，並按下「🚀 開始執行分析」按鈕。")
