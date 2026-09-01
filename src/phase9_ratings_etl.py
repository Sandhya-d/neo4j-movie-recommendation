import json
import random
from pathlib import Path

import pandas as pd


# Project folders
base_dir = Path.cwd()
raw_dir = base_dir / "data" / "movie_dataset_public_final" / "raw"
processed_dir = base_dir / "data" / "processed"

ratings_file = raw_dir / "ratings.json"
output_file = processed_dir / "ratings.csv"

# Using a smaller set of users so the Neo4j import is manageable
sample_size = 5000


def get_sample_users():
    print("Finding users from ratings.json...")

    user_ids = set()

    with open(ratings_file, "r", encoding="utf-8") as file:
        for i, line in enumerate(file):

            if not line.strip():
                continue

            rating = json.loads(line)
            user_ids.add(rating["user_id"])

            if (i + 1) % 5_000_000 == 0:
                print(
                    f"Scanned {i + 1:,} ratings "
                    f"and found {len(user_ids):,} users"
                )

    print(f"Total users found: {len(user_ids):,}")

    # Fixed seed so we get the same sample every time
    random.seed(42)

    sampled_users = random.sample(
        list(user_ids),
        min(sample_size, len(user_ids))
    )

    print(f"Selected {len(sampled_users):,} users")

    return set(sampled_users)


def create_ratings_csv(sampled_users):
    print("\nCollecting ratings for the selected users...")

    selected_ratings = []

    with open(ratings_file, "r", encoding="utf-8") as file:
        for i, line in enumerate(file):

            if not line.strip():
                continue

            rating = json.loads(line)

            # Keep every rating made by the sampled users
            if rating["user_id"] in sampled_users:
                selected_ratings.append(rating)

            if (i + 1) % 5_000_000 == 0:
                print(
                    f"Scanned {i + 1:,} ratings, "
                    f"kept {len(selected_ratings):,}"
                )

    ratings_df = pd.DataFrame(selected_ratings)

    # Rename the columns to match the naming used in Neo4j
    ratings_df = ratings_df.rename(
        columns={
            "user_id": "userId",
            "item_id": "itemId"
        }
    )

    ratings_df.to_csv(output_file, index=False)

    print(f"\nSaved {len(ratings_df):,} ratings to:")
    print(output_file)


if __name__ == "__main__":

    processed_dir.mkdir(parents=True, exist_ok=True)

    sampled_users = get_sample_users()

    create_ratings_csv(sampled_users)

    print("\nPhase 9 ETL completed.")
    print("ratings.csv is ready to be imported into Neo4j.")