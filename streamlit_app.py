import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import os
import locale
import numpy as np
from scipy import stats

# Türkçe gün adları için locale ayarı
try:
    locale.setlocale(locale.LC_TIME, 'tr_TR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'turkish')
    except:
        pass

# Sayfa yapılandırması
st.set_page_config(page_title="TEFAS Fon Analiz Dashboard", layout="wide")

# Başlık
st.title("📈 TEFAS Fon Performans Gösterge Paneli")
st.markdown("---")


# Gün adı çevirisi için fonksiyon
def get_turkish_day_name(date):
    """Tarihin Türkçe gün adını döndürür"""
    days = {
        'Monday': 'Pazartesi',
        'Tuesday': 'Salı',
        'Wednesday': 'Çarşamba',
        'Thursday': 'Perşembe',
        'Friday': 'Cuma',
        'Saturday': 'Cumartesi',
        'Sunday': 'Pazar'
    }
    try:
        day_name = date.strftime('%A')
        return days.get(day_name, day_name)
    except:
        return days.get(date.strftime('%A'), date.strftime('%A'))


# Kapsamlı fon analizi için fonksiyonlar
def calculate_comprehensive_metrics(fund_data):
    """Tüm fonlar için kapsamlı metrikler hesaplar"""
    if len(fund_data) < 5:
        return None

    # Son fiyat ve getiriler
    last_price = fund_data['unit_price'].iloc[-1]
    first_price = fund_data['unit_price'].iloc[0]

    # Farklı dönemler için getiriler
    returns = {
        '1Hafta': None, '1Ay': None, '3Ay': None, '6Ay': None, 'Yılbaşındanİtibaren': None
    }

    # 1 hafta (5 iş günü)
    if len(fund_data) >= 5:
        returns['1Hafta'] = (fund_data['unit_price'].iloc[-1] / fund_data['unit_price'].iloc[-5] - 1) * 100

    # 1 ay (21 iş günü)
    if len(fund_data) >= 21:
        returns['1Ay'] = (fund_data['unit_price'].iloc[-1] / fund_data['unit_price'].iloc[-21] - 1) * 100

    # 3 ay (63 iş günü)
    if len(fund_data) >= 63:
        returns['3Ay'] = (fund_data['unit_price'].iloc[-1] / fund_data['unit_price'].iloc[-63] - 1) * 100

    # 6 ay (126 iş günü)
    if len(fund_data) >= 126:
        returns['6Ay'] = (fund_data['unit_price'].iloc[-1] / fund_data['unit_price'].iloc[-126] - 1) * 100

    # Yılbaşından itibaren
    current_year = datetime.now().year
    year_start_data = fund_data[fund_data['change_date'].dt.year == current_year]
    if not year_start_data.empty:
        first_of_year = year_start_data['unit_price'].iloc[0]
        returns['Yılbaşındanİtibaren'] = (last_price / first_of_year - 1) * 100

    # Risk metrikleri
    daily_returns = fund_data['unit_price'].pct_change() * 100
    volatility = daily_returns.std()
    sharpe = (daily_returns.mean() * 252) / (volatility * np.sqrt(252)) if volatility and volatility > 0 else 0

    # Maksimum düşüş
    cumulative = (1 + daily_returns / 100).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min() * 100

    # Yatırımcı trendi
    investor_trend = (fund_data['investor_count'].iloc[-1] / fund_data['investor_count'].iloc[0] - 1) * 100
    investor_momentum = fund_data['investor_count'].pct_change(periods=5).mean() * 100

    # Hareketli ortalamalar
    ma_10 = fund_data['unit_price'].tail(10).mean()
    ma_20 = fund_data['unit_price'].tail(20).mean()
    price_vs_ma = ((last_price / ma_20 - 1) * 100) if ma_20 > 0 else 0

    # Volatilite bazlı risk skoru (0-100 arası, düşük volatilite iyi)
    vol_score = max(0, min(100, 100 - (volatility * 10))) if volatility else 50

    return {
        'Son Fiyat': last_price,
        'Toplam Getiri': (last_price / first_price - 1) * 100,
        '1Hafta': returns['1Hafta'],
        '1Ay': returns['1Ay'],
        '3Ay': returns['3Ay'],
        '6Ay': returns['6Ay'],
        'Yılbaşındanİtibaren': returns['Yılbaşındanİtibaren'],
        'Volatilite (Günlük)': volatility,
        'Sharpe Oranı': sharpe,
        'Maksimum Düşüş (%)': max_drawdown,
        'Yatırımcı Değişimi (%)': investor_trend,
        'Yatırımcı Momentum': investor_momentum,
        'Fiyat vs MA20 (%)': price_vs_ma,
        'Risk Skoru': vol_score,
        'Veri Sayısı': len(fund_data)
    }


def score_funds_comprehensive(metrics_dict, strategy='aggressive'):
    """Farklı stratejilere göre fonları skorla"""
    scores = {}

    for fund_name, metrics in metrics_dict.items():
        if not metrics or metrics['Veri Sayısı'] < 20:
            scores[fund_name] = -999
            continue

        score = 0

        if strategy == 'aggressive':  # Agresif - Yüksek getiri odaklı
            score += metrics['1Ay'] * 1.5 if metrics['1Ay'] else 0
            score += metrics['3Ay'] * 1.2 if metrics['3Ay'] else 0
            score += metrics['6Ay'] * 1.0 if metrics['6Ay'] else 0
            score += metrics['Yatırımcı Değişimi (%)'] * 0.5
            score -= abs(metrics['Maksimum Düşüş (%)']) * 0.3  # Risk cezası

        elif strategy == 'conservative':  # Konservatif - Düşük risk odaklı
            score -= abs(metrics['Maksimum Düşüş (%)']) * 0.5
            score += metrics['Sharpe Oranı'] * 20
            score += (100 - metrics['Risk Skoru']) / 2
            score += metrics['1Ay'] * 0.5 if metrics['1Ay'] else 0

        elif strategy == 'growth':  # Büyüme - Yatırımcı artışı odaklı
            score += metrics['Yatırımcı Değişimi (%)'] * 1.5
            score += metrics['Yatırımcı Momentum'] * 1.0
            score += metrics['1Ay'] * 0.8 if metrics['1Ay'] else 0
            score += metrics['3Ay'] * 0.6 if metrics['3Ay'] else 0

        elif strategy == 'momentum':  # Momentum - Son dönem performans
            score += metrics['1Hafta'] * 2.0 if metrics['1Hafta'] else 0
            score += metrics['1Ay'] * 1.5 if metrics['1Ay'] else 0
            score += metrics['Fiyat vs MA20 (%)'] * 1.0
            score += metrics['Yatırımcı Momentum'] * 0.8

        elif strategy == 'value':  # Değer - Düşük fiyatlı/geride kalmış
            score -= metrics['1Ay'] * 0.5 if metrics['1Ay'] else 0
            score -= metrics['3Ay'] * 0.5 if metrics['3Ay'] else 0
            score += max(0, 100 - metrics['Risk Skoru']) * 0.3
            score += metrics['Yatırımcı Momentum'] * 0.5

        elif strategy == 'balanced':  # Dengeli - Tüm faktörler
            score += metrics['1Ay'] * 0.8 if metrics['1Ay'] else 0
            score += metrics['3Ay'] * 0.6 if metrics['3Ay'] else 0
            score += metrics['Yatırımcı Değişimi (%)'] * 0.8
            score += metrics['Sharpe Oranı'] * 15
            score -= abs(metrics['Maksimum Düşüş (%)']) * 0.2

        scores[fund_name] = score

    return scores


# Trend analizi fonksiyonları
def calculate_trend(data, window=5):
    """Basit hareketli ortalama ile trend hesaplama"""
    return data.rolling(window=window).mean()


def calculate_momentum(data, window=5):
    """Momentum hesaplama (fiyat değişim hızı)"""
    return data.pct_change(periods=window) * 100


def detect_flow_signal(investor_count, window=3):
    """Giriş çıkış sinyali tespiti"""
    flow_change = investor_count.pct_change(periods=window) * 100
    signals = pd.Series(index=investor_count.index, data="Normal")
    signals[flow_change > 5] = "🚀 Güçlü Giriş"
    signals[flow_change > 2] = "📈 Zayıf Giriş"
    signals[flow_change < -5] = "🔻 Güçlü Çıkış"
    signals[flow_change < -2] = "📉 Zayıf Çıkış"
    return signals, flow_change


def calculate_risk_metrics(returns):
    """Risk metriklerini hesaplama"""
    if len(returns) < 2:
        return None
    volatility = returns.std() * np.sqrt(252)
    sharpe = (returns.mean() * 252) / volatility if volatility != 0 else 0
    max_drawdown = calculate_max_drawdown((1 + returns / 100).cumprod())
    return {
        'Volatilite': f"{volatility:.2%}",
        'Sharpe Oranı': f"{sharpe:.2f}",
        'Maksimum Düşüş': f"{max_drawdown:.2%}"
    }


def calculate_max_drawdown(cumulative_returns):
    """Maksimum düşüş hesaplama"""
    running_max = cumulative_returns.expanding().max()
    drawdown = (cumulative_returns - running_max) / running_max
    return drawdown.min()


def rank_funds(funds_df, history_df, metric='performance'):
    """Fonları performans veya popülerliğe göre sıralama"""
    fund_metrics = []

    for fund_code in funds_df['fund_code'].unique():
        fund_data = history_df[history_df['fund_code'] == fund_code].sort_values('change_date')
        if len(fund_data) < 5:
            continue

        last_30 = fund_data.tail(30)
        if len(last_30) > 1:
            price_change = (last_30['unit_price'].iloc[-1] - last_30['unit_price'].iloc[0]) / \
                           last_30['unit_price'].iloc[0] * 100
            investor_change = (last_30['investor_count'].iloc[-1] - last_30['investor_count'].iloc[0]) / \
                              last_30['investor_count'].iloc[0] * 100
            fund_metrics.append({
                'fund_code': fund_code,
                'fund_name': funds_df[funds_df['fund_code'] == fund_code]['fund_name'].values[0],
                'performance': price_change,
                'investor_growth': investor_change,
                'last_price': last_30['unit_price'].iloc[-1]
            })

    if metric == 'performance':
        ranked = sorted(fund_metrics, key=lambda x: x['performance'], reverse=True)
    elif metric == 'popularity':
        ranked = sorted(fund_metrics, key=lambda x: x['investor_growth'], reverse=True)
    else:
        ranked = sorted(fund_metrics, key=lambda x: (x['performance'] + x['investor_growth']), reverse=True)

    return ranked[:10]


# Veri yükleme fonksiyonları
@st.cache_data(ttl=0)
def load_funds(refresh=False):
    funds_path = "data/tefas_funds_data.csv"
    if not os.path.exists(funds_path):
        st.error(f"⚠️ {funds_path} dosyası bulunamadı!")
        return pd.DataFrame()
    df = pd.read_csv(funds_path)
    return df


@st.cache_data(ttl=0)
def load_funds_history(refresh=False):
    history_path = "data/tefas_funds_history_data.csv"
    if not os.path.exists(history_path):
        st.error(f"⚠️ {history_path} dosyası bulunamadı!")
        return pd.DataFrame()
    df = pd.read_csv(history_path)
    if 'change_date' in df.columns:
        df['change_date'] = pd.to_datetime(df['change_date'])
    return df


# Refresh butonu
if 'refresh_key' not in st.session_state:
    st.session_state.refresh_key = 0

col_refresh, col_empty = st.columns([1, 5])
with col_refresh:
    refresh_button = st.button("🔄 Verileri Yenile", use_container_width=True)

if refresh_button:
    st.cache_data.clear()
    st.session_state.refresh_key += 1
    st.success("✅ Veriler başarıyla yenilendi!")
    st.rerun()

# Verileri yükle
with st.spinner("Veriler yükleniyor..."):
    funds_df = load_funds(refresh=refresh_button)
    history_df = load_funds_history(refresh=refresh_button)

if funds_df.empty or history_df.empty:
    st.stop()

st.caption(f"📅 Son veri güncelleme: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Tab oluşturma - Çoklu sayfa deneyimi
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Fon Analizi",
    "🎯 Fon Önerileri",
    "📈 Trend Analizi",
    "🔄 Giriş/Çıkış İzleme",
    "📉 Risk Analizi",
    "🏆 Kapsamlı Fon Analizi"
])

# TAB 1: Fon Analizi (Mevcut Dashboard)
with tab1:
    st.markdown("### 📊 Detaylı Fon Analizi")

    fund_options = {f"{row['fund_code']} - {row['fund_name']}": row['fund_code']
                    for _, row in funds_df.iterrows()}

    default_index = 0
    for i, (display, code) in enumerate(fund_options.items()):
        if code == "SBH":
            default_index = i
            break

    selected_fund_display = st.selectbox(
        "📌 Fon Seçiniz",
        options=list(fund_options.keys()),
        index=default_index,
        key="fund_select_main"
    )
    selected_fund_code = fund_options[selected_fund_display]

    fund_history_all = history_df[history_df['fund_code'] == selected_fund_code].copy()

    if not fund_history_all.empty:
        min_date = fund_history_all['change_date'].min().date()
        max_date = fund_history_all['change_date'].max().date()
        default_start_date = max(max_date - timedelta(days=60), min_date)

        date_range = st.slider(
            "📅 Tarih Aralığı Seçin",
            min_value=min_date,
            max_value=max_date,
            value=(default_start_date, max_date),
            format="YYYY-MM-DD",
            key="date_range_main"
        )
    else:
        st.error("Seçilen fon için veri bulunamadı!")
        st.stop()

    fund_history = history_df[history_df['fund_code'] == selected_fund_code].copy()
    mask = (fund_history['change_date'].dt.date >= date_range[0]) & (
                fund_history['change_date'].dt.date <= date_range[1])
    filtered_history = fund_history.loc[mask].sort_values('change_date')

    if filtered_history.empty:
        st.warning("Seçilen tarih aralığında veri bulunmamaktadır!")
        st.stop()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Fon Kodu", selected_fund_code)
    with col2:
        st.metric("📅 Toplam Gün", len(filtered_history))
    with col3:
        latest_price = filtered_history['unit_price'].iloc[-1]
        prev_price = filtered_history['unit_price'].iloc[0]
        price_change = ((latest_price - prev_price) / prev_price * 100) if prev_price != 0 else 0
        st.metric("💰 Son Fiyat", f"{latest_price} ₺", f"{price_change:+.2f}%")
    with col4:
        latest_investors = filtered_history['investor_count'].iloc[-1]
        st.metric("👥 Son Yatırımcı Sayısı", f"{latest_investors:,}")

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=(
            "<b>💰 Birim Fiyat (TL)</b>",
            "<b>👥 Yatırımcı Sayısı</b>",
            "<b>🏦 Toplam Fon Değeri (TL)</b>"
        ),
        row_heights=[0.34, 0.33, 0.33]
    )

    fig.add_trace(
        go.Scatter(
            x=filtered_history['change_date'],
            y=filtered_history['unit_price'],
            mode='lines+markers',
            name='Birim Fiyat',
            line=dict(color='#1f77b4', width=2.5),
            marker=dict(size=4)
        ),
        row=1, col=1
    )

    trend_ma = calculate_trend(filtered_history['unit_price'], window=7)
    fig.add_trace(
        go.Scatter(
            x=filtered_history['change_date'],
            y=trend_ma,
            mode='lines',
            name='Trend (7 Gün MA)',
            line=dict(color='red', width=1.5, dash='dash'),
            opacity=0.7
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=filtered_history['change_date'],
            y=filtered_history['investor_count'],
            mode='lines+markers',
            name='Yatırımcı Sayısı',
            line=dict(color='#2ca02c', width=2.5),
            marker=dict(size=4),
            fill='tozeroy',
            fillcolor='rgba(44, 160, 44, 0.1)'
        ),
        row=2, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=filtered_history['change_date'],
            y=filtered_history['total_fund_value'],
            mode='lines+markers',
            name='Toplam Fon Değeri',
            line=dict(color='#d62728', width=2.5),
            marker=dict(size=4),
            fill='tozeroy',
            fillcolor='rgba(214, 39, 40, 0.1)'
        ),
        row=3, col=1
    )

    fig.update_layout(height=900, showlegend=False, hovermode='x unified')
    fig.update_xaxes(title_text="Tarih", row=3, col=1)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 Detaylı Veri Tablosu", expanded=False):
        display_df = filtered_history.copy()
        display_df['daily_return'] = display_df['unit_price'].pct_change() * 100
        display_df['day_name'] = display_df['change_date'].apply(get_turkish_day_name)
        display_df['change_date'] = display_df['change_date'].dt.strftime('%Y-%m-%d')

        display_df = display_df.rename(columns={
            'change_date': 'Tarih',
            'day_name': 'Gün',
            'unit_price': 'Birim Fiyat (₺)',
            'investor_count': 'Yatırımcı Sayısı',
            'total_fund_value': 'Toplam Fon Değeri (₺)',
            'daily_return': 'Günlük Getiri (%)'
        })

        if 'fund_code' in display_df.columns:
            display_df = display_df.drop('fund_code', axis=1)

        display_df['Birim Fiyat (₺)'] = display_df['Birim Fiyat (₺)'].apply(lambda x: str(x))
        display_df['Toplam Fon Değeri (₺)'] = display_df['Toplam Fon Değeri (₺)'].apply(lambda x: f"{x:,.2f}")
        display_df['Yatırımcı Sayısı'] = display_df['Yatırımcı Sayısı'].apply(lambda x: f"{x:,}")
        display_df['Günlük Getiri (%)'] = display_df['Günlük Getiri (%)'].apply(
            lambda x: f"{x:+.4f}%" if pd.notna(x) else "-")

        column_order = ['Tarih', 'Gün', 'Birim Fiyat (₺)', 'Yatırımcı Sayısı', 'Toplam Fon Değeri (₺)',
                        'Günlük Getiri (%)']
        display_df = display_df[column_order].sort_values('Tarih', ascending=False)

        st.dataframe(display_df, use_container_width=True, height=400)

# TAB 2: Fon Önerileri
with tab2:
    st.markdown("### 🎯 Akıllı Fon Önerileri")
    st.markdown("Performans ve yatırımcı ilgisine göre sıralanmış fonlar")

    col1, col2 = st.columns(2)
    with col1:
        metric_type = st.radio(
            "Sıralama Kriteri",
            options=['performance', 'popularity', 'balanced'],
            format_func=lambda x: {
                'performance': '🚀 Performans (Getiri)',
                'popularity': '👥 Popülerlik (Yatırımcı Artışı)',
                'balanced': '⚖️ Dengeli (Performans + Popülerlik)'
            }[x],
            horizontal=True
        )

    with col2:
        st.markdown("### 💡 Öneri Mantığı")
        st.info("""
        - **Performans**: Son 30 günlük fiyat artışı
        - **Popülerlik**: Son 30 günlük yatırımcı artışı
        - **Dengeli**: Her iki kriterin kombinasyonu
        """)

    ranked_funds = rank_funds(funds_df, history_df, metric=metric_type)

    if ranked_funds:
        st.markdown("### 🏆 En İyi 10 Fon")

        for i, fund in enumerate(ranked_funds, 1):
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
                with col1:
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                    st.markdown(f"**{medal} {fund['fund_code']}**")
                with col2:
                    st.write(f"{fund['fund_name']}")
                with col3:
                    st.metric("Getiri", f"{fund['performance']:+.2f}%", delta_color="normal")
                with col4:
                    st.metric("Yatırımcı Artışı", f"{fund['investor_growth']:+.2f}%", delta_color="normal")
                with col5:
                    st.write(f"💰 {fund['last_price']} ₺")
                st.markdown("---")
    else:
        st.warning("Yeterli veri bulunamadı!")

# TAB 3: Trend Analizi
with tab3:
    st.markdown("### 📈 Teknik Trend Analizi")

    selected_fund_trend = st.selectbox(
        "Trend analizi yapılacak fonu seçin",
        options=list(fund_options.keys()),
        key="trend_select"
    )
    trend_fund_code = fund_options[selected_fund_trend]

    trend_data = history_df[history_df['fund_code'] == trend_fund_code].sort_values('change_date')
    trend_data = trend_data.tail(90)

    if len(trend_data) > 10:
        trend_data['MA_7'] = calculate_trend(trend_data['unit_price'], 7)
        trend_data['MA_20'] = calculate_trend(trend_data['unit_price'], 20)
        trend_data['Momentum'] = calculate_momentum(trend_data['unit_price'], 5)

        fig_trend = go.Figure()

        fig_trend.add_trace(go.Scatter(
            x=trend_data['change_date'],
            y=trend_data['unit_price'],
            mode='lines',
            name='Fiyat',
            line=dict(color='blue', width=2)
        ))

        fig_trend.add_trace(go.Scatter(
            x=trend_data['change_date'],
            y=trend_data['MA_7'],
            mode='lines',
            name='MA 7 Gün',
            line=dict(color='orange', width=1.5, dash='dash')
        ))

        fig_trend.add_trace(go.Scatter(
            x=trend_data['change_date'],
            y=trend_data['MA_20'],
            mode='lines',
            name='MA 20 Gün',
            line=dict(color='red', width=1.5, dash='dash')
        ))

        fig_trend.update_layout(
            title="Fiyat Hareketi ve Hareketli Ortalamalar",
            xaxis_title="Tarih",
            yaxis_title="Fiyat (₺)",
            height=500,
            hovermode='x unified'
        )

        st.plotly_chart(fig_trend, use_container_width=True)

        col1, col2, col3 = st.columns(3)

        with col1:
            last_ma7 = trend_data['MA_7'].iloc[-1]
            last_ma20 = trend_data['MA_20'].iloc[-1]

            if last_ma7 > last_ma20:
                signal = "🟢 ALIM SİNYALİ (Yükselen Trend)"
            else:
                signal = "🔴 SATIŞ SİNYALİ (Düşen Trend)"

            st.metric("Trend Sinyali", signal)

        with col2:
            momentum = trend_data['Momentum'].iloc[-1]
            if pd.notna(momentum):
                momentum_signal = "🚀 Güçlü Momentum" if momentum > 2 else "📈 Zayıf Momentum" if momentum > 0 else "📉 Negatif Momentum"
                st.metric("5 Günlük Momentum", f"{momentum:+.2f}%", momentum_signal)

        with col3:
            gains = trend_data['unit_price'].diff().clip(lower=0)
            losses = -trend_data['unit_price'].diff().clip(upper=0)
            avg_gain = gains.tail(14).mean()
            avg_loss = losses.tail(14).mean()
            if avg_loss != 0:
                rsi = 100 - (100 / (1 + avg_gain / avg_loss))
                rsi_signal = "Aşırı Alım 🔥" if rsi > 70 else "Aşırı Satım ❄️" if rsi < 30 else "Normal"
                st.metric("RSI (14 Gün)", f"{rsi:.1f}", rsi_signal)
    else:
        st.warning("Trend analizi için yeterli veri bulunamadı (en az 10 gün gerekli)")

# TAB 4: Giriş/Çıkış İzleme
with tab4:
    st.markdown("### 🔄 Yatırımcı Giriş/Çıkış İzleme")

    selected_flow_fund = st.selectbox(
        "Giriş/çıkış izlenecek fonu seçin",
        options=list(fund_options.keys()),
        key="flow_select"
    )
    flow_fund_code = fund_options[selected_flow_fund]

    flow_data = history_df[history_df['fund_code'] == flow_fund_code].sort_values('change_date')
    flow_data = flow_data.tail(60)

    if len(flow_data) > 5:
        flow_signals, flow_change = detect_flow_signal(flow_data['investor_count'], window=3)

        fig_flow = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            subplot_titles=("Günlük Yatırımcı Değişimi (%)", "Yatırımcı Sayısı ve Sinyaller"),
            row_heights=[0.4, 0.6]
        )

        fig_flow.add_trace(
            go.Bar(
                x=flow_data['change_date'],
                y=flow_change,
                name='Değişim %',
                marker_color=['green' if x > 0 else 'red' for x in flow_change],
                hovertemplate='<b>Değişim</b>: %{y:+.2f}%<extra></extra>'
            ),
            row=1, col=1
        )

        fig_flow.add_trace(
            go.Scatter(
                x=flow_data['change_date'],
                y=flow_data['investor_count'],
                mode='lines+markers',
                name='Yatırımcı Sayısı',
                line=dict(color='blue', width=2),
                marker=dict(size=6)
            ),
            row=2, col=1
        )

        signal_points = flow_data[flow_signals != 'Normal']
        if not signal_points.empty:
            signal_colors = {
                '🚀 Güçlü Giriş': 'green',
                '📈 Zayıf Giriş': 'lightgreen',
                '🔻 Güçlü Çıkış': 'red',
                '📉 Zayıf Çıkış': 'orange'
            }

            for signal_type, color in signal_colors.items():
                signal_data = signal_points[flow_signals[signal_points.index] == signal_type]
                if not signal_data.empty:
                    fig_flow.add_trace(
                        go.Scatter(
                            x=signal_data['change_date'],
                            y=signal_data['investor_count'],
                            mode='markers',
                            name=signal_type,
                            marker=dict(size=12, symbol='star', color=color),
                            hovertemplate=f'<b>{signal_type}</b><extra></extra>'
                        ),
                        row=2, col=1
                    )

        fig_flow.update_layout(height=700, hovermode='x unified')
        fig_flow.update_xaxes(title_text="Tarih", row=2, col=1)
        fig_flow.update_yaxes(title_text="Değişim (%)", row=1, col=1)
        fig_flow.update_yaxes(title_text="Yatırımcı Sayısı", row=2, col=1)

        st.plotly_chart(fig_flow, use_container_width=True)

        st.markdown("### 📊 Son 10 Günlük Giriş/Çıkış Sinyalleri")
        recent_signals = pd.DataFrame({
            'Tarih': flow_data['change_date'].dt.strftime('%Y-%m-%d').tail(10),
            'Yatırımcı Sayısı': flow_data['investor_count'].tail(10),
            'Değişim (%)': flow_change.tail(10),
            'Sinyal': flow_signals.tail(10)
        })
        recent_signals['Değişim (%)'] = recent_signals['Değişim (%)'].apply(lambda x: f"{x:+.2f}%")

        st.dataframe(recent_signals, use_container_width=True)

        st.markdown("### 📈 Giriş/Çıkış İstatistikleri")
        col1, col2, col3 = st.columns(3)

        with col1:
            giris_gunleri = sum(flow_change > 2)
            st.metric("Güçlü Giriş Günleri", f"{giris_gunleri} gün")

        with col2:
            cikis_gunleri = sum(flow_change < -2)
            st.metric("Güçlü Çıkış Günleri", f"{cikis_gunleri} gün")

        with col3:
            net_degisim = flow_data['investor_count'].iloc[-1] - flow_data['investor_count'].iloc[0]
            st.metric("Net Yatırımcı Değişimi", f"{net_degisim:+,.0f}")
    else:
        st.warning("Giriş/çıkış analizi için yeterli veri bulunamadı (en az 6 gün gerekli)")

# TAB 5: Risk Analizi
with tab5:
    st.markdown("### 📉 Risk ve Getiri Analizi")

    selected_risk_funds = st.multiselect(
        "Karşılaştırılacak fonları seçin (en fazla 5 fon)",
        options=list(fund_options.keys()),
        default=list(fund_options.keys())[:3] if len(fund_options) >= 3 else list(fund_options.keys()),
        key="risk_select"
    )

    if selected_risk_funds:
        risk_data = {}
        for fund_display in selected_risk_funds[:5]:
            fund_code = fund_options[fund_display]
            fund_data = history_df[history_df['fund_code'] == fund_code].sort_values('change_date')
            fund_data = fund_data.tail(60)

            if len(fund_data) > 5:
                returns = fund_data['unit_price'].pct_change() * 100
                risk_metrics = calculate_risk_metrics(returns)

                risk_data[fund_display] = {
                    'Son Fiyat': fund_data['unit_price'].iloc[-1],
                    'Son 60 Gün Getiri': ((fund_data['unit_price'].iloc[-1] - fund_data['unit_price'].iloc[0]) /
                                          fund_data['unit_price'].iloc[0] * 100),
                    'Volatilite': risk_metrics['Volatilite'] if risk_metrics else "N/A",
                    'Sharpe Oranı': risk_metrics['Sharpe Oranı'] if risk_metrics else "N/A",
                    'Maks. Düşüş': risk_metrics['Maksimum Düşüş'] if risk_metrics else "N/A",
                    'Veri Noktası': len(fund_data)
                }

        if risk_data:
            risk_df = pd.DataFrame(risk_data).T
            st.markdown("### 📊 Fon Karşılaştırma Tablosu")
            st.dataframe(risk_df, use_container_width=True)

            st.markdown("### 📈 Getiri Karşılaştırması")
            fig_compare = go.Figure()

            for fund_display, data in risk_data.items():
                fund_code = fund_options[fund_display]
                fund_data = history_df[history_df['fund_code'] == fund_code].sort_values('change_date')
                fund_data = fund_data.tail(60)

                normalized_returns = (fund_data['unit_price'] / fund_data['unit_price'].iloc[0] - 1) * 100

                fig_compare.add_trace(go.Scatter(
                    x=fund_data['change_date'],
                    y=normalized_returns,
                    mode='lines',
                    name=fund_display,
                    line=dict(width=2)
                ))

            fig_compare.update_layout(
                title="Normalize Edilmiş Getiri Karşılaştırması (Son 60 Gün)",
                xaxis_title="Tarih",
                yaxis_title="Getiri (%)",
                height=500,
                hovermode='x unified'
            )

            st.plotly_chart(fig_compare, use_container_width=True)

            st.markdown("### 🎯 Risk-Getiri Grafiği")
            fig_risk = go.Figure()

            for fund_display, data in risk_data.items():
                if data['Volatilite'] != "N/A":
                    vol = float(data['Volatilite'].strip('%')) / 100
                    ret = data['Son 60 Gün Getiri']

                    fig_risk.add_trace(go.Scatter(
                        x=[vol],
                        y=[ret],
                        mode='markers+text',
                        name=fund_display,
                        text=[fund_display.split(' - ')[0]],
                        textposition="top center",
                        marker=dict(size=20, sizemode='area')
                    ))

            fig_risk.update_layout(
                title="Risk (Volatilite) vs Getiri",
                xaxis_title="Risk (Volatilite)",
                yaxis_title="60 Günlük Getiri (%)",
                height=500,
                showlegend=True
            )

            fig_risk.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
            fig_risk.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)

            st.plotly_chart(fig_risk, use_container_width=True)

            st.markdown("### ⚠️ Risk Uyarıları")
            for fund_display, data in risk_data.items():
                if data['Maks. Düşüş'] != "N/A":
                    max_dd = float(data['Maks. Düşüş'].strip('%'))
                    if max_dd < -15:
                        st.warning(f"🔴 **{fund_display}**: Yüksek maksimum düşüş (%{max_dd:.1f}) - Yüksek risk!")
                    elif max_dd < -10:
                        st.info(f"🟡 **{fund_display}**: Orta seviye maksimum düşüş (%{max_dd:.1f})")
                    else:
                        st.success(f"🟢 **{fund_display}**: Düşük maksimum düşüş (%{max_dd:.1f})")
        else:
            st.warning("Seçilen fonlar için yeterli veri bulunamadı!")
    else:
        st.info("Lütfen karşılaştırma yapmak için en az bir fon seçin.")

# TAB 6: Kapsamlı Fon Analizi (YENİ)
with tab6:
    st.markdown("### 🏆 Kapsamlı Fon Analizi ve Karşılaştırma")
    st.markdown("Tüm fonların detaylı metriklerini görüntüleyin ve farklı stratejilere göre sıralayın")

    # Tüm fonlar için metrikleri hesapla
    with st.spinner("Tüm fonlar için metrikler hesaplanıyor..."):
        all_metrics = {}
        for fund_display, fund_code in fund_options.items():
            fund_data = history_df[history_df['fund_code'] == fund_code].sort_values('change_date')
            if len(fund_data) >= 20:  # En az 20 gün verisi olan fonlar
                metrics = calculate_comprehensive_metrics(fund_data)
                if metrics:
                    all_metrics[fund_display] = metrics

    if all_metrics:
        # Filtreleme seçenekleri
        st.markdown("### 🔍 Filtreleme ve Sıralama Seçenekleri")

        col1, col2, col3 = st.columns(3)

        with col1:
            strategy = st.selectbox(
                "🎯 Yatırım Stratejisi",
                options=['aggressive', 'conservative', 'growth', 'momentum', 'value', 'balanced'],
                format_func=lambda x: {
                    'aggressive': '🚀 Agresif (Yüksek Getiri Odaklı)',
                    'conservative': '🛡️ Konservatif (Düşük Risk Odaklı)',
                    'growth': '📈 Büyüme (Yatırımcı Artışı Odaklı)',
                    'momentum': '⚡ Momentum (Son Trend Odaklı)',
                    'value': '💎 Değer (Geride Kalmış)',
                    'balanced': '⚖️ Dengeli (Tüm Faktörler)'
                }[x]
            )

        with col2:
            min_data_points = st.slider(
                "Minimum Veri Günü",
                min_value=20,
                max_value=100,
                value=30,
                step=10
            )

        with col3:
            top_n = st.slider(
                "Gösterilecek Fon Sayısı",
                min_value=5,
                max_value=50,
                value=20,
                step=5
            )

        # Stratejiye göre skorla ve sırala
        scores = score_funds_comprehensive(all_metrics, strategy)

        # Skorları ve metrikleri birleştir
        results = []
        for fund_name, metrics in all_metrics.items():
            if metrics and metrics['Veri Sayısı'] >= min_data_points:
                results.append({
                    'Fon': fund_name,
                    'Skor': scores.get(fund_name, -999),
                    'Son Fiyat (₺)': metrics['Son Fiyat'],
                    '1Hafta (%)': metrics['1Hafta'],
                    '1Ay (%)': metrics['1Ay'],
                    '3Ay (%)': metrics['3Ay'],
                    '6Ay (%)': metrics['6Ay'],
                    'Yılbaşı (%)': metrics['Yılbaşındanİtibaren'],
                    'Toplam Getiri (%)': metrics['Toplam Getiri'],
                    'Volatilite (%)': metrics['Volatilite (Günlük)'],
                    'Sharpe Oranı': metrics['Sharpe Oranı'],
                    'Maks. Düşüş (%)': metrics['Maksimum Düşüş (%)'],
                    'Yatırımcı Değ. (%)': metrics['Yatırımcı Değişimi (%)'],
                    'Yat. Momentum': metrics['Yatırımcı Momentum'],
                    'Fiyat/MA20 (%)': metrics['Fiyat vs MA20 (%)'],
                    'Risk Skoru': metrics['Risk Skoru']
                })

        # Skora göre sırala
        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values('Skor', ascending=False).head(top_n)

        # Strateji açıklaması
        strategy_explanations = {
            'aggressive': "📌 **Agresif Strateji**: Yüksek getiri potansiyeli olan fonları tercih eder. Kısa-orta vadeli yüksek kazanç hedefler. Risk toleransı yüksek yatırımcılar için uygundur.",
            'conservative': "📌 **Konservatif Strateji**: Düşük risk ve istikrarlı getiriyi hedefler. Maksimum düşüşü minimize eder. Riskten kaçınan yatırımcılar için idealdir.",
            'growth': "📌 **Büyüme Stratejisi**: Yatırımcı tabanı hızla büyüyen, popüler fonları tercih eder. Yüksek potansiyelli fonları arar.",
            'momentum': "📌 **Momentum Stratejisi**: Son dönemde en iyi performans gösteren ve trendi yukarı olan fonları seçer. Kısa vadeli trading için uygundur.",
            'value': "📌 **Değer Stratejisi**: Geride kalmış, düşük değerlenmiş potansiyelli fonları arar. Uzun vadeli yatırım için uygundur.",
            'balanced': "📌 **Dengeli Strateji**: Getiri, risk ve büyüme faktörlerini dengeli şekilde değerlendirir. Tüm yatırımcılar için referans stratejidir."
        }

        st.info(strategy_explanations[strategy])

        # Sonuçları göster
        st.markdown(f"### 📊 En İyi {top_n} Fon (Strateji: {strategy.upper()})")

        # Formatla ve göster
        display_df = results_df.copy()

        # Metrikleri formatla
        for col in display_df.columns:
            if ' (%)' in col or 'Değ. (%)' in col or 'Düşüş (%)' in col or 'Getiri (%)' in col:
                display_df[col] = display_df[col].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "-")
            elif 'Volatilite (%)' in col:
                display_df[col] = display_df[col].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "-")
            elif 'Sharpe Oranı' in col:
                display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "-")
            elif 'Son Fiyat' in col:
                display_df[col] = display_df[col].apply(lambda x: f"{x:,.4f}" if pd.notna(x) else "-")
            elif 'Skor' in col:
                display_df[col] = display_df[col].apply(lambda x: f"{x:.1f}" if x != -999 else "-")

        # Skor sütununu başa al
        cols = ['Skor'] + [c for c in display_df.columns if c != 'Skor']
        display_df = display_df[cols]

        st.dataframe(display_df, use_container_width=True, height=500)

        # Grafiksel karşılaştırmalar
        st.markdown("### 📊 Görsel Karşılaştırmalar")

        col1, col2 = st.columns(2)

        with col1:
            # Getiri karşılaştırması (ilk 10 fon)
            top_10 = results_df.head(10)
            fig_returns = go.Figure()

            fig_returns.add_trace(go.Bar(
                x=top_10['Fon'].apply(lambda x: x.split(' - ')[0]),
                y=top_10['1Ay (%)'],
                name='1 Aylık Getiri',
                marker_color='lightblue'
            ))

            fig_returns.add_trace(go.Bar(
                x=top_10['Fon'].apply(lambda x: x.split(' - ')[0]),
                y=top_10['3Ay (%)'],
                name='3 Aylık Getiri',
                marker_color='orange'
            ))

            fig_returns.update_layout(
                title="Getiri Karşılaştırması (En İyi 10 Fon)",
                xaxis_title="Fon Kodu",
                yaxis_title="Getiri (%)",
                height=400,
                barmode='group'
            )

            st.plotly_chart(fig_returns, use_container_width=True)

        with col2:
            # Risk-Getiri dağılımı
            fig_scatter = go.Figure()

            # Pozitif getiriler
            positive = results_df[
                results_df['3Ay (%)'].apply(lambda x: float(x.strip('%')) if isinstance(x, str) else x) > 0]
            negative = results_df[
                results_df['3Ay (%)'].apply(lambda x: float(x.strip('%')) if isinstance(x, str) else x) <= 0]

            fig_scatter.add_trace(go.Scatter(
                x=positive['Maks. Düşüş (%)'].apply(lambda x: float(x.strip('%')) if isinstance(x, str) else x),
                y=positive['3Ay (%)'].apply(lambda x: float(x.strip('%')) if isinstance(x, str) else x),
                mode='markers+text',
                name='Pozitif Getiri',
                text=positive['Fon'].apply(lambda x: x.split(' - ')[0]),
                textposition="top center",
                marker=dict(size=15, color='green', opacity=0.6)
            ))

            fig_scatter.add_trace(go.Scatter(
                x=negative['Maks. Düşüş (%)'].apply(lambda x: float(x.strip('%')) if isinstance(x, str) else x),
                y=negative['3Ay (%)'].apply(lambda x: float(x.strip('%')) if isinstance(x, str) else x),
                mode='markers+text',
                name='Negatif Getiri',
                text=negative['Fon'].apply(lambda x: x.split(' - ')[0]),
                textposition="top center",
                marker=dict(size=15, color='red', opacity=0.6)
            ))

            fig_scatter.update_layout(
                title="3 Aylık Getiri vs Maksimum Düşüş",
                xaxis_title="Maksimum Düşüş (%)",
                yaxis_title="3 Aylık Getiri (%)",
                height=400,
                hovermode='closest'
            )

            fig_scatter.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
            fig_scatter.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)

            st.plotly_chart(fig_scatter, use_container_width=True)

        # Ek analizler
        st.markdown("### 📈 Detaylı Metrik Analizleri")

        tab_metrics1, tab_metrics2, tab_metrics3 = st.tabs([
            "📊 Getiri Analizi",
            "👥 Yatırımcı Analizi",
            "⚠️ Risk Analizi"
        ])

        with tab_metrics1:
            # En yüksek getirili fonlar
            st.markdown("#### 🚀 En Yüksek Getirili Fonlar")
            top_performers = results_df.nlargest(5, '1Ay (%)')[['Fon', '1Ay (%)', '3Ay (%)', '6Ay (%)', 'Yılbaşı (%)']]
            top_performers['1Ay (%)'] = top_performers['1Ay (%)'].apply(
                lambda x: f"{float(x.strip('%')):+.2f}%" if isinstance(x, str) else x)
            top_performers['3Ay (%)'] = top_performers['3Ay (%)'].apply(
                lambda x: f"{float(x.strip('%')):+.2f}%" if isinstance(x, str) else x)
            top_performers['6Ay (%)'] = top_performers['6Ay (%)'].apply(
                lambda x: f"{float(x.strip('%')):+.2f}%" if isinstance(x, str) else x)
            top_performers['Yılbaşı (%)'] = top_performers['Yılbaşı (%)'].apply(
                lambda x: f"{float(x.strip('%')):+.2f}%" if isinstance(x, str) else x)
            st.dataframe(top_performers, use_container_width=True)

        with tab_metrics2:
            # En çok yatırımcı artışı
            st.markdown("#### 📈 En Hızlı Büyüyen Fonlar")
            top_growth = results_df.nlargest(5, 'Yatırımcı Değ. (%)')[
                ['Fon', 'Yatırımcı Değ. (%)', 'Yat. Momentum', '1Ay (%)', '3Ay (%)']]
            top_growth['Yatırımcı Değ. (%)'] = top_growth['Yatırımcı Değ. (%)'].apply(
                lambda x: f"{float(x.strip('%')):+.2f}%" if isinstance(x, str) else x)
            top_growth['Yat. Momentum'] = top_growth['Yat. Momentum'].apply(
                lambda x: f"{x:+.2f}%" if pd.notna(x) else "-")
            top_growth['1Ay (%)'] = top_growth['1Ay (%)'].apply(
                lambda x: f"{float(x.strip('%')):+.2f}%" if isinstance(x, str) else x)
            top_growth['3Ay (%)'] = top_growth['3Ay (%)'].apply(
                lambda x: f"{float(x.strip('%')):+.2f}%" if isinstance(x, str) else x)
            st.dataframe(top_growth, use_container_width=True)

        with tab_metrics3:
            # En düşük riskli fonlar
            st.markdown("#### 🛡️ En Düşük Riskli Fonlar")
            low_risk = results_df.nsmallest(5, 'Maks. Düşüş (%)')[
                ['Fon', 'Maks. Düşüş (%)', 'Volatilite (%)', 'Sharpe Oranı', 'Risk Skoru']]
            low_risk['Maks. Düşüş (%)'] = low_risk['Maks. Düşüş (%)'].apply(
                lambda x: f"{float(x.strip('%')):.2f}%" if isinstance(x, str) else x)
            low_risk['Volatilite (%)'] = low_risk['Volatilite (%)'].apply(
                lambda x: f"{float(x.strip('%')):.2%}" if isinstance(x, str) else x)
            low_risk['Sharpe Oranı'] = low_risk['Sharpe Oranı'].apply(
                lambda x: f"{float(x):.2f}" if isinstance(x, str) and x != '-' else x)
            st.dataframe(low_risk, use_container_width=True)

        # Performans özeti
        st.markdown("### 📊 Piyasa Özeti")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            avg_return_1m = results_df['1Ay (%)'].apply(
                lambda x: float(x.strip('%')) if isinstance(x, str) else 0).mean()
            st.metric("Ortalama 1 Aylık Getiri", f"{avg_return_1m:+.2f}%")

        with col2:
            avg_return_3m = results_df['3Ay (%)'].apply(
                lambda x: float(x.strip('%')) if isinstance(x, str) else 0).mean()
            st.metric("Ortalama 3 Aylık Getiri", f"{avg_return_3m:+.2f}%")

        with col3:
            avg_investor_growth = results_df['Yatırımcı Değ. (%)'].apply(
                lambda x: float(x.strip('%')) if isinstance(x, str) else 0).mean()
            st.metric("Ortalama Yatırımcı Artışı", f"{avg_investor_growth:+.2f}%")

        with col4:
            positive_count = len(
                results_df[results_df['1Ay (%)'].apply(lambda x: float(x.strip('%')) if isinstance(x, str) else 0) > 0])
            st.metric("Pozitif Getirili Fonlar", f"{positive_count}/{len(results_df)}")

    else:
        st.warning("Yeterli veriye sahip fon bulunamadı! (En az 20 günlük veri gerekiyor)")

st.markdown("---")
st.caption(
    "💡 **Gelişmiş Analiz Özellikleri:** 🎯 6 farklı yatırım stratejisi, 📊 Tüm fonları karşılaştırma, 📈 Detaylı metrikler, ⚡ Risk-getiri analizi")