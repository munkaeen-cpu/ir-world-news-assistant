
import streamlit as st
import feedparser
import requests
from datetime import datetime
from email.utils import parsedate_to_datetime

st.set_page_config(
    page_title="IR World News",
    page_icon="🌍",
    layout="wide"
)

st.title("🌍 IR World News Assistant")
st.write("International news for International Relations students")

SOURCES = {
    "BBC News": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "CNN": "https://rss.cnn.com/rss/edition_world.rss",
}

category = st.selectbox(
    "Choose a topic",
    [
        "All International News",
        "War and Conflict",
        "Diplomacy",
        "United Nations",
        "China and the United States",
        "Mongolia Foreign Policy"
    ]
)

keywords = {
    "All International News": [],
    "War and Conflict": [
        "war", "conflict", "military", "peace", "attack"
    ],
    "Diplomacy": [
        "diplomacy", "diplomatic", "foreign policy", "summit"
    ],
    "United Nations": [
        "united nations", "un", "security council"
    ],
    "China and the United States": [
        "china", "chinese", "united states", "beijing", "washington"
    ],
    "Mongolia Foreign Policy": [
        "mongolia", "mongolian", "ulaanbaatar"
    ],
}


@st.cache_data(ttl=600)
def load_feed(source_url):
    response = requests.get(
        source_url,
        headers={"User-Agent": "Mozilla/5.0 IRWorldNewsAssistant"},
        timeout=20
    )
    response.raise_for_status()
    return feedparser.parse(response.content).entries


if st.button("🔎 Get Latest News"):
    all_articles = []
    errors = []

    with st.spinner("Loading news from BBC and CNN..."):
        for source, url in SOURCES.items():
            try:
                entries = load_feed(url)

                for entry in entries:
                    title = entry.get("title", "Untitled")
                    summary = entry.get("summary", "")
                    text = f"{title} {summary}".lower()

                    selected_keywords = keywords[category]
                    if selected_keywords and not any(
                        word in text for word in selected_keywords
                    ):
                        continue

                    all_articles.append({
                        "source": source,
                        "title": title,
                        "url": entry.get("link", ""),
                        "summary": summary,
                        "date": entry.get("published", "Date unavailable")
                    })

            except Exception as error:
                errors.append(f"{source}: {error}")

    if all_articles:
        for article in all_articles[:20]:
            st.subheader(article["title"])
            st.caption(
                f'Source: {article["source"]} | '
                f'Date: {article["date"]}'
            )

            if article["summary"]:
                st.write(
                    article["summary"].replace("<p>", "").replace("</p>", "")
                )

            if article["url"]:
                st.markdown(f'[Read original article]({article["url"]})')

            st.divider()

    else:
        st.warning("No news could be loaded. The feeds may be unavailable.")
        for error in errors:
            st.caption(error)

st.info(
    "Study tip: Analyze each story using Realism, Liberalism, "
    "or Constructivism. Always read the original article for context."
)
