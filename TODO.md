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