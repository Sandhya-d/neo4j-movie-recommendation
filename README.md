# Neo4j Movie Recommendation System

This project is a graph-based movie recommendation system built using **Neo4j** and the **MovieLens Tag Genome 2021** dataset.

The system recommends movies using three different approaches:

* **Content-based recommendation** using movie tags
* **Graph embedding-based recommendation** using FastRP and kNN
* **Collaborative filtering** using similarities between users

These approaches are combined into a **hybrid recommendation system**. The recommendations are also evaluated using Precision and Recall metrics.

The project includes a **FastAPI backend** for serving recommendations through APIs and a **Streamlit web application** for interacting with the recommender.

---

## Prerequisites

Before running the project, make sure the following are installed:

* **Python 3.11+**
* **Neo4j Desktop**
* **Neo4j Graph Data Science (GDS) plugin**
* **VS Code** or any other code editor

Neo4j Desktop can be downloaded from:

https://neo4j.com/download/

The Graph Data Science plugin can be installed directly from Neo4j Desktop:

**Database → Plugins → Graph Data Science → Install**

---

## 1. Download the Dataset

This project uses the **MovieLens Tag Genome 2021** dataset.

https://grouplens.org/datasets/movielens/tag-genome-2021/

After downloading the dataset, extract it inside the project so that the folder structure looks like this:

```text
data/movie_dataset_public_final/
├── raw/
│   ├── metadata.json
│   ├── tags.json
│   ├── ratings.json
│   ├── reviews.json
│   ├── tag_count.json
│   └── survey_answers.json
└── scores/
    ├── glmer.csv
    └── tagdl.csv
```

---

## 2. Set Up Neo4j

Open **Neo4j Desktop** and create a new local DBMS.

Start the database and install the **Graph Data Science plugin** from the Plugins section.

Make sure you remember the Neo4j password you set while creating the database because it will be required by the Python application.

---

## 3. Install the Project Dependencies

Clone the repository:

```bash
git clone https://github.com/Sandhya-d/neo4j-movie-recommendation.git
```

Move into the project folder:

```bash
cd neo4j-movie-recommendation
```

Install the required Python packages:

```bash
python3 -m pip install -r requirements.txt
```

---

## 4. Configure Neo4j Credentials

Create your local environment file by copying the example file:

```bash
cp .env.example .env
```

Open `.env` and update it with your Neo4j credentials.

```env
NEO4J_URI=neo4j://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_actual_password_here
```

This keeps database credentials separate from the source code.

---

## 5. Run the Data Pipeline

The following steps should be executed in order.

### Step 1 — Prepare the Dataset

Run the ETL script:

```bash
python3 src/phase2_etl.py
```

The script reads the raw dataset, cleans and transforms it, and creates the CSV files required for Neo4j.

The generated files are:

```text
data/processed/movies.csv
data/processed/tags.csv
data/processed/movie_tag_relationships.csv
```

---

### Step 2 — Copy the CSV Files to Neo4j

Neo4j's `LOAD CSV` command reads files from its own import directory.

To find the import folder:

**Neo4j Desktop → Database → ... → Open Folder → Import**

Then copy the processed CSV files into that folder:

```bash
cp data/processed/*.csv "<paste the import folder path here>"
```

---

### Step 3 — Load the Graph into Neo4j

Open Neo4j Browser and run the queries available in:

```text
cypher/03_load_all.cypher
```

Run them in this order:

```text
Constraints
    ↓
Movies
    ↓
Tags
    ↓
Movie–Tag Relationships
```

This creates the main movie graph inside Neo4j.

---

### Step 4 — Create Strong Tag Relationships

Each movie in the dataset can have a large number of tag relationships.

Instead of using every tag for similarity calculations, the system keeps the **top 20 most relevant tags for each movie**.

Run:

```cypher
:auto MATCH (m:MOVIE)
CALL {
  WITH m
  MATCH (m)-[r:HAS_TAG]->(t:TAG)
  WITH m, t, r.score AS score
  ORDER BY score DESC
  LIMIT 20
  MERGE (m)-[r2:STRONG_TAG]->(t)
  SET r2.score = score
} IN TRANSACTIONS OF 500 ROWS;
```

This creates `STRONG_TAG` relationships containing the strongest tag signals for every movie.

Next, create the in-memory GDS graph:

```cypher
CALL gds.graph.project(
  'movieGraphFiltered',
  ['MOVIE', 'TAG'],
  {
    STRONG_TAG: {
      properties: 'score'
    }
  }
);
```

---

### Step 5 — Generate Movie Embeddings

The next stage creates graph embeddings using **FastRP**.

First, remove the previous projection if it already exists:

```cypher
CALL gds.graph.drop('movieGraphFiltered');
```

Create an undirected movie-tag graph:

```cypher
CALL gds.graph.project(
  'movieGraphUndirected',
  ['MOVIE', 'TAG'],
  {
    STRONG_TAG: {
      properties: 'score',
      orientation: 'UNDIRECTED'
    }
  }
);
```

Generate a 64-dimensional FastRP embedding for every node:

```cypher
CALL gds.fastRP.mutate(
  'movieGraphUndirected',
  {
    embeddingDimension: 64,
    relationshipWeightProperty: 'score',
    mutateProperty: 'fastrpEmbedding'
  }
);
```

The embedding captures the graph structure and tag relationships around each movie.

kNN is then used to identify movies with similar embeddings:

```cypher
CALL gds.knn.write(
  'movieGraphUndirected',
  {
    nodeProperties: ['fastrpEmbedding'],
    writeRelationshipType: 'SIMILAR_EMBEDDING',
    writeProperty: 'score',
    topK: 10
  }
);
```

The result is stored as `SIMILAR_EMBEDDING` relationships between similar movies.

---

### Step 6 — Load User Ratings

Prepare the ratings data:

```bash
python3 src/phase9_ratings_etl.py
```

This script selects a sample of **5,000 users** from the ratings dataset and prepares their ratings for Neo4j.

Copy the generated file into the Neo4j import folder:

```text
data/processed/ratings.csv
```

Then run the ratings-loading queries from:

```text
cypher/03_load_all.cypher
```

The graph will now contain:

```text
(USER)-[:RATED]->(MOVIE)
```

relationships.

---

### Step 7 — Build User Similarity

Create a GDS graph containing users, movies, and their rating relationships:

```cypher
CALL gds.graph.project(
  'userRatingGraphDirected',
  ['USER', 'MOVIE'],
  {
    RATED: {
      properties: 'rating'
    }
  }
);
```

Then calculate similarities between users:

```cypher
CALL gds.nodeSimilarity.write(
  'userRatingGraphDirected',
  {
    writeRelationshipType: 'SIMILAR_USER',
    writeProperty: 'score'
  }
);
```

Neo4j creates relationships such as:

```text
(USER)-[:SIMILAR_USER]->(USER)
```

These relationships are used for collaborative filtering.

---

## 6. Run the Recommendation Scripts

The individual recommendation components can be tested directly from Python.

### Content-Based Recommendation

```bash
python3 src/recommend.py
```

This recommends movies based mainly on shared tag information.

### Hybrid Recommendation

```bash
python3 src/hybrid_recommend.py
```

This combines:

```text
Tag Similarity
      +
FastRP Embedding Similarity
      +
Collaborative Filtering
      ↓
Final Recommendation Score
```

### Recommendation Evaluation

```bash
python3 src/phase12_evaluate.py
```

This evaluates the recommendation system using Precision and Recall.

### Graph Analysis

```bash
python3 src/graphify_layer.py
```

This pulls a Neo4j subgraph into Python using **NetworkX** for additional graph analysis and visualization.

---

## 7. Start the API and Web Application

The project contains both a FastAPI backend and a Streamlit frontend.

### Start FastAPI

Open a terminal and run:

```bash
uvicorn src.api:app --reload
```

Interactive API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

---

### Start Streamlit

Open another terminal:

```bash
streamlit run src/app.py
```

The Streamlit application should automatically open in the browser.

---

## Project Structure

```text
├── data/
│   └── dataset files and processed CSVs
│
├── src/
│   ├── config.py
│   ├── phase2_etl.py
│   ├── phase9_ratings_etl.py
│   ├── recommend.py
│   ├── hybrid_recommend.py
│   ├── phase12_evaluate.py
│   ├── api.py
│   ├── app.py
│   └── graphify_layer.py
│
├── cypher/
│   ├── 03_load_all.cypher
│   └── 04_queries.cypher
│
├── docs/
│   └── PHASE13_performance_summary.md
│
├── requirements.txt
├── .env.example
└── README.md
```

### Main Files

`phase2_etl.py` handles the main dataset cleaning and transformation.

`phase9_ratings_etl.py` prepares sampled user-rating data.

`recommend.py` contains the content-based recommendation logic.

`hybrid_recommend.py` combines the different recommendation approaches.

`phase12_evaluate.py` evaluates recommendation quality.

`api.py` exposes the recommendation system through FastAPI.

`app.py` provides the Streamlit user interface.

`graphify_layer.py` uses NetworkX to perform additional graph analysis outside Neo4j.

---

## Results

The final graph contains approximately:

* **84,661 movies**
* **1,094 tags**
* **10,547,319 movie-tag relationships**
* **5,000 sampled users**
* **560,134 ratings**

The hybrid recommender was evaluated using a 70/30 train-test split.

The final results were:

```text
Precision@10 = 0.0630
Recall@10    = 0.1538
Users Evaluated = 192
```

A more detailed performance summary is available in:

```text
docs/PHASE13_performance_summary.md
```

---

## Project Scope

The original ratings dataset contains around **28.4 million ratings**.

For this project, ratings from **5,000 users**, containing approximately **560,000 ratings**, were used. This keeps the complete pipeline practical to run locally while still providing enough user-rating information to demonstrate collaborative filtering.

The same chunk-based data processing approach used for the large movie-tag dataset can also be extended to load the complete ratings dataset if required.

For movie similarity, the system uses only the **top 20 tags for each movie** instead of every available `HAS_TAG` relationship.

These tags are stored as `STRONG_TAG` relationships.

Using the strongest tags helps reduce unnecessary graph relationships during similarity calculations while keeping the most useful information about each movie.

---

## Recommendation Pipeline

At a high level, the project works like this:

```text
MovieLens Dataset
       ↓
      ETL
       ↓
Processed CSV Files
       ↓
     Neo4j
       ↓
Movies ── HAS_TAG ── Tags
       ↓
Top 20 Tags per Movie
       ↓
   STRONG_TAG
       ↓
 ┌───────────────┬────────────────┐
 ↓               ↓                ↓
Tag Similarity   FastRP + kNN   User Ratings
 ↓               ↓                ↓
Content Score   Embedding Score  Collaborative Score
 └───────────────┬────────────────┘
                 ↓
        Hybrid Recommendation
                 ↓
           FastAPI Backend
                 ↓
         Streamlit Web App
```

The main goal of the project is to show how **graph databases, graph algorithms, embeddings, and collaborative filtering can work together to build a complete recommendation system using Neo4j**.
