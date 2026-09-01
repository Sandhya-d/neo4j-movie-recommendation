"""
PHASE 15 — Streamlit Frontend
Minimal UI: search a movie, see explainable recommendations, hit the FastAPI backend.
"""

import streamlit as st
import requests

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="Movie Recommendation System", layout="wide")
st.title("🎬 Neo4j Movie Recommendation System")
st.caption("Graph-based recommendations using the MovieLens Tag Genome dataset")

movie_title = st.text_input("Search for a movie", value="Toy Story")

col1, col2 = st.columns(2)
with col1:
    method = st.radio(
        "Recommendation method",
        ["Content-based (tag similarity)", "Embedding-based (FastRP + kNN)"],
    )
with col2:
    limit = st.slider("Number of recommendations", 3, 20, 10)

if st.button("Get Recommendations") and movie_title:
    endpoint = "similar" if method.startswith("Content") else "similar-embedding"
    url = f"{API_BASE}/movies/{movie_title}/{endpoint}?limit={limit}"

    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 404:
            st.error(f"No movie found matching '{movie_title}'")
        elif response.status_code != 200:
            st.error(f"API error: {response.status_code} — {response.text}")
        else:
            data = response.json()
            st.subheader(f"Because you liked: {data['source_movie']}")

            for rec in data["recommendations"]:
                with st.container(border=True):
                    score_key = "similarity" if "similarity" in rec else "score"
                    st.markdown(f"**{rec['title']}**  —  score: `{rec[score_key]:.3f}`")
                    if "reasons" in rec:
                        st.caption("Because it shares: " + ", ".join(rec["reasons"]))
    except requests.exceptions.ConnectionError:
        st.error("Can't reach the API. Make sure uvicorn is running: `uvicorn src.api:app --reload`")

st.divider()
st.subheader("Personalized recommendations (collaborative filtering)")
user_id = st.number_input("User ID", value=577039, step=1)

if st.button("Get Personalized Recommendations"):
    url = f"{API_BASE}/users/{user_id}/recommendations?limit=10"
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 404:
            st.error(f"No user found with ID {user_id}")
        elif response.status_code != 200:
            st.error(f"API error: {response.status_code} — {response.text}")
        else:
            data = response.json()
            st.subheader(f"Recommended for User {data['user_id']}")
            for rec in data["recommendations"]:
                with st.container(border=True):
                    st.markdown(f"**{rec['title']}**  —  avg rating from similar users: `{rec['avgRating']:.2f}`")
                    st.caption(f"Based on {rec['supportingUsers']} similar user(s)")
    except requests.exceptions.ConnectionError:
        st.error("Can't reach the API. Make sure uvicorn is running: `uvicorn src.api:app --reload`")