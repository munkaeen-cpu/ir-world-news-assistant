
import streamlit as st
import requests
from datetime import datetime, timedelta, timezone

st.set_page_config(
    page_title="IR World News",
    page_icon="🌍",
    layout="wide"
)

st.title("🌍 IR World News Assistant")
st.write(
    "International news for International Relations students"
)

category = st.selectbox(
    "Choose a topic",
    [
        "International Relations",
        "War and Conflict",
        "Diplomacy",
        "United Nations",
        "China and the United States",
        "Mongolia Foreign Policy"
    ]
)

queries = {
    "International Relations": "international relations diplomacy",
    "War and Conflict": "war conflict peace negotiations",
    "Diplomacy": "international diplomacy foreign policy",
    "United Nations": "United Nations international security",
    "China and the United States": "China United States relations",
    "Mongolia Foreign Policy": "Mongolia foreign policy diplomacy"
}

if st.button("🔎 Get Latest News"):
    with st.spinner("Searching for international news..."):
        try:
            now = datetime.now(timezone.utc)
            start = now - timedelta(days=7)

            params = {
                "query": queries[category],
                "mode": "ArtList",
                "format": "json",
                "maxrecords": 15,
                "sort": "DateDesc",
                "startdatetime": start.strftime("%Y%m%d%H%M%S"),
                "enddatetime": now.strftime("%Y%m%d%H%M%S")
            }

            response = requests.get(
                "https://api.gdeltproject.org/api/v2/doc/doc",
                params=params,
                timeout=25
            )
            response.raise_for_status()
            data = response.json()
            articles = data.get("articles", [])

            if not articles:
                st.info("No articles found. Try another topic.")
            else:
                for article in articles:
                    title = article.get("title", "Untitled")
                    url = article.get("url", "")
                    source = article.get("domain", "Unknown source")
                    date = article.get("seendate", "Date unavailable")

                    st.subheader(title)
                    st.caption(f"Source: {source} | Date: {date}")

                    if url:
                        st.markdown(f"[Read original article]({url})")

                    st.divider()

        except Exception as error:
            st.error(
                "Could not load news right now. "
                "Please try again later."
            )
            st.caption(f"Technical detail: {error}")

st.info(
    "Study tip: Connect each news story to Realism, "
    "Liberalism, or Constructivism in your class notes."
)
