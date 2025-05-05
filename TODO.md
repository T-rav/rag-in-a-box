# Insight Mesh Implementation TODO

## 1. Caddy Reverse Proxy Setup ✅
- [x] Configure Caddy to inject OpenWebUI auth token
- [x] Set up proper header propagation
- [x] Test token flow through proxy chain

## 2. LiteLLM Proxy Server Modifications
- [ ] Update pre_request_hook to receive auth headers
- [ ] Test header propagation

## 3. Dagster Integration
- [ ] Install and configure Dagster
- [ ] Set up Google Drive service account
- [ ] Configure document indexing pipeline
- [ ] Test end-to-end with Haystack

## 4. Haystack Integration
- [ ] Set up Haystack pipeline
- [ ] Configure vector store connection
- [ ] Configure elasticsearch connection
- [ ] Implement document retrieval logic
- [ ] Add reranking
- [ ] Add source metadata handling
- [ ] Test retrieval performance

## 5. OpenWebUI Source Display
- [ ] Modify pre_request_hook response format
- [ ] Add source metadata structure
- [ ] Update OpenWebUI to display sources
- [ ] Test source display

## Additional Tasks
- [ ] Implement error handling
- [ ] Set up logging
- [ ] Add monitoring

## Notes
- Keep track of any breaking changes
- Document all configuration options
- Maintain compatibility with future updates
- Consider scalability implications

# TODO: Slack Chat Integration & MCP Server

## 1. Slack Chat Integration
- [ ] **Create Slack App:**
  - Register a new Slack app and bot.
  - Set permissions: `chat:write`, `channels:history`, `users:read.email`, etc.
  - Install the app to your workspace and save the OAuth token.
- [ ] **Implement Bot Listener:**
  - Use `slack_bolt` or `slack_sdk` to listen for new messages and fetch message history.
  - Extract user ID and fetch user email for context/permissions.
- [ ] **Forward to LiteLLM:**
  - Send the message, history, and user context to LiteLLM.
  - Receive the LLM response and post it back to Slack (in the correct thread/channel).
- [ ] **Test End-to-End:**
  - Validate that the bot responds correctly and respects permissions.

## 2. MCP Server
- [ ] **Scaffold API Server:**
  - Use FastAPI, Flask, or similar to create the MCP server.
- [ ] **Implement RAG Hook Endpoint:**
  - Accepts user message and context.
  - Enriches prompt using Elasticsearch, Neo4j, and permission logic.
  - Returns enriched prompt/context to LiteLLM.
- [ ] **Integrate with Data Sources:**
  - Connect to Elasticsearch, Neo4j, and permissions DB.
  - Implement retrieval and enrichment logic.
- [ ] **Authentication & Permissions:**
  - Ensure endpoints are secure and permission-aware.
- [ ] **(Future) Agent Management:**
  - Design endpoints for managing and visualizing business ops agents.
- [ ] **Document API Contracts:**
  - Clearly document request/response formats and integration points.

## Next Steps
- [ ] Prioritize Slack integration or MCP server based on demo needs.
- [ ] Assign owners and deadlines for each task.
- [ ] Track progress in your project management tool. 