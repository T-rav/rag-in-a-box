import os
from neo4j import GraphDatabase

class Neo4jService:
    def __init__(self, uri=None, user=None, password=None):
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def create_or_update_channel(self, channel_id, properties):
        with self.driver.session() as session:
            session.run(
                """
                MERGE (c:Channel {id: $id})
                SET c += $properties
                """,
                {"id": channel_id, "properties": properties}
            ) 