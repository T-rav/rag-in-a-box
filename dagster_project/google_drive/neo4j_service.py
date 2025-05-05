from neo4j import GraphDatabase
import os

class Neo4jService:
    def __init__(self, uri=None, user=None, password=None):
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def create_or_update_folder(self, folder_id, name, parent_id=None):
        with self.driver.session() as session:
            session.run(
                """
                MERGE (f:Folder {id: $id})
                SET f.name = $name
                """,
                {"id": folder_id, "name": name}
            )
            if parent_id:
                session.run(
                    """
                    MATCH (parent:Folder {id: $parent_id}), (child:Folder {id: $id})
                    MERGE (parent)-[:CONTAINS]->(child)
                    """,
                    {"parent_id": parent_id, "id": folder_id}
                )

    def create_or_update_file(self, file_id, file_name, mime_type, created_time, modified_time, web_link, is_public, parent_id=None):
        with self.driver.session() as session:
            session.run(
                """
                MERGE (f:File {id: $file_id})
                SET f.name = $file_name,
                    f.mime_type = $mime_type,
                    f.created_time = $created_time,
                    f.modified_time = $modified_time,
                    f.web_link = $web_link,
                    f.is_public = $is_public
                """,
                {
                    "file_id": file_id,
                    "file_name": file_name,
                    "mime_type": mime_type,
                    "created_time": created_time,
                    "modified_time": modified_time,
                    "web_link": web_link,
                    "is_public": is_public,
                }
            )
            if parent_id:
                session.run(
                    """
                    MATCH (parent:Folder {id: $parent_id}), (child:File {id: $file_id})
                    MERGE (parent)-[:CONTAINS]->(child)
                    """,
                    {"parent_id": parent_id, "file_id": file_id}
                ) 