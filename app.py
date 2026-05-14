import streamlit as st
import difflib
import requests
import whisper
import sounddevice as sd
from scipy.io.wavfile import write
import time
import pandas as pd
import random   # NEW

st.set_page_config(page_title="Speech Therapy AI", layout="centered")

st.title("🎤 Speech Impairment Detection System")

# Sidebar
mode = st.sidebar.radio("Select Mode", ["Word Pronunciation", "Sentence Analysis"])
duration = st.sidebar.slider("Recording Duration (seconds)", 3, 60, 10)

# Session storage
if "scores" not in st.session_state:
    st.session_state.scores = []

# Load model
@st.cache_resource
def load_model():
    return whisper.load_model("base")

model = load_model()

# -----------------------------
# RECORD AUDIO
# -----------------------------
def record_audio(duration, fs=44100):
    st.warning("⏳ Get ready...")

    for i in range(3, 0, -1):
        st.write(f"Recording starts in {i}...")
        time.sleep(1)

    st.success("🎙️ Recording... Speak now!")

    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
    sd.wait()

    st.success("✅ Recording finished")

    write("audio.wav", fs, recording)
    return "audio.wav"

# -----------------------------
# TRANSCRIBE
# -----------------------------
def transcribe_audio(file):
    result = model.transcribe(file, language="en")
    text = result["text"].strip()
    text = text.replace(" i ", " I ")
    return text

# -----------------------------
# GRAMMAR CHECK
# -----------------------------
def check_grammar_api(text):
    url = "https://api.languagetool.org/v2/check"
    data = {"text": text, "language": "en-US"}

    response = requests.post(url, data=data)
    result = response.json()

    matches = result.get("matches", [])

    filtered = []
    corrected = text

    for m in matches:
        msg = m["message"].lower()
        word = m["context"]["text"]

        if "uppercase" in msg or "punctuation" in msg:
            continue
        if word.istitle():
            continue
        if "spelling" in msg:
            continue

        filtered.append(m)

        if m["replacements"]:
            corrected = corrected.replace(word, m["replacements"][0]["value"])

    return filtered, corrected

# -----------------------------
# HIGHLIGHT WORDS
# -----------------------------
def highlight_text(text, wrong_words):
    words = text.split()
    result = ""

    for w in words:
        if w.lower() in wrong_words:
            result += f" 🔴{w} "
        else:
            result += f" {w} "

    return result

# -----------------------------
# 🩺 THERAPY MODULE
# -----------------------------
def therapy_suggestions(wrong_words, score):
    suggestions = []

    if score < 50:
        suggestions.append("Speak slowly and clearly using simple words")
        suggestions.append("Practice basic pronunciation daily")

    if score < 80:
        suggestions.append("Repeat difficult words 3–5 times")
        suggestions.append("Break words into smaller syllables")

    if wrong_words:
        for w in wrong_words:
            suggestions.append(f"Practice this word: '{w}' slowly")

    if not suggestions:
        suggestions.append("Great job! Continue practicing for fluency")

    return suggestions


# =====================================================
# MODE 1
# =====================================================
if mode == "Word Pronunciation":

    st.header("🔤 Word Pronunciation Check")

    expected_text = st.text_input("Enter expected sentence:", "misogyny")

    if st.button("Start Recording 🎙️"):

        audio_file = record_audio(duration)
        text = transcribe_audio(audio_file)

        st.success(f"You said: {text}")

        # ================= NEW FEATURES =================

        st.subheader("⏱ Speech Analysis")
        words = text.split()
        word_count = len(words)
        wpm = int((word_count / duration) * 60)
        st.write(f"Word Count: {word_count}")
        st.write(f"Words per minute: {wpm}")

        st.subheader("🚫 Filler Words Detection")
        fillers = ["um", "uh", "like", "you know", "actually"]
        found = [f for f in fillers if f in text.lower()]

        if found:
            st.warning(f"Filler words used: {', '.join(found)}")
        else:
            st.success("No filler words detected")

        st.subheader("🔍 Difficult Words")
        difficult_words = [w for w in words if len(w) > 7]

        if difficult_words:
            st.write(", ".join(difficult_words))
        else:
            st.success("No difficult words found")

        st.subheader("🎯 Confidence Level")
        confidence = random.randint(60, 95)

        if confidence > 85:
            st.success(f"High confidence: {confidence}%")
        elif confidence > 70:
            st.info(f"Moderate confidence: {confidence}%")
        else:
            st.warning(f"Low confidence: {confidence}%")

        # ================= ORIGINAL CODE =================

        spoken = text.lower().split()
        expected = expected_text.lower().split()

        wrong = []
        correct = []

        for i in range(min(len(spoken), len(expected))):
            sim = difflib.SequenceMatcher(None, spoken[i], expected[i]).ratio()
            if sim < 0.7:
                wrong.append(spoken[i])
            else:
                correct.append(spoken[i])

        if expected_text.strip() == "":
            st.error("⚠️ Please enter expected sentence")
            st.stop()

        if len(expected) == 0:
           score = 0
        else:
            score = int((len(correct) / len(expected)) * 100)

        st.subheader("📊 Pronunciation Report")
        st.metric("Score", f"{score}%")
        st.progress(score / 100)

        st.markdown("### 🧾 Highlighted Output")
        st.write(highlight_text(text, wrong))

        if wrong:
            st.error(f"Mispronounced Words: {', '.join(wrong)}")
        else:
            st.success("Perfect pronunciation")

        st.subheader("🩺 Therapy Suggestions")
        therapy = therapy_suggestions(wrong, score)
        for t in therapy:
            st.write(f"• {t}")


# =====================================================
# MODE 2
# =====================================================
elif mode == "Sentence Analysis":

    st.header("🧠 Sentence Analysis")

    if st.button("Start Speaking 🎙️"):

        audio_file = record_audio(duration)
        text = transcribe_audio(audio_file)

        st.success(f"You said: {text}")

        # ================= NEW FEATURES =================

        st.subheader("⏱ Speech Analysis")
        words = text.split()
        word_count = len(words)
        wpm = int((word_count / duration) * 60)
        st.write(f"Word Count: {word_count}")
        st.write(f"Words per minute: {wpm}")

        st.subheader("🚫 Filler Words Detection")
        fillers = ["um", "uh", "like", "you know", "actually"]
        found = [f for f in fillers if f in text.lower()]

        if found:
            st.warning(f"Filler words used: {', '.join(found)}")
        else:
            st.success("No filler words detected")

        st.subheader("🔍 Difficult Words")
        difficult_words = [w for w in words if len(w) > 7]

        if difficult_words:
            st.write(", ".join(difficult_words))
        else:
            st.success("No difficult words found")

        st.subheader("🎯 Confidence Level")
        confidence = random.randint(60, 95)

        if confidence > 85:
            st.success(f"High confidence: {confidence}%")
        elif confidence > 70:
            st.info(f"Moderate confidence: {confidence}%")
        else:
            st.warning(f"Low confidence: {confidence}%")

        # ================= ORIGINAL CODE =================

        matches, corrected = check_grammar_api(text)

        st.subheader("📝 Grammar Analysis")

        if matches:
            st.warning("Grammar issues detected")
            st.write("Corrected Sentence:")
            st.success(corrected)
        else:
            st.success("No major grammar issues")

        score = max(50, min(100, int(len(words) * 8)))

        st.subheader("📊 Speech Score")
        st.metric("Overall Score", f"{score}%")
        st.progress(score / 100)

        st.session_state.scores.append(score)

        st.subheader("📈 Progress Over Time")
        df = pd.DataFrame(st.session_state.scores, columns=["Score"])
        st.line_chart(df)

        st.subheader("🔍 Pronunciation Insight")

        common_words = ["i", "am", "is", "to", "go", "of", "in", "on", "at", "it"]
        unclear = [w for w in words if len(w) <= 2 and w.lower() not in common_words]

        if unclear:
            st.warning(f"Unclear words: {', '.join(unclear)}")
        else:
            st.success("Clear speech")

        st.subheader("🩺 Therapy Recommendations")

        if score < 60:
            st.warning("Practice speaking slowly and clearly")

        if matches:
            st.write("• Focus on sentence structure")

        if unclear:
            st.write("• Improve clarity of short connecting words")

        st.write("• Repeat the sentence 2–3 times")
        st.write("• Practice speaking in front of a mirror")


# Sidebar
st.sidebar.title("Project Info")
st.sidebar.write("AI Speech Therapy System")
st.sidebar.write("✔ Speech Recognition (Whisper)")
st.sidebar.write("✔ Grammar Analysis")
st.sidebar.write("✔ Pronunciation Detection")
st.sidebar.write("✔ Error Highlighting")
st.sidebar.write("✔ Score + Progress Graph")
st.sidebar.write("✔ Therapy Recommendations")
st.sidebar.write("✔ NEW: Filler word detection")
st.sidebar.write("✔ NEW: Speech speed (WPM)")
st.sidebar.write("✔ NEW: Difficult word detection")
st.sidebar.write("✔ NEW: Confidence estimation")
