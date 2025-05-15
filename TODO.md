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
- [ ] **Test End-to-End:** (HIGH PRIORITY)
  - Validate that the bot responds correctly
  - Verify auth token handling in RAG hook
  - Test user permissions and context retrieval
  - Ensure proper error handling and logging
- [x] **Implement AI Apps Features:**
  - Configure bot with new Slack AI Apps capabilities
  - Set up suggested prompts and thread status indicators
  - Migrate from Socket Mode to new AI Apps framework
- [x] **Add Agent Process Support:**
  - Implement background process execution from Slack
  - Create agent process definitions for common tasks
  - Add user-friendly status reporting

## 1.1 Slack Agent Enhancements (MEDIUM PRIORITY)
- [ ] **Add More Agent Processes:**
  - Expand available agent processes to include data cleaning, analytics, and export functionality
  - Add specialized agents for different data sources
  - Implement parameterized processes that accept user inputs
- [ ] **Process Monitoring:**
  - Implement comprehensive job monitoring system for tracking progress of long-running jobs
  - Add notifications when jobs complete or encounter errors
  - Create job status dashboard accessible through bot commands
- [ ] **Process Output Reporting:**
  - Add automatic reporting capabilities that share job results directly in Slack
  - Include visualizations and summary statistics in reports
  - Allow reports to be saved and shared with team members
- [ ] **User-Specific Job History:**
  - Maintain per-user job history for review and auditing
  - Allow users to easily rerun previous jobs with same parameters
  - Implement job templates based on common usage patterns

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
- [x] **Test MCP Integration:** (HIGH PRIORITY)
  - Verify token handling for both auth types
  - Test user lookup and permission checks
  - Validate context retrieval and enrichment
  - Implement comprehensive test suite with test coverage reporting
- [ ] **Agent Management:** (MEDIUM PRIORITY)
  - Design endpoints for managing and visualizing business ops agents
  - Implement job scheduling and management API
  - Create monitoring endpoints for job status tracking
- [ ] **Document API Contracts:** (HIGH PRIORITY)
  - Document auth token formats
  - Document request/response formats
  - Document integration points with LiteLLM

## 3. Infrastructure (HIGH PRIORITY)
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
- [ ] **Deployment:**
  - Finalize Docker container configurations
  - Set up container orchestration
  - Implement CI/CD pipeline for automated testing and deployment
  - Document deployment procedures

## 4. Search & NLP Improvements (LOW PRIORITY)
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

## 5. Testing & Documentation (HIGH PRIORITY)
- [x] **MCP Server Testing:**
  - Create comprehensive test plan
  - Implement unit tests for all components
  - Set up test coverage reporting
  - Document test scenarios and expectations
- [ ] **End-to-End Testing:**
  - Create comprehensive test plan for the entire system
  - Implement automated testing for critical paths
  - Document testing procedures and expected results
- [ ] **User Documentation:**
  - Create user guides for Slack interaction
  - Document available commands and agent processes
  - Provide troubleshooting information
- [ ] **Developer Documentation:**
  - Document system architecture
  - Create API documentation
  - Document deployment and maintenance procedures