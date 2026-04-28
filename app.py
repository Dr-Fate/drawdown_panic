import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

def fetch_data(ticker):
    """
    Fetch historical data for a given ticker.
    We need at least 252 days for the max_price and 200 days for SMA.
    Fetching 2 years of data to be safe.
    """
    try:
        # Using auto_adjust=True to get adjusted prices if possible,
        # but yfinance 1.3.0 behavior might vary.
        df = yf.download(ticker, period="2y", progress=False)
        if df.empty:
            return None
        return df
    except Exception as e:
        st.error(f"Error fetching data for {ticker}: {e}")
        return None

def calculate_metrics(df, ticker):
    """
    Calculate required metrics for a ticker.
    """
    if df is None or len(df) < 252:
        return None

    # Handle multi-index columns if yfinance returns them (common in recent versions)
    if isinstance(df.columns, pd.MultiIndex):
        close_prices = df['Close'][ticker]
    else:
        close_prices = df['Close']

    price = float(close_prices.iloc[-1])
    sma200 = float(close_prices.rolling(window=200).mean().iloc[-1])
    max_price_252 = float(close_prices.tail(252).max())

    drawdown_asset = (price / max_price_252) - 1
    diff_sma200 = (price / sma200) - 1

    # Determine state
    bear_threshold = -0.15
    if ticker.upper() == "SMH":
        bear_threshold = -0.20

    # State Logic Implementation:
    # 1. price >= sma200 -> NORMAL
    # 2. price < sma200:
    #    - drawdown > -15% -> ALERTA
    #    - drawdown <= bear_threshold -> BEAR
    # Note: For SMH, if -20% < drawdown <= -15%, it falls into ALERTA
    # because it's price < sma200 and drawdown > -20%.

    if price >= sma200:
        state = "NORMAL"
    else:
        if drawdown_asset <= bear_threshold:
            state = "BEAR"
        else:
            state = "ALERTA"

    return {
        "Activo": ticker,
        "Precio": price,
        "SMA200": sma200,
        "Dif. SMA200 (%)": diff_sma200 * 100,
        "Drawdown (%)": drawdown_asset * 100,
        "Estado": state
    }

def main():
    st.set_page_config(page_title="Investment Tracker", layout="wide")
    st.title("📈 Investment Strategy Tracker")
    st.write("Seguimiento de inversiones basado en SMA200 y Drawdown para estrategias tipo Golden Cross.")

    # Sidebar for inputs
    st.sidebar.header("Configuración")
    default_tickers = "VUSA.L, VFEA.L, SMH"
    ticker_input = st.sidebar.text_area("Lista de Tickers (separados por coma)", default_tickers)
    refresh_button = st.sidebar.button("Refrescar Datos")

    tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

    if "results" not in st.session_state or refresh_button:
        results = []
        data_cache = {}
        for ticker in tickers:
            with st.spinner(f"Descargando datos para {ticker}..."):
                df = fetch_data(ticker)
                if df is not None:
                    data_cache[ticker] = df
                    metrics = calculate_metrics(df, ticker)
                    if metrics:
                        results.append(metrics)
        st.session_state.results = results
        st.session_state.data_cache = data_cache
        st.session_state.last_refresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if st.session_state.results:
        df_results = pd.DataFrame(st.session_state.results)

        # 9. EXTRA: ordenar por drawdown
        df_results = df_results.sort_values(by="Drawdown (%)", ascending=True)

        st.write(f"Última actualización: {st.session_state.last_refresh}")

        # 6. OUTPUT (TABLA PRINCIPAL) & 7. VISUAL
        def style_state(row):
            if row["Estado"] == "NORMAL":
                color = "background-color: #d4edda; color: #155724;" # Green
            elif row["Estado"] == "ALERTA":
                color = "background-color: #fff3cd; color: #856404;" # Yellow
            elif row["Estado"] == "BEAR":
                color = "background-color: #f8d7da; color: #721c24;" # Red
            else:
                color = ""
            return [color] * len(row)

        styled_df = df_results.style.apply(style_state, axis=1).format({
            "Precio": "{:.2f}",
            "SMA200": "{:.2f}",
            "Dif. SMA200 (%)": "{:.2f}%",
            "Drawdown (%)": "{:.2f}%"
        })

        # Use st.dataframe for better interactivity, but st.table for the requested "principal table" look
        st.dataframe(styled_df, use_container_width=True)

        # 9. EXTRA: gráfico de precio + SMA200
        st.subheader("Gráficos de Evolución")
        for ticker in tickers:
            df = st.session_state.data_cache.get(ticker)
            if df is not None and len(df) >= 200:
                if isinstance(df.columns, pd.MultiIndex):
                    close_series = df['Close'][ticker]
                else:
                    close_series = df['Close']

                sma200_series = close_series.rolling(window=200).mean()

                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df.index, y=close_series, name="Precio"))
                fig.add_trace(go.Scatter(x=df.index, y=sma200_series, name="SMA200"))

                fig.update_layout(
                    title=f"{ticker} - Precio vs SMA200",
                    xaxis_title="Fecha",
                    yaxis_title="Precio",
                    template="plotly_white",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("No se encontraron resultados. Verifique los tickers ingresados.")

if __name__ == "__main__":
    main()
