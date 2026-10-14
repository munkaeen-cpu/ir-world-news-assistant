"""
International Relations Study Platform
- Uses free GDELT API + public RSS feeds
- No paid AI required
- Supports local SQLite fallback and free Supabase/Postgres when configured
- Saves notes, flashcards, and saved articles
"""

import os
import sqlite3
import datetime
import random
import hashlib
import textwrap
import re
from urllib.parse import quote_plus
from io import BytesIO

import requests
import feedparser
from bs4 import BeautifulSoup
import streamlit as st

# Optional Postgres driver for Supabase support
try:
    import psycopg2
except Exception:
    psycopg2 = None

# --------------------------------------
# App config
# --------------------------------------
st.set_page_config(page_title="IR Study Platform", layout="wide", initial_sidebar_state="expanded")

# Folder for local fallback database
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "data.db")

# Free public services used
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

RSS_FEEDS = {
    "Reuters World": "http://feeds.reuters.com/Reuters/worldNews",
    "Al Jazeera English": "https://www.aljazeera.com/xml/rss/all.xml",
    "BBC World": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "The Guardian World": "https://www.theguardian.com/world/rss",
    "Voice of America": "https://www.voanews.com/rss",
    "NPR International": "https://www.npr.org/rss/rss.php?id=1004",
    "Xinhua World": "http://www.xinhuanet.com/english/rss/worldrss.xml",
}

GDELT_QUERIES = {
    "Wars and conflicts": "war OR conflict OR fighting OR battle OR offensive",
    "US-China relations": "US China OR United States China OR Sino-American OR US-China",
    "Russia and Ukraine": "Russia Ukraine OR Russo-Ukrainian OR Russia OR Ukraine",
    "Middle East": "Middle East OR Israel OR Palestine OR Syria OR Iran OR Yemen OR Lebanon",
    "United Nations and NATO": "United Nations OR UN OR NATO OR alliance",
    "International trade and sanctions": "trade OR sanctions OR tariff OR WTO OR trade war",
    "Mongolia's foreign policy": "Mongolia OR \"Third Neighbor\" OR \"Third Neighbour\" OR Ulaanbaatar"
}

IR_THEORIES = {
    "Realism": {
        "definition": "Realism focuses on the state as the main actor in an anarchic international system, where power and security matter most.",
        "keywords": ["power", "security", "anarchy", "self-help", "national interest"],
    },
    "Liberalism": {
        "definition": "Liberalism emphasizes cooperation, institutions, trade, law, and interdependence between states and societies.",
        "keywords": ["institutions", "cooperation", "trade", "law", "interdependence"],
    },
    "Constructivism": {
        "definition": "Constructivism studies how ideas, identities, and norms shape state interests and international behavior.",
        "keywords": ["identity", "norms", "ideas", "beliefs", "social construction"],
    },
    "Marxism": {
        "definition": "Marxism analyzes international relations through class relations, capitalism, inequality, and global economic structures.",
        "keywords": ["capitalism", "class", "inequality", "imperialism", "dependency"],
    },
    "English School": {
        "definition": "The English School examines international society: shared norms, rules, diplomacy, and order among states.",
        "keywords": ["international society", "order", "diplomacy", "norms", "law"],
    },
}

VOCAB = [
    ("sovereignty", "supreme authority of a state over its territory and people", "төрийн дээд эрх, бүрэн эрх"),
    ("hegemony", "dominant influence or leadership by one state over others", "давамгайлал"),
    ("deterrence", "to prevent action by threat or fear of consequences", "сөрөг нөлөөгөөр урьдчилан сэргийлэх"),
    ("interdependence", "mutual reliance between states or economies", "харилцан хамаарал"),
    ("sanctions", "penalties imposed to change a state's behavior", "хориг арга хэмжээ"),
    ("soft power", "influence through culture, values, and attraction rather than force", "зөөлөн хүч"),
    ("balance of power", "a condition in which states check the dominance of a stronger power", "эрх мэдлийн тэнцвэр"),
]

# --------------------------------------
# Database backend switch
# --------------------------------------
def get_db_url():
    try:
        return st.secrets["db"]["database_url"]
    except Exception:
        return os.getenv("DATABASE_URL")

def is_postgres_enabled():
    return bool(get_db_url()) and psycopg2 is not None

def get_db_connection():
    db_url = get_db_url()
    if db_url and psycopg2 is not None:
        return psycopg2.connect(db_url, sslmode="require")
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    if is_postgres_enabled():
        cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id SERIAL PRIMARY KEY,
            title TEXT,
            course TEXT,
            topic TEXT,
            tags TEXT,
            date TEXT,
            content TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS flashcards (
            id SERIAL PRIMARY KEY,
            deck TEXT,
            front TEXT,
            back TEXT,
            tags TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            difficulty INTEGER DEFAULT 0
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id SERIAL PRIMARY KEY,
            title TEXT,
            source TEXT,
            url TEXT UNIQUE,
            published TEXT,
            summary TEXT,
            content_hash TEXT,
            fetched_at TIMESTAMPTZ DEFAULT NOW()
        )
        """)
    else:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            course TEXT,
            topic TEXT,
            tags TEXT,
            date TEXT,
            content TEXT,
            created_at TEXT
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deck TEXT,
            front TEXT,
            back TEXT,
            tags TEXT,
            created_at TEXT,
            difficulty INTEGER DEFAULT 0
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            source TEXT,
            url TEXT UNIQUE,
            published TEXT,
            summary TEXT,
            content_hash TEXT,
            fetched_at TEXT
        )
        """)

    conn.commit()
    return conn

# Initialize database once
conn = init_db()

def db_query(sql, params=(), commit=False):
    try:
        if is_postgres_enabled():
            conn_db = get_db_connection()
            cur = conn_db.cursor()
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            if commit:
                conn_db.commit()
            return cur
        else:
            sqlite_sql = sql.replace("%s", "?")
            conn_db = get_db_connection()
            cur = conn_db.cursor()
            if params:
                cur.execute(sqlite_sql, params)
            else:
                cur.execute(sqlite_sql)
            if commit:
                conn_db.commit()
            return cur
    except Exception as e:
        st.error(f"Database error: {e}")
        return None

# --------------------------------------
# Utility functions
# --------------------------------------
def short_hash(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()

def safe_value(data, key, default=""):
    if isinstance(data, dict):
        return data.get(key, default)
    return default

def parse_date(date_str):
    if not date_str:
        return ""
    try:
        return datetime.datetime.fromisoformat(date_str).isoformat()
    except Exception:
        try:
            from dateutil import parser
            return parser.parse(date_str).isoformat()
        except Exception:
            return str(date_str)

# --------------------------------------
# News fetching
# --------------------------------------
def fetch_gdelt_articles(query, max_records=10):
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": max_records
    }
    try:
        url = GDELT_DOC_API + "?" + "&".join(f"{k}={quote_plus(str(v))}" for k, v in params.items())
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("articles", [])[:max_records]:
            title = item.get("title") or item.get("seentitle") or ""
            url = item.get("url") or item.get("sourceurl") or ""
            source = item.get("sourcecountry") or item.get("domain") or item.get("source") or ""
            published = item.get("seendate") or item.get("date") or ""
            excerpt = item.get("excerpt") or ""
            results.append({
                "title": title,
                "url": url,
                "source": source,
                "published": published,
                "excerpt": excerpt,
                "category": "GDELT",
                "via": "GDELT"
            })
        return results
    except Exception as e:
        st.warning(f"GDELT fetch failed: {e}")
        return []

def fetch_rss_feed(feed_url, max_items=5):
    try:
        feed = feedparser.parse(feed_url)
        entries = feed.entries[:max_items]
        results = []
        for entry in entries:
            title = safe_value(entry, "title", "")
            link = safe_value(entry, "link", "")
            source = safe_value(feed.feed, "title", "") or safe_value(entry, "source", "")
            published = safe_value(entry, "published", safe_value(entry, "updated", ""))
            summary = safe_value(entry, "summary", "")
            cleaned = BeautifulSoup(summary, "html.parser").get_text() if summary else ""
            results.append({
                "title": title,
                "url": link,
                "source": source,
                "published": published,
                "excerpt": cleaned,
                "category": "RSS",
                "via": "RSS"
            })
        return results
    except Exception as e:
        st.warning(f"RSS fetch failed for {feed_url}: {e}")
        return []

def fetch_latest_news(limit_per_feed=3, gdelt_per_topic=3, categories=None):
    categories = categories or list(GDELT_QUERIES.keys())
    articles = []

    for category in categories:
        query = GDELT_QUERIES.get(category, category)
        result = fetch_gdelt_articles(query, max_records=gdelt_per_topic)
        for item in result:
            item["category"] = category
            articles.append(item)

    for feed_name, feed_url in RSS_FEEDS.items():
        result = fetch_rss_feed(feed_url, max_items=limit_per_feed)
        for item in result:
            item["category"] = feed_name
            articles.append(item)

    # Deduplicate by URL or title
    seen = set()
    deduped = []
    for item in articles:
        key = item.get("url") or item.get("title") or ""
        if not key:
            continue
        k = short_hash(key)
        if k in seen:
            continue
        seen.add(k)
        deduped.append(item)

    def sort_key(article):
        return article.get("published") or ""

    deduped.sort(key=lambda a: sort_key(a), reverse=True)
    return deduped

def extractive_summary_from_url(url, max_sentences=2):
    try:
        headers = {"User-Agent": "IRStudyPlatform/1.0"}
        response = requests.get(url, headers=headers, timeout=12)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
        if not paragraphs:
            meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
            if meta and meta.get("content"):
                paragraphs = [meta.get("content")]
        text = " ".join(paragraphs)
        text = " ".join(text.split())
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        summary = " ".join(sentences[:max_sentences])
        if summary and not summary.endswith("."):
            summary += "."
        return summary
    except Exception:
        return ""

# --------------------------------------
# Notes
# --------------------------------------
def save_note(title, course, topic, tags, date, content):
    created = datetime.datetime.utcnow().isoformat()
    tags_str = ",".join(tags) if isinstance(tags, (list, tuple)) else (tags or "")

    if is_postgres_enabled():
        db_query(
            """
            INSERT INTO notes (title, course, topic, tags, date, content, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """,
            (title, course, topic, tags_str, str(date), content),
            commit=True
        )
    else:
        db_query(
            """
            INSERT INTO notes (title, course, topic, tags, date, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, course, topic, tags_str, str(date), content, created),
            commit=True
        )

def update_note(note_id, title, course, topic, tags, date, content):
    tags_str = ",".join(tags) if isinstance(tags, (list, tuple)) else (tags or "")
    if is_postgres_enabled():
        db_query(
            """
            UPDATE notes
            SET title=%s, course=%s, topic=%s, tags=%s, date=%s, content=%s
            WHERE id=%s
            """,
            (title, course, topic, tags_str, str(date), content, note_id),
            commit=True
        )
    else:
        db_query(
            """
            UPDATE notes
            SET title=?, course=?, topic=?, tags=?, date=?, content=?
            WHERE id=?
            """,
            (title, course, topic, tags_str, str(date), content, note_id),
            commit=True
        )

def delete_note(note_id):
    db_query("DELETE FROM notes WHERE id=%s" if is_postgres_enabled() else "DELETE FROM notes WHERE id=?", (note_id,), commit=True)

def list_notes(search=None, course=None, topic=None):
    sql = "SELECT id, title, course, topic, tags, date, content, created_at FROM notes"
    clauses = []
    params = []

    if search:
        q = f"%{search}%"
        if is_postgres_enabled():
            clauses.append("(title ILIKE %s OR content ILIKE %s OR tags ILIKE %s)")
        else:
            clauses.append("(title LIKE ? OR content LIKE ? OR tags LIKE ?)")
        params.extend([q, q, q])

    if course:
        if is_postgres_enabled():
            clauses.append("course = %s")
        else:
            clauses.append("course = ?")
        params.append(course)

    if topic:
        if is_postgres_enabled():
            clauses.append("topic = %s")
        else:
            clauses.append("topic = ?")
        params.append(topic)

    if clauses:
        sql += " WHERE " + " AND ".join(clauses)

    sql += " ORDER BY created_at DESC"
    cur = db_query(sql, params)
    if cur:
        return cur.fetchall()
    return []

# --------------------------------------
# Flashcards
# --------------------------------------
def save_flashcard(deck, front, back, tags=None):
    if is_postgres_enabled():
        db_query(
            """
            INSERT INTO flashcards (deck, front, back, tags, created_at, difficulty)
            VALUES (%s, %s, %s, %s, NOW(), 0)
            """,
            (deck, front, back, ",".join(tags) if isinstance(tags, (list, tuple)) else (tags or "")),
            commit=True
        )
    else:
        db_query(
            """
            INSERT INTO flashcards (deck, front, back, tags, created_at, difficulty)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (deck, front, back, ",".join(tags) if isinstance(tags, (list, tuple)) else (tags or ""), datetime.datetime.utcnow().isoformat()),
            commit=True
        )

def list_flashcards(deck=None, tag=None):
    sql = "SELECT id, deck, front, back, tags, difficulty FROM flashcards"
    clauses = []
    params = []

    if deck:
        if is_postgres_enabled():
            clauses.append("deck = %s")
        else:
            clauses.append("deck = ?")
        params.append(deck)

    if tag:
        if is_postgres_enabled():
            clauses.append("tags ILIKE %s")
        else:
            clauses.append("tags LIKE ?")
        params.append(f"%{tag}%")

    if clauses:
        sql += " WHERE " + " AND ".join(clauses)

    sql += " ORDER BY id ASC"
    cur = db_query(sql, params)
    if cur:
        return cur.fetchall()
    return []

def update_flashcard_difficulty(card_id, delta):
    db_query(
        "UPDATE flashcards SET difficulty = difficulty + %s WHERE id=%s" if is_postgres_enabled() else "UPDATE flashcards SET difficulty = difficulty + ? WHERE id=?",
        (delta, card_id) if is_postgres_enabled() else (delta, card_id),
        commit=True
    )

def delete_flashcard(card_id):
    db_query("DELETE FROM flashcards WHERE id=%s" if is_postgres_enabled() else "DELETE FROM flashcards WHERE id=?", (card_id,), commit=True)

# --------------------------------------
# Rule-based flashcard generation
# --------------------------------------
def generate_flashcards_from_text(text, deck="Auto Deck", max_cards=20):
    if not text or not text.strip():
        return []
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    candidates = []
    for s in sentences:
        if len(s.split()) < 6:
            continue
        if ":" in s or " is " in s.lower() or " are " in s.lower() or " means " in s.lower() or " refers to " in s.lower():
            candidates.append(s)
        elif any(word[:1].isupper() for word in s.split()[:4]):
            candidates.append(s)
    chosen = candidates[:max_cards]

    cards = []
    for s in chosen:
        if ":" in s:
            left, right = s.split(":", 1)
            front = f"What is {left.strip()}?"
            back = right.strip()
        elif " is " in s.lower():
            left = s.split(" is ", 1)[0]
            front = f"What is {left.strip()}?"
            back = s
        elif " are " in s.lower():
            left = s.split(" are ", 1)[0]
            front = f"What are {left.strip()}?"
            back = s
        else:
            front = "Explain: " + s[:80]
            back = s
        cards.append({"front": front, "back": back})
    return cards

# --------------------------------------
# Article persistence
# --------------------------------------
def save_article_to_db(article):
    url = article.get("url") or ""
    title = article.get("title") or ""
    source = article.get("source") or ""
    published = article.get("published") or ""
    summary = article.get("excerpt") or article.get("summary") or ""
    content_hash = short_hash((title or "") + (url or "") + (summary or ""))
    fetched_at = datetime.datetime.utcnow().isoformat()

    if is_postgres_enabled():
        try:
            db_query(
                """
                INSERT INTO articles (title, source, url, published, summary, content_hash, fetched_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (url) DO NOTHING
                """,
                (title, source, url, published, summary, content_hash),
                commit=True
            )
            return True
        except Exception as e:
            st.warning(f"Failed to save article: {e}")
            return False
    else:
        try:
            db_query(
                """
                INSERT OR IGNORE INTO articles (title, source, url, published, summary, content_hash, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (title, source, url, published, summary, content_hash, fetched_at),
                commit=True
            )
            return True
        except Exception as e:
            st.warning(f"Failed to save article: {e}")
            return False

# --------------------------------------
# Example generator
# --------------------------------------
def generate_example_for_concept(concept):
    templates = {
        "Realism": {
            "definition": IR_THEORIES["Realism"]["definition"],
            "case": "The Cold War rivalry between the United States and the Soviet Union is a classic example of power competition and security rivalry.",
            "actors": "United States, Soviet Union, NATO members, Warsaw Pact states",
            "explanation": "Realism suggests states were driven by security and power competition in a system without a higher authority.",
            "b1_answer": "Realism says states care most about security and power. During the Cold War, the US and USSR competed for strength and influence.",
            "mongolian": "Реализм нь улс орнууд аюулгүй байдал, эрх мэдлийг хамгийн чухалчилдаг гэж үздэг. Хүйтэн дайн дээр АНУ, ЗХУ хүчээ харьцуулан өрсөлдсөн."
        },
        "Liberalism": {
            "definition": IR_THEORIES["Liberalism"]["definition"],
            "case": "The post-1945 creation of the United Nations and international institutions shows cooperation among states.",
            "actors": "United Nations, major states, international organizations",
            "explanation": "Liberalism argues institutions, diplomacy, and economic cooperation can reduce conflict.",
            "b1_answer": "Liberalism says cooperation and institutions can reduce war and help countries work together.",
            "mongolian": "Либерализм нь байгууллага, хамтын ажиллагаа, худалдаа нь мөргөлдөөнийг бууруулж чадна гэж үздэг."
        },
        "Constructivism": {
            "definition": IR_THEORIES["Constructivism"]["definition"],
            "case": "The global norm against colonialism after the Second World War changed how states justified power and legitimacy.",
            "actors": "Colonial powers, newly independent states, the United Nations",
            "explanation": "Constructivism emphasizes that ideas and norms changed what was considered legitimate or illegitimate.",
            "b1_answer": "Constructivism says ideas and norms shape the way states behave. After WWII, many states rejected colonialism.",
            "mongolian": "Конструктивизм нь санаа, үнэт зүйлс нь улс орнуудын үйлдлийг удирддаг гэж үздэг. Дэлхийн II дайны дараа колоничлолыг буруушаах үзэл улам өргөжсөн."
        },
        "Marxism": {
            "definition": IR_THEORIES["Marxism"]["definition"],
            "case": "Historical colonial economies extracted wealth from colonies to benefit imperial powers and capitalist classes.",
            "actors": "Imperial powers, colonies, multinational firms, local elites",
            "explanation": "Marxism argues that economic structures and class interests shape international domination and inequality.",
            "b1_answer": "Marxism focuses on capitalism and inequality between rich and poor countries.",
            "mongolian": "Марксизм нь капитализм, анги, тэгш бус байдалд анхаардаг. Энэ нь орнуудын хөгжлийн ялгааг тайлбарлахад хэрэглэгддэг."
        },
        "English School": {
            "definition": IR_THEORIES["English School"]["definition"],
            "case": "The Concert of Europe after Napoleon tried to maintain order through diplomacy and shared rules among states.",
            "actors": "European great powers, diplomats, courts and governments",
            "explanation": "The English School sees the international system as a society of states that share norms and institutions.",
            "b1_answer": "The English School says states are part of an international society with rules and diplomacy.",
            "mongolian": "Английн сургууль нь улс орнуудын хооронд дүрэм, дипломат ёс, олон улсын нийгэмлэг байдаг гэж үздэг."
        },
        "Security Dilemma": {
            "definition": "A security dilemma happens when a state arms or strengthens security, and other states interpret this as threatening, leading to escalation.",
            "case": "Two neighboring states each build up military forces because each fears the other, even if neither wants war.",
            "actors": "Neighboring states, military institutions, border regions",
            "explanation": "Defensive actions can lead to mutual suspicion and arms races.",
            "b1_answer": "A security dilemma is when trying to be safe makes other states feel more threatened.",
            "mongolian": "Аюулгүй байдлын дилемма гэдэг нь аюулгүй байдлаа бэхжүүлэх оролдлого бусдыг илүү айлгаж, хурцадмал байдал үүсгэдэг нөхцөлийг хэлнэ."
        },
        "Balance of Power": {
            "definition": "Balance of power is the idea that states form alliances or build strength to prevent one state from dominating the system.",
            "case": "European states formed alliances to counter Napoleonic France in the 19th century.",
            "actors": "European great powers, diplomats, alliances",
            "explanation": "Power is checked through alliances, diplomacy, and military balancing.",
            "b1_answer": "Balance of power means countries work together to stop one country from becoming too strong.",
            "mongolian": "Эрх мэдлийн тэнцвэр гэдэг нь нэг улс маш хүчтэй болохыг зогсоохын тулд бусад улсууд нэгдэж, тэнцвэржүүлдэг явдал юм."
        },
        "Soft Power": {
            "definition": "Soft power is influence exercised through culture, values, ideas, and attraction rather than force.",
            "case": "A country's film, language, education, or political values can attract others.",
            "actors": "States, universities, media, cultural institutions",
            "explanation": "Soft power works through persuasion and legitimacy rather than coercion.",
            "b1_answer": "Soft power is influence through culture and ideas, not military force.",
            "mongolian": "Зөөлөн хүч гэдэг нь цэрэг, албадлага биш харин соёл, үнэт зүйл, үзэл баримтлалээр нөлөөлөхийг хэлнэ."
        },
        "Third Neighbor Policy": {
            "definition": "Mongolia's Third Neighbor Policy seeks to develop relations with countries other than its two immediate neighbors, Russia and China.",
            "case": "Mongolia builds cooperation with Japan, the United States, the European Union, and other partners to widen diplomatic and economic options.",
            "actors": "Mongolia, Russia, China, Japan, United States, EU states",
            "explanation": "The policy aims to diversify ties and reduce overdependence on any single neighbor.",
            "b1_answer": "Third Neighbor Policy is when Mongolia works with countries besides Russia and China to broaden its options.",
            "mongolian": "Гуравдагч хөршийн бодлого гэдэг нь Монгол Улс Орос, Хятадаас гадна бусад улстай харилцаа хөгжүүлэхийг хэлнэ."
        }
    }
    return templates.get(concept)

# --------------------------------------
# Styling
# --------------------------------------
st.markdown("""
<style>
:root {
  --bg: #061522;
  --panel: #0f1f32;
  --card: #102845;
  --muted: #b9c9dc;
  --accent: #5aa7ff;
  --text: #edf5ff;
  --success: #5cc38e;
  --warning: #f0b34a;
  --danger: #ff7a7a;
}
.reportview-container, .main {
  background: #061522;
  color: var(--text);
}
.stSidebar {
  background: #081a2c;
}
.css-1d391kg, .block-container {
  padding-top: 1rem;
}
div[data-testid="stExpander"] {
  background: #0c1d2f;
  border-radius: 10px;
}
.card {
  background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
  border: 1px solid rgba(255,255,255,0.07);
  padding: 16px;
  border-radius: 12px;
  margin-bottom: 12px;
}
.muted {
  color: var(--muted);
  font-size: 0.9rem;
}
.accent {
  color: var(--accent);
  font-weight: 600;
}
.headline {
  font-size: 1.05rem;
  font-weight: 700;
  color: #edf5ff;
}
</style>
""", unsafe_allow_html=True)

# --------------------------------------
# UI helpers
# --------------------------------------
def sidebar_navigation():
    menu = st.sidebar.radio("Navigation", [
        "Dashboard",
        "News Feed",
        "News Analysis",
        "Lecture Notes",
        "Example Generator",
        "Flashcard Maker",
        "Study Mode",
        "IR Theory Guide",
        "Settings"
    ])
    st.sidebar.markdown("---")
    st.sidebar.markdown("Quick actions")
    if st.sidebar.button("Add lecture note"):
        st.session_state.page = "Lecture Notes"
        st.rerun()
    if st.sidebar.button("Create flashcards"):
        st.session_state.page = "Flashcard Maker"
        st.rerun()
    if st.sidebar.button("Study mode"):
        st.session_state.page = "Study Mode"
        st.rerun()
    st.sidebar.markdown("---")
    note_count = db_query("SELECT COUNT(*) FROM notes").fetchone()[0] if db_query("SELECT COUNT(*) FROM notes") else 0
    card_count = db_query("SELECT COUNT(*) FROM flashcards").fetchone()[0] if db_query("SELECT COUNT(*) FROM flashcards") else 0
    article_count = db_query("SELECT COUNT(*) FROM articles").fetchone()[0] if db_query("SELECT COUNT(*) FROM articles") else 0
    st.sidebar.markdown(f"Notes: **{note_count}**")
    st.sidebar.markdown(f"Flashcards: **{card_count}**")
    st.sidebar.markdown(f"Saved articles: **{article_count}**")
    return menu

# --------------------------------------
# Pages
# --------------------------------------
def page_dashboard():
    st.header("Dashboard")
    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])

    with c1:
        st.markdown("### Latest international news")
        articles = fetch_latest_news(limit_per_feed=3, gdelt_per_topic=3)
        for article in articles[:6]:
            title = article.get("title") or "Untitled"
            source = article.get("source") or "Unknown source"
            published = article.get("published") or "Unknown date"
            excerpt = article.get("excerpt") or ""
            url = article.get("url") or "#"
            st.markdown(f"""
            <div class="card">
              <div class="headline">{title}</div>
              <div class="muted">{source} • {published}</div>
              <div class="muted" style="margin-top:8px;">{excerpt[:220]}...</div>
              <div style="margin-top:8px;"><a href="{url}" target="_blank">Open source</a></div>
            </div>
            """, unsafe_allow_html=True)

    with c2:
        st.markdown("### Quick stats")
        note_count = db_query("SELECT COUNT(*) FROM notes").fetchone()[0] if db_query("SELECT COUNT(*) FROM notes") else 0
        card_count = db_query("SELECT COUNT(*) FROM flashcards").fetchone()[0] if db_query("SELECT COUNT(*) FROM flashcards") else 0
        st.metric("Saved notes", note_count)
        st.metric("Saved flashcards", card_count)

        st.markdown("### Quick actions")
        if st.button("Add Lecture", use_container_width=True):
            st.session_state.page = "Lecture Notes"
            st.rerun()
        if st.button("Create Flashcards", use_container_width=True):
            st.session_state.page = "Flashcard Maker"
            st.rerun()
        if st.button("Study Mode", use_container_width=True):
            st.session_state.page = "Study Mode"
            st.rerun()

    with c3:
        st.markdown("### Recent lecture notes")
        rows = list_notes()
        if rows:
            for row in rows[:5]:
                nid, title, course, topic, tags, date, content, created = row
                st.markdown(f"- **{title}** — {course} / {topic}")
        else:
            st.info("No lecture notes yet.")

    with c4:
        st.markdown("### Daily IR concept")
        concept = random.choice(list(IR_THEORIES.keys()))
        info = IR_THEORIES[concept]
        st.markdown(f"**{concept}**")
        st.write(info["definition"])
        st.caption("Keywords: " + ", ".join(info["keywords"]))

def page_news_feed():
    st.header("News Feed")
    st.markdown("This page collects free international news using the GDELT API and public RSS feeds. Extractive summaries are clearly labeled and are not AI-generated.")
    categories = st.multiselect("Categories", list(GDELT_QUERIES.keys()), default=list(GDELT_QUERIES.keys()))
    search_text = st.text_input("Search headlines and sources", "")
    if st.button("Refresh"):
        st.rerun()

    with st.spinner("Fetching live news..."):
        articles = fetch_latest_news(limit_per_feed=3, gdelt_per_topic=3, categories=categories)

    if search_text:
        search_lower = search_text.lower()
        articles = [a for a in articles if search_lower in (a.get("title", "") + " " + a.get("source", "")).lower()]

    st.caption(f"{len(articles)} articles found")

    for article in articles:
        title = article.get("title") or "Untitled"
        source = article.get("source") or "Unknown source"
        published = article.get("published") or "Unknown date"
        category = article.get("category") or "General"
        url = article.get("url") or "#"
        excerpt = article.get("excerpt") or ""

        if not excerpt and url:
            excerpt = extractive_summary_from_url(url, max_sentences=2)

        st.markdown(f"""
        <div class="card">
          <div class="headline">{title}</div>
          <div class="muted">{source} • {published} • {category}</div>
          <div style="margin-top:10px;">
            <strong>Extractive summary (auto):</strong> {excerpt[:500] if excerpt else "No summary available."}
          </div>
          <div style="margin-top:10px;"><a href="{url}" target="_blank">Read original article</a></div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Save article", key=f"save_article_{short_hash(url)}"):
                saved = save_article_to_db(article)
                if saved:
                    st.success("Article saved.")
        with col2:
            if st.button("Save to notes", key=f"save_to_note_{short_hash(url)}"):
                st.session_state.prefill_note = {
                    "title": title,
                    "content": f"Source: {source}\nURL: {url}\nPublished: {published}\n\nExtractive summary (auto):\n{excerpt or 'No summary available.'}\n\nYour analysis:\n"
                }
                st.session_state.page = "Lecture Notes"
                st.rerun()

def page_news_analysis():
    st.header("News Analysis")
    st.markdown("Connect a saved news story to IR theory. Keep facts separate from opinion or interpretation.")

    rows = db_query("SELECT id, title, source, url, published, summary FROM articles ORDER BY fetched_at DESC")
    if rows is None:
        st.warning("No article database available.")
        return
    rows = rows.fetchall()

    if not rows:
        st.info("No saved articles yet. Save an article from the News Feed first.")
        return

    selection = st.selectbox("Select saved article", [f"{r[1]} — {r[2]}" for r in rows])
    actual = next(r for r in rows if f"{r[1]} — {r[2]}" == selection)

    article_id, title, source, url, published, summary = actual
    st.markdown(f"### {title}")
    st.markdown(f"**Source:** {source}")
    st.markdown(f"**Published:** {published}")
    st.markdown(f"**URL:** [Open original]({url})")
    st.markdown(f"**Extractive summary (auto):** {summary or 'No summary available.'}")

    st.markdown("---")
    with st.form("news_analysis_form"):
        facts = st.text_area("Facts from the article only", height=120)
        theories = st.multiselect("Relevant IR theories", list(IR_THEORIES.keys()))
        explanation = st.text_area("How the theory explains the event", height=120)
        opinion = st.text_area("Analysis/opinion (clearly labeled as opinion)", height=120)
        submitted = st.form_submit_button("Save as lecture note")

        if submitted:
            note_title = f"News Analysis: {title[:80]}"
            note_content = (
                f"Source: {source}\n"
                f"URL: {url}\n"
                f"Published: {published}\n\n"
                f"Facts only:\n{facts}\n\n"
                f"Relevant theories:\n{', '.join(theories)}\n\n"
                f"Theory explanation:\n{explanation}\n\n"
                f"Opinion / interpretation:\n{opinion}\n"
            )
            save_note(
                title=note_title,
                course="IR News Analysis",
                topic="Current Affairs",
                tags=["news", "analysis"],
                date=str(datetime.date.today()),
                content=note_content
            )
            st.success("Saved analysis as a lecture note.")

def page_lecture_notes():
    st.header("Lecture Notes")
    st.markdown("Add notes, upload TXT/PDF when practical, search, and manage saved lectures.")

    if "prefill_note" in st.session_state:
        prefill_title = st.session_state.prefill_note.get("title", "")
        prefill_content = st.session_state.prefill_note.get("content", "")
    else:
        prefill_title = ""
        prefill_content = ""

    with st.form("note_form"):
        title = st.text_input("Lecture title", value=prefill_title)
        course = st.text_input("Course", value="")
        topic = st.text_input("Topic", value="")
        tags = st.text_input("Tags (comma separated)", value="")
        note_date = st.date_input("Date", value=datetime.date.today())
        uploaded = st.file_uploader("Upload TXT or PDF (optional)", type=["txt", "pdf"])
        content = st.text_area("Lecture text", value=prefill_content, height=300)
        submitted = st.form_submit_button("Save note")

        if submitted:
            if uploaded is not None:
                try:
                    if uploaded.name.lower().endswith(".pdf"):
                        try:
                            import PyPDF2
                            pdf_reader = PyPDF2.PdfReader(uploaded)
                            extracted = []
                            for p in pdf_reader.pages:
                                text = p.extract_text() or ""
                                extracted.append(text)
                            content = content + "\\n\\n" + "\\n".join(extracted)
                        except Exception:
                            st.warning("PDF extraction failed, but the file was uploaded. Text may be unavailable.")
                    else:
                        uploaded_text = uploaded.read().decode("utf-8", errors="ignore")
                        content = content + "\\n\\n" + uploaded_text
                except Exception as e:
                    st.warning(f"Upload failed: {e}")

            if not title.strip():
                st.error("Please enter a lecture title.")
            else:
                save_note(
                    title=title.strip(),
                    course=course.strip(),
                    topic=topic.strip(),
                    tags=[t.strip() for t in tags.split(",") if t.strip()],
                    date=str(note_date),
                    content=content
                )
                st.success("Note saved.")
                if "prefill_note" in st.session_state:
                    del st.session_state.prefill_note

    st.markdown("---")
    st.subheader("Search and manage lecture notes")
    search = st.text_input("Search notes", "")
    course_filter = st.text_input("Course filter", "")
    topic_filter = st.text_input("Topic filter", "")

    rows = list_notes(search=search or None, course=course_filter or None, topic=topic_filter or None)
    st.caption(f"{len(rows)} notes found")

    for row in rows:
        note_id, title, course, topic, tags, date, content, created = row
        with st.expander(f"{title} — {course} / {topic} ({date})"):
            st.write(f"**Tags:** {tags}")
            st.write(content[:2000] + ("..." if len(content) > 2000 else ""))
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if st.button("Edit", key=f"edit_note_{note_id}"):
                    st.session_state.edit_note = {
                        "id": note_id,
                        "title": title,
                        "course": course,
                        "topic": topic,
                        "tags": tags,
                        "date": date,
                        "content": content,
                    }
                    st.rerun()
            with col2:
                if st.button("Delete", key=f"delete_note_{note_id}"):
                    delete_note(note_id)
                    st.success("Note deleted.")
                    st.rerun()
            with col3:
                if st.button("Flashcards from note", key=f"cards_from_{note_id}"):
                    cards = generate_flashcards_from_text(content, deck=f"{title} Deck", max_cards=20)
                    for card in cards:
                        save_flashcard(deck=f"{title} Deck", front=card["front"], back=card["back"], tags=[topic])
                    st.success(f"Generated {len(cards)} flashcards from this note.")
                    st.rerun()

    if "edit_note" in st.session_state:
        edit = st.session_state.edit_note
        st.markdown("---")
        st.subheader("Edit note")
        with st.form("edit_note_form"):
            edit_title = st.text_input("Edit title", value=edit["title"])
            edit_course = st.text_input("Edit course", value=edit["course"])
            edit_topic = st.text_input("Edit topic", value=edit["topic"])
            edit_tags = st.text_input("Edit tags", value=edit["tags"])
            edit_date = st.date_input("Edit date", value=datetime.date.fromisoformat(edit["date"]) if edit["date"] else datetime.date.today())
            edit_content = st.text_area("Edit lecture text", value=edit["content"], height=300)
            save_edit = st.form_submit_button("Save changes")

            if save_edit:
                update_note(
                    edit["id"],
                    edit_title.strip(),
                    edit_course.strip(),
                    edit_topic.strip(),
                    [t.strip() for t in edit_tags.split(",") if t.strip()],
                    str(edit_date),
                    edit_content
                )
                st.success("Note updated.")
                del st.session_state.edit_note
                st.rerun()

def page_example_generator():
    st.header("Example Generator")
    st.markdown("Generate clear examples using IR theories. Historical cases are used when they are well established; hypothetical examples are clearly labeled.")

    concept = st.selectbox("Select a concept", [
        "Realism",
        "Liberalism",
        "Constructivism",
        "Marxism",
        "English School",
        "Security Dilemma",
        "Balance of Power",
        "Soft Power",
        "Third Neighbor Policy"
    ])

    if st.button("Generate example"):
        template = generate_example_for_concept(concept)
        if not template:
            st.warning("No template found for that concept.")
            return

        st.markdown("### Structured example")
        st.markdown(f"**a. Concept definition:** {template['definition']}")
        st.markdown(f"**b. Real-world case:** {template['case']}")
        st.markdown(f"**c. Countries or actors involved:** {template['actors']}")
        st.markdown(f"**d. Explanation of how the concept applies:** {template['explanation']}")
        st.markdown(f"**e. Short B1-level English answer for class:** {template['b1_answer']}")
        st.markdown(f"**f. Mongolian explanation:** {template['mongolian']}")

def page_flashcard_maker():
    st.header("Flashcard Maker")
    st.markdown("Create cards manually or generate them from a lecture note using a transparent rule-based method. This is not AI-generated unless you later configure a paid API.")

    notes = list_notes()
    note_titles = ["Select a note"] + [f"{row[1]} ({row[2]})" for row in notes]
    selected_note = st.selectbox("Generate cards from a note", note_titles)

    if st.button("Generate cards from selected note"):
        if selected_note == "Select a note":
            st.warning("Please select a note first.")
        else:
            note_index = note_titles.index(selected_note) - 1
            note = notes[note_index]
            content = note[6]
            cards = generate_flashcards_from_text(content, deck=f"{note[1]} Deck", max_cards=20)
            if not cards:
                st.warning("No cards could be generated from this note.")
            else:
                st.success(f"Generated {len(cards)} cards. Edit and save as needed.")
                for i, card in enumerate(cards):
                    with st.expander(f"Card {i + 1}"):
                        front = st.text_input("Front", value=card["front"], key=f"auto_front_{note[0]}_{i}")
                        back = st.text_area("Back", value=card["back"], key=f"auto_back_{note[0]}_{i}")
                        if st.button("Save this card", key=f"save_auto_card_{note[0]}_{i}"):
                            save_flashcard(deck=f"{note[1]} Deck", front=front, back=back, tags=[note[3]])
                            st.success("Card saved.")

    st.markdown("---")
    st.subheader("Manual card creation")
    with st.form("manual_card_form"):
        deck = st.text_input("Deck name", "Manual Deck")
        front = st.text_area("Front / question")
        back = st.text_area("Back / answer")
        tags = st.text_input("Tags (comma separated)", "")
        submitted = st.form_submit_button("Save manual card")

        if submitted:
            if not front.strip() or not back.strip():
                st.error("Both front and back are required.")
            else:
                save_flashcard(deck=deck.strip() or "Manual Deck", front=front.strip(), back=back.strip(), tags=[t.strip() for t in tags.split(",") if t.strip()])
                st.success("Manual card saved.")

    st.markdown("---")
    st.subheader("Existing flashcards")
    all_cards = list_flashcards()
    if not all_cards:
        st.info("No flashcards saved yet.")
    else:
        decks = {}
        for card in all_cards:
            decks.setdefault(card[1], []).append(card)

        for deck_name, cards in decks.items():
            st.markdown(f"### {deck_name}")
            for card in cards:
                card_id, deck_name, front, back, tags, difficulty = card
                st.markdown(f"- **Q:** {front}")
                st.markdown(f"  **A:** {back}")
                st.caption(f"Difficulty: {difficulty} | Tags: {tags}")
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("Mark known", key=f"mark_known_{card_id}"):
                        update_flashcard_difficulty(card_id, -1)
                        st.rerun()
                with col2:
                    if st.button("Mark difficult", key=f"mark_difficult_{card_id}"):
                        update_flashcard_difficulty(card_id, 1)
                        st.rerun()

def page_study_mode():
    st.header("Study Mode")
    st.markdown("Practice one card at a time. Use reveal answer, mark difficult, and move through a deck.")

    all_cards = list_flashcards()
    if not all_cards:
        st.info("No flashcards available. Create some first in the Flashcard Maker page.")
        return

    # Filter by deck
    decks = ["All"] + sorted({card[1] for card in all_cards})
    deck_choice = st.selectbox("Choose deck", decks)
    tag_filter = st.text_input("Filter by tag", "")

    if "study_cards" not in st.session_state or st.session_state.get("study_deck") != deck_choice or st.session_state.get("study_tag") != tag_filter:
        cards = all_cards
        if deck_choice != "All":
            cards = [c for c in cards if c[1] == deck_choice]
        if tag_filter:
            cards = [c for c in cards if tag_filter.lower() in (c[4] or "").lower()]
        st.session_state.study_cards = [
            {"id": c[0], "front": c[2], "back": c[3], "difficulty": c[5]}
            for c in cards
        ]
        st.session_state.study_index = 0
        st.session_state.study_deck = deck_choice
        st.session_state.study_tag = tag_filter

    cards = st.session_state.study_cards
    idx = st.session_state.study_index

    if idx >= len(cards):
        st.success("Study session complete.")
        if st.button("Restart"):
            st.session_state.study_index = 0
            st.rerun()
        return

    card = cards[idx]
    st.markdown(f"### Card {idx + 1} of {len(cards)}")
    st.markdown(f"**Question:** {card['front']}")
    if st.button("Reveal answer"):
        st.markdown(f"**Answer:** {card['back']}")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("Mark known"):
            update_flashcard_difficulty(card["id"], -1)
            st.session_state.study_index += 1
            st.rerun()
    with col2:
        if st.button("Mark difficult"):
            update_flashcard_difficulty(card["id"], 1)
            st.session_state.study_index += 1
            st.rerun()
    with col3:
        if st.button("Next"):
            st.session_state.study_index += 1
            st.rerun()

    difficult_cards = [c for c in list_flashcards() if c[5] > 0]
    if difficult_cards:
        st.markdown("### Revision list")
        for card in difficult_cards[:5]:
            st.markdown(f"- {card[2]}")

def page_ir_theory_guide():
    st.header("IR Theory Study Guide")
    st.markdown("Quick beginner-friendly explanations of major International Relations theories.")

    for name, info in IR_THEORIES.items():
        st.markdown(f"### {name}")
        st.write(info["definition"])
        st.caption("Keywords: " + ", ".join(info["keywords"]))

    st.markdown("---")
    st.subheader("Academic vocabulary with Mongolian explanation")
    for term, eng_def, mon_def in VOCAB:
        st.markdown(f"- **{term}** — {eng_def}. **Mongolian:** {mon_def}")

def page_settings():
    st.header("Settings")
    st.markdown("This application uses free public data and local SQLite by default. If a Supabase/Postgres database URL is configured in Streamlit secrets, it will use it automatically.")
    st.code("DATABASE_URL is optional. If missing, app runs with local SQLite only.")
    st.markdown("Local database path: " + DB_PATH)
    if st.button("Reset app state"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --------------------------------------
# Main router
# --------------------------------------
if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

page = sidebar_navigation()

if page == "Dashboard":
    page_dashboard()
elif page == "News Feed":
    page_news_feed()
elif page == "News Analysis":
    page_news_analysis()
elif page == "Lecture Notes":
    page_lecture_notes()
elif page == "Example Generator":
    page_example_generator()
elif page == "Flashcard Maker":
    page_flashcard_maker()
elif page == "Study Mode":
    page_study_mode()
elif page == "IR Theory Guide":
    page_ir_theory_guide()
elif page == "Settings":
    page_settings()
else:
    st.info("Select a page from the sidebar.")
