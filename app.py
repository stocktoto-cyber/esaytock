import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import ta

# --- 頁面設定 ---
st.set_page_config(page_title="台股量價回測系統", layout="wide")
st.title("📈 台股量價與布林通道回測工具")

# --- 側邊欄：控制面板 ---
st.sidebar.header("1. 股票搜尋")
stock_id = st.sidebar.text_input("輸入股票代碼 (例如: 2330)", value="2330")

# 自動補全 .TW
if stock_id and not stock_id.endswith('.TW') and not stock_id.endswith('.TWO'):
    # 預設嘗試上市 (.TW)，若找不到可能需手動改 .TWO (這邊先預設上市)
    ticker = f"{stock_id}.TW"
else:
    ticker = stock_id

st.sidebar.header("2. 回測期間選擇")
period_option = st.sidebar.selectbox(
    "選擇預設區間或自訂",
    ["近一年", "近三年", "近五年", "AI爆發期 (2023-至今)", "疫情期間 (2020-2022)", "美中貿易戰 (2018-2019)", "自訂日期"]
)

# 定義時間區間邏輯
end_date = datetime.now()
start_date = end_date - timedelta(days=365) # 預設

if period_option == "近一年":
    start_date = end_date - timedelta(days=365)
elif period_option == "近三年":
    start_date = end_date - timedelta(days=365*3)
elif period_option == "近五年":
    start_date = end_date - timedelta(days=365*5)
elif period_option == "AI爆發期 (2023-至今)":
    start_date = datetime(2023, 1, 1)
    end_date = datetime.now()
elif period_option == "疫情期間 (2020-2022)":
    start_date = datetime(2020, 1, 1)
    end_date = datetime(2022, 12, 31)
elif period_option == "美中貿易戰 (2018-2019)":
    start_date = datetime(2018, 1, 1)
    end_date = datetime(2020, 1, 15) # 第一階段協議簽署
elif period_option == "自訂日期":
    start_date = st.sidebar.date_input("開始日期", end_date - timedelta(days=365))
    end_date = st.sidebar.date_input("結束日期", end_date)

st.sidebar.header("3. 指標參數設定")
# 指標 1: 成交量倍數 (控制 1-2 倍)
vol_multiplier = st.sidebar.slider("成交量爆發倍數 (相對於20日均量)", 1.0, 3.0, 1.5, 0.1)

# 指標 2: 布林通道
bb_window = 20
bb_std = 2

# --- 數據處理函數 ---
@st.cache_data
def load_data(ticker, start, end):
    try:
        df = yf.download(ticker, start=start, end=end)
        if df.empty:
            return None
        # 處理 MultiIndex (yfinance 新版可能的格式問題)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        return df
    except Exception as e:
        return None

# --- 主程式邏輯 ---
data = load_data(ticker, start_date, end_date)

if data is not None and not data.empty:
    
    # 【關鍵修改】將成交量從「股」換算成「張」 (除以 1000)
    data['Volume'] = data['Volume'] / 1000

    # 1. 計算技術指標
    # 布林通道 (Bollinger Bands)
    indicator_bb = ta.volatility.BollingerBands(close=data["Close"], window=bb_window, window_dev=bb_std)
    data["BB_High"] = indicator_bb.bollinger_hband()
    data["BB_Low"] = indicator_bb.bollinger_lband()
    data["BB_Mid"] = indicator_bb.bollinger_mavg()
    data["BB_Width"] = data["BB_High"] - data["BB_Low"] # 通道距離
    
    # 成交量平均 (使用 20 日，這裡算出來的也會是「張」)
    data["Vol_MA20"] = data["Volume"].rolling(window=20).mean()

    # 2. 篩選策略訊號 (Backtesting Logic)
    # 條件：當日成交量 > 設定倍數 * 月均量
    signals = data[data["Volume"] > (data["Vol_MA20"] * vol_multiplier)]
    
    # 顯示統計資訊
    st.subheader(f"📊 股票代碼: {ticker} | 區間: {start_date.date()} ~ {end_date.date()}")
    
    col1, col2, col3 = st.columns(3)
    if len(data) > 0:
        roi = ((data['Close'].iloc[-1] - data['Close'].iloc[0]) / data['Close'].iloc[0] * 100)
        col1.metric("區間漲跌幅", f"{roi:.2f}%")
        col2.metric("符合爆量條件天數", f"{len(signals)} 天")
        col3.metric("當前布林通道寬度", f"{data['BB_Width'].iloc[-1]:.2f}")

    # --- 繪圖 (使用 Plotly) ---
    fig = go.Figure()

    # K線圖
    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data['Open'], high=data['High'],
        low=data['Low'], close=data['Close'],
        name='K線'
    ))

    # 布林通道
    fig.add_trace(go.Scatter(x=data.index, y=data['BB_High'], line=dict(color='gray', width=1), name='布林上緣'))
    fig.add_trace(go.Scatter(x=data.index, y=data['BB_Low'], line=dict(color='gray', width=1), name='布林下緣', fill='tonexty'))

    # 標記訊號點 (爆量日)
    if not signals.empty:
        fig.add_trace(go.Scatter(
            x=signals.index, 
            y=signals['High'] * 1.02, # 標記在 K 線上方一點點
            mode='markers',
            marker=dict(symbol='triangle-down', size=10, color='orange'),
            name=f'爆量訊號 (> {vol_multiplier}x)'
        ))

    fig.update_layout(title="股價走勢與布林通道 (橘色三角為爆量訊號)", xaxis_rangeslider_visible=False, height=600)
    st.plotly_chart(fig, use_container_width=True)

    # --- 顯示詳細數據 (已中文化並修正單位) ---
    st.subheader("🔎 爆量日詳細數據與布林寬度")
    if not signals.empty:
        # 1. 整理要顯示的欄位
        display_df = signals[['Close', 'Volume', 'Vol_MA20', 'BB_Width']].copy()
        
        # 2. 計算倍數
        display_df['Volume_Ratio'] = display_df['Volume'] / display_df['Vol_MA20']

        # 3. 將英文欄位重新命名為中文 (標註「張」)
        display_df.columns = ['收盤價', '成交量 (張)', '月均量 (MA20/張)', '布林通道寬度', '量增倍數']
        
        # 4. 將日期索引名稱改為中文
        display_df.index.name = '日期'

        # 5. 設定顯示格式
        formatted_df = display_df.style.format({
            '收盤價': '{:.2f}',
            '成交量 (張)': '{:,.0f}',       # 整數顯示，加千分位
            '月均量 (MA20/張)': '{:,.0f}', # 整數顯示，加千分位
            '布林通道寬度': '{:.2f}',
            '量增倍數': '{:.2f}倍'
        })
        
        st.dataframe(formatted_df)
    else:
        st.info("選定區間內無符合成交量條件的交易日。")

else:
    st.error(f"找不到代碼 {ticker} 的資料，請確認輸入是否正確 (若是上櫃股票請嘗試手動加上 .TWO)。")
