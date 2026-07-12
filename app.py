import os
import streamlit as st
from openai import OpenAI
from pydub import AudioSegment

# Tworzenie katalogu na zapisywane pliki, jeśli nie istnieje
MEDIA_DIR = "saved_media"
os.makedirs(MEDIA_DIR, exist_ok=True)

st.title("Aplikacja do Podsumowywania Audio i Wideo")

# Krok 1: Wymaganie podania klucza API od użytkownika
st.info("Wprowadź swój klucz API OpenAI, aby korzystać z aplikacji.")
user_api_key = st.text_input("Klucz API OpenAI:", type="password", help="Twój klucz API jest używany wyłącznie do autoryzacji zapytań w tej sesji.")

# Blokada aplikacji do momentu wprowadzenia klucza
if not user_api_key:
    st.warning("Proszę wprowadzić klucz API powyżej, aby odblokować funkcje aplikacji.")
    st.stop()

# Inicjalizacja klienta OpenAI z kluczem użytkownika
try:
    client = OpenAI(api_key=user_api_key)
except Exception as e:
    st.error(f"Nie udało się zainicjalizować klienta OpenAI: {e}")
    st.stop()

st.success("Klucz API został wprowadzony. Możesz teraz korzystać z aplikacji.")
st.divider()

# Krok 2: Upload pliku (Obsługa formatów audio i wideo)
uploaded_file = st.file_uploader(
    "Wybierz plik audio lub wideo", 
    type=["mp3", "wav", "m4a", "mp4", "avi", "mov", "mkv"]
)

if uploaded_file is not None:
    # Określenie typu pliku
    file_extension = os.path.splitext(uploaded_file.name)[1].lower()
    is_video = file_extension in [".mp4", ".avi", ".mov", ".mkv"]
    
    # Ścieżka zapisu oryginalnego pliku
    saved_file_path = os.path.join(MEDIA_DIR, uploaded_file.name)
    
    # Zapisanie pliku wejściowego na dysku
    with open(saved_file_path, "wb") as f:
        f.write(uploaded_file.read())
    
    st.success(f"Zapisano plik: {uploaded_file.name}")

    # v1 i v2: Wyświetlanie / odtwarzanie przesłanego pliku
    if is_video:
        st.subheader("Odtwarzacz Wideo")
        st.video(saved_file_path)
    else:
        st.subheader("Odtwarzacz Audio")
        st.audio(saved_file_path)

    # v3: Wyodrębnienie audio z wideo (jeżeli przesłano wideo)
    audio_to_transcribe_path = saved_file_path
    
    if is_video:
        st.info("Trwa wyodrębnianie audio z pliku wideo...")
        try:
            extracted_audio_name = os.path.splitext(uploaded_file.name)[0] + ".mp3"
            extracted_audio_path = os.path.join(MEDIA_DIR, extracted_audio_name)
            
            # Konwersja za pomocą pydub
            video_audio = AudioSegment.from_file(saved_file_path)
            video_audio.export(extracted_audio_path, format="mp3")
            
            audio_to_transcribe_path = extracted_audio_path
            st.success("Wyodrębniono ścieżkę audio.")
        except Exception as e:
            st.error(f"Wystąpił błąd podczas wyodrębniania audio: {e}")
            st.stop()

    st.divider()
    
    # Przycisk uruchamiający proces
    if st.button("Generuj podsumowanie nagrania"):
        transcription_text = ""
        
        # v4: Transkrypcja audio (proces w tle)
        with st.spinner("Trwa przetwarzanie nagrania (transkrypcja)..."):
            try:
                with open(audio_to_transcribe_path, "rb") as audio_file:
                    transcription_response = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file
                    )
                transcription_text = transcription_response.text
                
                # Zapis transkrypcji do pliku tekstowego na dysku
                transcription_txt_path = os.path.join(MEDIA_DIR, os.path.splitext(uploaded_file.name)[0] + "_transkrypcja.txt")
                with open(transcription_txt_path, "w", encoding="utf-8") as f:
                    f.write(transcription_text)
                
            except Exception as e:
                st.error(f"Błąd podczas transkrypcji. Upewnij się, że wprowadzony klucz API jest poprawny. Szczegóły: {e}")
                st.stop()

        # v5: Generowanie podsumowania tekstu i jego wyświetlenie
        with st.spinner("Trwa generowanie podsumowania (GPT-4o)..."):
            try:
                prompt = (
                    "Przeanalizuj poniższą transkrypcję i przygotuj zwięzłe podsumowanie "
                    "w najważniejszych punktach. Skup się na kluczowych informacjach i wnioskach.\n\n"
                    f"Tekst:\n{transcription_text}"
                )
                
                summary_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Jesteś pomocnym asystentem, który precyzyjnie podsumowuje nagrania tekstowe."},
                        {"role": "user", "content": prompt}
                    ]
                )
                
                summary_text = summary_response.choices[0].message.content
                
                # Zapis podsumowania do pliku tekstowego
                summary_txt_path = os.path.join(MEDIA_DIR, os.path.splitext(uploaded_file.name)[0] + "_podsumowanie.txt")
                with open(summary_txt_path, "w", encoding="utf-8") as f:
                    f.write(summary_text)
                
                # Prezentacja wyników użytkownikowi (tylko podsumowanie)
                st.subheader("Podsumowanie w najważniejszych punktach:")
                st.markdown(summary_text)
                st.info(f"Wyniki zostały zapisane lokalnie w folderze '{MEDIA_DIR}'.")
                
            except Exception as e:
                st.error(f"Błąd podczas generowania podsumowania: {e}")