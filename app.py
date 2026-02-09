import streamlit as st
import pandas as pd
from openai import OpenAI
import json
import urllib.parse
import os

# ==========================================
# ⚙️ KONFIGURACJA (Obsługa Chmury i Lokalna)
# ==========================================
# 1. Najpierw sprawdzamy, czy klucz jest w "Sejfie" chmury (Streamlit Cloud)
if "API_KEY" in st.secrets:
    OPENAI_KEY = st.secrets["API_KEY"]
# 2. Jeśli nie, sprawdzamy, czy jest w pliku config.py (Lokalnie u Ciebie)
else:
    try:
        from config import API_KEY
        OPENAI_KEY = API_KEY
    except ImportError:
        st.error("❌ Brak klucza API! Jeśli jesteś lokalnie: stwórz plik config.py. Jeśli w chmurze: ustaw Secrets.")
        st.stop()

FILENAME_CSV = "baza_piosenek.csv"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE_PATH = os.path.join(BASE_DIR, FILENAME_CSV)

# ==========================================
# 🧠 FUNKCJE (LOGIKA)
# ==========================================
def analyze_request_smart(client, user_mood, user_genre, unique_genres_in_db):
    # Lista gatunków jako tekst dla AI
    genres_list_str = ", ".join([str(g) for g in unique_genres_in_db])
    
    prompt = f"""
    Jesteś profesjonalnym DJ-em. 
    1. Nastrój użytkownika: "{user_mood}"
    2. Preferowany gatunek: "{user_genre}"
    3. Dostępne gatunki w bazie: [{genres_list_str}]
    
    Zadanie:
    A. Określ Valence (0.0 - 1.0) i Energy (0.0 - 1.0).
    B. Wybierz pasujące gatunki z bazy (synonimy). Np. jak user chce "rap", wybierz "hiphop", "drill" itp.
    
    Zwróć JSON: {{
        "valence": <float>, 
        "energy": <float>, 
        "diagnosis": "<krótki opis emocji>",
        "selected_genres": ["gatunek1", ...] (lub ["ALL"])
    }}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        return data.get('valence'), data.get('energy'), data.get('diagnosis'), data.get('selected_genres')
    except Exception as e:
        return 0.5, 0.5, "Błąd AI", ["ALL"]

def find_matching_songs(valence, energy, selected_genres, limit=5):
    if not os.path.exists(FILE_PATH):
        return pd.DataFrame()

    try:
        df = pd.read_csv(FILE_PATH, on_bad_lines='skip')
        
        # Filtrowanie po gatunku
        if "ALL" not in selected_genres:
            df = df[df['genre'].isin(selected_genres)]
            # Jak nic nie znajdzie w tych gatunkach, szukaj wszędzie (fallback)
            if df.empty:
                df = pd.read_csv(FILE_PATH, on_bad_lines='skip')
        
        # Obliczanie odległości matematycznej
        working_df = df.copy()
        working_df['distance'] = (abs(working_df['valence'] - valence) * 1.5 + abs(working_df['energy'] - energy))
        
        # Wybierz najlepsze i wylosuj 5
        candidates = working_df.sort_values('distance').head(30)
        
        if not candidates.empty:
            return candidates.sample(n=min(len(candidates), limit))
        else:
            return pd.DataFrame()
    except:
        return pd.DataFrame()

# ==========================================
# 🎨 WYGLĄD STRONY (UI)
# ==========================================

# Ustawienia strony (Tytuł w przeglądarce i ikona)
st.set_page_config(page_title="MOAI 2026", page_icon="🎧", layout="centered")

# Nagłówek
st.title("🎧 MOAI 2026 - Twój AI DJ")
st.markdown("Opisz, jak się czujesz, a sztuczna inteligencja dobierze idealną muzykę z Twojej bazy.")

# Wczytanie gatunków na start (żeby AI wiedziało co ma w bazie)
try:
    df_start = pd.read_csv(FILE_PATH, on_bad_lines='skip')
    unique_genres = [x for x in df_start['genre'].unique() if str(x) != 'nan']
except:
    st.error("⚠️ Nie znaleziono pliku bazy danych (csv).")
    unique_genres = []

# Formularz
with st.container():
    col1, col2 = st.columns(2)
    with col1:
        mood = st.text_input("Jak się czujesz?", placeholder="np. wściekła, zakochana, chcę spać")
    with col2:
        genre = st.text_input("Gatunek (opcjonalnie)", placeholder="np. rap, pop (lub puste)")

    generate_btn = st.button("🎵 Generuj Playlistę", type="primary")

# Logika po kliknięciu
if generate_btn and mood:
    client = OpenAI(api_key=OPENAI_KEY)
    
    with st.spinner('🤖 AI analizuje Twoje emocje i przeszukuje bazę...'):
        v, e, diag, genres = analyze_request_smart(client, mood, genre, unique_genres)
        playlist = find_matching_songs(v, e, genres)

    # Wyświetlanie wyników
    st.markdown("---")
    st.success(f"Diagnoza: {diag.upper()}")
    
    # Kafelki z parametrami
    m1, m2, m3 = st.columns(3)
    m1.metric("Radość (Valence)", f"{v:.2f}")
    m2.metric("Energia (Energy)", f"{e:.2f}")
    
    # Ładne wyświetlanie listy gatunków
    if "ALL" in genres:
        genres_display = "Wszystkie"
    else:
        genres_display = ", ".join(genres)
    m3.metric("Wybrane gatunki", genres_display)

    st.subheader("🎧 Twoja Playlista:")

    if not playlist.empty:
        for index, row in playlist.iterrows():
            artist = row['artist']
            track = row['track_name']
            genre_tag = row['genre']
            
            # Generowanie linku do Spotify Search
            query = urllib.parse.quote(f"{artist} {track}")
            link = f"https://open.spotify.com/search/{query}"
            
            # Karta piosenki
            with st.container():
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{artist} - {track}**")
                    st.caption(f"🏷️ {genre_tag}")
                with c2:
                    st.link_button("Odtwórz ▶️", link)
                st.divider()
    else:
        st.warning("Nie znaleziono pasujących piosenek. Spróbuj zmienić opis.")

elif generate_btn and not mood:
    st.warning("⚠️ Musisz wpisać, jak się czujesz!")