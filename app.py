import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import ta

# --- 頁面設定 ---
st.set_page_config(page_title="台股量價回測系統", layout="wide")
st.title("📈 台股量價與布林通道回測工具")

# --- 初始化 Session State ---
if 'run_analysis' not in st.session_state:
    st.session_state.run_analysis = False

# --- 側邊欄：控制面板 ---
st.sidebar.header("1. 股票與期間")
stock_id = st.sidebar.text_input("輸入股票代碼", value="00663L")

# 自動加上 .TW 後綴 (如果使用者沒加)
if stock_id and not stock_id.endswith('.TW') and not stock_id.endswith('.TWO'):
    ticker = f"{stock_id}.TW"
else:
    ticker = stock_id

# 強制更新按鈕
if st.sidebar.button("🔄 強制更新今日資料"):
    st.cache_data.clear()
    st.session_state.run_analysis = True

# 選擇回測區間 (已加入「近一個月」)
period_option = st.sidebar.selectbox(
    "選擇回測區間",
    ["近一個月", "近一年", "近三年", "近五年", "AI爆發期 (2023-至今)", "疫情期間 (2020-2022)", "美中貿易戰 (2018-2019)", "自訂日期"]
)

# 日期計算邏輯
today = datetime.now().date()
tomorrow = today + timedelta(days=1)  # 確保能抓到今天的收盤

start_date = today - timedelta(days=365)
end_date = tomorrow

if period_option == "近一個月":
    start_date = today - timedelta(days=30)
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
    col_d1, col_d2 = st.sidebar.columns(2)
    with col_d1:
        start_date = st.date_input("開始日期", today - timedelta(days=30))
    with col_d2:
        user_end_date = st.date_input("結束日期", today)
        if user_end_date == today:
            end_date = tomorrow
        else:
            end_date = user_end_date

st.sidebar.header("2. 策略參數設定")
vol_multiplier = st.sidebar.slider("成交量爆發倍數 (vs 20日均量)", 1.0, 3.0, 1.5, 0.1)

st.sidebar.subheader("布林通道位置篩選")
bb_strategy = st.sidebar.radio(
    "選擇訊號過濾條件",
    ("不限 (僅看成交量)", "爆量 + 站上布林上緣 (強勢)", "爆量 + 跌破布林下緣 (弱勢/反彈)")
)

bb_tolerance = st.sidebar.slider(
    "訊號觸發寬容度 (%)", 
    min_value=0.0, 
    max_value=10.0, 
    value=1.0, 
    step=0.1, 
    help="數值越大越寬鬆。例如設定 5%，代表股價只要接近上緣 5% 範圍內就會視為觸發。"
)

bb_window = 20
bb_std = 2

st.sidebar.markdown("---")
def start_click():
    st.session_state.run_analysis = True

run_btn = st.sidebar.button("🚀 開始執行分析", on_click=start_click, type="primary")

# --- 數據處理函數 ---
@st.cache_data(ttl=60)
def load_data(ticker, start, end):
    try:
        # 下載資料
        df = yf.download(ticker, start=str(start), end=str(end), auto_adjust=True)
        
        if df.empty:
            return None
            
        # 處理 yfinance 新版的 MultiIndex 問題
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        return None

# --- 主程式邏輯 ---
if st.session_state.run_analysis:
    if start_date >= end_date:
         st.error("日期設定錯誤：開始日期必須早於結束日期。")
    
    else:
        with st.spinner(f"正在分析 {ticker} (已啟用即時更新)..."):
            # 【關鍵修改】資料預讀緩衝區 (Buffer)
            # 為了讓第一天就有 20MA 和布林通道，我們多抓 40 天前的資料
            buffer_days = 40
            real_start_date = start_date - timedelta(days=buffer_days)
            
            raw_data = load_data(ticker, real_start_date, end_date)

        if raw_data is not None and not raw_data.empty:
            # 複製一份資料進行計算
            data = raw_data.copy()
            data['Volume'] = data['Volume'] / 1000  # 換算成「張」

            # 1. 計算技術指標 (使用包含緩衝區的完整資料)
            indicator_bb = ta.volatility.BollingerBands(close=data["Close"], window=bb_window, window_dev=bb_std)
            data["BB_High"] = indicator_bb.bollinger_hband()
            data["BB_Low"] = indicator_bb.bollinger_lband()
            data["BB_Mid"] = indicator_bb.bollinger_mavg() 
            data["BB_Width"] = data["BB_High"] - data["BB_Low"]
            data["Vol_MA20"] = data["Volume"].rolling(window=20).mean()

            # 【關鍵修改】計算完指標後，再切除緩衝區，只保留使用者想看的日期
            # 轉換 start_date 為 pandas 可以識別的字串或時間戳記
            data = data.loc[str(start_date):]

            if data.empty:
                 st.warning("選定區間內無資料，請檢查日期或緩衝區設定。")
            else:
                # --- 顯示最新行情資訊 ---
                latest = data.iloc[-1]
                prev = data.iloc[-2] if len(data) > 1 else latest
                
                latest_date_str = latest.name.strftime('%Y-%m-%d')
                
                st.subheader(f"🎫 {ticker} 最新行情 ({latest_date_str})")
                
                diff = latest['Close'] - prev['Close']
                diff_pct = (diff / prev['Close']) * 100
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("目前股價", f"{latest['Close']:.2f}", f"{diff:.2f} ({diff_pct:.2f}%)")
                m2.metric("最新成交量 (張)", f"{latest['Volume']:,.0f}")
                m3.metric("布林上緣", f"{latest['BB_High']:.2f}")
                m4.metric("布林下緣", f"{latest['BB_Low']:.2f}")
                
                st.markdown("---")

                # 2. 篩選策略訊號
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
                
                # --- 顯示回測結果 ---
                st.subheader(f"📊 歷史回測結果 | 策略: {bb_strategy}")
                
                col1, col2, col3, col4 = st.columns(4)
                
                if len(data) > 0:
                    roi = ((data['Close'].iloc[-1] - data['Close'].iloc[0]) / data['Close'].iloc[0] * 100)
                    col1.metric("區間漲跌幅 (Buy&Hold)", f"{roi:.2f}%")
                    col2.metric("符合策略天數", f"{len(signals)} 天")
                    col3.metric("最新布林寬度", f"{data['BB_Width'].iloc[-1]:.2f}")
                    
                    if not signals.empty:
                        avg_signal_price = signals['Close'].mean()
                        col4.metric("訊號平均價格", f"{avg_signal_price:.2f}")
                    else:
                        col4.metric("訊號平均價格", "無訊號")

                # --- 繪圖 ---
                fig = go.Figure()

                # K線
                fig.add_trace(go.Candlestick(
                    x=data.index,
                    open=data['Open'], high=data['High'],
                    low=data['Low'], close=data['Close'],
                    name='K線'
                ))

                # 月線 (20MA)
                fig.add_trace(go.Scatter(
                    x=data.index, 
                    y=data['BB_Mid'], 
                    line=dict(color='blue', width=1.5), 
                    name='月線 (20MA)'
                ))

                # 布林通道
                fig.add_trace(go.Scatter(x=data.index, y=data['BB_High'], line=dict(color='gray', width=1, dash='dot'), name='布林上緣'))
                fig.add_trace(go.Scatter(x=data.index, y=data['BB_Low'], line=dict(color='gray', width=1, dash='dot'), name='布林下緣', fill='tonexty'))

                # 標記訊號
                if not signals.empty:
                    plot_y = signal_y_position[signals.index]
                    fig.add_trace(go.Scatter(
                        x=signals.index, 
                        y=plot_y,
                        mode='markers',
                        marker=dict(symbol=marker_symbol, size=12, color=signal_color),
                        name=signal_name
                    ))

                fig.update_layout(
                    title=f"股價走勢圖 (已還原分割權值)", 
                    xaxis_rangeslider_visible=False, 
                    height=600,
                    xaxis_title="日期",
                    yaxis_title="股價"
                )
                st.plotly_chart(fig, use_container_width=True)

                # --- 詳細數據 ---
                st.subheader("🔎 策略訊號詳細數據")
                if not signals.empty:
                    display_df = signals[['Close', 'Volume', 'Vol_MA20', 'BB_High', 'BB_Low', 'BB_Width']].copy()
                    display_df['Volume_Ratio'] = display_df['Volume'] / display_df['Vol_MA20']

                    display_df.columns = ['收盤價', '成交量 (張)', '月均量', '布林上緣', '布林下緣', '通道寬度', '量增倍數']
                    display_df.index.name = '日期'
                    # 將 index 轉為字串格式，讓表格顯示好看一點
                    display_df.index = display_df.index.strftime('%Y-%m-%d')

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
            st.error(f"找不到代碼 {ticker} 的資料，或今日資料尚未更新。")
else:
    st.info("👈 請在左側設定參數，並按下「🚀 開始執行分析」按鈕。")
