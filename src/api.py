"""
PHASE 14 — FastAPI
Wraps recommend.py + hybrid_recommend.py logic into real HTTP endpoints.

To Run:
    pip install fastapi uvicorn
    uvicorn src.api:app --reload

"""

from fastapi import FastAPI, HTTPException
from neo4j import GraphDatabase

NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "Sandhyaa"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
app = FastAPI(title="Neo4j Movie Recommendation API")


def find_movie_id(title_substring):
    with driver.session() as session:
        result = session.run(
            """
            MATCH (m:MOVIE) WHERE toLower(m.title) CONTAINS toLower($title)
            RETURN m.itemId AS itemId, m.title AS title LIMIT 1
            """,
            title=title_substring,
        )
        record = result.single()
        return (record["itemId"], record["title"]) if record else (None, None)


@app.get("/")
def root():
    return {"message": "Neo4j Movie Recommendation API — see /docs for endpoints"}


@app.get("/movies/{movie_title}")
def get_movie(movie_title: str):
    item_id, title = find_movie_id(movie_title)
    if item_id is None:
        raise HTTPException(status_code=404, detail=f"No movie found matching '{movie_title}'")
    with driver.session() as session:
        result = session.run(
            "MATCH (m:MOVIE {itemId: $id}) RETURN m.title AS title, m.avgRating AS avgRating, m.directedBy AS directedBy",
            id=item_id,
        )
        record = result.single()
        return dict(record)


@app.get("/movies/{movie_title}/tags")
def get_movie_tags(movie_title: str, limit: int = 10):
    item_id, title = find_movie_id(movie_title)
    if item_id is None:
        raise HTTPException(status_code=404, detail=f"No movie found matching '{movie_title}'")
    with driver.session() as session:
        result = session.run(
            """
            MATCH (m:MOVIE {itemId: $id})-[r:HAS_TAG]->(t:TAG)
            RETURN t.name AS tag, r.score AS score ORDER BY r.score DESC LIMIT $limit
            """,
            id=item_id, limit=limit,
        )
        return {"movie": title, "tags": [dict(r) for r in result]}


@app.get("/movies/{movie_title}/similar")
def get_similar_movies(movie_title: str, limit: int = 10):
    """Content-based, explainable recommendation — uses filtered STRONG_TAG
    relationships (top 20 tags/movie) to avoid memory blowups on popular movies
    that would otherwise touch huge numbers of raw HAS_TAG relationships."""
    item_id, title = find_movie_id(movie_title)
    if item_id is None:
        raise HTTPException(status_code=404, detail=f"No movie found matching '{movie_title}'")
    with driver.session() as session:
        result = session.run(
            """
            MATCH (m1:MOVIE {itemId: $id})-[r1:STRONG_TAG]->(t:TAG)<-[r2:STRONG_TAG]-(m2:MOVIE)
            WHERE m1 <> m2
            WITH m2, t, (r1.score * r2.score) AS contribution
            ORDER BY contribution DESC
            WITH m2, sum(contribution) AS similarity, collect(t.name)[0..4] AS topReasons
            RETURN m2.title AS title, similarity, topReasons AS reasons
            ORDER BY similarity DESC LIMIT $limit
            """,
            id=item_id, limit=limit,
        )
        return {"source_movie": title, "recommendations": [dict(r) for r in result]}


@app.get("/movies/{movie_title}/similar-embedding")
def get_embedding_similar_movies(movie_title: str, limit: int = 10):
    """FastRP + kNN embedding-based recommendation (Phase 8)."""
    item_id, title = find_movie_id(movie_title)
    if item_id is None:
        raise HTTPException(status_code=404, detail=f"No movie found matching '{movie_title}'")
    with driver.session() as session:
        result = session.run(
            """
            MATCH (m:MOVIE {itemId: $id})-[r:SIMILAR_EMBEDDING]->(similar:MOVIE)
            RETURN similar.title AS title, r.score AS score
            ORDER BY r.score DESC LIMIT $limit
            """,
            id=item_id, limit=limit,
        )
        return {"source_movie": title, "recommendations": [dict(r) for r in result]}


@app.get("/users/{user_id}/recommendations")
def get_user_recommendations(user_id: int, limit: int = 10):
    """Collaborative filtering recommendation (Phase 10)."""
    with driver.session() as session:
        exists = session.run("MATCH (u:USER {userId: $id}) RETURN u LIMIT 1", id=user_id).single()
        if not exists:
            raise HTTPException(status_code=404, detail=f"No user found with id {user_id}")

        result = session.run(
            """
            MATCH (target:USER {userId: $id})-[:SIMILAR_USER]->(similarUser:USER)
            MATCH (similarUser)-[r:RATED]->(m:MOVIE)
            WHERE r.rating >= 4.0 AND NOT EXISTS { (target)-[:RATED]->(m) }
            RETURN m.title AS title, avg(r.rating) AS avgRating, count(similarUser) AS supportingUsers
            ORDER BY avgRating DESC, supportingUsers DESC LIMIT $limit
            """,
            id=user_id, limit=limit,
        )
        return {"user_id": user_id, "recommendations": [dict(r) for r in result]}


@app.on_event("shutdown")
def shutdown():
    driver.close()