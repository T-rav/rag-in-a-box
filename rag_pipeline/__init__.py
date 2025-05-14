from .pre_request_hook import RAGHandler

# Create a singleton instance of the RAG handler
rag_handler_instance = RAGHandler()

# Export the instance
__all__ = ['rag_handler_instance'] 