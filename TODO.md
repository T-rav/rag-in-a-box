# Insight Mesh Implementation TODO

## 1. Caddy Reverse Proxy Setup ✅
- [x] Configure Caddy to inject OpenWebUI auth token
- [x] Set up proper header propagation
- [x] Test token flow through proxy chain

## 2. LiteLLM Proxy Server Modifications
- [ ] Update pre_request_hook to receive auth headers
- [ ] Test header propagation
- [x] Implement OpenWebUI integration to fetch user email based on the ID in JWT token
- [x] Cache email lookups in Redis to avoid repeated API calls to OpenWebUI

## 3. Dagster Integration
- [ ] Install and configure Dagster
- [ ] Set up Google Drive service account
- [ ] Configure document indexing pipeline
- [ ] Test end-to-end with Haystack

## 4. Haystack Integration
- [x] Set up Haystack pipeline
- [x] Configure vector store connection
- [x] Configure elasticsearch connection
- [x] Implement document retrieval logic
- [ ] Add reranking
- [x] Add source metadata handling
- [x] Implement database integration for user email lookup
- [x] Set up Redis caching for email lookups
- [x] Add permission-based document filtering using email/domain
- [ ] Test retrieval performance

## 5. OpenWebUI Source Display
- [ ] Modify pre_request_hook response format
- [ ] Add source metadata structure
- [ ] Update OpenWebUI to display sources
- [ ] Test source display

## Additional Tasks
- [x] Implement error handling
- [x] Set up logging
- [ ] Add monitoring
- [x] Set up Redis for caching JWT token to email mappings
- [x] Configure PostgreSQL integration for user data

## Notes
- Keep track of any breaking changes
- Document all configuration options
- Maintain compatibility with future updates
- Consider scalability implications
- OpenWebUI manages the user database, we just need to query it 