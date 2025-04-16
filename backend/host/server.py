import os
import sys
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pathlib import Path
from pydantic import BaseModel
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
import uuid
import json
from host_agent import HostAgent

# 🔄 Ensure root path is in sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# 📁 Load .env from root
root_dir = Path(__file__).resolve().parents[2]
dotenv_path = root_dir / ".env"
load_dotenv(dotenv_path=dotenv_path)

# 🚀 Initialize FastAPI
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Can be set to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔗 Set up HostAgent
REMOTE_AGENTS = ["http://localhost:10010", "http://localhost:10011"]
print("🚀 Initializing HostAgent with remote agents:")
for url in REMOTE_AGENTS:
    print(f"🔗 {url}")
host = HostAgent(remote_agent_addresses=REMOTE_AGENTS)
adk_agent = host.create_agent()

# 🧠 Wrap in ADK runner
session_service = InMemorySessionService()
runner = Runner(agent=adk_agent, app_name="host_app", session_service=session_service)

# Define a consistent session ID to avoid "Session not found" errors
# This approach uses a fixed session for simplicity
USER_ID = "user-1"
SESSION_ID = "host-session-1"

# Initialize the session once at startup
print(f"Creating persistent session: {SESSION_ID}")
session_service.create_session(
    app_name="host_app",
    user_id=USER_ID,
    session_id=SESSION_ID
)

class QueryRequest(BaseModel):
    query: str

@app.post("/query")
async def query_handler(request: QueryRequest):
    """Handle user queries and return agent responses."""
    user_query = request.query
    
    if not user_query:
        return JSONResponse({"error": "Missing 'query'"}, status_code=400)
    
    content = Content(role="user", parts=[Part(text=user_query)])
    #print("AGENT RESPONSE:")
    #print(content)
    try:
        final_response = None
        # Use the persistent session ID instead of generating a new one each time
        async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
            print("Event type:", type(event))
            print("Event content:", event)
            for response in event:
                print(f"📡 Received response: {response}")
                if hasattr(event, "content") and event.content:
                    print("Event content:", event.content)
                    for part in event.content.parts:
                        if part.text:
                            print(f"📡 Received response: {part.text}")
                            final_response = part.text

        return {"response": final_response or "⚠️ No response from agent."}

    except Exception as e:
        print(f"❌ Error in FastAPI: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# New WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections for streaming agent responses."""
    await websocket.accept()
    print("WebSocket connection established")
    
    try:
        while True:
            # Wait for messages from the client
            data = await websocket.receive_text()
            try:
                data_json = json.loads(data)
                user_query = data_json.get("query", "")
                
                if not user_query:
                    await websocket.send_json({"error": "Missing 'query'"})
                    continue
                
                # Send a message indicating processing has started
                await websocket.send_json({"status": "processing", "message": "Processing your query..."})
                
                # Create the query content
                content = Content(role="user", parts=[Part(text=user_query)])
                
                # Stream responses back to the client
                response_parts = []
                async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
                    print("WebSocket Event:", type(event))
                    
                    if hasattr(event, "content") and event.content:
                        for part in event.content.parts:
                            print(f"WebSocket response part: {part}")
                            print(f"WebSocket response part TEXT: {part.text}")
                            if part.text:
                                chunk_text = part.text
                                print(f"WebSocket response chunk: {chunk_text}")
                                
                                # Send each part of the response as it becomes available
                                await websocket.send_json({
                                    "status": "chunk", 
                                    "chunk": chunk_text,
                                    "complete": False
                                })
                                response_parts.append(chunk_text)
                
                # Send a complete message with the full response
                full_response = "".join(response_parts) if response_parts else "⚠️ No response from agent."
                await websocket.send_json({
                    "status": "complete",
                    "response": full_response,
                    "complete": True
                })
                
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
            except Exception as e:
                print(f"❌ Error in agent processing: {e}")
                await websocket.send_json({
                    "status": "error",
                    "error": str(e),
                    "complete": True
                })
    
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"❌ Unexpected WebSocket error: {e}")

# Add this block to run via `python server.py`
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, timeout_keep_alive=50000)