# 🤖 Google Agent-to-Agent Protocol Demo (A2A)

This project demonstrates multi-agent collaboration across organizations using the [Google Agent-to-Agent Protocol (A2A)](https://ai.google.dev/agents/docs/a2a/overview). It features a **Host Agent** that can discover and delegate tasks to specialized **Remote Agents** (e.g., NewsAgent and WeatherAgent) via agent cards.

## 🚀 Project Structure

```
Agent2AgentProtocol/
├── backend/
│   ├── host/               # Host Agent using A2A
│   │   ├── main.py         # CLI for testing
│   │   ├── server.py       # FastAPI wrapper for Host Agent
│   │   ├── host_agent.py   # Core host logic (delegation, routing)
│   │   └── remote_agent_connection.py
│   ├── agents/
│   │   ├── news/           # NewsAgent
│   │   │   ├── agent.py
│   │   │   └── task_manager.py
│   │   └── weather/        # WeatherAgent (similar structure)
│   ├── common/             # Shared ADK types, A2A client, utils
│   │   └── ...
└── .env                   # Shared secrets like API keys
```

## 🧠 Agents

### 🔹 HostAgent
- Uses Google A2A to discover and delegate tasks
- Loads agent cards from remote agent URLs
- Orchestrates communication between agents using ADK runner

### 🔸 NewsAgent (via LangGraph + DeepSeek/OpenAI)
- Uses LangGraph with a ReAct agent
- Integrates tool: `get_latest_news(topic)`
- Returns structured response format
- Can be invoked via streaming or non-streaming

### 🔸 WeatherAgent (LangGraph)
- Similar to NewsAgent
- Tool: `get_weather(city)`

## 💡 How A2A Works
- Remote agents expose a `/.well-known/agent.json` endpoint describing their capabilities
- HostAgent fetches these Agent Cards at runtime and interacts with them via A2AClient
- Uses ADK tools like `Runner`, `InvocationContext`, `ToolContext`, etc.

## 📦 Requirements
- Python 3.10+
- Install dependencies:

```bash
pip install -r requirements.txt
```

## ▶️ Run Agents

Start NewsAgent:
```bash
cd backend/agents/news
python -m fastapi_server  # Exposes on port 10010
```

Start WeatherAgent:
```bash
cd backend/agents/weather
python -m fastapi_server  # Exposes on port 10011
```

Start HostAgent:
```bash
cd backend/host
python server.py  # Exposes FastAPI on port 11000
```

## 🧪 Test via CURL
```bash
curl -X POST http://localhost:11000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Latest news on AI"}'
```

## 🧑‍🏫 Features Demonstrated
- ✅ Dynamic capability discovery using Agent Cards
- ✅ Modular AI agents using LangGraph + tools
- ✅ FastAPI wrapper for frontend integration (e.g., Streamlit)
- ✅ Both streaming and non-streaming support

## 📸 Presentation Assets
- Included Google A2A diagrams, architecture visuals, and YouTube thumbnail under `/assets`

## 🙌 Acknowledgements
- Google ADK Team
- LangGraph / LangChain
- DeepSeek / OpenAI
- CrewAI (for showcasing multi-framework compatibility)

---

_This is a learning and demo project. PRs welcome!_

