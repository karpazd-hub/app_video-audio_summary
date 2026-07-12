
import streamlit as st
from moviepy import VideoFileClip
from moviepy import AudioFileClip
import os
from pathlib import Path
from openai import OpenAI
from dotenv import dotenv_values
import hashlib


# config + title
st.set_page_config(page_title="Audio/Video Summarizer", layout="centered")



# init total cost
if "total_cost" not in st.session_state:
    st.session_state.total_cost = 0.0
# init

if "last_file" not in st.session_state:
    st.session_state.last_file = None
if "show_dialog" not in st.session_state:
    st.session_state.show_dialog = False


if "stage" not in st.session_state:
    st.session_state.stage = "idle"

if "transcription" not in st.session_state:
    st.session_state.transcription = ""

if "summary" not in st.session_state:
    st.session_state.summary = ""




# tytuł + metric
st.title("Transkrypcja i Podsumowanie Audio/Video")
cost_placeholder = st.empty()
cost_placeholder.metric(
    "💰 Koszt sesji",
    f"${st.session_state.total_cost:.4f}"
)


# clean up
def cleanup_temp_files(*paths):
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

# dialog
@st.dialog("Potwierdzenie kosztów")
def confirm_cost_dialog(estimated_cost):
    st.write(f"Szacowany koszt operacji: **${estimated_cost:.4f}**")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Kontynuuj", use_container_width=True):
            st.session_state.show_dialog = False
            st.session_state.stage = "run_pipeline"
            st.rerun()

    with col2:
        if st.button("❌ Anuluj", use_container_width=True):
            st.session_state.show_dialog = False
            st.rerun()

# # Inicjalizacja klienta OpenAI
# env = dotenv_values(".env")
# openai_client = OpenAI(api_key=env["OPENAI_API_KEY"])

# API_KEY
if not st.session_state.get("openai_api_key"):
    # Najpierw szukamy klucza w bezpiecznych sekretach (lokalnie lub w Streamlit Cloud)
    if "OPENAI_API_KEY" in st.secrets:
        st.session_state["openai_api_key"] = st.secrets["OPENAI_API_KEY"]
    else:
        # Jeśli klucza nie ma w sekretach, prosimy użytkownika o wpisanie go ręcznie
        st.info("Dodaj swój klucz API OpenAI, aby móc korzystać z tej aplikacji")
        user_key = st.text_input("Klucz API", type="password")
        if user_key:
            st.session_state["openai_api_key"] = user_key
            st.rerun()

# Blokada aplikacji
if not st.session_state.get("openai_api_key"):
    st.stop()

# Inicjalizacja Klienta
openai_client = OpenAI(api_key=st.session_state["openai_api_key"])




# def koszty
def calc_cost(input_tokens, output_tokens, in_price, out_price):
    return (input_tokens / 1_000_000) * in_price + (output_tokens / 1_000_000) * out_price

# def szacunkowe koszty
@st.cache_data
def estimate_cost(file_path):
    try:
        ext = Path(file_path).suffix.lower()

        if ext in [".mp3", ".wav", ".m4a"]:
            audio = AudioFileClip(file_path)
            duration_sec = audio.duration
            audio.close()
        else:
            video = VideoFileClip(file_path)
            duration_sec = video.duration
            video.close()

        duration_min = duration_sec / 60

        # Whisper (real cost)
        whisper_cost = duration_min * 0.006

        # bardziej realistyczne NLP
        words_per_min = 170
        tokens_per_word = 1.25

        estimated_tokens = duration_min * words_per_min * tokens_per_word

        # GPT-4o pricing (bardziej realistyczny model miksu input/output)
        input_tokens = estimated_tokens * 0.85
        output_tokens = estimated_tokens * 0.15

        input_cost = input_tokens / 1_000_000 * 2.5
        output_cost = output_tokens / 1_000_000 * 10

        total = whisper_cost + input_cost + output_cost

        return total

    except Exception:
        return None


# 1. Upload pliku
uploaded_file = st.file_uploader(
    "Wgraj plik wideo lub audio", 
    type=["mp4", "avi", "mov", "mp3", "wav", "m4a"]
)



# st.empty dla statusów
placeholder = st.empty()


# funkcja upload
if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    current_file_id = hashlib.md5(file_bytes).hexdigest()

    

    # NOWY UPLOAD → usuń stare temp pliki
    if st.session_state.last_file and st.session_state.last_file != current_file_id:
        cleanup_temp_files(
            st.session_state.get("temp_input_path"),
            st.session_state.get("temp_audio_path")
        )

    st.session_state.last_file = current_file_id


    # reset tylko przy NOWYM pliku (opcjonalnie)
    if st.session_state.get("file_id") != current_file_id:
        

        # cleanup poprzedniego pliku
        cleanup_temp_files(
            st.session_state.get("temp_input_path"),
            st.session_state.get("temp_audio_path")
        )

        # reset ONLY dla nowego pliku
        st.session_state.stage = "idle"
        st.session_state.transcription = ""
        st.session_state.summary = ""
        st.session_state.total_cost = 0.0
        st.session_state.show_dialog = False

        st.session_state.file_id = current_file_id

        
    

    
        

    temp_input_path = f"temp_input_{uploaded_file.name}"
    temp_audio_path = f"temp_audio_{uploaded_file.name}.mp3"

    st.session_state.temp_input_path = temp_input_path
    st.session_state.temp_audio_path = temp_audio_path

    
    with open(temp_input_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Podgląd
    file_extension = uploaded_file.name.split(".")[-1].lower()
    is_video = file_extension in ["mp4", "avi", "mov"]
    is_audio = file_extension in ["mp3", "wav", "m4a"]

    if is_video:
        st.video(uploaded_file)

    elif is_audio:
        st.audio(uploaded_file)

    estimated_cost = estimate_cost(temp_input_path)
    if estimated_cost is None:
        estimated_cost = 0.02

    # ==========================================
    # WYNIKI JUŻ WYGNEROWANE
    # ==========================================

    if st.session_state.stage == "done":

        st.divider()
        st.subheader("Transkrypcja")

        st.text_area(
            label="Transkrypcja",
            value=st.session_state.transcription,
            height=300,
            label_visibility="collapsed",
            key="transcription_done"
        )

        st.download_button(
            label="Pobierz transkrypcję",
            data=st.session_state.transcription,
            file_name="transkrypcja.txt",
            mime="text/plain"
        )

        st.divider()
        st.subheader("Podsumowanie")

        st.text_area(
            label="Podsumowanie",
            value=st.session_state.summary,
            height=300,
            label_visibility="collapsed",
            key="summary_done"
        )

        st.download_button(
            label="Pobierz podsumowanie",
            data=st.session_state.summary,
            file_name="podsumowanie.txt",
            mime="text/plain"
        )

        st.stop()


    # ==========================================
    # EKRAN STARTOWY
    # ==========================================

    if st.session_state.stage == "idle":

        if st.button("▶ Rozpocznij przetwarzanie"):
            st.session_state.show_dialog = True
            

        if st.session_state.get("show_dialog", False):
            confirm_cost_dialog(estimated_cost)

        st.stop()

    
        
    # Rozpoznawanie rozszerzenia pliku
    file_extension = uploaded_file.name.split(".")[-1].lower()
    is_video = file_extension in ["mp4", "avi", "mov"]
    is_audio = file_extension in ["mp3", "wav", "m4a"]

    
    
    try:
        # 2. Wyodrębnianie audio (jeśli to wideo) lub przygotowanie pliku audio
        if is_video:
            if not os.path.exists(temp_audio_path):
                with st.spinner("Krok 1/3: Wyodrębnianie dźwięku z wideo..."):
                    placeholder.info("Krok 1/3: Wyodrębnianie dźwięku z wideo")

                    video = VideoFileClip(temp_input_path)
                    video.audio.write_audiofile(temp_audio_path, logger=None)
                    video.close()
            # TUTAJ DEFINIUJEMY ZMIENNĄ, KTÓRA WCZEŚNIEJ ŚWIECIŁA NA ŻÓŁTO
            final_audio_to_transcribe = temp_audio_path
        else:
            final_audio_to_transcribe = temp_input_path


               
        # transkrypcja
        with st.spinner("Krok 2/3: Transkrypcja na tekst..."):
            placeholder.info("Krok 2/3: Transkrypcja na tekst")

            with open(final_audio_to_transcribe, "rb") as audio_file:
                transcript_response = openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )

            full_text = transcript_response.text
            st.session_state.transcription = full_text   

            duration_seconds = transcript_response.usage.seconds
            duration_minutes = duration_seconds / 60

            transcription_cost = duration_minutes * 0.006
            st.session_state.total_cost += transcription_cost

            cost_placeholder.metric(
                "💰 Koszt sesji",
                f"${st.session_state.total_cost:.4f}"
            )

        
        
        

        

       
        
          
                

      
        
        with st.spinner("Krok 3/3: Generowanie podsumowania..."):
            placeholder.info("Krok 3/3: Generowanie podsumowania")

            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Jesteś pomocnym asystentem. Zrób zwięzłe, strukturyzowane podsumowanie poniższego tekstu w punktach, w języku polskim."},
                    {"role": "user", "content": full_text}
                ]
            )

            summary = response.choices[0].message.content

            # ZAPIS DO SESSION STATE
            st.session_state.transcription = full_text
            st.session_state.summary = summary

            usage = response.usage

            summary_cost = calc_cost(
                usage.prompt_tokens,
                usage.completion_tokens,
                in_price=2.5,
                out_price=10
            )

            st.session_state.total_cost += summary_cost

            cost_placeholder.metric(
                "💰 Koszt sesji",
                f"${st.session_state.total_cost:.4f}"
            )

            placeholder.empty()

            #st.session_state.processed_files.add(current_file_id)
            st.session_state.stage = "done"
            

            st.rerun()

         
     
        
    except Exception as e:
        placeholder.empty()
        st.error(f"Wystąpił błąd: {e}")

    # UWAGA: Sekcja "finally" została usunięta, aby Streamlit 
    # nie kasował plików podczas generowania przycisków download.

else:
    # Ten komunikat wyświetli się TYLKO wtedy, gdy uploaded_file jest puste (None)
    st.info("Dodaj plik Wideo/Audio w polu powyżej, aby rozpocząć.")