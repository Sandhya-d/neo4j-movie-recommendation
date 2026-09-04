from neo4j import GraphDatabase


from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

driver = GraphDatabase.driver(
    uri,
    auth=(username, password)
)


# Weights used for the final recommendation score
tag_weight = 0.4
embedding_weight = 0.3
collab_weight = 0.3


def get_movie(movie_name):
    """Find a movie using part of its title."""

    with driver.session() as session:
        result = session.run(
            """
            MATCH (m:MOVIE)
            WHERE toLower(m.title) CONTAINS toLower($movie_name)
            RETURN m.itemId AS itemId, m.title AS title
            LIMIT 1
            """,
            movie_name=movie_name
        )

        movie = result.single()

        if movie:
            return movie["itemId"], movie["title"]

        return None, None


def recommend_by_movie(movie_name, limit=10):
    movie_id, actual_title = get_movie(movie_name)

    if movie_id is None:
        return {
            "error": f"Movie '{movie_name}' was not found"
        }

    with driver.session() as session:
        result = session.run(
            """
            MATCH (movie:MOVIE {itemId: $movie_id})

            OPTIONAL MATCH
            (movie)-[r1:STRONG_TAG]->(tag:TAG)<-[r2:STRONG_TAG]-(candidate:MOVIE)

            WITH movie,
                 candidate,
                 sum(r1.score * r2.score) AS tag_score

            WHERE candidate IS NOT NULL

            OPTIONAL MATCH
            (movie)-[similar:SIMILAR_EMBEDDING]->(candidate)

            WITH candidate,
                 tag_score,
                 coalesce(similar.score, 0.0) AS embedding_score

            WITH candidate,
                 tag_score,
                 embedding_score,
                 (tag_score * $tag_weight) +
                 (embedding_score * $embedding_weight) AS final_score

            RETURN candidate.title AS title,
                   final_score,
                   tag_score,
                   embedding_score

            ORDER BY final_score DESC
            LIMIT $limit
            """,
            movie_id=movie_id,
            tag_weight=tag_weight,
            embedding_weight=embedding_weight,
            limit=limit
        )

        recommendations = [dict(record) for record in result]

    return {
        "source_movie": actual_title,
        "recommendations": recommendations
    }


def recommend_for_user(user_id, movie_name, limit=10):
    movie_id, actual_title = get_movie(movie_name)

    if movie_id is None:
        return {
            "error": f"Movie '{movie_name}' was not found"
        }

    with driver.session() as session:
        result = session.run(
            """
            MATCH (movie:MOVIE {itemId: $movie_id})
            MATCH (user:USER {userId: $user_id})

            OPTIONAL MATCH
            (movie)-[r1:STRONG_TAG]->(tag:TAG)<-[r2:STRONG_TAG]-(candidate:MOVIE)

            WITH user,
                 movie,
                 candidate,
                 sum(r1.score * r2.score) AS tag_score

            WHERE candidate IS NOT NULL
              AND NOT EXISTS {
                  (user)-[:RATED]->(candidate)
              }

            OPTIONAL MATCH
            (movie)-[similar:SIMILAR_EMBEDDING]->(candidate)

            WITH user,
                 candidate,
                 tag_score,
                 coalesce(similar.score, 0.0) AS embedding_score

            OPTIONAL MATCH
            (user)-[:SIMILAR_USER]->(similar_user:USER)-[rating:RATED]->(candidate)

            WHERE rating.rating >= 4.0

            WITH candidate,
                 tag_score,
                 embedding_score,
                 avg(rating.rating) AS collaborative_score

            WITH candidate,
                 tag_score,
                 embedding_score,
                 collaborative_score,
                 (tag_score * $tag_weight) +
                 (embedding_score * $embedding_weight) +
                 (coalesce(collaborative_score, 0.0) * $collab_weight / 5.0)
                 AS final_score

            RETURN candidate.title AS title,
                   final_score,
                   tag_score,
                   embedding_score,
                   collaborative_score

            ORDER BY final_score DESC
            LIMIT $limit
            """,
            movie_id=movie_id,
            user_id=user_id,
            tag_weight=tag_weight,
            embedding_weight=embedding_weight,
            collab_weight=collab_weight,
            limit=limit
        )

        recommendations = [dict(record) for record in result]

    return {
        "user_id": user_id,
        "source_movie": actual_title,
        "recommendations": recommendations
    }


if __name__ == "__main__":

    print("Movie-based hybrid recommendations\n")

    movie_result = recommend_by_movie("Toy Story")

    if "error" in movie_result:
        print(movie_result["error"])

    else:
        print("Movie:", movie_result["source_movie"])

        for recommendation in movie_result["recommendations"]:
            print(
                recommendation["title"],
                "- score:",
                round(recommendation["final_score"], 4)
            )


    print("\nUser-based hybrid recommendations\n")

    user_result = recommend_for_user(
        577039,
        "Toy Story"
    )

    if "error" in user_result:
        print(user_result["error"])

    else:
        print(
            "User:",
            user_result["user_id"],
            "| Movie:",
            user_result["source_movie"]
        )

        for recommendation in user_result["recommendations"]:
            print(
                recommendation["title"],
                "- score:",
                round(recommendation["final_score"], 4)
            )


    driver.close()