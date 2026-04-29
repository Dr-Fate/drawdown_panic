import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import json
import os

PORTFOLIO_FILE = "portfolio_history.json"

def load_portfolio_history():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    # Initial structure if file doesn't exist
    return {}

def save_portfolio_history(history):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(history, f, indent=2)

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

    price_cols_to_try = ['Adj Close', 'Close']
    close_prices = None

    for col in price_cols_to_try:
        if col in df.columns:
            if isinstance(df.columns, pd.MultiIndex):
                close_prices = df[col][ticker]
            else:
                close_prices = df[col]
            break

    if close_prices is None:
        return None

    price = float(close_prices.iloc[-1])
    sma200 = float(close_prices.rolling(window=200).mean().iloc[-1])

    rolling_max_252 = close_prices.rolling(window=252).max()
    max_price_252 = float(rolling_max_252.iloc[-1])

    drawdown_asset = (price / max_price_252) - 1
    diff_sma200 = (price / sma200) - 1

    buffer = 0.01

    bear_threshold = -0.15
    if ticker.upper() == "SMH":
        bear_threshold = -0.20

    if price >= sma200 * (1 - buffer):
        state = "NORMAL"
    else:
        if drawdown_asset <= bear_threshold:
            state = "BEAR"
        else:
            state = "ALERTA"

    if ticker.upper() == "VFEA.L":
        if state == "BEAR":
            action = "ACTIVAR BOT"
        elif state == "ALERTA":
            action = "OBSERVAR"
        else:
            action = "MANTENER"
    else:
        if state == "BEAR":
            action = "EVALUAR SALIDA"
        elif state == "ALERTA":
            action = "OBSERVAR"
        else:
            action = "MANTENER"

    min_move = 0.03
    if abs(diff_sma200) < min_move:
        action = "NO OPERAR (COMISIONES)"

    return {
        "Activo": ticker,
        "Precio": price,
        "SMA200": sma200,
        "Dif. SMA200 (%)": diff_sma200 * 100,
        "Drawdown (%)": drawdown_asset * 100,
        "Estado": state,
        "Acción Sugerida": action
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

    # Portfolio Tracking Module
    st.header("💼 Seguimiento de Portfolio")
    st.write(f"Fecha actual: {datetime.now().strftime('%Y-%m-%d')}")

    # Optional Broker Balance
    broker_balance = st.sidebar.number_input("Saldo Broker (USD) - Opcional", value=0.0, step=100.0)

    portfolio_data = load_portfolio_history()

    # Section Usuario vs Mercado (Visual Separation)
    user_col1, user_col2 = st.columns([1, 2])

    with user_col1:
        st.subheader("📍 Entrada de Datos")
        for ticker in tickers:
            with st.expander(f"📥 {ticker}", expanded=False):
                existing_entry = portfolio_data.get(ticker, {})
                if not isinstance(existing_entry, dict):
                    existing_entry = {}

                cap_inv = float(existing_entry.get("capital_invertido", 0.0))
                val_act = float(existing_entry.get("valor_actual", 0.0))

                new_cap = st.number_input(f"Capital Invertido (USD) - {ticker}", value=cap_inv, key=f"cap_{ticker}", label_visibility="collapsed")
                st.caption("Capital Invertido (USD)")
                new_val = st.number_input(f"Valor Actual (USD) - {ticker}", value=val_act, key=f"val_{ticker}", label_visibility="collapsed")
                st.caption("Valor Actual (USD)")

                if st.button(f"Guardar {ticker}", key=f"save_{ticker}"):
                    max_val = float(existing_entry.get("max_valor", 0.0))
                    if new_val > max_val:
                        max_val = new_val

                    historial = existing_entry.get("historial", [])
                    # Evitar duplicados por fecha
                    today = datetime.now().strftime("%Y-%m-%d")
                    historial = [h for h in historial if h["fecha"] != today]
                    historial.append({
                        "fecha": today,
                        "valor": new_val
                    })
                    # Mantener historial ordenado cronológicamente
                    historial.sort(key=lambda x: x["fecha"])

                    portfolio_data[ticker] = {
                        "capital_invertido": new_cap,
                        "valor_actual": new_val,
                        "max_valor": max_val,
                        "historial": historial
                    }
                    save_portfolio_history(portfolio_data)
                    st.success(f"Datos de {ticker} guardados.")
                    st.rerun()

                if st.button(f"Resetear Historial {ticker}", key=f"reset_{ticker}"):
                    portfolio_data[ticker] = {
                        "capital_invertido": 0.0,
                        "valor_actual": 0.0,
                        "max_valor": 0.0,
                        "historial": []
                    }
                    save_portfolio_history(portfolio_data)
                    st.warning(f"Historial de {ticker} reseteado.")
                    st.rerun()

    with user_col2:
        st.subheader("📊 Historial del Portfolio")

        # Display deterministic history from JSON
        history_rows = []
        for ticker in tickers:
            data = portfolio_data.get(ticker, {})
            if isinstance(data, dict):
                for entry in data.get("historial", []):
                    history_rows.append({
                        "Fecha": entry["fecha"],
                        "Activo": ticker,
                        "Valor (USD)": float(entry["valor"])
                    })

        if history_rows:
            df_hist = pd.DataFrame(history_rows).sort_values(by=["Fecha", "Activo"], ascending=[False, True])

            # Management UI: st.data_editor for history
            edited_hist = st.data_editor(
                df_hist,
                use_container_width=True,
                num_rows="dynamic",
                key="history_editor"
            )

            # Check if history was changed in editor
            if not edited_hist.equals(df_hist):
                # Rebuild portfolio_data from edited_hist
                # Note: this is a simple implementation. In a real app we'd be more careful.
                # First, clear all histories but keep capital/max/current?
                # Actually, better to just update the 'historial' list for each ticker.

                new_histories = {t: [] for t in tickers}
                for _, row in edited_hist.iterrows():
                    t = row["Activo"]
                    if t in new_histories:
                        new_histories[t].append({
                            "fecha": row["Fecha"],
                            "valor": float(row["Valor (USD)"])
                        })

                # Update JSON data
                for t in tickers:
                    if t in portfolio_data:
                        portfolio_data[t]["historial"] = sorted(new_histories[t], key=lambda x: x["fecha"])
                        # Update max_valor based on history
                        if new_histories[t]:
                            portfolio_data[t]["max_valor"] = max([h["valor"] for h in new_histories[t]])
                            portfolio_data[t]["valor_actual"] = new_histories[t][-1]["valor"]

                save_portfolio_history(portfolio_data)
                st.info("Historial actualizado y persistido.")
                st.rerun()

            # Evolution chart
            st.subheader("📈 Evolución del Valor")
            fig_user = go.Figure()
            for ticker in tickers:
                ticker_hist = [h for h in history_rows if h["Activo"] == ticker]
                if ticker_hist:
                    df_ticker_hist = pd.DataFrame(ticker_hist).sort_values(by="Fecha")
                    fig_user.add_trace(go.Scatter(x=df_ticker_hist["Fecha"], y=df_ticker_hist["Valor (USD)"], name=ticker))

            fig_user.update_layout(template="plotly_white", margin=dict(l=0, r=0, t=30, b=0), height=300)
            st.plotly_chart(fig_user, use_container_width=True)
        else:
            st.info("Aún no hay historial guardado.")

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

        # Merge with user portfolio data
        user_data_rows = []
        total_user_value = 0.0

        for ticker in tickers:
            entry = portfolio_data.get(ticker, {})
            if not isinstance(entry, dict):
                entry = {}
            valor_actual = float(entry.get("valor_actual", 0.0))
            max_val = float(entry.get("max_valor", 0.0))
            cap_inv = float(entry.get("capital_invertido", 0.0))

            total_user_value += valor_actual

            drawdown_user = (valor_actual / max_val - 1) if max_val > 0 else 0.0
            drawdown_inv = (valor_actual / cap_inv - 1) if cap_inv > 0 else 0.0

            user_data_rows.append({
                "Activo": ticker,
                "Valor Usuario": valor_actual,
                "Máximo Usuario": max_val,
                "Capital Invertido": cap_inv,
                "Drawdown Usuario (%)": drawdown_user * 100,
                "Drawdown Inversión (%)": drawdown_inv * 100
            })

        df_user = pd.DataFrame(user_data_rows)
        df_results = pd.merge(df_results, df_user, on="Activo")

        # 9. EXTRA: ordenar por drawdown
        df_results = df_results.sort_values(by="Drawdown (%)", ascending=True)

        st.write(f"Última actualización: {st.session_state.last_refresh}")

        # Check Broker Discrepancy
        if broker_balance > 0:
            diff_broker = abs(broker_balance - total_user_value)
            if diff_broker > (total_user_value * 0.01): # > 1% diff
                st.info(f"ℹ️ Diferencia con Broker: ${diff_broker:.2f} (Calculado: ${total_user_value:.2f} vs Broker: ${broker_balance:.2f})")

        # 5. VALIDACIÓN DE DATOS (REVISADA)
        for _, row in df_results.iterrows():
            cap_inv = row["Capital Invertido"]
            dd_activo = row["Drawdown (%)"] / 100
            valor_teorico = cap_inv * (1 + dd_activo)
            valor_real = row["Valor Usuario"]

            if cap_inv > 0:
                diff_relativa = abs(valor_real / valor_teorico - 1) if valor_teorico > 0 else 0.0
                if diff_relativa > 0.05:
                    st.warning(f"⚠️ Posible inconsistencia en {row['Activo']}: El valor real (${valor_real:.2f}) difiere significativamente del teórico (${valor_teorico:.2f}) basado en el mercado. Revisa los valores ingresados o con tu broker.")

        # 6. OUTPUT (TABLA PRINCIPAL) & 7. VISUAL
        def style_combined(row):
            styles = [""] * len(row)

            # Market State Coloring (applies to whole row or specific columns)
            # Let's apply market state color to the 'Estado' column and user drawdown to its column
            state_idx = df_results.columns.get_loc("Estado")
            user_dd_idx = df_results.columns.get_loc("Drawdown Usuario (%)")

            # Market State Color
            market_color = ""
            if row["Estado"] == "NORMAL":
                market_color = "background-color: #d4edda; color: #155724;"
            elif row["Estado"] == "ALERTA":
                market_color = "background-color: #fff3cd; color: #856404;"
            elif row["Estado"] == "BEAR":
                market_color = "background-color: #f8d7da; color: #721c24;"

            # User Drawdown Color
            user_dd_val = row["Drawdown Usuario (%)"]
            user_color = ""
            if user_dd_val > -10:
                user_color = "background-color: #d4edda; color: #155724;" # Green
            elif -20 <= user_dd_val <= -10:
                user_color = "background-color: #fff3cd; color: #856404;" # Yellow
            else:
                user_color = "background-color: #f8d7da; color: #721c24;" # Red

            # Applying styles
            # Prompt 7 says "Colorear NORMAL -> verde, etc." for market table.
            # Prompt 5 of NEW request says "Colorear > -10% -> verde, etc." for user drawdown.
            # Usually users want the whole row colored by state, but let's be more precise.
            # To match the previous visual where whole row was colored:
            styles = [market_color] * len(row)
            styles[user_dd_idx] = user_color # Override user drawdown cell

            return styles

        styled_df = df_results.style.apply(style_combined, axis=1).format({
            "Precio": "{:.2f}",
            "SMA200": "{:.2f}",
            "Dif. SMA200 (%)": "{:.2f}%",
            "Drawdown (%)": "{:.2f}%",
            "Valor Usuario": "{:.2f}",
            "Máximo Usuario": "{:.2f}",
            "Drawdown Usuario (%)": "{:.2f}%",
            "Drawdown Inversión (%)": "{:.2f}%"
        })

        st.subheader("🏛️ Resumen de Mercado y Usuario")
        st.dataframe(styled_df, use_container_width=True)

        # 9. EXTRA: gráfico de precio + SMA200
        st.subheader("Gráficos de Evolución")
        for ticker in tickers:
            df = st.session_state.data_cache.get(ticker)
            if df is not None and len(df) >= 200:
                price_cols_to_try = ['Adj Close', 'Close']
                close_series = None
                for col in price_cols_to_try:
                    if col in df.columns:
                        if isinstance(df.columns, pd.MultiIndex):
                            close_series = df[col][ticker]
                        else:
                            close_series = df[col]
                        break

                if close_series is None:
                    continue

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
