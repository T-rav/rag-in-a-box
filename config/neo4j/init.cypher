// Create constraints for unique identifiers
CREATE CONSTRAINT file_id IF NOT EXISTS
FOR (f:File) REQUIRE f.id IS UNIQUE;

CREATE CONSTRAINT owner_email IF NOT EXISTS
FOR (o:Owner) REQUIRE o.email IS UNIQUE;

CREATE CONSTRAINT folder_id IF NOT EXISTS
FOR (f:Folder) REQUIRE f.id IS UNIQUE;

// Create indexes for better query performance
CREATE INDEX file_name IF NOT EXISTS
FOR (f:File) ON (f.name);

CREATE INDEX owner_name IF NOT EXISTS
FOR (o:Owner) ON (o.displayName);

// Create full-text indexes for content search
CREATE FULLTEXT INDEX file_content IF NOT EXISTS
FOR (f:File) ON EACH [f.name, f.content];

// Create relationship indexes
CREATE INDEX relationship_types IF NOT EXISTS
FOR ()-[r]-() ON (type(r));

// Create metadata for the graph
CREATE (meta:Metadata {
    version: '1.0',
    last_updated: datetime(),
    description: 'Google Drive file relationships and metadata'
});

// Create initial folder structure
MERGE (root:Folder {id: 'root', name: 'Root'})
WITH root
MERGE (meta)-[:DESCRIBES]->(root);

// Create common file types as categories
MERGE (doc:FileType {name: 'Document'})
MERGE (sheet:FileType {name: 'Spreadsheet'})
MERGE (slide:FileType {name: 'Presentation'})
MERGE (image:FileType {name: 'Image'})
MERGE (other:FileType {name: 'Other'});

// Create relationship types metadata
CREATE (rt:RelationshipTypes {
    types: [
        'OWNED_BY',
        'IN_FOLDER',
        'SIMILAR_TO',
        'RELATED_TO',
        'VERSION_OF',
        'SHARED_WITH'
    ]
});

// Create indexes for relationship properties
CREATE INDEX similarity_score IF NOT EXISTS
FOR ()-[r:SIMILAR_TO]-() ON (r.score);

CREATE INDEX shared_permissions IF NOT EXISTS
FOR ()-[r:SHARED_WITH]-() ON (r.permission); 