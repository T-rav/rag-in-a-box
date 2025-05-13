# Insight Mesh Implementation TODO

## 1. Slack Chat Integration
- [x] **Create Slack App:**
  - Register a new Slack app and bot.
  - Set permissions: `chat:write`, `channels:history`, `users:read.email`, etc.
  - Install the app to your workspace and save the OAuth token.
- [x] **Implement Bot Listener:**
  - Use `slack_bolt` to listen for new messages and fetch message history.
  - Extract user ID and forward in auth header.
- [x] **Forward to LiteLLM:**
  - Send messages with `X-Auth-Token: slack:{user_id}` header.
  - Use LiteLLM proxy for consistent handling with OpenWebUI.
- [ ] **Test End-to-End:**
  - Validate that the bot responds correctly
  - Verify auth token handling in RAG hook
  - Test user permissions and context retrieval
  - Ensure proper error handling and logging

## 2. MCP Server
- [x] **Scaffold API Server:**
  - Use FastAPI for the MCP server.
- [x] **Implement RAG Hook Endpoint:**
  - Accepts user message and context.
  - Enriches prompt using Elasticsearch, Neo4j, and permission logic.
  - Returns enriched prompt/context to LiteLLM.
- [x] **Integrate with Data Sources:**
  - Connect to Elasticsearch, Neo4j, and permissions DB.
  - Implement retrieval and enrichment logic.
- [x] **Authentication & Permissions:**
  - Handle both JWT and Slack auth tokens
  - Look up user info from appropriate sources
  - Apply permission filtering
- [ ] **Test MCP Integration:**
  - Verify token handling for both auth types
  - Test user lookup and permission checks
  - Validate context retrieval and enrichment
  - Monitor performance and error rates
- [ ] **(Future) Agent Management:**
  - Design endpoints for managing and visualizing business ops agents.
- [ ] **Document API Contracts:**
  - Document auth token formats
  - Document request/response formats
  - Document integration points with LiteLLM

## 3. Infrastructure
- [ ] **Monitoring:**
  - Set up logging for auth token handling
  - Monitor token validation success/failure rates
  - Track context retrieval performance
  - Set up alerts for auth/permission issues
- [ ] **Security:**
  - Review token handling security
  - Audit permission checks
  - Monitor for unusual access patterns
  - Regular security reviews

## 4. Search & NLP Improvements
- [ ] **Entity Extraction Pipeline:**
  - Implement NLP entity extraction during indexing
  - Extract key entities (people, organizations, topics, etc.)
  - Store entities in Neo4j for relationship mapping
  - Add entity metadata to Elasticsearch documents
- [ ] **Hybrid Search Enhancement:**
  - Implement sparse embeddings (BM25) in Elasticsearch
  - Configure hybrid search combining dense and sparse vectors
  - Tune BM25 parameters for optimal results
  - Add field boosting for entity matches
- [ ] **Search Quality:**
  - Set up evaluation metrics for search quality
  - Implement A/B testing framework
  - Create test dataset with relevance judgments
  - Monitor search performance metrics
- [ ] **Integration:**
  - Update MCP server to use hybrid search
  - Modify context retrieval to leverage entities
  - Add entity-based filtering options
  - Update RAG prompt to use entity context