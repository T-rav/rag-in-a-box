#  RAG in a Box

RAG stack for chat bots that aims to be a deploy, configure and go solution. 

🧠 OpenWebUI  -> The chat UI because why not!  
🔄 LiteLLM Proxy	-> Monitor, Observe and Managae LLMOps centrally - make use of LangFuse to handle prompt managment     
📚 RAG Pipeline	Python (your code) -> Custom RAG injection code loaded dynamically like a plugin _(Inject company data, do auth checks, add guardrails to make it safe and prod ready)_   
🛡️ Caddy	Static binary (Go)	-> Auth Proxy to allow OpenWebUI and LiteLLM to centralize auth  

**All you need to do is build the data pipelines to ingest and index, then the code to query and inject.**  
