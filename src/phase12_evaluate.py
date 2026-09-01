"""
PHASE 12 — Evaluation (corrected with train/test split)
For each test user, holds out some of their liked movies as "test" data,
lets the recommender work only from the rest, then checks if it
rediscovers the held-out movies.
"""

from neo4j import GraphDatabase
import random

NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "Sandhyaa"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

K = 10
N_TEST_USERS = 200
RATING_THRESHOLD = 4.0
HOLDOUT_FRACTION = 0.3  # hide 30% of each user's liked movies as test set

random.seed(42)


def get_sample_users(n):
    with driver.session() as session:
        result = session.run(
            """
            MATCH (u:USER)-[r:RATED]->()
            WITH u, count(r) AS ratingCount
            WHERE ratingCount >= 10
            RETURN u.userId AS userId
            LIMIT $n
            """,
            n=n,
        )
        return [r["userId"] for r in result]


def get_liked_movies(user_id):
    with driver.session() as session:
        result = session.run(
            """
            MATCH (u:USER {userId: $userId})-[r:RATED]->(m:MOVIE)
            WHERE r.rating >= $threshold
            RETURN m.itemId AS itemId
            """,
            userId=user_id, threshold=RATING_THRESHOLD,
        )
        return set(r["itemId"] for r in result)


def get_collaborative_recommendations_excluding(user_id, k, exclude_ids):
    """Recommend based on similar users, but only exclude the TRAIN set (not held-out test items)."""
    with driver.session() as session:
        result = session.run(
            """
            MATCH (target:USER {userId: $userId})-[:SIMILAR_USER]->(similarUser:USER)
            MATCH (similarUser)-[r:RATED]->(m:MOVIE)
            WHERE r.rating >= 4.0 AND NOT m.itemId IN $excludeIds
            RETURN m.itemId AS itemId, avg(r.rating) AS avgRating
            ORDER BY avgRating DESC LIMIT $k
            """,
            userId=user_id, k=k, excludeIds=list(exclude_ids),
        )
        return [r["itemId"] for r in result]


def evaluate():
    test_users = get_sample_users(N_TEST_USERS)
    print(f"Evaluating recommender on {len(test_users)} users (with train/test split)...")

    precisions, recalls = [], []
    users_evaluated = 0

    for user_id in test_users:
        liked = get_liked_movies(user_id)
        if len(liked) < 5:  # need enough to split meaningfully
            continue

        liked_list = list(liked)
        random.shuffle(liked_list)
        n_holdout = max(1, int(len(liked_list) * HOLDOUT_FRACTION))
        test_set = set(liked_list[:n_holdout])       # hidden — what we check against
        train_set = set(liked_list[n_holdout:])      # visible — recommender can "see" these were liked

        # exclude only the train set from candidates — test set stays eligible to be recommended
        recommended = get_collaborative_recommendations_excluding(user_id, K, train_set)
        if not recommended:
            continue

        hits = len(set(recommended) & test_set)

        if users_evaluated < 5:
            print(f"  User {user_id}: test_set={len(test_set)}, recommended={len(recommended)}, hits={hits}")

        precision = hits / len(recommended)
        recall = hits / len(test_set)

        precisions.append(precision)
        recalls.append(recall)
        users_evaluated += 1

    avg_precision = sum(precisions) / len(precisions) if precisions else 0
    avg_recall = sum(recalls) / len(recalls) if recalls else 0

    print("\nEvaluation Results")
    print("------------------")
    print(f"Users evaluated : {users_evaluated}")
    print(f"Precision@{K}    : {avg_precision:.4f}")
    print(f"Recall@{K}       : {avg_recall:.4f}")


if __name__ == "__main__":
    evaluate()
    driver.close()