
import os
import json
import sqlite3
import base64
import json
import whisper

from langchain_core.messages import HumanMessage
from langchain_openrouter import ChatOpenRouter
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

# ---------- AI ----------

llm = ChatOpenRouter(
    model="openrouter/free",
    api_key=os.environ["OPENROUTER_API_KEY"]
)

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
whisper_model = whisper.load_model("base")
#takes the recorded audio, temporarily saves it as a WAV file, 
#sends it to Whisper, and returns the transcribed text.

def transcribe_voice(audio_bytes):

    with open("temp_audio.wav", "wb") as f:
        f.write(audio_bytes)

    result = whisper_model.transcribe(
        "temp_audio.wav",
        language="hi",
        task="transcribe"
    )

    text = result["text"].strip()

    try:
        text = transliterate(
            text,
            sanscript.URDU,
            sanscript.DEVANAGARI
        )
    except Exception:
        pass

    return text

# ---------- DATABASE ----------

conn = sqlite3.connect("upyogi.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS grievances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint TEXT NOT NULL,
    category TEXT,
    location TEXT,
    urgency TEXT,
    department TEXT,
    summary TEXT,
    status TEXT DEFAULT 'New',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()

# Add citizen information fields if they do not already exist

cursor.execute("PRAGMA table_info(grievances)")
existing_columns = [column[1] for column in cursor.fetchall()]

if "citizen_name" not in existing_columns:
    cursor.execute(
        "ALTER TABLE grievances ADD COLUMN citizen_name TEXT"
    )

if "mobile_number" not in existing_columns:
    cursor.execute(
        "ALTER TABLE grievances ADD COLUMN mobile_number TEXT"
    )

if "citizen_address" not in existing_columns:
    cursor.execute(
        "ALTER TABLE grievances ADD COLUMN citizen_address TEXT"
    )

conn.commit()

# ---------- GRIEVANCE PROCESSING ----------

def process_grievance(complaint):

    prompt = f"""
You are an AI government grievance classification system.

Analyze the citizen complaint below.

Return ONLY valid JSON with exactly these fields:
- category
- location
- urgency
- department
- summary

Do not add markdown or explanation.

Citizen complaint:
{complaint}
"""

    response = llm.invoke(prompt)

    return json.loads(response.content)
DEPARTMENT_MAP = {
    "Water Supply": "Water Supply Department",
    "Sanitation": "Municipal Corporation",
    "Roads": "Public Works",
    "Electricity": "Electricity Department",
    "Street Lighting": "Municipal Corporation",
    "Public Safety": "Police",
    "Health": "Health Department",
    "Education": "Education Department",
    "Other": "Relevant Department"
}


def get_department(category):

    return DEPARTMENT_MAP.get(
        category,
        "Relevant Department"
    )
    
def process_image_grievance(image_bytes, location):

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    message = HumanMessage(content=[
        {
            "type": "text",
            "text": """
            Analyze this image as a citizen grievance.
            Describe the problem visible in the image in one sentence.
            """
        },
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{image_b64}"
            }
        }
    ])

    description = llm.invoke([message]).content

    prompt = f"""
    You are an AI government grievance classification system.

    Grievance:
    {description}

    Return ONLY valid JSON with exactly these fields:
    - category
    - location
    - urgency
    - summary

    Category MUST be exactly one of:
    Water Supply, Sanitation, Roads, Electricity,
    Street Lighting, Public Safety, Health, Education, Other.

    If location is unknown, use "Unknown".
    Do not add markdown or explanation.
    """

    result = llm.invoke(prompt)

    data = json.loads(result.content)

    data["location"] = location
    
    data["department"] = get_department(
        data["category"]
    )

    return data
def save_image_grievance(
    image_bytes,
    citizen_name,
    mobile_number,
    citizen_address,
    location
):

    data = process_image_grievance(
        image_bytes,
        location
    )

    cursor.execute("""
        INSERT INTO grievances
        (
            complaint,
            category,
            location,
            urgency,
            department,
            summary,
            citizen_name,
            mobile_number,
            citizen_address
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "[Image grievance]",
        data["category"],
        data["location"],
        data["urgency"],
        data["department"],
        data["summary"],
        citizen_name,
        mobile_number,
        citizen_address
    ))

    conn.commit()

    return data

def save_grievance(
    complaint,
    citizen_name,
    mobile_number,
    citizen_address,
    location
):

    data = process_grievance(complaint)

    data["location"] = location
    data["department"] = get_department(
        data["category"]
    )

    cursor.execute("""
        INSERT INTO grievances
        (
            complaint,
            category,
            location,
            urgency,
            department,
            summary,
            citizen_name,
            mobile_number,
            citizen_address
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        complaint,
        data["category"],
        data["location"],
        data["urgency"],
        data["department"],
        data["summary"],
        citizen_name,
        mobile_number,
        citizen_address
    ))

    conn.commit()

    return data

def submit_grievance(
    complaint,
    citizen_name,
    mobile_number,
    citizen_address,
    location
):

    if not complaint.strip():
        return None

    return save_grievance(
        complaint,
        citizen_name,
        mobile_number,
        citizen_address,
        location
    )


# ---------- OFFICER ----------

def get_all_grievances():

    cursor.execute("""
        SELECT
            id,
            complaint,
            category,
            location,
            urgency,
            department,
            summary,
            status,
            created_at,
            citizen_name,
            mobile_number,
            citizen_address
        FROM grievances
        ORDER BY created_at DESC
    """)

    return cursor.fetchall()


def update_status(grievance_id, new_status):

    allowed_statuses = [
        "New",
        "Assigned",
        "In Progress",
        "Resolved"
    ]

    if new_status not in allowed_statuses:
        return False

    cursor.execute("""
        UPDATE grievances
        SET status = ?
        WHERE id = ?
    """, (new_status, grievance_id))

    conn.commit()

    return True


# ---------- SYSTEMIC ISSUES ----------

SYSTEMIC_THRESHOLD = 0.75


def detect_systemic_issues():

    grievances = get_all_grievances()
    issues = []

    for i in range(len(grievances)):
        for j in range(i + 1, len(grievances)):

            g1 = grievances[i]
            g2 = grievances[j]

            same_location = g1[3].lower() == g2[3].lower()
            same_category = g1[2].lower() == g2[2].lower()

            if not (same_location and same_category):
                continue

            embeddings = embedding_model.encode([g1[6], g2[6]])

            similarity = cosine_similarity(
                [embeddings[0]],
                [embeddings[1]]
            )[0][0]

            relatedness_score = (
                0.6 * float(similarity)
                + 0.2 * int(same_location)
                + 0.2 * int(same_category)
            )

            if relatedness_score >= SYSTEMIC_THRESHOLD:

                issues.append({
    "location": g1[3],
    "category": g1[2],
    "grievance_ids": [g1[0], g2[0]],
    "relatedness_score": round(
        float(relatedness_score), 3
    ),
    "evidence": [
        g1[6],
        g2[6]
    ],
    "recommended_action": (
        f"Investigate the underlying {g1[2].lower()} issue "
        f"affecting multiple complaints in {g1[3]}."
    )
})

    return issues


def add_systemic_priority(issues):

    for issue in issues:

        grievance_count = len(issue["grievance_ids"])
        score = issue["relatedness_score"]

        if grievance_count >= 3 and score >= 0.80:
            priority = "Critical"
        elif grievance_count >= 2 and score >= 0.75:
            priority = "High"
        else:
            priority = "Medium"

        issue["priority"] = priority

    return issues


def get_officer_intelligence():

    grievances = get_all_grievances()

    systemic_issues = add_systemic_priority(
        detect_systemic_issues()
    )

    return {
        "total_grievances": len(grievances),
        "new_grievances": sum(
            1 for g in grievances if g[7] == "New"
        ),
        "systemic_issues": systemic_issues
    }
