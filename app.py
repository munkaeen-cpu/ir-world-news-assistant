
import streamlit as st
import requests
import time
from datetime import datetime, timedelta, timezone

st.set_page_config(
    page_title="IR World News",
    page_icon="🌍",
    layout="wide"
)

st.title("🌍 IR World News Assistant")
st.write("International news for International Relations students")

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


@st.cache_data(ttl=600)
def get_news(query):
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=7)

    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": 10,
        "sort": "DateDesc",
        "startdatetime": start.strftime("%Y%m%d%H%M%S"),
        "enddatetime": now.strftime("%Y%m%d%H%M%S")
    }

    url = "https://api.gdeltproject.org/api/v2/doc/doc"

    for attempt in range(2):
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": "IRWorldNewsAssistant/1.0"},
            timeout=30
        )

        if response.status_code == 429 and attempt == 0:
            time.sleep(5)
            continue

        response.raise_for_status()
        return response.json().get("articles", [])

    return []


if st.button("🔎 Get Latest News"):
    with st.spinner("Searching for international news..."):
        try:
            articles = get_news(queries[category])

            if not articles:
                st.info(
                    "No articles found right now. "
                    "Please try again later or choose another topic."
                )
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

        except requests.exceptions.HTTPError as error:
            if error.response is not None and error.response.status_code == 429:
                st.warning(
                    "The news service is temporarily limiting requests. "
                    "Please wait a few minutes and try again."
                )
            else:
                st.error("The news service returned an error.")
                st.caption(str(error))

        except requests.exceptions.RequestException:
            st.error(
                "Could not connect to the news service. "
                "Please try again later."
            )

        except Exception as error:
            st.error("Something went wrong.")
            st.caption(str(error))

st.info(
    "Study tip: Connect each news story to Realism, "
    "Liberalism, or Constructivism in your class notes."
)
