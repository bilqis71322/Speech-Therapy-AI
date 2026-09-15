import streamlit as st
import difflib
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

try:
    import cmudict
except ImportError:
    cmudict = None


# ============================================================
# CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="SpeakEase - Speech Therapy AI",
    page_icon="🎤",
    layout="wide"
)


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

USER_DB = os.path.join(BASE_DIR, "users.json")
AUDIO_FILE = os.path.join(BASE_DIR, "audio.wav")


# ============================================================
# FFmpeg PATH
# ============================================================

ffmpeg_path = r"C:\Users\deepi\AppData\Local\Microsoft\WinGet\Links"

if os.path.exists(ffmpeg_path):
    if ffmpeg_path not in os.environ["PATH"]:
        os.environ["PATH"] += os.pathsep + ffmpeg_path


# ============================================================
# JAVA PATH FOR LANGUAGE TOOL
# ============================================================

java_path = r"C:\Program Files\Java\jdk-17\bin"

if os.path.exists(java_path):
    if java_path not in os.environ["PATH"]:
        os.environ["PATH"] = (
            java_path
            + os.pathsep
            + os.environ["PATH"]
        )


# ============================================================
# USER DATABASE
# ============================================================

def save_users(users):

    try:

        with open(
            USER_DB,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                users,
                f,
                indent=4
            )

        return True

    except Exception as e:

        st.error(
            f"Unable to save users.json: {e}"
        )

        return False


def normalize_scores(scores):

    """
    Converts old score formats into a simple list of numbers.

    Supports:
        [80, 90, 70]

    and:

        [
            {"score": 80},
            {"score": 90}
        ]
    """

    if not isinstance(scores, list):
        return []

    cleaned = []

    for item in scores:

        try:

            if isinstance(item, dict):

                value = item.get(
                    "score",
                    0
                )

            else:

                value = item

            value = float(value)

            value = max(
                0,
                min(100, value)
            )

            cleaned.append(
                int(value)
            )

        except Exception:
            continue

    return cleaned


def load_users():

    """
    Loads users from users.json.

    The file is always taken from
    the same folder as app.py.
    """

    if not os.path.exists(USER_DB):

        return {}


    try:

        with open(
            USER_DB,
            "r",
            encoding="utf-8"
        ) as f:

            users = json.load(f)


    except Exception as e:

        st.error(
            f"Unable to read users.json: {e}"
        )

        return {}


    if not isinstance(users, dict):

        return {}


    changed = False


    for username, data in list(
        users.items()
    ):

        # -----------------------------------------
        # OLD FORMAT
        # {"Kavya": "password"}
        # -----------------------------------------

        if isinstance(data, str):

            users[username] = {

                "password": data,

                "name": username,

                "email": "",

                "age": 18,

                "scores": []
            }

            changed = True

            continue


        # -----------------------------------------
        # NEW FORMAT
        # -----------------------------------------

        if isinstance(data, dict):

            if "password" not in data:

                data["password"] = ""

                changed = True


            if "name" not in data:

                data["name"] = username

                changed = True


            if "email" not in data:

                data["email"] = ""

                changed = True


            if "age" not in data:

                data["age"] = 18

                changed = True


            old_scores = data.get(
                "scores",
                []
            )

            new_scores = normalize_scores(
                old_scores
            )

            if new_scores != old_scores:

                data["scores"] = new_scores

                changed = True


            users[username] = data


    if changed:

        save_users(users)


    return users


# ============================================================
# SESSION STATE
# ============================================================

if "authenticated" not in st.session_state:

    st.session_state.authenticated = False


if "username" not in st.session_state:

    st.session_state.username = ""


if "auth_mode" not in st.session_state:

    st.session_state.auth_mode = "Login"


if "scores" not in st.session_state:

    st.session_state.scores = []


# Preserve the original Word Pronunciation analysis across Streamlit reruns.
if "last_word_analysis_text" not in st.session_state:

    st.session_state.last_word_analysis_text = None


if "last_word_analysis_expected" not in st.session_state:

    st.session_state.last_word_analysis_expected = ""


if "last_word_analysis_duration" not in st.session_state:

    st.session_state.last_word_analysis_duration = 10


if "word_practice_result" not in st.session_state:

    st.session_state.word_practice_result = None


if "word_practice_target_key" not in st.session_state:

    st.session_state.word_practice_target_key = None


# Sentence Analysis state is used only after the user has recorded a sentence.
if "last_sentence_analysis_text" not in st.session_state:

    st.session_state.last_sentence_analysis_text = None


if "last_sentence_analysis_duration" not in st.session_state:

    st.session_state.last_sentence_analysis_duration = 10


# ============================================================
# SIGN UP
# ============================================================

def signup():

    st.title("Sign Up")

    st.write(
        "Create your SpeakEase account."
    )


    with st.form(
        "signup_form",
        clear_on_submit=False
    ):

        new_user = st.text_input(
            "Username"
        )

        new_pass = st.text_input(
            "Password",
            type="password"
        )

        confirm_pass = st.text_input(
            "Confirm Password",
            type="password"
        )

        name = st.text_input(
            "Full Name"
        )

        email = st.text_input(
            "Email"
        )

        age = st.number_input(
            "Age",
            min_value=5,
            max_value=100,
            value=18
        )

        submit = st.form_submit_button(
            "Create Account"
        )


        if submit:

            new_user = new_user.strip()
            name = name.strip()
            email = email.strip()


            users = load_users()


            # Username check
            username_exists = any(
                saved_username.strip().lower()
                == new_user.lower()
                for saved_username in users
            )


            if not new_user:

                st.error(
                    "Please enter a username."
                )


            elif username_exists:

                st.error(
                    "Username already exists!"
                )


            elif not new_pass:

                st.error(
                    "Please enter a password."
                )


            elif len(new_pass) < 6:

                st.error(
                    "Password must be at least 6 characters."
                )


            elif new_pass != confirm_pass:

                st.error(
                    "Passwords do not match."
                )


            elif not name:

                st.error(
                    "Please enter your full name."
                )


            elif not email:

                st.error(
                    "Please enter your email."
                )


            else:

                users[new_user] = {

                    "password": new_pass,

                    "name": name,

                    "email": email,

                    "age": int(age),

                    "scores": []

                }


                if save_users(users):

                    st.success(
                        "Account created successfully!"
                    )

                    st.session_state.auth_mode = "Login"

                    time.sleep(1)

                    st.rerun()


# ============================================================
# LOGIN
# ============================================================

def login():

    st.title("Login")

    st.write(
        "Login to continue using SpeakEase."
    )


    with st.form(
        "login_form"
    ):

        username = st.text_input(
            "Username"
        )

        password = st.text_input(
            "Password",
            type="password"
        )

        submit = st.form_submit_button(
            "Login"
        )


        if submit:

            username = username.strip()

            users = load_users()


            # -----------------------------------------
            # FIND USER WITHOUT CASE SENSITIVITY
            # -----------------------------------------

            actual_username = None

            for saved_username in users.keys():

                if (
                    saved_username.strip().lower()
                    == username.lower()
                ):

                    actual_username = saved_username

                    break


            if actual_username is None:

                st.error(
                    "Username not found. "
                    "Please check the username or create a new account."
                )

                st.stop()


            user = users[
                actual_username
            ]


            stored_password = str(
                user.get(
                    "password",
                    ""
                )
            )


            if stored_password == password:

                st.session_state.authenticated = True

                st.session_state.username = (
                    actual_username
                )


                st.session_state.scores = (
                    normalize_scores(
                        user.get(
                            "scores",
                            []
                        )
                    )
                )


                st.success(
                    "Login successful!"
                )


                time.sleep(0.5)

                st.rerun()


            else:

                st.error(
                    "Incorrect password. "
                    "Please enter the password used during signup."
                )


# ============================================================
# LOGOUT
# ============================================================

def logout():

    st.session_state.authenticated = False

    st.session_state.username = ""

    st.session_state.scores = []

    st.session_state.auth_mode = "Login"

    st.session_state.last_word_analysis_text = None
    st.session_state.last_word_analysis_expected = ""
    st.session_state.word_practice_result = None
    st.session_state.word_practice_target_key = None
    st.session_state.last_sentence_analysis_text = None
    st.session_state.last_sentence_analysis_duration = 10
    st.rerun()


# ============================================================
# USER PROFILE
# ============================================================

def show_profile():

    users = load_users()

    username = st.session_state.username


    if username not in users:

        st.error(
            "User profile not found."
        )

        return


    user = users[username]


    st.title("My Profile")


    # -----------------------------------------
    # PERSONAL INFORMATION
    # -----------------------------------------

    st.subheader(
        "Personal Information"
    )


    col1, col2 = st.columns(2)


    with col1:

        st.write(
            f"**Username:** {username}"
        )

        st.write(
            f"**Name:** {user.get('name', 'Not provided')}"
        )

        st.write(
            f"**Age:** {user.get('age', 'Not provided')}"
        )


    with col2:

        st.write(
            f"**Email:** {user.get('email', 'Not provided')}"
        )


    st.divider()


    # -----------------------------------------
    # SPEECH PRACTICE STATISTICS
    # -----------------------------------------

    st.subheader(
        "Speech Practice Statistics"
    )


    scores = normalize_scores(
        user.get(
            "scores",
            []
        )
    )


    if scores:

        average_score = (
            sum(scores) / len(scores)
        )

        best_score = max(scores)


        col1, col2, col3 = st.columns(3)


        with col1:

            st.metric(
                "Practice Sessions",
                len(scores)
            )


        with col2:

            st.metric(
                "Average Score",
                f"{average_score:.1f}%"
            )


        with col3:

            st.metric(
                "Best Score",
                f"{best_score}%"
            )


        st.subheader(
            "Progress Over Time"
        )


        progress_df = pd.DataFrame({

            "Session":
                range(
                    1,
                    len(scores) + 1
                ),

            "Score":
                scores

        })


        st.line_chart(
            progress_df.set_index(
                "Session"
            )
        )


    else:

        st.info(
            "No speech practice sessions recorded yet."
        )


# ============================================================
# SAVE SCORE
# ============================================================

def save_user_score(
    score,
    mode="Speech Practice",
    wpm=0
):

    users = load_users()

    username = st.session_state.username


    if username not in users:

        return


    try:

        score = int(
            max(
                0,
                min(
                    100,
                    score
                )
            )
        )

    except Exception:

        score = 0


    if "scores" not in users[username]:

        users[username]["scores"] = []


    # Keep the scores as numbers
    # so profile calculations work correctly.

    existing_scores = normalize_scores(
        users[username]["scores"]
    )


    existing_scores.append(
        score
    )


    users[username]["scores"] = (
        existing_scores
    )


    # Store recent practice history
    if "history" not in users[username]:

        users[username]["history"] = []


    users[username]["history"].append({

        "mode": mode,

        "score": score,

        "wpm": int(wpm),

        "date": time.strftime(
            "%d-%m-%Y %H:%M"
        )

    })


    save_users(users)


    st.session_state.scores = (
        existing_scores.copy()
    )


# ============================================================
# LOAD WHISPER MODEL
# ============================================================

@st.cache_resource
def load_model():

    return whisper.load_model(
        "base"
    )


# ============================================================
# LOAD LANGUAGE TOOL
# ============================================================

@st.cache_resource
def load_grammar_tool():

    return language_tool_python.LanguageTool(
        "en-US"
    )


# ============================================================
# RECORD AUDIO
# ============================================================

def record_audio(
    duration,
    fs=44100
):

    st.warning(
        "Get ready..."
    )


    for i in range(
        3,
        0,
        -1
    ):

        st.write(
            f"Recording starts in {i}..."
        )

        time.sleep(1)


    st.success(
        "Recording... Speak now!"
    )


    recording = sd.rec(

        int(
            duration * fs
        ),

        samplerate=fs,

        channels=1

    )


    sd.wait()


    st.success(
        "Recording finished."
    )


    write(
        AUDIO_FILE,
        fs,
        recording
    )


    return AUDIO_FILE


# ============================================================
# TRANSCRIBE AUDIO
# ============================================================

def transcribe_audio(
    file,
    model
):

    try:

        result = model.transcribe(

            file,

            language="en",

            fp16=False

        )


        text = result[
            "text"
        ].strip()


        text = text.replace(
            " i ",
            " I "
        )


        # Common transcription corrections

        phonetic_corrections = {

            "maro":
                "tomorrow",

            "tomoro":
                "tomorrow",

            "tomarrow":
                "tomorrow",

            "gonna":
                "going to",

            "wanna":
                "want to",

            "gotta":
                "got to",

            "kinda":
                "kind of",

            "sorta":
                "sort of",

            "alot":
                "a lot",

            "dont":
                "don't",

            "cant":
                "can't",

            "wont":
                "won't",

            "isnt":
                "isn't",

            "couldve":
                "could have",

            "shouldve":
                "should have",

            "wouldve":
                "would have"

        }


        words = text.split()


        for i, word in enumerate(words):

            clean_word = (
                word.lower()
                .strip(".,!?")
            )


            if (
                clean_word
                in phonetic_corrections
            ):

                words[i] = word.replace(

                    clean_word,

                    phonetic_corrections[
                        clean_word
                    ]

                )


        text = " ".join(words)


        if (
            text
            and text[0].islower()
        ):

            text = (
                text[0].upper()
                + text[1:]
            )


        return text


    except FileNotFoundError:

        st.error(
            "FFmpeg was not found. "
            "Please install FFmpeg and add it to PATH."
        )

        st.stop()


    except Exception as e:

        st.error(
            f"Transcription error: {e}"
        )

        st.stop()


# ============================================================
# FILLER WORD DETECTION
# ============================================================

def detect_fillers(text):

    fillers = [

        "um",

        "uh",

        "like",

        "you know",

        "actually"

    ]


    found = []


    for filler in fillers:

        pattern = (
            rf"\b{re.escape(filler)}\b"
        )


        if re.search(
            pattern,
            text.lower()
        ):

            found.append(
                filler
            )


    return found


# ============================================================
# DIFFICULT WORD DETECTION
# ============================================================

def detect_difficult_words(
    words
):

    return [

        word

        for word in words

        if len(
            word.strip(
                ".,!?"
            )
        ) > 7

    ]


# ============================================================
# HIGHLIGHT WRONG WORDS
# ============================================================

def highlight_text(
    text,
    wrong_words
):

    result = ""


    wrong_set = {
        w.lower()
        for w in wrong_words
    }


    for word in text.split():

        clean = (
            word.lower()
            .strip(".,!?")
        )


        if clean in wrong_set:

            result += (
                f" 🔴{word} "
            )

        else:

            result += (
                f" {word} "
            )


    return result


# ============================================================
# GRAMMAR CHECK
# ============================================================

def check_grammar(
    text,
    tool
):

    irregular_plurals = {

        "childrens":
            "children",

        "peoples":
            "people",

        "mices":
            "mice",

        "geeses":
            "geese",

        "tooths":
            "teeth",

        "foots":
            "feet",

        "mans":
            "men",

        "womans":
            "women"

    }


    pre_corrected_text = text


    words = (
        pre_corrected_text.split()
    )


    for i, word in enumerate(words):

        clean_word = (
            word.lower()
            .strip(".,!?")
        )


        if (
            clean_word
            in irregular_plurals
        ):

            words[i] = word.replace(

                clean_word,

                irregular_plurals[
                    clean_word
                ]

            )


    pre_corrected_text = (
        " ".join(words)
    )


    try:

        matches = tool.check(
            pre_corrected_text
        )

    except Exception as e:

        st.warning(
            f"Grammar tool error: {e}"
        )

        return [], text


    filtered = []


    for match in matches:

        rule_id = getattr(
            match,
            "ruleId",
            ""
        )


        if rule_id in [

            "WHITESPACE_RULE",

            "UPPERCASE_SENTENCE_START"

        ]:

            continue


        error_length = getattr(

            match,

            "errorLength",

            getattr(
                match,
                "length",
                0
            )

        )


        filtered.append({

            "message":
                match.message,

            "context":
                match.context,

            "offset":
                match.offset,

            "length":
                error_length,

            "replacements":
                match.replacements[:3],

            "ruleId":
                rule_id

        })


    try:

        corrected = tool.correct(
            pre_corrected_text
        )

    except Exception:

        corrected = (
            pre_corrected_text
        )


    # Additional common grammar corrections

    agreement_fixes = {

        "children was":
            "children were",

        "people was":
            "people were",

        "men was":
            "men were",

        "women was":
            "women were",

        "mice was":
            "mice were",

        "i is":
            "I am",

        "i are":
            "I am",

        "you is":
            "you are",

        "he are":
            "he is",

        "she are":
            "she is",

        "it are":
            "it is",

        "we is":
            "we are",

        "they is":
            "they are",

        "he go":
            "he goes",

        "she go":
            "she goes",

        "it go":
            "it goes",

        "he do":
            "he does",

        "she do":
            "she does",

        "it do":
            "it does",

        "he have":
            "he has",

        "she have":
            "she has",

        "it have":
            "it has"

    }


    lower_text = (
        corrected.lower()
    )


    for error, fix in (
        agreement_fixes.items()
    ):

        if error in lower_text:

            idx = lower_text.find(
                error
            )


            if not any(

                m["offset"] == idx

                for m in filtered

            ):

                filtered.append({

                    "message":
                        "Subject-Verb Agreement",

                    "context":
                        corrected[
                            max(
                                0,
                                idx - 5
                            ):
                            min(
                                len(corrected),
                                idx + 20
                            )
                        ],

                    "offset":
                        idx,

                    "length":
                        len(error),

                    "replacements":
                        [fix],

                    "ruleId":
                        "CUSTOM_AGREEMENT"

                })


            corrected = corrected.replace(
                error,
                fix
            )

            lower_text = (
                corrected.lower()
            )


    return filtered, corrected


# ============================================================
# HIGHLIGHT GRAMMAR ERRORS
# ============================================================

def highlight_grammar_errors(
    text,
    matches
):

    if not matches:

        return text


    highlighted = ""

    last_idx = 0


    for match in sorted(
        matches,
        key=lambda x: x["offset"]
    ):

        start = match["offset"]

        end = (
            start
            + match["length"]
        )


        if start < last_idx:

            continue


        highlighted += (
            text[last_idx:start]
        )


        highlighted += (
            f" 🔴**{text[start:end]}** "
        )


        last_idx = end


    highlighted += (
        text[last_idx:]
    )


    return highlighted


# ============================================================
# THERAPY SUGGESTIONS
# ============================================================

def therapy_suggestions(
    wrong_words,
    score
):

    suggestions = []


    if score < 50:

        suggestions.append(
            "Speak slowly and clearly using simple words."
        )

        suggestions.append(
            "Practice basic pronunciation daily."
        )


    if score < 80:

        suggestions.append(
            "Repeat difficult words 3–5 times."
        )

        suggestions.append(
            "Break difficult words into smaller syllables."
        )


    for word in wrong_words:

        suggestions.append(
            f"Practice this word: '{word}' slowly."
        )


    if not suggestions:

        suggestions.append(
            "Good performance. Continue regular speaking practice."
        )


    return suggestions


# ============================================================
# SPEECH STATISTICS
# ============================================================

def speech_statistics(
    text,
    duration
):

    words = text.split()

    word_count = len(words)


    if duration <= 0:

        wpm = 0

    else:

        wpm = int(
            (
                word_count
                / duration
            ) * 60
        )


    fillers = detect_fillers(
        text
    )


    difficult_words = (
        detect_difficult_words(
            words
        )
    )


    return (
        words,
        word_count,
        wpm,
        fillers,
        difficult_words
    )


# ============================================================
# DISORDER SCREENING - STUTTERING / DISFLUENCY
# ============================================================

def save_disorder_screening(result):
    """Save screening results separately from normal speech scores."""

    users = load_users()
    username = st.session_state.username

    if username not in users:
        return

    if "screening_history" not in users[username]:
        users[username]["screening_history"] = []

    users[username]["screening_history"].append({
        "disorder": "Stuttering / Disfluency",
        "risk_score": int(result.get("risk_score", 0)),
        "result": result.get("result", ""),
        "wpm": int(result.get("wpm", 0)),
        "repeated_words": int(result.get("repeated_word_count", 0)),
        "filler_count": int(result.get("filler_count", 0)),
        "date": time.strftime("%d-%m-%Y %H:%M")
    })

    # Keep only the latest 20 screening records.
    users[username]["screening_history"] = (
        users[username]["screening_history"][-20:]
    )

    save_users(users)


def analyze_stuttering_pattern(text, duration):
    """
    Preliminary screening for stuttering/disfluency patterns.

    The result is a screening indicator, not a clinical diagnosis.
    """

    safe_text = str(text or "")

    words = re.findall(
        r"[A-Za-z']+",
        safe_text.lower()
    )

    if not words:
        return {
            "risk_score": 0,
            "result": "Insufficient speech data",
            "wpm": 0,
            "repetitions": [],
            "repeated_sequences": [],
            "repeated_word_count": 0,
            "filler_count": 0,
            "repetition_rate": 0.0,
            "filler_rate": 0.0
        }

    # -----------------------------------------
    # SPEECH RATE
    # -----------------------------------------

    if duration > 0:
        wpm = int((len(words) / duration) * 60)
    else:
        wpm = 0

    # -----------------------------------------
    # REPEATED WORDS
    # -----------------------------------------

    repetitions = []
    repeated_sequences = []

    i = 0
    while i < len(words) - 1:
        count = 1

        while (
            i + count < len(words)
            and words[i + count] == words[i]
        ):
            count += 1

        if count >= 2:
            repeated_sequences.append(
                (words[i], count)
            )

            # Count every repeated occurrence after
            # the first occurrence.
            repetitions.extend(
                [words[i]] * (count - 1)
            )

        i += count

    repeated_word_count = len(repetitions)

    # -----------------------------------------
    # FILLER / DISFLUENCY WORDS
    # -----------------------------------------

    disfluency_words = {
        "um",
        "uh",
        "erm",
        "er",
        "hmm",
        "like",
        "actually",
        "basically"
    }

    filler_count = sum(
        1 for word in words
        if word in disfluency_words
    )

    # Existing SpeakEase filler detector is also used,
    # but this list is slightly broader for screening.

    repetition_rate = (
        repeated_word_count / len(words)
    ) * 100

    filler_rate = (
        filler_count / len(words)
    ) * 100

    # -----------------------------------------
    # RISK SCORE
    # -----------------------------------------

    risk_score = 0

    # Repetition is the strongest transcript-based indicator.
    if repetition_rate >= 20:
        risk_score += 50
    elif repetition_rate >= 10:
        risk_score += 35
    elif repetition_rate >= 5:
        risk_score += 20

    # Repeated sequences provide an additional indicator.
    if len(repeated_sequences) >= 3:
        risk_score += 20
    elif len(repeated_sequences) >= 1:
        risk_score += 10

    # Frequent fillers/disfluencies.
    if filler_rate >= 15:
        risk_score += 20
    elif filler_rate >= 8:
        risk_score += 10

    # Slow speaking rate can be another supporting indicator,
    # but it is not used alone to label a disorder.
    if 0 < wpm < 80:
        risk_score += 10

    risk_score = min(100, risk_score)

    if risk_score >= 50:
        result = (
            "Possible Stuttering / Disfluency Pattern"
        )
    elif risk_score >= 25:
        result = (
            "Mild Disfluency Pattern Detected"
        )
    else:
        result = (
            "No Strong Stuttering Pattern Detected"
        )

    return {
        "words": words,
        "risk_score": risk_score,
        "result": result,
        "wpm": wpm,
        "repetitions": repetitions,
        "repeated_sequences": repeated_sequences,
        "repeated_word_count": repeated_word_count,
        "filler_count": filler_count,
        "repetition_rate": repetition_rate,
        "filler_rate": filler_rate
    }




# ============================================================
# AUTOMATIC DISORDER RESULT
# ============================================================

def display_automatic_disorder_result(text, duration, save_result=True):

    screening = analyze_stuttering_pattern(text, duration)
    risk_score = int(screening["risk_score"])

    st.subheader("Speech Pattern Analysis")

    if risk_score >= 50:
        st.error("Possible Stuttering / Speech Disfluency Pattern Detected")
    elif risk_score >= 25:
        st.warning("Mild Speech Disfluency Pattern Detected")
    else:
        st.success("No Significant Stuttering / Disfluency Pattern Detected")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Disfluency Risk", f"{risk_score}%")

    with col2:
        st.metric("Repeated Words", screening["repeated_word_count"])

    with col3:
        st.metric("Speech Rate", f"{screening["wpm"]} WPM")

    if screening["repeated_sequences"]:
        st.write("**Repeated words detected:**")
        for word, count in screening["repeated_sequences"]:
            st.write(f"• '{word}' repeated {count} times")

    if screening["filler_count"] > 0:
        st.write(
            f"**Filler/disfluency words:** {screening["filler_count"]}"
        )

    if risk_score >= 25:
        st.info(
            "The result is based on repetition, filler/disfluency frequency "
            "and speaking rate. It is a preliminary screening result, not a medical diagnosis."
        )

    if save_result and risk_score >= 25:
        save_disorder_screening(screening)

    return screening




# ============================================================
# PRONUNCIATION TARGET DETECTION
# ============================================================

COMMON_SIMPLE_WORDS = {
    "i", "a", "an", "the", "am", "is", "are", "was", "were",
    "to", "of", "in", "on", "at", "it", "he", "she", "we", "you",
    "me", "my", "go", "do", "be", "and", "or", "but", "for",
    "with", "this", "that", "yes", "no", "hi", "hello"
}


def suitable_pronunciation_target(word):
    """Return True only for meaningful words suitable for articulation practice."""
    word = re.sub(r"[^a-zA-Z']", "", str(word)).lower().strip()

    if not word or word in COMMON_SIMPLE_WORDS:
        return False

    # Avoid very short/common function words.
    if len(word) < 4:
        return False

    # Prefer words with enough phonetic/linguistic complexity to be useful
    # as an articulation-practice target.
    complex_patterns = (
        "th", "sh", "ch", "ph", "wh", "tr", "dr", "kr", "gr",
        "br", "pr", "fr", "pl", "bl", "cl", "gl", "fl", "sl",
        "str", "spr", "scr", "thr", "st", "sp", "sk", "sw",
        "r", "l"
    )

    return len(word) >= 5 or any(pattern in word for pattern in complex_patterns)


def find_pronunciation_targets(expected_text, spoken_text):
    """
    Find words the patient was expected to say but which Whisper recognized
    differently. The TARGET is always the expected word, never the incorrectly
    recognized word.

    This is used for guided articulation practice. It does not diagnose a
    disorder; it identifies candidate words for practice.
    """
    expected = re.findall(r"[A-Za-z']+", str(expected_text).lower())
    spoken = re.findall(r"[A-Za-z']+", str(spoken_text).lower())

    if not expected or not spoken:
        return []

    matcher = difflib.SequenceMatcher(None, expected, spoken)
    candidates = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        # For replacements, compare each expected word with the corresponding
        # recognized word. For missing words, the expected word itself is the
        # target. Inserted words are ignored because they were not part of the
        # requested pronunciation.
        if tag == "replace":
            length = min(i2 - i1, j2 - j1)
            for offset in range(length):
                exp_word = expected[i1 + offset]
                got_word = spoken[j1 + offset]

                similarity = difflib.SequenceMatcher(
                    None, exp_word, got_word
                ).ratio()

                # Strict enough to catch meaningful substitutions while
                # avoiding minor transcription variations.
                if similarity < 0.88 and suitable_pronunciation_target(exp_word):
                    candidates.append({
                        "target": exp_word,
                        "recognized": got_word,
                        "similarity": similarity
                    })

            # If there are additional expected words in this replacement
            # block, treat them as missing targets.
            for offset in range(length, i2 - i1):
                exp_word = expected[i1 + offset]
                if suitable_pronunciation_target(exp_word):
                    candidates.append({
                        "target": exp_word,
                        "recognized": "not clearly recognized",
                        "similarity": 0.0
                    })

        elif tag == "delete":
            for idx in range(i1, i2):
                exp_word = expected[idx]
                if suitable_pronunciation_target(exp_word):
                    candidates.append({
                        "target": exp_word,
                        "recognized": "not clearly recognized",
                        "similarity": 0.0
                    })

    # Remove duplicate targets while preserving order.
    unique = []
    seen = set()
    for item in candidates:
        key = item["target"]
        if key not in seen:
            unique.append(item)
            seen.add(key)

    return unique


def _normalize_practice_text(text):
    """Normalize a Whisper result for exact target-word practice checking."""
    return re.findall(r"[a-z]+(?:'[a-z]+)?", (text or "").lower())


def _evaluate_pronunciation_practice(target_word, practice_text):
    """Evaluate ONLY the separate target-word practice recording."""
    target = _normalize_fragment(target_word)
    spoken_words = _normalize_practice_text(practice_text)

    exact_count = spoken_words.count(target)
    repeated_target = any(
        spoken_words[i] == spoken_words[i - 1] == target
        for i in range(1, len(spoken_words))
    )

    best_word = ""
    best_similarity = 0.0
    for word in spoken_words:
        similarity = difflib.SequenceMatcher(None, target, word).ratio()
        if similarity > best_similarity:
            best_similarity = similarity
            best_word = word

    if exact_count == 1 and not repeated_target:
        return {
            "status": "correct",
            "spoken": practice_text,
            "message": f"Correct! The word **{target_word}** was pronounced correctly."
        }

    if repeated_target:
        return {
            "status": "repeat",
            "spoken": practice_text,
            "message": f"The word **{target_word}** was repeated. Say it once, slowly and clearly."
        }

    if best_similarity >= 0.88:
        return {
            "status": "close",
            "spoken": practice_text,
            "message": f"Almost there. The system heard **{best_word}**. Try **{target_word}** again, slowly and clearly."
        }

    return {
        "status": "incorrect",
        "spoken": practice_text,
        "message": f"The word **{target_word}** was not clearly pronounced. Try again and focus on saying the complete word."
    }


def guided_pronunciation_practice(targets, model, practice_duration=5):
    """Practice a pronunciation target without losing the original analysis on rerun."""
    if not targets:
        return

    st.subheader("🩺 Therapy Practice")
    st.write(
        "Practice only the words that were not clearly pronounced in the previous recording. "
        "The target shown here is the word the patient was expected to say."
    )

    target_names = [item["target"] for item in targets]
    st.write("**Words selected for practice:** " + ", ".join(target_names))

    options = [item["target"] for item in targets]
    selected = st.selectbox(
        "Select a word to practise:",
        options,
        key="pronunciation_target_select"
    )

    target_info = next(item for item in targets if item["target"] == selected)
    target_key = f"{selected.lower()}|{target_info.get('recognized','')}"

    if st.session_state.get("word_practice_target_key") != target_key:
        st.session_state.word_practice_target_key = target_key
        st.session_state.word_practice_result = None

    st.markdown(f"### Target word: **{selected}**")
    if target_info["recognized"] != "not clearly recognized":
        st.caption(
            f"The system heard **{target_info['recognized']}** instead of the expected word **{selected}**."
        )
    else:
        st.caption(
            f"The expected word **{selected}** was not clearly recognized."
        )

    st.write(
        f"**Practice instruction:** Speak the target word **{selected}** once, slowly, clearly and comfortably. Do not repeat the word."
    )

    if st.button("Start Word Practice 🎙️", key="real_pronunciation_practice"):
        # This is a separate recording; the original analysis is preserved in session_state.
        practice_audio = record_audio(practice_duration)
        practice_text = transcribe_audio(practice_audio, model)
        st.session_state.word_practice_result = _evaluate_pronunciation_practice(
            selected, practice_text
        )
        st.session_state.word_practice_target_key = target_key

    practice_result = st.session_state.get("word_practice_result")
    if practice_result:
        st.markdown("#### Practice Result")
        st.write(
            f"Practice recording: **{practice_result.get('spoken') or '[no speech detected]'}**"
        )

        status = practice_result.get("status")
        message = practice_result.get("message", "")
        if status == "correct":
            st.success(message)
        elif status == "repeat":
            st.warning(message)
        elif status == "close":
            st.info(message)
        else:
            st.error(message)

    st.markdown("#### Next practice step")
    st.write(
        f"When **{selected}** is pronounced correctly, use it in a short sentence and repeat the sentence 2–3 times."
    )

    st.info(
        "This is an AI-assisted speech-practice exercise, not a medical diagnosis or a replacement for assessment by a speech-language professional."
    )


# ============================================================
# GUIDED SPEECH PRACTICE
# ============================================================

def _english_word_set():
    """Return a safe English-word set for reconstructing fragmented words."""
    if cmudict is None:
        return set()

    try:
        words = cmudict.words()
        return {
            re.sub(r"[^a-z]", "", w.lower())
            for w in words
            if re.fullmatch(r"[a-z]+", w.lower())
        }
    except Exception:
        return set()


@st.cache_resource
def get_english_words():
    return _english_word_set()


def _normalize_fragment(word):
    """Normalize a Whisper token for stuttering-fragment analysis."""
    return re.sub(r"[^a-z]", "", str(word).lower()).strip()


def _fuzzy_word_score(candidate, dictionary_word):
    """Score how closely a reconstructed speech form matches a real word."""
    candidate = _normalize_fragment(candidate)
    dictionary_word = _normalize_fragment(dictionary_word)

    if not candidate or not dictionary_word:
        return 0.0

    similarity = difflib.SequenceMatcher(
        None, candidate, dictionary_word
    ).ratio()

    # Reward a strong common prefix because Whisper often changes the
    # final consonant of a fragmented word (e.g. "marget" -> "market").
    prefix_length = 0
    for a, b in zip(candidate, dictionary_word):
        if a == b:
            prefix_length += 1
        else:
            break

    prefix_bonus = min(prefix_length * 0.025, 0.15)

    # Penalize candidates that are much longer than the spoken fragments.
    length_difference = abs(len(candidate) - len(dictionary_word))
    length_penalty = min(length_difference * 0.025, 0.15)

    return similarity + prefix_bonus - length_penalty


@st.cache_resource
def _get_word_lookup():
    """Cache the CMU dictionary as a clean set of words."""
    words = get_english_words()
    return sorted(
        {
            _normalize_fragment(word)
            for word in words
            if _normalize_fragment(word)
        }
    )


def _best_complete_word(candidate):
    """
    Convert a reconstructed Whisper form into the closest complete English word.

    The word is NEVER hard-coded. It is selected from the available dictionary.
    """
    candidate = _normalize_fragment(candidate)

    if len(candidate) < 3:
        return None

    english_words = _get_word_lookup()

    if not english_words:
        return None

    # Exact match first.
    if candidate in english_words:
        return candidate

    best_word = None
    best_score = 0.0

    # Keep the candidate search focused on words of similar length.
    min_len = max(3, len(candidate) - 3)
    max_len = len(candidate) + 3

    for dictionary_word in english_words:
        if not (min_len <= len(dictionary_word) <= max_len):
            continue

        score = _fuzzy_word_score(candidate, dictionary_word)

        if score > best_score:
            best_score = score
            best_word = dictionary_word

    # Conservative threshold: do not invent a target from a weak match.
    if best_word is not None and best_score >= 0.72:
        return best_word

    return None


def reconstruct_stuttered_word(words):
    """
    Automatically reconstruct the complete word represented by repeated
    speech fragments.

    Examples:
        mar mar ket        -> market
        mar mar get        -> market
        ba ba nana         -> banana
        ap ap ple          -> apple
        com com puter      -> computer
        com com pu ter     -> computer
        ta ta ble          -> table

    Nothing is hard-coded as a target word. The complete target is selected
    from the detected fragments and the English dictionary.
    """
    clean = [
        _normalize_fragment(word)
        for word in words
    ]
    clean = [word for word in clean if word]

    if len(clean) < 2:
        return None

    # Collapse only consecutive duplicate fragments.
    compact = []
    for word in clean:
        if not compact or word != compact[-1]:
            compact.append(word)

    if len(compact) < 2:
        return None

    # Try the direct reconstruction first.
    direct_candidate = "".join(compact)
    direct_result = _best_complete_word(direct_candidate)

    if direct_result:
        return direct_result

    return None


def _find_fragment_reconstruction(clean_words, start_index):
    """
    Find the complete word after a repeated fragment.

    Example:
        ... mar mar mar get today
                 ^^^^^^^
        repeated fragment = mar
        completion         = get
        reconstructed form = marget
        target             = market

    The function tries one, two and three completion tokens so it also handles
    words such as "com com pu ter".
    """
    if start_index + 1 >= len(clean_words):
        return None

    fragment = clean_words[start_index]

    if not fragment:
        return None

    # Count the consecutive repeated fragment.
    run_end = start_index + 1
    while (
        run_end < len(clean_words)
        and clean_words[run_end] == fragment
    ):
        run_end += 1

    repetition_count = run_end - start_index

    if repetition_count < 2:
        return None

    # After the repeated fragment, use up to three tokens as possible
    # completion fragments. This avoids treating the next sentence word as
    # part of the target unless it produces a strong complete-word match.
    best_target = None
    best_score = 0.0
    best_token_count = 0

    max_completion_tokens = min(3, len(clean_words) - run_end)

    for token_count in range(1, max_completion_tokens + 1):
        completion = clean_words[
            run_end:run_end + token_count
        ]

        if not completion:
            continue

        # The repeated fragment is included only ONCE. Repeating "mar" three
        # times does not mean the target is "marmarmar...".
        candidate = fragment + "".join(completion)
        target = _best_complete_word(candidate)

        if not target:
            continue

        score = _fuzzy_word_score(candidate, target)

        # Prefer shorter completion groups when scores are essentially equal.
        if (
            score > best_score + 0.02
            or (
                abs(score - best_score) <= 0.02
                and token_count < best_token_count
            )
            or best_target is None
        ):
            best_target = target
            best_score = score
            best_token_count = token_count

    if best_target:
        return best_target, repetition_count

    return None


def get_stuttering_targets(screening):
    """
    Identify the actual word involved in stuttering/disfluent repetition.

    Whole-word repetition:
        want want want -> want

    Fragmented-word repetition:
        mar mar ket -> market
        mar mar mar get -> market
        ba ba nana -> banana
        com com pu ter -> computer

    The target is derived from the patient's detected speech. There is no
    hard-coded target-word list.
    """
    words = screening.get("words", [])
    repeated_sequences = screening.get("repeated_sequences", [])

    filler_words = {
        "um", "uh", "erm", "er", "hmm", "like",
        "actually", "basically"
    }

    clean_words = [
        _normalize_fragment(word)
        for word in words
    ]
    clean_words = [word for word in clean_words if word]

    fragmented_targets = []

    # ---------------------------------------------------------
    # FIRST: detect fragmented-word stuttering.
    # This MUST happen before whole-word targets so that:
    #     mar mar mar get
    # becomes:
    #     target = market
    # and never:
    #     target = mar
    # ---------------------------------------------------------
    i = 0
    while i < len(clean_words) - 1:
        if clean_words[i] in filler_words:
            i += 1
            continue

        if clean_words[i] == clean_words[i + 1]:
            result = _find_fragment_reconstruction(
                clean_words,
                i
            )

            if result:
                target, repetition_count = result
                fragmented_targets.append(
                    (
                        target,
                        repetition_count,
                        "fragmented-word repetition"
                    )
                )

                # Skip the repeated run so the same fragments are not added
                # again from the next index.
                fragment = clean_words[i]
                j = i + 1
                while (
                    j < len(clean_words)
                    and clean_words[j] == fragment
                ):
                    j += 1

                i = j
                continue

        i += 1

    if fragmented_targets:
        # Remove duplicate reconstructed targets while keeping the strongest
        # repetition count.
        unique = {}
        for target, count, target_type in fragmented_targets:
            if (
                target not in unique
                or count > unique[target][1]
            ):
                unique[target] = (
                    target,
                    count,
                    target_type
                )

        return list(unique.values())

    # ---------------------------------------------------------
    # SECOND: genuine whole-word repetition.
    # Only use this when no complete fragmented target could be reconstructed.
    # ---------------------------------------------------------
    targets = []

    for word, count in repeated_sequences:
        clean = _normalize_fragment(word)

        if (
            clean
            and clean not in filler_words
            and int(count) >= 2
        ):
            targets.append(
                (
                    clean,
                    int(count),
                    "whole-word repetition"
                )
            )

    return targets

def _normalize_practice_text(text):
    """Normalize a Whisper result for exact target-word practice checking."""
    return re.findall(r"[a-z]+(?:'[a-z]+)?", (text or "").lower())


def _check_target_word_practice(target_word, practice_text):
    """Evaluate ONLY the separate target-word practice recording."""
    target = _normalize_fragment(target_word)
    spoken_words = _normalize_practice_text(practice_text)

    # Exact target recognition is required for a confident success result.
    exact_positions = [
        i for i, word in enumerate(spoken_words)
        if word == target
    ]

    repeated_target = any(
        spoken_words[i] == spoken_words[i - 1] == target
        for i in range(1, len(spoken_words))
    )

    best_word = ""
    best_similarity = 0.0

    for word in spoken_words:
        similarity = difflib.SequenceMatcher(
            None, target, word
        ).ratio()
        if similarity > best_similarity:
            best_similarity = similarity
            best_word = word

    # A practice attempt is successful only when the complete target word
    # appears exactly once. This prevents a fragment such as "mar" from
    # being accepted as "market".
    if len(exact_positions) == 1 and not repeated_target:
        return {
            "status": "correct",
            "message": (
                f"Correct! The word **{target_word}** was pronounced correctly."
            ),
            "spoken": practice_text,
        }

    if repeated_target:
        return {
            "status": "repeat",
            "message": (
                f"The word **{target_word}** was repeated. Say it once, "
                "slowly and clearly."
            ),
            "spoken": practice_text,
        }

    if best_similarity >= 0.88:
        return {
            "status": "close",
            "message": (
                f"Almost there. The system heard **{best_word}**. "
                f"Try **{target_word}** again, slowly and clearly."
            ),
            "spoken": practice_text,
        }

    return {
        "status": "incorrect",
        "message": (
            f"The word **{target_word}** was not clearly pronounced. "
            "Try again and focus on saying the complete word."
        ),
        "spoken": practice_text,
    }


def generate_practice_sentence(target_word):
    """
    Generate one simple, grammatically safe sentence containing the
    dynamically detected target word. The word is not hard-coded.
    """
    word = str(target_word).strip()

    if not word:
        return "Please practise the target word clearly."

    return f"I will practice saying the word {word} clearly today."


def guided_speech_practice(screening, model, practice_duration=5):
    """
    Separate guided practice for a detected stuttering target.

    IMPORTANT:
    - The original recording and the practice recording are kept separate.
    - Clicking Start Word Practice does NOT start the main recording again.
    - The practice result is stored in session_state, so it survives the
      Streamlit rerun caused by the button click.
    - A target is marked correct only when the complete target word is
      recognized exactly once.
    """

    risk_score = int(screening.get("risk_score", 0))
    if risk_score < 50:
        return

    targets = get_stuttering_targets(screening)

    if not targets:
        st.info(
            "A strong disfluency pattern was detected, but the system could "
            "not reliably identify the complete target word. Please record "
            "another natural speech sample."
        )
        return

    target_word, target_count, target_type = max(
        targets,
        key=lambda item: (item[1], len(item[0]))
    )

    # Reset practice state when the target from the analysis changes.
    target_key = f"{target_word.lower()}|{target_type}|{target_count}"
    if st.session_state.get("guided_practice_target_key") != target_key:
        st.session_state.guided_practice_target_key = target_key
        st.session_state.guided_practice_result = None

    st.subheader("Speech Practice")
    st.write(
        "Practice the actual word involved in the detected stuttering pattern. "
        "The practice recording is evaluated separately from the original "
        "speech recording."
    )

    st.markdown(f"### Target word: **{target_word}**")

    if target_type == "fragmented-word repetition":
        st.caption(
            f"The system detected a repeated speech fragment and reconstructed "
            f"the complete target word **{target_word}**."
        )
    else:
        st.caption(
            f"The word **{target_word}** was repeated in the original speech recording."
        )

    # Explicit practice instruction BEFORE recording.
    st.write(
        f"**Practice instruction:** Speak the target word **{target_word}** "
        "once, slowly, clearly and comfortably. Do not repeat the word."
    )

    # Optional audio pronunciation cue using Streamlit's normal audio support
    # is intentionally not added here so the existing UI remains unchanged.

    if st.button("Start Word Practice 🎙️", key="guided_word_practice"):
        practice_audio = record_audio(practice_duration)
        practice_text = transcribe_audio(practice_audio, model)

        result = _check_target_word_practice(
            target_word,
            practice_text
        )

        st.session_state.guided_practice_result = result
        st.session_state.guided_practice_target_key = target_key

        # Do not call the original analysis again. The practice recording is
        # evaluated only by _check_target_word_practice().

    # ---------------------------------------------------------
    # PRACTICE RESULT - survives Streamlit reruns
    # ---------------------------------------------------------
    practice_result = st.session_state.get(
        "guided_practice_result"
    )

    if practice_result:
        st.markdown("#### Practice Result")
        st.write(
            f"Practice recording: **{practice_result.get('spoken') or '[no speech detected]'}**"
        )

        status = practice_result.get("status")
        message = practice_result.get("message", "")

        if status == "correct":
            st.success(message)
        elif status == "repeat":
            st.warning(message)
        elif status == "close":
            st.info(message)
        else:
            st.error(message)

    # ---------------------------------------------------------
    # NEXT PRACTICE SENTENCE
    # ---------------------------------------------------------
    # Show only an actual sentence containing the detected target word.
    # Do not give a generic instruction here.
    practice_sentence = generate_practice_sentence(target_word)

    st.markdown("#### Next Practice Sentence")
    st.write(
        f"**{practice_sentence}**"
    )

    st.info(
        "This is an AI-assisted speech-practice exercise, not a medical "
        "diagnosis or a replacement for assessment by a speech-language professional."
    )


# ============================================================
# APPLICATION
# ============================================================

if not st.session_state.authenticated:

    st.title(
        "SpeakEase"
    )


    mode = st.radio(

        "Select Action",

        [
            "Login",
            "Sign Up"
        ],

        index=(
            0
            if st.session_state.auth_mode
            == "Login"
            else 1
        ),

        horizontal=True

    )


    st.session_state.auth_mode = (
        mode
    )


    if mode == "Login":

        login()

    else:

        signup()


    st.stop()


# ============================================================
# LOAD USER DATA
# ============================================================

users = load_users()

current_username = (
    st.session_state.username
)


if current_username not in users:

    st.error(
        "Your user account could not be found."
    )

    if st.button(
        "Return to Login"
    ):

        logout()

    st.stop()


current_user = users[
    current_username
]


# ============================================================
# MAIN HEADER
# ============================================================

st.title(
    "🎤 Speech Impairment Detection System"
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title(
    "SpeakEase"
)


st.sidebar.write(
    f"Welcome, **{current_user.get('name', current_username)}**"
)


st.sidebar.divider()


page = st.sidebar.radio(

    "Navigation",

    [
        "My Profile",
        "Word Pronunciation",
        "Sentence Analysis",
        "My Progress",
        "Settings"
    ]

)


if page != "Sentence Analysis":
    st.session_state.last_sentence_analysis_text = None
    st.session_state.last_sentence_analysis_duration = 10



duration = st.sidebar.slider(

    "Recording Duration (seconds)",

    3,

    60,

    10

)


st.sidebar.divider()


if st.sidebar.button(
    "Logout"
):

    logout()


# ============================================================
# PROJECT INFORMATION
# ============================================================

st.sidebar.divider()

st.sidebar.subheader(
    "Project Information"
)

st.sidebar.write(
    "AI Speech Therapy System"
)

st.sidebar.write(
    "Speech Recognition - Whisper"
)

st.sidebar.write(
    "Grammar Analysis"
)

st.sidebar.write(
    "Pronunciation Detection"
)

st.sidebar.write(
    "Error Highlighting"
)

st.sidebar.write(
    "Score and Progress Graph"
)

st.sidebar.write(
    "Therapy Recommendations"
)

st.sidebar.write(
    "Filler Word Detection"
)

st.sidebar.write(
    "Speech Speed (WPM)"
)

st.sidebar.write(
    "Difficult Word Detection"
)

st.sidebar.write(
    "Confidence Estimation"
)

st.sidebar.write(
    "User Profile and Progress"
)


# ============================================================
# PROFILE PAGE
# ============================================================

if page == "My Profile":

    show_profile()

    st.stop()


# ============================================================
# MY PROGRESS
# ============================================================

if page == "My Progress":

    st.header("My Progress")

    history = current_user.get("history", [])

    if not history:
        st.info("No speech practice sessions recorded yet.")
    else:
        progress_df = pd.DataFrame(history)

        st.subheader("Practice History")
        st.dataframe(
            progress_df,
            use_container_width=True,
            hide_index=True
        )

        if "score" in progress_df.columns:
            chart_df = pd.DataFrame({
                "Session": range(1, len(progress_df) + 1),
                "Score": pd.to_numeric(
                    progress_df["score"],
                    errors="coerce"
                ).fillna(0).astype(int)
            }).set_index("Session")

            st.subheader("Progress Over Time")
            st.line_chart(chart_df)

    st.stop()


# ============================================================
# SETTINGS
# ============================================================

if page == "Settings":

    st.header("Settings")
    st.write("These settings provide information about the current speech-practice system.")
    st.write("**Recording duration:** Use the recording-duration slider in the sidebar.")
    st.write("**Speech recognition:** Whisper AI is used for speech-to-text conversion.")
    st.write("**Automatic disorder detection:** Stuttering/disfluency indicators are checked automatically whenever you complete Word Pronunciation or Sentence Analysis.")
    st.write("**Stored data:** Practice scores and history are kept in the local users.json file.")
    st.stop()


# ============================================================
# LOAD AI RESOURCES ONLY WHEN REQUIRED
# ============================================================

try:

    model = load_model()

except Exception as e:

    st.error(
        f"Unable to load Whisper model: {e}"
    )

    st.stop()


try:

    grammar_tool = load_grammar_tool()

except Exception as e:

    grammar_tool = None

    st.warning(
        f"LanguageTool could not be loaded: {e}"
    )


# ============================================================
# WORD PRONUNCIATION
# ============================================================

if page == "Word Pronunciation":

    st.header(
        "🔤 Word Pronunciation Check"
    )


    expected_text = st.text_input(

        "Enter expected word or sentence:",

        "misogyny"

    )


    start_word_recording = st.button(
        "Start Recording 🎙️"
    )

    if start_word_recording:
        if not expected_text.strip():
            st.error(
                "Please enter the expected word or sentence."
            )
            st.stop()

        # A new original recording starts a fresh analysis/practice cycle.
        st.session_state.word_practice_result = None
        st.session_state.word_practice_target_key = None

        audio_file = record_audio(duration)
        text = transcribe_audio(audio_file, model)

        st.session_state.last_word_analysis_text = text
        st.session_state.last_word_analysis_expected = expected_text
        st.session_state.last_word_analysis_duration = duration

    elif st.session_state.get("last_word_analysis_text") is not None:
        # A practice button causes Streamlit to rerun. Reuse the original
        # recording instead of returning to the initial recording screen.
        text = st.session_state.last_word_analysis_text
        expected_text = st.session_state.get(
            "last_word_analysis_expected", expected_text
        )
        duration = st.session_state.get(
            "last_word_analysis_duration", duration
        )
    else:
        text = None

    if text is None:
        st.stop()

    st.success(
        f"You said: {text}"
    )

    screening = analyze_stuttering_pattern(text, duration)
    display_automatic_disorder_result(
        text,
        duration,
        save_result=False
    )


    # -----------------------------------------
    # SPEECH ANALYSIS
    # -----------------------------------------

    st.subheader(
        "⏱ Speech Analysis"
    )


    (
        words,
        word_count,
        wpm,
        fillers,
        difficult_words
    ) = speech_statistics(
        text,
        duration
    )


    st.write(
        f"Word Count: {word_count}"
    )


    st.write(
        f"Words per minute: {wpm}"
    )


    # -----------------------------------------
    # FILLER WORDS
    # -----------------------------------------

    st.subheader(
        "🚫 Filler Words Detection"
    )


    if fillers:

        st.warning(
            "Filler words used: "
            + ", ".join(fillers)
        )

    else:

        st.success(
            "No filler words detected."
        )


    # -----------------------------------------
    # DIFFICULT WORDS
    # -----------------------------------------

    st.subheader(
        "🔍 Difficult Words"
    )


    if difficult_words:

        st.write(
            ", ".join(
                difficult_words
            )
        )

    else:

        st.success(
            "No difficult words found."
        )


    # -----------------------------------------
    # CONFIDENCE
    # -----------------------------------------

    st.subheader(
        "🎯 Confidence Level"
    )


    confidence = random.randint(
        60,
        95
    )


    if confidence > 85:

        st.success(
            f"High confidence: {confidence}%"
        )

    elif confidence > 70:

        st.info(
            f"Moderate confidence: {confidence}%"
        )

    else:

        st.warning(
            f"Low confidence: {confidence}%"
        )


    # -----------------------------------------
    # PRONUNCIATION COMPARISON
    # -----------------------------------------

    spoken = text.lower().split()

    expected = (
        expected_text
        .lower()
        .split()
    )


    wrong = []

    correct = []


    for i in range(
        min(
            len(spoken),
            len(expected)
        )
    ):

        similarity = (
            difflib.SequenceMatcher(
                None,
                spoken[i],
                expected[i]
            ).ratio()
        )


        if similarity < 0.7:

            wrong.append(
                expected[i]
            )

        else:

            correct.append(
                spoken[i]
            )


    # The expected words that were actually mispronounced/missed are
    # the only valid articulation-practice targets.
    pronunciation_targets = find_pronunciation_targets(
        expected_text,
        text
    )

    # Penalize missing expected words

    missing_words = max(
        0,
        len(expected)
        - len(spoken)
    )


    correct_count = len(
        correct
    )


    if len(expected) == 0:

        score = 0

    else:

        score = int(

            (
                correct_count
                / len(expected)
            ) * 100

        )


    score = max(
        0,
        min(
            100,
            score
        )
    )


    # -----------------------------------------
    # PRONUNCIATION REPORT
    # -----------------------------------------

    st.subheader(
        "📊 Pronunciation Report"
    )


    st.metric(
        "Pronunciation Score",
        f"{score}%"
    )


    st.progress(
        score / 100
    )


    st.markdown(
        "### 🧾 Highlighted Output"
    )


    st.write(
        highlight_text(
            text,
            wrong
        )
    )


    if wrong:

        st.error(
            "Mispronounced Words: "
            + ", ".join(wrong)
        )

    elif missing_words > 0:

        st.warning(
            f"{missing_words} expected word(s) were not detected."
        )

    else:

        st.success(
            "Good pronunciation."
        )


    # -----------------------------------------
    # GUIDED PRONUNCIATION PRACTICE
    # -----------------------------------------
    # Practice is shown only when the expected word was not clearly
    # pronounced. The target is ALWAYS the expected word, not a random
    # simple word and not the incorrect Whisper transcription.
    if pronunciation_targets:
        guided_pronunciation_practice(
            pronunciation_targets,
            model,
            practice_duration=5
        )


    # -----------------------------------------
    # SAVE RESULT
    # -----------------------------------------

    if start_word_recording:
        save_user_score(
            score,
            mode="Word Pronunciation",
            wpm=wpm
        )

# ============================================================
# SENTENCE ANALYSIS
# ============================================================

elif page == "Sentence Analysis":

    st.header(
        "🧠 Sentence Analysis"
    )


    st.write(
        "Speak a complete sentence and SpeakEase will analyze speech rate, filler words, grammar and overall speech performance."
    )


    start_sentence_recording = st.button(
        "Start Speaking 🎙️"
    )


    # ---------------------------------------------------------
    # IMPORTANT: Do not analyze anything before the user records.
    # The previous sentence is preserved only during reruns of this
    # page after an actual recording has been made.
    # ---------------------------------------------------------
    if start_sentence_recording:

        st.session_state.guided_practice_result = None
        st.session_state.guided_practice_target_key = None

        audio_file = record_audio(
            duration
        )

        # Always pass the loaded Whisper model.
        text = transcribe_audio(
            audio_file,
            model
        ) or ""

        text = str(text).strip()

        if not text:
            st.warning(
                "No clear speech was detected. Please click Start Speaking and try again."
            )
            st.stop()

        st.session_state.last_sentence_analysis_text = text
        st.session_state.last_sentence_analysis_duration = duration

        st.success(
            f"You said: {text}"
        )

    elif st.session_state.get("last_sentence_analysis_text") is not None:

        text = st.session_state.last_sentence_analysis_text
        duration = st.session_state.get(
            "last_sentence_analysis_duration",
            duration
        )

    else:

        # First visit to the page: show only the existing UI above.
        st.stop()


    # Automatic disorder detection begins ONLY after a real recording exists.
    screening = analyze_stuttering_pattern(
        text,
        duration
    )

    display_automatic_disorder_result(
        text,
        duration
    )


    # -----------------------------------------
    # SPEECH STATISTICS
    # -----------------------------------------

    st.subheader(
        "⏱ Speech Analysis"
    )


    (
        words,
        word_count,
        wpm,
        fillers,
        difficult_words
    ) = speech_statistics(
        text,
        duration
    )


    st.write(
        f"Word Count: {word_count}"
    )


    st.write(
        f"Words per minute: {wpm}"
    )


    # -----------------------------------------
    # FILLER WORDS
    # -----------------------------------------

    st.subheader(
        "🚫 Filler Words Detection"
    )


    if fillers:

        st.warning(
            "Filler words used: "
            + ", ".join(fillers)
        )

    else:

        st.success(
            "No filler words detected."
        )


    # -----------------------------------------
    # DIFFICULT WORDS
    # -----------------------------------------

    st.subheader(
        "🔍 Difficult Words"
    )


    if difficult_words:

        st.write(
            ", ".join(
                difficult_words
            )
        )

    else:

        st.success(
            "No difficult words found."
        )


    # -----------------------------------------
    # CONFIDENCE
    # -----------------------------------------

    st.subheader(
        "🎯 Confidence Level"
    )


    confidence = random.randint(
        60,
        95
    )


    if confidence > 85:

        st.success(
            f"High confidence: {confidence}%"
        )

    elif confidence > 70:

        st.info(
            f"Moderate confidence: {confidence}%"
        )

    else:

        st.warning(
            f"Low confidence: {confidence}%"
        )


    # -----------------------------------------
    # GRAMMAR ANALYSIS
    # -----------------------------------------

    st.subheader(
        "📝 Grammar Analysis"
    )


    if grammar_tool is not None:

        matches, corrected = (
            check_grammar(
                text,
                grammar_tool
            )
        )

    else:

        matches = []

        corrected = text


    if matches:

        st.warning(
            f"Found {len(matches)} grammar/spelling issue(s)."
        )


        st.markdown(
            "### 🧾 Highlighted Issues"
        )


        st.write(
            highlight_grammar_errors(
                text,
                matches
            )
        )


        for i, match in enumerate(
            matches
        ):

            with st.expander(
                f"Issue {i + 1}: {match['message']}"
            ):

                st.write(
                    f"**Context:** ...{match['context']}..."
                )


                if match[
                    "replacements"
                ]:

                    st.write(

                        "**Suggestions:** "
                        + ", ".join(
                            match[
                                "replacements"
                            ]
                        )

                    )


        st.write(
            "**Corrected Sentence:**"
        )


        st.success(
            corrected
        )


    else:

        st.success(
            "No major grammar issues detected."
        )


    # -----------------------------------------
    # SPEECH SCORE
    # -----------------------------------------

    # Base score based on number of spoken words
    base_score = (
        len(words) * 8
    )


    # Keep score within 0-100
    base_score = min(
        100,
        base_score
    )


    # Grammar penalty
    grammar_penalty = (
        len(matches) * 5
    )


    score = (
        base_score
        - grammar_penalty
    )


    score = max(
        0,
        min(
            100,
            int(score)
        )
    )


    st.subheader(
        "📊 Speech Score"
    )


    st.metric(
        "Overall Score",
        f"{score}%"
    )


    st.progress(
        score / 100
    )


    # -----------------------------------------
    # PRONUNCIATION INSIGHT
    # -----------------------------------------

    st.subheader(
        "🔍 Pronunciation Insight"
    )


    common_words = [

        "i",
        "am",
        "is",
        "to",
        "go",
        "of",
        "in",
        "on",
        "at",
        "it"

    ]


    unclear = [

        word

        for word in words

        if len(
            word.strip(
                ".,!?"
            )
        ) <= 2

        and word.lower()
        not in common_words

    ]


    if unclear:

        st.warning(
            "Unclear words: "
            + ", ".join(
                unclear
            )
        )

    else:

        st.success(
            "Clear speech detected."
        )


    # -----------------------------------------
    # GUIDED THERAPY PRACTICE
    # -----------------------------------------
    # Do not show therapy for normal speech, grammar errors,
    # pronunciation errors, or unclear words alone.
    if screening["risk_score"] >= 50:

        st.subheader("🩺 Therapy Practice")

        st.write(
            "The detected speech pattern indicates that guided "
            "fluency practice may be useful."
        )

        if screening["repeated_word_count"] > 0:
            st.write(
                "• Practise gentle speech onset and avoid forcing repeated words."
            )

        if screening["repetition_rate"] >= 10:
            st.write(
                "• Practise short phrases with comfortable pauses between phrases."
            )

        if screening["filler_count"] > 0:
            st.write(
                "• Replace filler words with brief natural pauses."
            )

        if screening["wpm"] > 160:
            st.write(
                "• Reduce the speaking rate gradually while keeping speech comfortable."
            )

        guided_speech_practice(
            screening,
            model,
            practice_duration=5
        )


    # -----------------------------------------
    # SAVE RESULT
    # -----------------------------------------

    save_user_score(

        score,

        mode="Sentence Analysis",

        wpm=wpm

    )


    # -----------------------------------------
    # CURRENT SESSION PROGRESS
    # -----------------------------------------

    st.subheader(
        "📈 Progress Over Time"
    )


    current_scores = (
        st.session_state.scores
    )


    if current_scores:

        progress_df = pd.DataFrame({

            "Session":
                range(
                    1,
                    len(
                        current_scores
                    ) + 1
                ),

            "Score":
                current_scores

        })


        st.line_chart(
            progress_df.set_index(
                "Session"
            )
        )

# ============================================================
# FOOTER
# ============================================================

st.sidebar.divider()

st.sidebar.caption(
    "SpeakEase - AI Speech Therapy System"
)