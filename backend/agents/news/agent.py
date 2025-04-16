from langchain_core.tools import tool
from langchain_deepseek import ChatDeepSeek
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, ToolMessage
from typing import AsyncIterable, Any, Dict, Literal
from pydantic import BaseModel
from pathlib import Path
import os
from dotenv import load_dotenv
import time

print("🚀 Initializing NewsAgent...")

# Load shared .env from root
root_dir = Path(__file__).resolve().parents[3]
dotenv_path = root_dir / ".env"
load_dotenv(dotenv_path=dotenv_path)

api_key = os.getenv("DEEPSEEK_API_KEY")
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
os.environ["LANGCHAIN_PROJECT"] = "Agent2AgentProtocol"
if not api_key:
    raise EnvironmentError(f"❌ DEEPSEEK_API_KEY not found in {dotenv_path}")
else:
    print(f"✅ DEEPSEEK_API_KEY loaded from {dotenv_path}")

# Memory for threading
memory = MemorySaver()

# 🛠️ Tool - for now, returns a hardcoded news string
@tool
def get_latest_news(topic: str = "technology") -> dict:
    """Fetches the latest news for a given topic. Returns hardcoded response for now."""
    print(f"📰 Tool called: get_latest_news with topic='{topic}'")
    return {
        "topic": topic,
        "headline": f"Breaking: Big News in {topic.title()}!",
        "summary": f"This is a hardcoded update for '{topic}'. Real news API integration coming soon."
    }

# 🧾 Format for response returned by the agent
class ResponseFormat(BaseModel):
    status: Literal["input_required", "completed", "error"] = "input_required"
    message: str

# 🧠 NewsAgent powered by LangGraph + DeepSeek
class NewsAgent:
    SYSTEM_INSTRUCTION = (
        "You are a news assistant. Your job is to use the 'get_latest_news' tool "
        "to answer user questions about current news on any topic. "
        "If the user doesn't specify a topic, default to 'technology'. "
        "Set status to 'completed' when you successfully return a headline. "
        "Set status to 'input_required' if user needs to clarify topic. "
        "Set status to 'error' only if something fails."
    )

    def __init__(self):
        print("⚙️ Creating LangGraph ReAct agent for NewsAgent...")
        self.model = ChatDeepSeek(model="deepseek-chat", api_key=api_key)
        self.tools = [get_latest_news]

        self.graph = create_react_agent(
            self.model,
            tools=self.tools,
            checkpointer=memory,
            prompt=self.SYSTEM_INSTRUCTION,
            response_format=ResponseFormat
        )

    async def invoke(self, query: str, session_id: str) -> dict:
        print(f"🧠 invoke() called with query='{query}' and session_id='{session_id}'")
        config = {"configurable": {"thread_id": session_id}}
        await self.graph.ainvoke({"messages": [("user", query)]}, config)
        return self.get_agent_response(config)

    async def stream(self, query: str, session_id: str) -> AsyncIterable[Dict[str, Any]]:
        print(f"📡 stream() called with query='{query}' and session_id='{session_id}'")
        inputs = {"messages": [("user", query)]}
        config = {"configurable": {"thread_id": session_id}}

        async for item in self.graph.astream(inputs, config, stream_mode="values"):
            message = item["messages"][-1]
            if isinstance(message, AIMessage) and message.tool_calls:
                yield {
                    "is_task_complete": False,
                    "require_user_input": False,
                    "content": "🔍 Fetching the latest news..."
                }
            elif isinstance(message, ToolMessage):
                yield {
                    "is_task_complete": False,
                    "require_user_input": False,
                    "content": "🛠️ Processing the news article..."
                }

        yield self.get_agent_response(config)

    def get_agent_response(self, config) -> dict:
        state = self.graph.get_state(config)
        structured = state.values.get("structured_response")
        if isinstance(structured, ResponseFormat):
            print(f"✅ Structured response received: {structured}")
            return {
                "is_task_complete": structured.status == "completed",
                "require_user_input": structured.status == "input_required",
                "content": structured.message
            }

        print("⚠️ No structured response. Returning fallback message.")
        return {
            "is_task_complete": False,
            "require_user_input": True,
            "content": "⚠️ Something went wrong. Please try again."
        }

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

print("✅ NewsAgent is fully initialized and ready.")
