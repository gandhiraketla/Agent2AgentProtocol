# 🤖 Google Agent-to-Agent Protocol Demo (A2A)

This project demonstrates multi-agent collaboration across organizations using the [Google Agent-to-Agent Protocol (A2A)](https://ai.google.dev/agents/docs/a2a/overview). It features a **Host Agent** that can discover and delegate tasks to specialized **Remote Agents** (e.g., NewsAgent and WeatherAgent) via agent cards.

## 🚀 Project Structure

```
Agent2AgentProtocol/
├── backend/
│   ├── host/               # Host Agent using A2A
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

### 🔸 NewsAgent (via LangGraph + OpenAI)
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
python server.py
```

Start WeatherAgent:
```bash
cd backend/agents/weather
python server.py
```

Start HostAgent:
```bash
cd backend/host
python server.py  # Exposes FastAPI on port 11000
```

## 🧪 Test via HTML UI
```bash
Go to /frontend/ui folder and open ui.html in browser.
```


_This is a learning and demo project. PRs welcome!_

