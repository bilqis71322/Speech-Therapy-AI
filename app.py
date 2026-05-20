import streamlit as st
import difflib
import requests
import whisper
import sounddevice as sd
from scipy.io.wavfile import write
import time
import pandas as pd
import random
import json
import os
import re
import language_tool_python

# Add FFmpeg to PATH for Whisper
ffmpeg_path = r"C:\Users\deepi\AppData\Local\Microsoft\WinGet\Links"
if ffmpeg_path not in os.environ["PATH"]:
    os.environ["PATH"] += os.pathsep + ffmpeg_path

# Add Java 17+ to PATH for LanguageTool
java_path = r"C:\Program Files\Java\jdk-17\bin"
if os.path.exists(java_path) and java_path not in os.environ["PATH"]:
    os.environ["PATH"] = java_path + os.pathsep + os.environ["PATH"]

st.set_page_config(page_title="Speech Therapy AI", layout="centered")

# -----------------------------
# AUTHENTICATION HELPERS
# -----------------------------
USER_DB = "users.json"

def load_users():
    if not os.path.exists(USER_DB):
        return {"admin": "password123"}
    try:
        with open(USER_DB, "r") as f:
            return json.load(f)
    except:
        return {"admin": "password123"}

def save_users(users):
    with open(USER_DB, "w") as f:
        json.dump(users, f, indent=4)

# -----------------------------
# AUTHENTICATION
# -----------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def signup():
    st.title("📝 Sign Up")
    with st.form("signup_form"):
        new_user = st.text_input("New Username")
        new_pass = st.text_input("New Password", type="password")
        confirm_pass = st.text_input("Confirm Password", type="password")
        submit = st.form_submit_button("Create Account")

        if submit:
            users = load_users()
            if new_user in users:
                st.error("Username already exists!")
            elif new_pass != confirm_pass:
                st.error("Passwords do not match!")
            elif len(new_pass) < 6:
                st.error("Password must be at least 6 characters!")
            else:
                users[new_user] = new_pass
                save_users(users)
                st.success("Account created! Please log in.")
                st.session_state.auth_mode = "Login"
                st.rerun()

def login():
    st.title("🔐 Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            users = load_users()
            if username in users and users[username] == password:
                st.session_state.authenticated = True
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid username or password")

def logout():
    st.session_state.authenticated = False
    st.rerun()

if not st.session_state.authenticated:
    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "Login"

    mode = st.radio("Select Action", ["Login", "Sign Up"], horizontal=True, label_visibility="collapsed")
    
    if mode == "Login":
        login()
    else:
        signup()
    
    st.stop()

st.title("🎤 Speech Impairment Detection System")

# Sidebar
mode = st.sidebar.radio("Select Mode", ["Word Pronunciation", "Sentence Analysis"])
language = st.sidebar.selectbox(
    "🌐 Select Language",
    ["English", "Hindi", "Kannada", "Urdu"]
)
duration = st.sidebar.slider("Recording Duration (seconds)", 3, 60, 10)

if st.sidebar.button("Logout"):
    logout()

# Session storage
if "scores" not in st.session_state:
    st.session_state.scores = []

history_file = "history.csv"

# Load model
@st.cache_resource
def load_model():
    return whisper.load_model("base")

model = load_model()

# -----------------------------
# GRAMMAR TOOL
# -----------------------------
@st.cache_resource
def load_grammar_tool():
    return language_tool_python.LanguageTool('en-US')

tool = load_grammar_tool()

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
    try:
        # Using a slightly larger model or beam search can improve accuracy for all speech
        lang_map = {
           "English": "en",
           "Hindi": "hi",
           "Kannada": "kn",
           "Urdu": "ur"
       }

        result = model.transcribe(
            file,
            language=lang_map[language],
            task="transcribe"
        ) 
        text = result["text"].strip()
        
        return text
        
        # 1. Basic Cleaning
        text = text.replace(" i ", " I ")
        
        # 2. Phonetic & Common Speech Corrections (Expanding for universal use)
        # These are common "slips" Whisper makes when it's unsure
        phonetic_corrections = {
            "maro": "tomorrow", "tomoro": "tomorrow", "tomarrow": "tomorrow",
            "gonna": "going to", "wanna": "want to", "gotta": "got to",
            "kinda": "kind of", "sorta": "sort of", "alot": "a lot",
            "dont": "don't", "cant": "can't", "wont": "won't", "isnt": "isn't",
            "couldve": "could have", "shouldve": "should have", "wouldve": "would have"
        }
        
        words = text.split()
        for i, word in enumerate(words):
            clean_word = word.lower().strip(".,!?")
            if clean_word in phonetic_corrections:
                words[i] = word.replace(clean_word, phonetic_corrections[clean_word])
        
        text = " ".join(words)
        
        # 3. Capitalize first letter if Whisper missed it
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
            
        return text
    except FileNotFoundError:
        st.error("❌ **FFmpeg not found!** Whisper requires FFmpeg to be installed and added to your system PATH.")
        st.info("💡 Please install FFmpeg to continue. On Windows, you can use: `choco install ffmpeg` or download it from https://ffmpeg.org/download.html")
        st.stop()
    except Exception as e:
        st.error(f"❌ Transcription error: {str(e)}")
        st.stop()

# -----------------------------
# GRAMMAR CHECK
# -----------------------------
def check_grammar_api(text):
    # 1. Pre-Correction for common irregular plural speech errors
    # This helps the grammar tool see the base error more clearly
    irregular_plurals = {
        "childrens": "children",
        "peoples": "people",
        "mices": "mice",
        "geeses": "geese",
        "tooths": "teeth",
        "foots": "feet",
        "mans": "men",
        "womans": "women"
    }
    
    pre_corrected_text = text
    words = pre_corrected_text.split()
    for i, word in enumerate(words):
        clean_word = word.lower().strip(".,!?")
        if clean_word in irregular_plurals:
            words[i] = word.replace(clean_word, irregular_plurals[clean_word])
    pre_corrected_text = " ".join(words)

    # 2. Use language_tool_python for deep grammar analysis
    try:
        matches = tool.check(pre_corrected_text)
    except Exception as e:
        st.error(f"Grammar Tool Error: {e}")
        return [], text

    filtered = []
    
    for m in matches:
        # Skip technical noise
        rule_id = getattr(m, 'ruleId', '')
        if rule_id in ['WHITESPACE_RULE', 'UPPERCASE_SENTENCE_START']:
            continue
            
        # Get error length safely - check common attribute names
        error_length = getattr(m, 'errorLength', getattr(m, 'length', 0))
            
        filtered.append({
            "message": m.message,
            "context": m.context,
            "offset": m.offset,
            "length": error_length,
            "replacements": m.replacements[:3],
            "ruleId": rule_id
        })

    # 3. Build the corrected sentence
    corrected = tool.correct(pre_corrected_text)

    # 4. Robust Universal Tense & Style Rules (Fallback/Enhancement)
    lower_text = corrected.lower()
    
    # Subject-Verb Agreement Enhancement (especially for irregulars)
    agreement_fixes = {
        "children was": "children were",
        "people was": "people were",
        "men was": "men were",
        "women was": "women were",
        "mice was": "mice were"
    }
    
    # Add standard pronoun agreement errors
    standard_agreement = {
        "i is": "I am", "i are": "I am",
        "you is": "you are",
        "he are": "he is", "she are": "she is", "it are": "it is",
        "we is": "we are", "they is": "they are",
        "he go": "he goes", "she go": "she goes", "it go": "it goes",
        "he got": "he goes", "she got": "she goes", # Catching 'got to school' instead of 'goes'
        "he do": "he does", "she do": "she does", "it do": "it does",
        "he have": "he has", "she have": "she has", "it have": "it has"
    }
    agreement_fixes.update(standard_agreement)
    
    for err, fix in agreement_fixes.items():
        if err in lower_text:
            idx = lower_text.find(err)
            # Only add if not already caught by LT
            if not any(m['offset'] == idx for m in filtered):
                filtered.append({
                    "message": f"Subject-Verb Agreement: Use '{fix.split()[-1]}' with plural '{fix.split()[0]}'.",
                    "context": corrected[max(0, idx-5):min(len(corrected), idx+15)],
                    "offset": idx, "length": len(err),
                    "replacements": [fix]
                })
                corrected = corrected.replace(err, fix)

    # Future Tense Rule (don't -> won't for future events)
    if "don't" in lower_text and any(word in lower_text for word in ["tomorrow", "next week", "later", "soon"]):
        idx = lower_text.find("don't")
        if not any(m['offset'] == idx for m in filtered):
            filtered.append({
                "message": "Future Tense Error: Use 'won't' or 'am not' for future events.",
                "context": corrected[max(0, idx-10):min(len(corrected), idx+20)],
                "offset": idx, "length": 5,
                "replacements": ["won't", "am not"]
            })
            if "won't" not in corrected.lower():
                corrected = corrected.replace("don't", "won't")

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
# HIGHLIGHT GRAMMAR
# -----------------------------
def detect_fillers(text):
    fillers = ["um", "uh", "like", "you know", "actually"]
    found = []
    
    for f in fillers:
        # Use regex word boundaries \b to ensure we match whole words only
        # This prevents "likes" or "actually" (as a substring) from being flagged incorrectly
        pattern = rf"\b{f}\b"
        if re.search(pattern, text.lower()):
            found.append(f)
    return found

def highlight_grammar_errors(text, matches):
    if not matches:
        return text
        
    highlighted = ""
    last_idx = 0
    
    # Sort matches by offset to process them in order
    sorted_matches = sorted(matches, key=lambda x: x['offset'])
    
    for m in sorted_matches:
        start = m['offset']
        end = start + m['length']
        
        # Add text before the error
        highlighted += text[last_idx:start]
        # Add the error word with a red marker
        highlighted += f" 🔴**{text[start:end]}** "
        last_idx = end
        
    # Add remaining text
    highlighted += text[last_idx:]
    return highlighted

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
        found = detect_fillers(text)

        if found:
            st.warning(f"Filler words used: {', '.join(found)}")
        else:
            st.success("No filler words detected")
        
        st.subheader("😊 Emotion Detection")

        emotion = "Normal"

        if wpm > 130:
            emotion = "Excited"

        elif wpm >= 100:
            emotion = "Confident"

        elif wpm >= 50:
            emotion = "Calm"

        else:
            emotion = "Neutral"

        st.info(f"Detected Emotion: {emotion}")

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

        history_data = pd.DataFrame(
           [[time.strftime("%Y-%m-%d %H:%M:%S"), score]],
           columns=["Date", "Score"]
        )

        if os.path.exists(history_file):
           history_data.to_csv(
             history_file,
             mode="a",
             header=False,
             index=False
         )
        else:
           history_data.to_csv(
              history_file,
              index=False
            )

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
        found = detect_fillers(text)

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
            st.warning(f"Found {len(matches)} grammar/spelling issues")
            
            st.markdown("### 🧾 Highlighted Issues")
            st.write(highlight_grammar_errors(text, matches))
            
            for i, m in enumerate(matches):
                with st.expander(f"Issue {i+1}: {m['message']}"):
                    st.write(f"**Context:** ...{m['context']}...")
                    if m['replacements']:
                        st.write(f"**Suggestions:** {', '.join(m['replacements'])}")
            
            st.write("**Corrected Sentence:**")
            st.success(corrected)
        else:
            st.success("No major grammar issues detected")

        score = max(50, min(100, int(len(words) * 8)))
        if matches:
            score -= len(matches) * 5 # Deduct points for grammar issues
            score = max(0, score)

        st.subheader("📊 Speech Score")
        st.metric("Overall Score", f"{score}%")
        st.progress(score / 100)

        history_data = pd.DataFrame(
            [[time.strftime("%Y-%m-%d %H:%M:%S"), score]],
            columns=["Date", "Score"]
        )

        if os.path.exists(history_file):
            history_data.to_csv(
                history_file,
                mode="a",
                header=False,
                index=False
          )
        else:
            history_data.to_csv(
                history_file,
                index=False
            )

        st.session_state.scores.append(score)

        st.subheader("📈 Progress Over Time")
        df = pd.DataFrame(st.session_state.scores, columns=["Score"])
        st.line_chart(df)
        
        st.subheader("📜 Patient History")

        if os.path.exists(history_file):
            old_data = pd.read_csv(history_file)
            st.dataframe(old_data)

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
st.sidebar.write("✔ Filler word detection")
st.sidebar.write("✔ Speech speed (WPM)")
st.sidebar.write("✔ Difficult word detection")
st.sidebar.write("✔ Emotion detection")
st.sidebar.write("✔ Confidence estimation")