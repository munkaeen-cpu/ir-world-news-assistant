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
:root { --pink-900: #74284f; --pink-700: #ad3f79; --pink-500: #d95f9c; --ink: #43243a; }
.stApp { background: linear-gradient(180deg, #fff8fc 0%, #fff3f9 48%, #fdf7fc 100%); color: var(--ink); }
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1440px; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #74284f 0%, #a63f77 58%, #c6538c 100%); }
[data-testid="stSidebar"] * { color: #fff7fb !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.22); }
.hero {
  background: radial-gradient(circle at 88% 15%, rgba(255,255,255,.23), transparent 27%), linear-gradient(115deg, #74284f 0%, #ad3f79 53%, #d95f9c 100%);
  color: white; padding: 1.9rem 2rem; border-radius: 22px; margin-bottom: 1.2rem; box-shadow: 0 12px 30px rgba(173,63,121,.20);
}
.hero h1 { color: white; font-size: 2.15rem; margin: 0 0 .4rem 0; }
.hero p { color: #fff0f7; font-size: 1rem; margin: 0; }
.stat { background: rgba(255,255,255,.92); border: 1px solid #f2c8dd; padding: 1rem; border-radius: 16px; min-height: 85px; box-shadow: 0 4px 16px rgba(173,63,121,.06); }
.stat-label { color: #96627e; font-size: .85rem; }
.stat-value { color: #74284f; font-size: 1.3rem; font-weight: 750; margin-top: .2rem; }
.news-card { background: rgba(255,255,255,.95); border: 1px solid #f0c8dc; border-radius: 17px; padding: 1rem 1.2rem; margin: .7rem 0; box-shadow: 0 5px 18px rgba(116,40,79,.045); }
.news-title { font-size: 1.05rem; font-weight: 700; line-height: 1.45; color: #572342; margin-bottom: .45rem; }
.news-meta { color: #946d83; font-size: .82rem; margin-bottom: .6rem; }
.news-summary { color: #65465a; line-height: 1.65; }
.tag { display: inline-block; background: #fde4f0; color: #9e326b; padding: .2rem .6rem; border-radius: 999px; font-size: .75rem; font-weight: 700; margin-bottom: .45rem; }
.study-card { background: #fff; border: 1px solid #f0c8dc; padding: 1rem 1.15rem; border-radius: 15px; margin: .5rem 0; }
h1, h2, h3, h4 { color: #74284f; }
a { color: #ad3f79 !important; font-weight: 650; }
a:hover { color: #74284f !important; }
div.stButton > button, div[data-testid="stDownloadButton"] > button { background: linear-gradient(100deg, #ad3f79, #d95f9c); color: white; border: 0; border-radius: 11px; font-weight: 700; min-height: 2.55rem; box-shadow: 0 4px 12px rgba(173,63,121,.16); }
div.stButton > button:hover, div[data-testid="stDownloadButton"] > button:hover { background: #74284f; color: white; border: 0; }
div[data-baseweb="input"] > div, div[data-baseweb="select"] > div, div[data-baseweb="textarea"] > div { border-color: #efbfd6 !important; border-radius: 11px !important; }
div[data-testid="stExpander"] { background: rgba(255,255,255,.7); border: 1px solid #f0c8dc; border-radius: 14px; }
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
