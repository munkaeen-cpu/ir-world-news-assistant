import re
import html
from datetime import timezone
from email.utils import parsedate_to_datetime
from collections import Counter

import feedparser
import requests
import streamlit as st

st.set_page_config(
    page_title="IR World News Assistant",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- Styling ----
st.markdown("""
<style>
.stApp { background: #f4f7fb; }
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1440px; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #102744 0%, #173b60 100%); }
[data-testid="stSidebar"] * { color: #f4f8ff !important; }
.hero {
  background: linear-gradient(110deg, #102744 0%, #14568a 100%);
  color: white; padding: 1.8rem 2rem; border-radius: 18px; margin-bottom: 1.2rem;
  box-shadow: 0 10px 28px rgba(16,39,68,.12);
}
.hero h1 { color: white; font-size: 2.15rem; margin: 0 0 .4rem 0; }
.hero p { color: #e0edfb; font-size: 1rem; margin: 0; }
.stat { background: white; border: 1px solid #e1eaf4; padding: 1rem; border-radius: 14px; min-height: 85px; }
.stat-label { color: #60758d; font-size: .85rem; }
.stat-value { color: #102744; font-size: 1.3rem; font-weight: 750; margin-top: .2rem; }
.news-card { background: white; border: 1px solid #e1eaf4; border-radius: 15px; padding: 1rem 1.2rem; margin: .7rem 0; }
.news-title { font-size: 1.05rem; font-weight: 700; line-height: 1.45; color: #132d4b; margin-bottom: .45rem; }
.news-meta { color: #627991; font-size: .82rem; margin-bottom: .6rem; }
.news-summary { color: #31465d; line-height: 1.6; }
.tag { display: inline-block; background: #eaf3ff; color: #145a96; padding: .2rem .55rem; border-radius: 999px; font-size: .75rem; font-weight: 650; margin-bottom: .45rem; }
.study-card { background: white; border: 1px solid #e1eaf4; padding: 1rem 1.15rem; border-radius: 14px; margin: .5rem 0; }
div.stButton > button { border-radius: 10px; font-weight: 650; min-height: 2.55rem; }
</style>
""", unsafe_allow_html=True)

SOURCES = {
    "BBC News": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "CNN": "https://rss.cnn.com/rss/edition_world.rss",
}
TOPICS = {
    "All international news": [],
    "War & conflict": ["war", "conflict", "military", "peace", "attack", "ceasefire", "missile"],
    "Diplomacy": ["diplomacy", "diplomatic", "foreign policy", "summit", "ambassador", "talks"],
    "United Nations": ["united nations", "security council", "un secretary", "un chief"],
    "China–US relations": ["china", "chinese", "united states", "beijing", "washington", "trade war"],
    "Mongolia foreign policy": ["mongolia", "mongolian", "ulaanbaatar"],
    "Economy & trade": ["economy", "trade", "tariff", "sanctions", "market", "export"],
    "Climate & environment": ["climate", "environment", "emissions", "renewable", "warming"],
}
THEORY_NOTES = {
    "Realism": "Focus on state power, national interests, military capability, security, and competition.",
    "Liberalism": "Focus on cooperation, international organizations, trade, diplomacy, and shared rules.",
    "Constructivism": "Focus on identity, norms, ideas, historical memory, and how actors understand events.",
}
STOPWORDS = set("""
a an the and or but if then than to of in on at for from by with about into over after before
is are was were be been being it its this that these those as their they them we our you your
can could may might will would should have has had do does did not no so such very also more
most some many much other another each both all any who what when where why how which while
international relations news says said new latest according report reports amid during against
""".split())

def clean_text(raw):
    raw = re.sub(r"<[^>]+>", " ", raw or "")
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()

@st.cache_data(ttl=600, show_spinner=False)
def load_feed(source_url):
    response = requests.get(
        source_url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; IRWorldNewsAssistant/1.0)"},
        timeout=15,
    )
    response.raise_for_status()
    return feedparser.parse(response.content).entries

def parse_date(entry):
    raw = entry.get("published") or entry.get("updated") or ""
    if not raw:
        return "Date unavailable", 0
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%d %b %Y"), int(dt.timestamp())
    except (TypeError, ValueError, OverflowError):
        return raw, 0
