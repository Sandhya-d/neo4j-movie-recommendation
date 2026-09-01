from neo4j import GraphDatabase
NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "Sandhyaa"

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD),
)

def find_movie(title):
    with driver.session() as session:
        result = session.run(
            """
            MATCH (movie:MOVIE)
            WHERE toLower(movie.title) CONTAINS toLower($title)
            RETURN movie.itemId AS itemId, movie.title AS title
            LIMIT 1
            """,
            title=title,
        )

        movie = result.single()

        if not movie:
            return None, None

        return movie["itemId"], movie["title"]

def get_recommendations(movie_title, limit=5):
    movie_id, matched_title = find_movie(movie_title)

    if movie_id is None:
        return {
            "error": f"No movie found matching '{movie_title}'"
        }

    with driver.session() as session:
        result = session.run(
            """
            MATCH (source:MOVIE {itemId: $movieId})-[sourceTag:HAS_TAG]
                  ->(tag:TAG)<-[otherTag:HAS_TAG]-(movie:MOVIE)
            WHERE source <> movie

            WITH
                movie,
                sum(sourceTag.score * otherTag.score) AS similarity,
                collect(tag.name) AS sharedTags

            RETURN
                movie.title AS title,
                similarity,
                sharedTags[0..4] AS reasons

            ORDER BY similarity DESC
            LIMIT $limit
            """,
            movieId=movie_id,
            limit=limit,
        )

        recommendations = []

        for record in result:
            recommendations.append(
                {
                    "title": record["title"],
                    "score": round(record["similarity"], 4),
                    "because": record["reasons"],
                }
            )

    return {
        "source_movie": matched_title,
        "recommendations": recommendations,
    }

def main():
    result = get_recommendations("Toy Story")

    if "error" in result:
        print(result["error"])
        return

    print(f"\nRecommendations for {result['source_movie']}:\n")

    for movie in result["recommendations"]:
        print(f"{movie['title']} ({movie['score']})")

        if movie["because"]:
            print(f"Shared tags: {', '.join(movie['because'])}")

        print()

if __name__ == "__main__":
    try:
        main()
    finally:
        driver.close()