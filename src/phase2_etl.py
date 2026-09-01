import json
from pathlib import Path

import pandas as pd

base_dir = Path.cwd()
raw_dir = base_dir / "data" / "movie_dataset_public_final" / "raw"
scores_dir = base_dir / "data" / "movie_dataset_public_final" / "scores"
processed_dir = base_dir / "data" / "processed"

chunk_size = 500_000


def read_json_file(file_path):
    content = file_path.read_text(encoding="utf-8").strip()

    try:
        data = json.loads(content)

        if isinstance(data, list):
            return data

        return [data]

    except json.JSONDecodeError:
        records = []

        for line in content.splitlines():
            if line.strip():
                records.append(json.loads(line))

        return records


def create_movies_file():
    print("Creating movies.csv...")

    metadata_file = raw_dir / "metadata.json"
    movies = pd.DataFrame(read_json_file(metadata_file))

    movies = movies.rename(columns={"item_id": "itemId"})

    columns = [
        "itemId",
        "title",
        "directedBy",
        "starring",
        "avgRating",
        "imdbId",
        "dateAdded",
    ]

    available_columns = [column for column in columns if column in movies.columns]
    movies = movies[available_columns]

    movies = movies.dropna(subset=["itemId", "title"])
    movies = movies.drop_duplicates(subset=["itemId"])
    movies["itemId"] = movies["itemId"].astype(int)

    output_file = processed_dir / "movies.csv"
    movies.to_csv(output_file, index=False)

    print(f"Created movies.csv with {len(movies):,} movies")

    return set(movies["itemId"])


def create_tags_file():
    print("Creating tags.csv...")

    tags_file = raw_dir / "tags.json"
    tags = pd.DataFrame(read_json_file(tags_file))

    tags = tags.rename(
        columns={
            "id": "tagId",
            "tag": "name",
        }
    )

    tags = tags[["tagId", "name"]]
    tags = tags.dropna()
    tags = tags.drop_duplicates(subset=["tagId"])
    tags["tagId"] = tags["tagId"].astype(int)

    output_file = processed_dir / "tags.csv"
    tags.to_csv(output_file, index=False)

    print(f"Created tags.csv with {len(tags):,} tags")


def create_movie_tag_relationships(valid_movie_ids):
    print("Creating movie_tag_relationships.csv...")

    scores_file = scores_dir / "glmer.csv"
    output_file = processed_dir / "movie_tag_relationships.csv"

    total_rows = 0
    write_header = True

    for chunk_number, chunk in enumerate(
        pd.read_csv(scores_file, chunksize=chunk_size),
        start=1,
    ):
        chunk = chunk.rename(columns={"item_id": "itemId"})

        chunk = chunk[chunk["itemId"].isin(valid_movie_ids)]
        chunk = chunk[["itemId", "tag", "score"]]
        chunk = chunk.dropna()

        chunk.to_csv(
            output_file,
            mode="w" if write_header else "a",
            header=write_header,
            index=False,
        )

        write_header = False
        total_rows += len(chunk)

        if chunk_number % 5 == 0:
            processed_rows = chunk_number * chunk_size
            print(f"Processed {processed_rows:,} rows")

    print(f"Created {total_rows:,} movie-tag relationships")


def main():
    if not raw_dir.exists():
        raise FileNotFoundError(
            f"Raw data folder was not found: {raw_dir}"
        )

    processed_dir.mkdir(parents=True, exist_ok=True)

    movie_ids = create_movies_file()
    create_tags_file()
    create_movie_tag_relationships(movie_ids)

    print()
    print("Data processing complete.")
    print("Files are available in data/processed/")


if __name__ == "__main__":
    main()