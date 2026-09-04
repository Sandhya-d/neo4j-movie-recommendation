from neo4j import GraphDatabase
import networkx as nx
import matplotlib.pyplot as plt


# Neo4j connection
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

driver = GraphDatabase.driver(
    uri,
    auth=(username, password)
)


def get_movie_subgraph(movie_name):
    """Pull a small movie-tag graph from Neo4j."""

    with driver.session() as session:
        result = session.run(
            """
            MATCH (movie:MOVIE)-[r1:STRONG_TAG]->(tag:TAG)

            WHERE toLower(movie.title)
                  CONTAINS toLower($movie_name)

            OPTIONAL MATCH
            (tag)<-[r2:STRONG_TAG]-(related_movie:MOVIE)

            WHERE movie <> related_movie

            RETURN movie.title AS source_movie,
                   tag.name AS tag,
                   r1.score AS source_score,
                   related_movie.title AS related_movie,
                   r2.score AS related_score

            LIMIT 200
            """,
            movie_name=movie_name
        )

        graph = nx.Graph()

        for record in result:

            source_movie = record["source_movie"]
            tag = record["tag"]
            related_movie = record["related_movie"]

            graph.add_node(
                source_movie,
                type="movie"
            )

            graph.add_node(
                tag,
                type="tag"
            )

            graph.add_edge(
                source_movie,
                tag,
                weight=record["source_score"]
            )

            if related_movie:
                graph.add_node(
                    related_movie,
                    type="movie"
                )

                graph.add_edge(
                    related_movie,
                    tag,
                    weight=record["related_score"]
                )

        return graph


def analyze_graph(graph):
    """Print some basic information about the graph."""

    print("\nGraph Summary")
    print("-------------")

    print("Nodes:", graph.number_of_nodes())
    print("Edges:", graph.number_of_edges())

    movie_nodes = [
        node
        for node, data in graph.nodes(data=True)
        if data.get("type") == "movie"
    ]

    tag_nodes = [
        node
        for node, data in graph.nodes(data=True)
        if data.get("type") == "tag"
    ]

    print("Movies:", len(movie_nodes))
    print("Tags:", len(tag_nodes))

    # Find the most connected nodes
    centrality = nx.degree_centrality(graph)

    top_nodes = sorted(
        centrality.items(),
        key=lambda item: item[1],
        reverse=True
    )[:5]

    print("\nMost connected nodes")

    for node, score in top_nodes:
        node_type = graph.nodes[node].get("type")

        print(
            node,
            f"({node_type})",
            "-",
            round(score, 4)
        )

    components = nx.number_connected_components(graph)

    print("\nConnected components:", components)

    return centrality


def draw_graph(
    graph,
    file_name="graphify_visualization.png"
):
    """Create a simple visualization of the graph."""

    plt.figure(figsize=(14, 10))

    positions = nx.spring_layout(
        graph,
        k=0.5,
        seed=42
    )

    movie_nodes = [
        node
        for node, data in graph.nodes(data=True)
        if data.get("type") == "movie"
    ]

    tag_nodes = [
        node
        for node, data in graph.nodes(data=True)
        if data.get("type") == "tag"
    ]

    nx.draw_networkx_nodes(
        graph,
        positions,
        nodelist=movie_nodes,
        node_color="skyblue",
        node_size=600,
        label="Movies"
    )

    nx.draw_networkx_nodes(
        graph,
        positions,
        nodelist=tag_nodes,
        node_color="lightcoral",
        node_size=300,
        label="Tags"
    )

    nx.draw_networkx_edges(
        graph,
        positions,
        alpha=0.3
    )

    nx.draw_networkx_labels(
        graph,
        positions,
        font_size=7
    )

    plt.legend()
    plt.title("Movie and Tag Subgraph")
    plt.axis("off")
    plt.tight_layout()

    plt.savefig(
        file_name,
        dpi=150
    )

    print(f"\nGraph saved as {file_name}")


if __name__ == "__main__":

    graph = get_movie_subgraph("Toy Story")

    analyze_graph(graph)

    draw_graph(graph)

    driver.close()