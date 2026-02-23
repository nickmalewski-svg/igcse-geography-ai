# --------------------------------------
# 1️⃣ Imports
# --------------------------------------
import streamlit as st
import openai
import pandas as pd
import re
from datetime import datetime
from fpdf import FPDF
from supabase import create_client

# --------------------------------------
# 2️⃣ Secrets
# --------------------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
OPENAI_KEY = st.secrets["OPENAI_API_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
openai.api_key = OPENAI_KEY

# --------------------------------------
# 3️⃣ Page config & styling
# --------------------------------------
st.set_page_config(page_title="IGCSE Geography AI", layout="wide")
st.markdown("""
<style>
h1,h2,h3 {color:#2E86C1;}
.stButton button {background-color:#2E86C1;color:white;border-radius:8px;}
.stTextInput>div>input {border-radius:5px;}
body {background-color:#F8F9F9;}
</style>
""", unsafe_allow_html=True)

# --------------------------------------
# 4️⃣ Session state
# --------------------------------------
if "user" not in st.session_state:
    st.session_state["user"] = None

# --------------------------------------
# 5️⃣ Authentication
# --------------------------------------
def login_signup():
    st.subheader("Login / Signup")
    option = st.radio("Choose an option:", ["Login", "Signup"])
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Submit"):
        if option == "Signup":
            try:
                res = supabase.auth.sign_up({"email": email, "password": password})
                if res.user:
                    st.success("Signup successful! You can now login.")
                else:
                    st.error("Signup failed. Check email/password.")
            except Exception as e:
                st.error(f"Signup error: {e}")
        else:
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if res.user:
                    st.session_state["user"] = res.user
                    st.success(f"Logged in as {email}")
                else:
                    st.error("Login failed. Check email/password.")
            except Exception as e:
                st.error(f"Login error: {e}")
    st.stop()

if st.session_state["user"] is None:
    login_signup()

user_id = st.session_state["user"].id
user_email = st.session_state["user"].email

# --------------------------------------
# 6️⃣ Sidebar Navigation
# --------------------------------------
page = st.sidebar.selectbox("Navigate:", ["🏠 Home", "📝 Take Exam", "📊 Dashboard"])

# --------------------------------------
# 7️⃣ Home Page
# --------------------------------------
if page == "🏠 Home":
    st.title("🌍 Welcome to the Adaptive IGCSE Geography AI")
    st.markdown("""
    - Take **adaptive mock exams** on IGCSE Geography topics.
    - Answer **MCQs, short answers, essays, and map/image questions**.
    - Receive **AI-generated grading and feedback**.
    - Track your progress with **dashboard and badges**.
    """)

# --------------------------------------
# 8️⃣ Take Exam Page
# --------------------------------------
if page == "📝 Take Exam":
    st.title("📝 Take Adaptive Exam")
    topics = st.multiselect(
        "Select topics for your exam:",
        ["Rivers", "Population", "Urbanization", "Climate Change"]
    )
    if not topics:
        st.stop()

    # Fetch past results
    try:
        results = supabase.table("exam_results").select("*").eq("user_id", user_id).execute()
        past_results = pd.DataFrame(results.data)
    except Exception as e:
        st.error(f"Error fetching past results: {e}")
        past_results = pd.DataFrame()

    # Adaptive logic
    def calculate_mastery(past_results, topics):
        mastery = {}
        for t in topics:
            topic_scores = past_results[past_results["topics"].str.contains(t)] if not past_results.empty else pd.DataFrame()
            mastery[t] = topic_scores["total_score"].mean() if not topic_scores.empty else 0
        return mastery

    def questions_per_topic(mastery):
        topic_q = {}
        for t, score in mastery.items():
            if score < 50: topic_q[t] = {"MCQ":3,"SA":2,"Essay":2,"Map":1}
            elif score < 80: topic_q[t] = {"MCQ":2,"SA":1,"Essay":1,"Map":1}
            else: topic_q[t] = {"MCQ":1,"SA":1,"Essay":1,"Map":1}
        return topic_q

    mastery = calculate_mastery(past_results, topics)
    topic_q = questions_per_topic(mastery)

   # Select model safely
MODEL_TO_USE = "gpt-3.5-turbo"  # default safe choice
# MODEL_TO_USE = "gpt-4"  # uncomment if your API key has GPT-4 access

# Generate exam
if st.button("Generate Exam"):
    with st.spinner("Generating exam..."):
        exam_prompt = "Generate a personalized IGCSE Geography exam with MCQs, short answers, essays, and map/image questions:\n"
        for topic,q in topic_q.items():
            exam_prompt += f"- {topic}: {q['MCQ']} MCQs, {q['SA']} SA, {q['Essay']} essays, {q['Map']} map/image question.\n"
        exam_prompt += "Provide model answers, rubric for essays, and image URLs."

        try:
            response = openai.chat.completions.create(
                model=MODEL_TO_USE,
                messages=[{"role": "user", "content": exam_prompt}],
                max_tokens=3000
            )
            exam_text = response.choices[0].message.content
            st.session_state["exam_text"] = exam_text
            st.text_area("📄 Exam Paper", exam_text, height=500)
        except openai.error.InvalidRequestError as e:
            st.error(f"OpenAI model error: {e}")
        except openai.error.AuthenticationError as e:
            st.error(f"OpenAI API key error: {e}")
        except openai.error.APIConnectionError as e:
            st.error(f"Connection error to OpenAI API: {e}")
        except openai.error.OpenAIError as e:
            st.error(f"Unexpected OpenAI API error: {e}")

    # Parse exam
    def parse_exam(text):
        mcq_answers = re.findall(r"Answer:\s*([A-D])", text)
        sa_answers = re.findall(r"Q\d+:.*?A:\s*(.*?)(?:\nQ\d+:|$)", text, flags=re.DOTALL)
        sa_answers = [ans.strip() for ans in sa_answers if len(ans.strip()) < 300]
        essay_answers = [ans.strip() for ans in sa_answers if len(ans.strip()) > 100]
        map_matches = re.findall(r"(https?://\S+\.(?:png|jpg|jpeg|gif))", text)
        return mcq_answers, sa_answers[:len(sa_answers)-len(essay_answers)], essay_answers, map_matches

    if "exam_text" in st.session_state:
        mcq_model, sa_model, essay_model, map_urls = parse_exam(st.session_state["exam_text"])

        st.subheader("✏️ Your Answers")
        mcq_student = [st.text_input(f"MCQ {i+1} Answer (A-D)", key=f"mcq_{i}").upper() for i in range(len(mcq_model))]
        sa_student = [st.text_area(f"SA {i+1}", key=f"sa_{i}", height=100) for i in range(len(sa_model))]
        essay_student = [st.text_area(f"Essay {i+1}", key=f"essay_{i}", height=150) for i in range(len(essay_model))]

        st.subheader("🗺 Map/Image Questions")
        map_student = []
        for i, url in enumerate(map_urls):
            st.image(url, caption=f"Map Question {i+1}")
            ans = st.text_input(f"Map Question {i+1} Answer:", key=f"map_{i}")
            map_student.append(ans)

        # Submit & grade
        if st.button("Submit & Get Feedback"):
            with st.spinner("Grading exam..."):
                # --- MCQs ---
                mcq_feedback, mcq_score = [], 0
                for s,m in zip(mcq_student,mcq_model):
                    if s==m: mcq_feedback.append(f"✅ {s}"); mcq_score+=1
                    else: mcq_feedback.append(f"❌ {s}, correct: {m}")
                # --- SA ---
                sa_feedback, sa_score = [],0
                for s,m in zip(sa_student,sa_model):
                    prompt=f"Grade out of 5:\nModel:{m}\nStudent:{s}\nProvide score and brief feedback."
                    res=openai.chat.completions.create(
                        model="gpt-4",
                        messages=[{"role":"user","content":prompt}],
                        max_tokens=150
                    )
                    text=res.choices[0].message.content
                    sa_feedback.append(text)
                    match=re.search(r"(\d+)",text); sa_score+=int(match.group(1)) if match else 0
                # --- Essays ---
                essay_feedback, essay_score=[],0
                for s,m in zip(essay_student,essay_model):
                    prompt=f"Grade essay out of 10 using rubric: Accuracy 0-4, Examples 0-2, Structure 0-2, Terms 0-2.\nModel:{m}\nStudent:{s}\nProvide total score and feedback."
                    res=openai.chat.completions.create(
                        model="gpt-4",
                        messages=[{"role":"user","content":prompt}],
                        max_tokens=250
                    )
                    text=res.choices[0].message.content
                    essay_feedback.append(text)
                    match=re.search(r"Total\s*out of\s*(\d+)",text); essay_score+=int(match.group(1)) if match else 0
                # --- Map ---
                map_feedback,map_score=[],0
                for s,url in zip(map_student,map_urls):
                    prompt=f"Check student's answer based on map URL {url}.\nAnswer:{s}\nScore 0-5"
                    res=openai.chat.completions.create(
                        model="gpt-4",
                        messages=[{"role":"user","content":prompt}],
                        max_tokens=100
                    )
                    text=res.choices[0].message.content
                    map_feedback.append(text)
                    match=re.search(r"(\d+)",text); map_score+=int(match.group(1)) if match else 0

                total_score=mcq_score+sa_score+essay_score+map_score

                # Display feedback
                st.subheader("✅ Results")
                st.markdown("**MCQs:**"); [st.markdown(f"- {f}") for f in mcq_feedback]
                st.markdown("**SA:**"); [st.markdown(f"- {f}") for f in sa_feedback]
                st.markdown("**Essays:**"); [st.markdown(f"- {f}") for f in essay_feedback]
                st.markdown("**Map Questions:**"); [st.markdown(f"- {f}") for f in map_feedback]
                st.markdown(f"**Total Score:** {total_score}")

                # Save to Supabase
                supabase.table("exam_results").insert({
                    "user_id":user_id,"topics":", ".join(topics),
                    "mcq_score":mcq_score,"short_score":sa_score,
                    "essay_score":essay_score,"total_score":total_score
                }).execute()

                # --- Badges ---
                badges_awarded=[]
                for t,score in mastery.items():
                    if score>=80: badges_awarded.append(f"Mastered {t}")
                if total_score>90: badges_awarded.append("Top Scorer")
                for b in badges_awarded:
                    supabase.table("badges").insert({"user_id":user_id,"badge_name":b,"date_awarded":datetime.now().isoformat()}).execute()

                st.subheader("🏆 Badges")
                badges = supabase.table("badges").select("*").eq("user_id", user_id).execute()
                for b in badges.data: st.success(f"{b['badge_name']} ({b['date_awarded'][:10]})")

                # PDF report using FPDF
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                pdf.multi_cell(0,10,txt=f"Exam Report for {user_email}\n\n{st.session_state['exam_text']}\n\n" +
                                "\n".join(mcq_feedback+sa_feedback+essay_feedback+map_feedback))
                pdf_file = f"{user_email}_exam_report.pdf"
                pdf.output(pdf_file)
                st.success(f"PDF report generated: {pdf_file}")

# --------------------------------------
# 9️⃣ Dashboard Page
# --------------------------------------
if page=="📊 Dashboard":
    st.title("📊 Dashboard")
    results = supabase.table("exam_results").select("*").eq("user_id", user_id).execute()
    student_data = pd.DataFrame(results.data)
    if not student_data.empty:
        st.line_chart(student_data[["mcq_score","short_score","essay_score","total_score"]])
        st.subheader("🏆 Badges")
        badges = supabase.table("badges").select("*").eq("user_id", user_id).execute()
        for b in badges.data: st.success(f"{b['badge_name']} ({b['date_awarded'][:10]})")
    else: st.write("No exams taken yet.")


