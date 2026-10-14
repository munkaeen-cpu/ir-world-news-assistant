import re
import html
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests
import streamlit as st

st.set_page_config(
    page_title="IR World News Assistant",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- Visual style ----
st.markdown("""
<style>
:root { --navy: #102744; --blue: #1769aa; --pale: #f3f7fc; }
.stApp { background: #f4f7fb; }
.block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1440px; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #102744 0%, #173b60 100%); }
[data-testid="stSidebar"] * { color: #f4f8ff !important; }
.hero {
  background: linear-gradient(110deg, rgba(12,34,62,.98), rgba(23,88,139,.90)),
              radial-gradient(circle at 80% 30%, #3e8ac0, transparent 45%);
  color: white; padding: 2rem 2.2rem; border-radius: 20px; margin-bottom: 1.25rem;
  box-shadow: 0 12px 30px rgba(16,39,68,.13);
}
.hero h1 { color: white; font-size: 2.25rem; margin: 0 0 .45rem 0; }
.hero p { color: #e0edfb; font-size: 1.05rem; margin: 0; }
.stat {
  background: white; border: 1px solid #e1eaf4; padding: 1rem 1.15rem;
  border-radius: 15px; min-height: 95px; box-shadow: 0 3px 12px rgba(21,49,78,.04);
}
.stat-label { color: #60758d; font-size: .88rem; }
.stat-value { color: #102744; font-size: 1.45rem; font-weight: 750; margin-top: .25rem; }
.news-card {
  background: white; border: 1px solid #e1eaf4; border-radius: 16px;
  padding: 1.1rem 1.25rem; margin: .7rem 0; box-shadow: 0 4px 14px rgba(21,49,78,.045);
}
.news-title { font-size: 1.08rem; font-weight: 700; line-height: 1.45; margin-bottom: .5rem; color: #132d4b; }
.news-meta { color: #627991; font-size: .83rem; margin-bottom: .65rem; }
.news-summary { color: #31465d; line-height: 1.6; }
.topic-tag {
 display: inline-block; background: #eaf3ff; color: #145a96; padding: .22rem .6rem;
 border-radius: 999px; font-size: .75rem; font-weight: 650; margin-bottom: .5rem;
}
.side-card { background: white; border: 1px solid #e1eaf4; border-radius: 15px; padding: 1rem; margin-bottom: .8rem; }
a { color: #1769aa !important; font-weight: 650; text-decoration: none; }
a:hover { text-decoration: underline; }
h2, h3 { color: #142f4e; }
div.stButton > button {
  border-radius: 10px; border: 0; font-weight: 650; min-height: 2.7rem;
}
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
    "United Nations": ["united nations", "security council", "un chief", "un secretary"],
    "China–US relations": ["china", "chinese", "united states", "beijing", "washington", "trade war"],
    "Mongolia foreign policy": ["mongolia", "mongolian", "ulaanbaatar"],
    "Economy & trade": ["economy", "trade", "tariff", "sanctions", "market", "export"],
    "Climate & environment": ["climate", "environment", "emissions", "renewable", "warming"],
}

THEORY_NOTES = {
    "Realism": "Focus on power, national interests, military strength, security, and competition between states.",
    "Liberalism": "Focus on cooperation, international organizations, trade, diplomacy, and shared rules.",
    "Constructivism": "Focus on identity, norms, ideas, historical memory, and how leaders understand events.",
}

@st.cache_data(ttl=600, show_spinner=False)
def load_feed(source_url):
    response = requests.get(
        source_url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; IRWorldNewsAssistant/1.0)"},
        timeout=15,
    )
    response.raise_for_status()
    return feedparser.parse(response.content).entries

def clean_summary(raw):
    raw = re.sub(r"<[^>]+>", " ", raw or "")
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()

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

def get_articles():
    articles, errors = [], []
    for source, url in SOURCES.items():
        try:
            for entry in load_feed(url):
                title = clean_summary(entry.get("title", "Untitled"))
                summary = clean_summary(entry.get("summary", entry.get("description", "")))
                link = entry.get("link", "")
                date_label, timestamp = parse_date(entry)
                articles.append({
                    "source": source, "title": title, "summary": summary,
                    "url": link, "date": date_label, "timestamp": timestamp,
                })
        except Exception:
            errors.append(source)
    # Remove duplicate headlines and show newest first when dates are available.
    unique, seen = [], set()
    for article in sorted(articles, key=lambda a: a["timestamp"], reverse=True):
        key = article["title"].casefold()
        if key and key not in seen:
            unique.append(article)
            seen.add(key)
    return unique, errors

# ---- Sidebar ----
with st.sidebar:
    st.markdown("## 🌍 IR World News")
    st.caption("Your international relations briefing")
    page = st.radio(
        "NAVIGATION",
        ["🏠 Home", "📰 Latest News", "🌏 Mongolia Focus", "📚 IR Theory Lab", "ℹ️ About"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown("**QUICK LINKS**")
    st.markdown("[BBC World News ↗](https://www.bbc.com/news/world)")
    st.markdown("[CNN World ↗](https://edition.cnn.com/world)")
    st.markdown("[United Nations ↗](https://news.un.org/)")
    st.markdown("---")
    st.caption("Built for International Relations students.")

# ---- Header ----
st.markdown("""
<div class="hero">
  <h1>Stay informed. Think globally. 🌐</h1>
  <p>International headlines, global perspectives, and ideas for your IR studies.</p>
</div>
""", unsafe_allow_html=True)

if "articles" not in st.session_state:
    st.session_state.articles = []
if "feed_errors" not in st.session_state:
    st.session_state.feed_errors = []

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.markdown('<div class="stat"><div class="stat-label">🗞️ News sources</div><div class="stat-value">BBC · CNN</div></div>', unsafe_allow_html=True)
with col_b:
    st.markdown('<div class="stat"><div class="stat-label">🌍 Focus</div><div class="stat-value">Global affairs</div></div>', unsafe_allow_html=True)
with col_c:
    st.markdown('<div class="stat"><div class="stat-label">🎓 Designed for</div><div class="stat-value">IR students</div></div>', unsafe_allow_html=True)

st.write("")
left, right = st.columns([4, 1])
with left:
    st.markdown("### 📰 International news desk")
    st.caption("Headlines are fetched from the publishers' RSS feeds. Open the original article for full context.")
with right:
    if st.button("🔄 Refresh news", type="primary", use_container_width=True):
        load_feed.clear()
        st.session_state.articles, st.session_state.feed_errors = get_articles()

if not st.session_state.articles and not st.session_state.feed_errors:
    with st.spinner("Connecting to BBC and CNN feeds..."):
        st.session_state.articles, st.session_state.feed_errors = get_articles()

if st.session_state.feed_errors:
    st.warning("Some feeds could not be reached: " + ", ".join(st.session_state.feed_errors) +
               ". The publisher may be temporarily unavailable.")

if page == "📚 IR Theory Lab":
    st.markdown("### 📚 IR Theory Lab")
    st.write("Use these lenses to build a short analysis of a news story.")
    for theory, description in THEORY_NOTES.items():
        with st.expander(theory, expanded=(theory == "Realism")):
            st.write(description)
    st.markdown("**Quick analysis template**")
    st.code("1. What happened?\n2. Which actors are involved?\n3. What are their interests?\n4. Which IR theory best explains the event?\n5. What evidence supports your explanation?")
elif page == "ℹ️ About":
    st.markdown("### About IR World News Assistant")
    st.write("A learning dashboard for International Relations students. It gathers headlines from available BBC and CNN RSS feeds and links to the original publisher pages.")
    st.info("Headlines, dates, and feed availability depend on the publishers. This app does not replace reading the full original article.")
elif page == "🌏 Mongolia Focus":
    chosen_topic = "Mongolia foreign policy"
    query = st.text_input("Search Mongolia-related news", placeholder="e.g. foreign policy, China, Russia, Japan")
    candidates = [a for a in st.session_state.articles if any(k in (a["title"] + " " + a["summary"]).lower() for k in TOPICS[chosen_topic])]
    if query.strip():
        candidates = [a for a in candidates if query.casefold() in (a["title"] + " " + a["summary"]).casefold()]
    st.caption(f"{len(candidates)} matching articles")
    if not candidates:
        st.info("No Mongolia-related headlines were found in the currently loaded feeds. Try refreshing or search the publisher websites.")
    for a in candidates:
        st.markdown(f'<div class="news-card"><div class="topic-tag">MONGOLIA FOCUS</div><div class="news-title">{html.escape(a["title"])}</div><div class="news-meta">{html.escape(a["source"])} · {html.escape(a["date"])}</div><div class="news-summary">{html.escape(a["summary"][:500])}</div><br><a href="{html.escape(a["url"], quote=True)}" target="_blank">Read original article ↗</a></div>', unsafe_allow_html=True)
else:
    filter1, filter2, filter3 = st.columns([2, 2, 2])
    with filter1:
        search = st.text_input("🔎 Search headlines", placeholder="Search a country, event, keyword…")
    with filter2:
        topic = st.selectbox("Topic", list(TOPICS.keys()))
    with filter3:
        source_filter = st.selectbox("Source", ["All sources", *SOURCES.keys()])

    visible = st.session_state.articles
    if page == "📰 Latest News":
        st.caption("Latest headlines from available feeds")
    selected_keywords = TOPICS[topic]
    if selected_keywords:
        visible = [a for a in visible if any(k in (a["title"] + " " + a["summary"]).lower() for k in selected_keywords)]
    if source_filter != "All sources":
        visible = [a for a in visible if a["source"] == source_filter]
    if search.strip():
        term = search.casefold()
        visible = [a for a in visible if term in (a["title"] + " " + a["summary"]).casefold()]

    st.caption(f"Showing {min(len(visible), 20)} of {len(visible)} matching headlines")
    if not visible:
        st.info("No matching headlines found. Try another topic or search term.")
    for a in visible[:20]:
        safe_title = html.escape(a["title"])
        safe_summary = html.escape(a["summary"][:600])
        safe_source = html.escape(a["source"])
        safe_date = html.escape(a["date"])
        safe_url = html.escape(a["url"], quote=True)
        st.markdown(
            f'<div class="news-card"><div class="topic-tag">{safe_source.upper()}</div>'
            f'<div class="news-title">{safe_title}</div>'
            f'<div class="news-meta">🗓️ {safe_date} &nbsp; · &nbsp; 📰 {safe_source}</div>'
            f'<div class="news-summary">{safe_summary or "No summary supplied by the feed."}</div>'
            f'<br><a href="{safe_url}" target="_blank" rel="noopener noreferrer">Read original article ↗</a></div>',
            unsafe_allow_html=True,
        )

st.markdown("---")
with st.expander("🎓 Study tip: connect the news to IR theory"):
    theory = st.selectbox("Choose a theory", list(THEORY_NOTES.keys()), key="study_theory")
    st.write(THEORY_NOTES[theory])
    st.caption("Ask: Who has power? What interests are at stake? Which institutions, identities, or norms matter?")
st.caption("IR World News Assistant · Educational use · Always verify context in the original article.")
