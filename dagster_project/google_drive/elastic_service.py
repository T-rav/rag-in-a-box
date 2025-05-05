from elasticsearch import Elasticsearch
import os

class ElasticsearchService:
    def __init__(self, host=None, port=None):
        self.host = host or os.getenv("ELASTICSEARCH_HOST", "elasticsearch")
        self.port = int(port or os.getenv("ELASTICSEARCH_PORT", "9200"))
        self.es = Elasticsearch(hosts=[{"scheme": "http", "host": self.host, "port": self.port}])

    def index_document(self, index, doc_id, document):
        self.es.index(index=index, id=doc_id, document=document) 