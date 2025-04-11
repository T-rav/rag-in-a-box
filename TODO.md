# RAG-in-a-Box Implementation TODO

## 1. Caddy Reverse Proxy Setup
- [ ] Configure Caddy to inject OpenWebUI auth token
- [ ] Set up proper header propagation
- [ ] Test token flow through proxy chain

## 2. LiteLLM Proxy Server Modifications
- [ ] Identify auth header injection point in proxy_server.py
- [ ] Modify request handling to preserve auth headers
- [ ] Update pre_request_hook to receive auth headers
- [ ] Test header propagation

## 3. Custom Docker Image
- [ ] Create Dockerfile extending LiteLLM base
- [ ] Add patched proxy_server.py
- [ ] Include custom_callbacks.py
- [ ] Add Haystack dependencies
- [ ] Build and test locally
- [ ] Update docker-compose.yml
- [ ] CI Pipeline

## 4. Haystack Integration
- [ ] Set up Haystack pipeline
- [ ] Configure vector store connection
- [ ] Configure elasticserch connection
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