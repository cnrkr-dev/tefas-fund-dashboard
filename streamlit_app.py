import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import os
import locale

# Türkçe gün adları için locale ayarı
try:
    locale.setlocale(locale.LC_TIME, 'tr_TR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'turkish')
    except:
        # Eğer Türkçe locale yoksa, manuel çeviri yapacağız
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
    # Önce locale ile dene, olmazsa manuel çevir
    try:
        day_name = date.strftime('%A')
        return days.get(day_name, day_name)
    except:
        return days.get(date.strftime('%A'), date.strftime('%A'))


# Veri yükleme fonksiyonları - cache yenileme için parametre eklendi
@st.cache_data(ttl=0)  # ttl=0 ile cache süresiz ama manuel refresh ile temizlenebilir
def load_funds(refresh=False):
    """TEFAS funds CSV dosyasını yükler"""
    funds_path = "data/tefas_funds_data.csv"
    if not os.path.exists(funds_path):
        st.error(f"⚠️ {funds_path} dosyası bulunamadı!")
        return pd.DataFrame()

    df = pd.read_csv(funds_path)
    return df


@st.cache_data(ttl=0)
def load_funds_history(refresh=False):
    """TEFAS funds history CSV dosyasını yükler"""
    history_path = "data/tefas_funds_history_data.csv"
    if not os.path.exists(history_path):
        st.error(f"⚠️ {history_path} dosyası bulunamadı!")
        return pd.DataFrame()

    df = pd.read_csv(history_path)

    # change_date sütununu datetime'a çevir
    if 'change_date' in df.columns:
        df['change_date'] = pd.to_datetime(df['change_date'])

    return df


# Refresh butonu için session state
if 'refresh_key' not in st.session_state:
    st.session_state.refresh_key = 0

# Sidebar yerine ana sayfada refresh butonu
col_refresh, col_empty = st.columns([1, 5])
with col_refresh:
    refresh_button = st.button("🔄 Verileri Yenile", use_container_width=True,
                               help="CSV dosyalarındaki en son verileri yükler")

# Refresh butonuna basıldığında cache'i temizle
if refresh_button:
    st.cache_data.clear()
    st.session_state.refresh_key += 1
    st.success("✅ Veriler başarıyla yenilendi! Sayfa yenileniyor...")
    st.rerun()

# Verileri yükle
with st.spinner("Veriler yükleniyor..."):
    funds_df = load_funds(refresh=refresh_button)
    history_df = load_funds_history(refresh=refresh_button)

# Veri kontrolü
if funds_df.empty or history_df.empty:
    st.stop()

# Son yüklenme zamanını göster
st.caption(f"📅 Son veri güncelleme: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

st.markdown("---")

# Filtreleme bölümü
st.subheader("🔍 Filtreleme Seçenekleri")

# Fon seçimi - ayrı satır
selected_fund_display = None
selected_fund_code = "SBH"  # Varsayılan fon kodu

# Fon kodları ve isimlerini birleştir
fund_options = {f"{row['fund_code']} - {row['fund_name']}": row['fund_code']
                for _, row in funds_df.iterrows()}

# Varsayılan olarak SBH fonunu seç
default_index = 0
for i, (display, code) in enumerate(fund_options.items()):
    if code == "SBH":
        default_index = i
        break

selected_fund_display = st.selectbox(
    "📌 Fon Seçiniz",
    options=list(fund_options.keys()),
    index=default_index,
    help="Göstermek istediğiniz fonu seçin"
)
selected_fund_code = fund_options[selected_fund_display]

# Tarih aralığı - ayrı satır
fund_history_all = history_df[history_df['fund_code'] == selected_fund_code].copy()

if not fund_history_all.empty:
    min_date = fund_history_all['change_date'].min().date()
    max_date = fund_history_all['change_date'].max().date()

    # Varsayılan olarak son 60 gün
    default_start_date = max(max_date - timedelta(days=60), min_date)

    date_range = st.slider(
        "📅 Tarih Aralığı Seçin",
        min_value=min_date,
        max_value=max_date,
        value=(default_start_date, max_date),
        format="YYYY-MM-DD",
        help="Göstermek istediğiniz tarih aralığını seçin"
    )
else:
    st.error("Seçilen fon için veri bulunamadı!")
    st.stop()

# Seçilen fonun verilerini filtrele
fund_history = history_df[history_df['fund_code'] == selected_fund_code].copy()

if fund_history.empty:
    st.warning(f"⚠️ {selected_fund_code} kodlu fon için tarihsel veri bulunamadı!")
    st.stop()

# Seçilen tarih aralığına göre filtrele
start_date, end_date = date_range
mask = (fund_history['change_date'].dt.date >= start_date) & (fund_history['change_date'].dt.date <= end_date)
filtered_history = fund_history.loc[mask].sort_values('change_date')

if filtered_history.empty:
    st.warning("Seçilen tarih aralığında veri bulunmamaktadır!")
    st.stop()

st.markdown("---")

# Gösterge panelinde bilgiler - 4 sütun
st.subheader("📊 Özet Bilgiler")

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

st.markdown("---")

# Ana grafik
st.subheader(f"📊 {selected_fund_display} - Zaman Serisi Analizi")

# İkincil eksenli alt grafikler oluştur
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

# Birim fiyat grafiği (1. satır)
fig.add_trace(
    go.Scatter(
        x=filtered_history['change_date'],
        y=filtered_history['unit_price'],
        mode='lines+markers',
        name='Birim Fiyat',
        line=dict(color='#1f77b4', width=2.5),
        marker=dict(size=6, symbol='circle'),
        hovertemplate='<b>📅 Tarih</b>: %{x|%Y-%m-%d}<br>' +
                      '<b>💰 Birim Fiyat</b>: %{y} ₺<br>' +
                      '<extra></extra>'
    ),
    row=1, col=1
)

# Yatırımcı sayısı grafiği (2. satır)
fig.add_trace(
    go.Scatter(
        x=filtered_history['change_date'],
        y=filtered_history['investor_count'],
        mode='lines+markers',
        name='Yatırımcı Sayısı',
        line=dict(color='#2ca02c', width=2.5),
        marker=dict(size=6, symbol='square'),
        fill='tozeroy',
        fillcolor='rgba(44, 160, 44, 0.1)',
        hovertemplate='<b>📅 Tarih</b>: %{x|%Y-%m-%d}<br>' +
                      '<b>👥 Yatırımcı Sayısı</b>: %{y:,.0f}<br>' +
                      '<extra></extra>'
    ),
    row=2, col=1
)

# Toplam fon değeri grafiği (3. satır)
fig.add_trace(
    go.Scatter(
        x=filtered_history['change_date'],
        y=filtered_history['total_fund_value'],
        mode='lines+markers',
        name='Toplam Fon Değeri',
        line=dict(color='#d62728', width=2.5),
        marker=dict(size=6, symbol='diamond'),
        fill='tozeroy',
        fillcolor='rgba(214, 39, 40, 0.1)',
        hovertemplate='<b>📅 Tarih</b>: %{x|%Y-%m-%d}<br>' +
                      '<b>🏦 Toplam Değer</b>: %{y:,.2f} ₺<br>' +
                      '<extra></extra>'
    ),
    row=3, col=1
)

# Grafik düzenlemeleri
fig.update_layout(
    height=900,
    showlegend=False,
    hovermode='x unified',
    plot_bgcolor='white',
    paper_bgcolor='white',
    font=dict(size=12)
)

# Eksen etiketleri ve grid ayarları
fig.update_xaxes(
    title_text="<b>Tarih</b>",
    row=3, col=1,
    showgrid=True,
    gridwidth=1,
    gridcolor='lightgray',
    tickangle=45
)
fig.update_xaxes(
    title_text="",
    row=1, col=1,
    showgrid=True,
    gridwidth=1,
    gridcolor='lightgray'
)
fig.update_xaxes(
    title_text="",
    row=2, col=1,
    showgrid=True,
    gridwidth=1,
    gridcolor='lightgray'
)

fig.update_yaxes(
    title_text="<b>Fiyat (₺)</b>",
    row=1, col=1,
    gridcolor='lightgray',
    zeroline=True,
    zerolinecolor='lightgray'
)
fig.update_yaxes(
    title_text="<b>Yatırımcı Sayısı</b>",
    row=2, col=1,
    gridcolor='lightgray',
    zeroline=True,
    zerolinecolor='lightgray'
)
fig.update_yaxes(
    title_text="<b>Toplam Değer (₺)</b>",
    row=3, col=1,
    gridcolor='lightgray',
    zeroline=True,
    zerolinecolor='lightgray'
)

# Grafiği göster
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# Detaylı veri tablosu
with st.expander("📋 Detaylı Veri Tablosu", expanded=False):
    display_df = filtered_history.copy()

    # Günlük getiri hesapla (bir önceki güne göre birim fiyat değişimi)
    display_df['daily_return'] = display_df['unit_price'].pct_change() * 100

    # Gün adını ekle
    display_df['day_name'] = display_df['change_date'].apply(get_turkish_day_name)

    # Tarih formatını düzenle
    display_df['change_date'] = display_df['change_date'].dt.strftime('%Y-%m-%d')

    # Sütunları yeniden adlandır (Fon Kodu sütununu çıkar)
    display_df = display_df.rename(columns={
        'change_date': 'Tarih',
        'day_name': 'Gün',
        'unit_price': 'Birim Fiyat (₺)',
        'investor_count': 'Yatırımcı Sayısı',
        'total_fund_value': 'Toplam Fon Değeri (₺)',
        'daily_return': 'Günlük Getiri (%)'
    })

    # Fon Kodu sütununu drop et
    if 'fund_code' in display_df.columns:
        display_df = display_df.drop('fund_code', axis=1)

    # Formatlama - Birim Fiyat'ta yuvarlama YOK, orijinal değer olduğu gibi
    display_df['Birim Fiyat (₺)'] = display_df['Birim Fiyat (₺)'].apply(lambda x: str(x))
    display_df['Toplam Fon Değeri (₺)'] = display_df['Toplam Fon Değeri (₺)'].apply(lambda x: f"{x:,.2f}")
    display_df['Yatırımcı Sayısı'] = display_df['Yatırımcı Sayısı'].apply(lambda x: f"{x:,}")
    display_df['Günlük Getiri (%)'] = display_df['Günlük Getiri (%)'].apply(
        lambda x: f"{x:+.4f}%" if pd.notna(x) else "-")

    # Sütun sırasını düzenle (Tarih, Gün, diğerleri)
    column_order = ['Tarih', 'Gün', 'Birim Fiyat (₺)', 'Yatırımcı Sayısı', 'Toplam Fon Değeri (₺)', 'Günlük Getiri (%)']
    display_df = display_df[column_order]

    # Tarihe göre azalan sıralama (en son tarih en başta)
    display_df = display_df.sort_values('Tarih', ascending=False)

    st.dataframe(display_df, use_container_width=True, height=400)

# İstatistiksel özet
with st.expander("📊 İstatistiksel Özet ve Analiz", expanded=False):
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### 💰 Birim Fiyat")
        st.metric("Maksimum", f"{filtered_history['unit_price'].max()}")
        st.metric("Minimum", f"{filtered_history['unit_price'].min()}")
        st.metric("Ortalama", f"{filtered_history['unit_price'].mean()}")
        st.metric("Standart Sapma", f"{filtered_history['unit_price'].std()}")
        st.metric("Değişim Oranı",
                  f"{((filtered_history['unit_price'].iloc[-1] - filtered_history['unit_price'].iloc[0]) / filtered_history['unit_price'].iloc[0] * 100):+.4f}%")

    with col2:
        st.markdown("#### 👥 Yatırımcı Sayısı")
        st.metric("Maksimum", f"{filtered_history['investor_count'].max():,.0f}")
        st.metric("Minimum", f"{filtered_history['investor_count'].min():,.0f}")
        st.metric("Ortalama", f"{filtered_history['investor_count'].mean():,.0f}")
        st.metric("Standart Sapma", f"{filtered_history['investor_count'].std():,.0f}")
        st.metric("Değişim",
                  f"{filtered_history['investor_count'].iloc[-1] - filtered_history['investor_count'].iloc[0]:+,.0f}")

    with col3:
        st.markdown("#### 🏦 Toplam Fon Değeri")
        st.metric("Maksimum", f"{filtered_history['total_fund_value'].max():,.2f} ₺")
        st.metric("Minimum", f"{filtered_history['total_fund_value'].min():,.2f} ₺")
        st.metric("Ortalama", f"{filtered_history['total_fund_value'].mean():,.2f} ₺")
        st.metric("Standart Sapma", f"{filtered_history['total_fund_value'].std():,.2f} ₺")
        last_val = filtered_history['total_fund_value'].iloc[-1]
        first_val = filtered_history['total_fund_value'].iloc[0]
        st.metric("Değişim Oranı", f"{((last_val - first_val) / first_val * 100):+.2f}%" if first_val != 0 else "N/A")

    # Günlük getiri istatistikleri
    st.markdown("---")
    st.markdown("#### 📈 Günlük Getiri Analizi")

    # Günlük getirileri hesapla
    daily_returns = filtered_history['unit_price'].pct_change() * 100

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Ortalama Günlük Getiri", f"{daily_returns.mean():+.4f}%")
    with col2:
        st.metric("Maksimum Günlük Getiri", f"{daily_returns.max():+.4f}%")
    with col3:
        st.metric("Minimum Günlük Getiri", f"{daily_returns.min():+.4f}%")
    with col4:
        st.metric("Günlük Getiri Std. Sapma", f"{daily_returns.std():+.4f}%")

    # Gün bazında ortalama getiriler
    st.markdown("---")
    st.markdown("#### 📅 Gün Bazında Ortalama Getiriler")

    # Gün adlarını ekle
    filtered_history_with_days = filtered_history.copy()
    filtered_history_with_days['day_name'] = filtered_history_with_days['change_date'].apply(get_turkish_day_name)
    filtered_history_with_days['daily_return'] = filtered_history_with_days['unit_price'].pct_change() * 100

    # Gün bazında ortalama getirileri hesapla
    day_returns = filtered_history_with_days.groupby('day_name')['daily_return'].agg(['mean', 'count']).round(4)
    day_returns = day_returns.rename(columns={'mean': 'Ortalama Getiri (%)', 'count': 'Gün Sayısı'})

    # Gün sıralamasını düzenle
    day_order = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
    day_returns = day_returns.reindex(day_order)

    st.dataframe(day_returns, use_container_width=True)

# Korelasyon bilgisi
with st.expander("📈 Metrikler Arası Korelasyon", expanded=False):
    corr_price_investors = filtered_history['unit_price'].corr(filtered_history['investor_count'])
    corr_price_value = filtered_history['unit_price'].corr(filtered_history['total_fund_value'])
    corr_investors_value = filtered_history['investor_count'].corr(filtered_history['total_fund_value'])

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Birim Fiyat & Yatırımcı Sayısı",
            f"{corr_price_investors:.3f}",
            help="1'e yakın pozitif değerler güçlü pozitif korelasyonu gösterir"
        )

    with col2:
        st.metric(
            "Birim Fiyat & Toplam Değer",
            f"{corr_price_value:.3f}",
            help="1'e yakın pozitif değerler güçlü pozitif korelasyonu gösterir"
        )

    with col3:
        st.metric(
            "Yatırımcı Sayısı & Toplam Değer",
            f"{corr_investors_value:.3f}",
            help="1'e yakın pozitif değerler güçlü pozitif korelasyonu gösterir"
        )

st.markdown("---")
st.caption(
    "💡 **İpuçları:** Grafik üzerinde fare ile yakınlaştırma/uzaklaştırma yapabilir, veri noktalarına tıklayarak detayları görebilirsiniz. 🔄 Verileri Yenile butonu ile CSV dosyalarındaki en son verileri yükleyebilirsiniz.")