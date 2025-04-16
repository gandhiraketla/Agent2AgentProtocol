import os
import logging
from dotenv import load_dotenv
import sys

# 📁 Ensure project root is on sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import click
from pathlib import Path

# 📦 A2A modules from shared common/ folder
from common.server import A2AServer
from common.types import AgentCard, AgentCapabilities, AgentSkill, MissingAPIKeyError
from common.utils.push_notification_auth import PushNotificationSenderAuth

# 🧠 Local agent and task manager for Weather
from agents.weather.agent import WeatherAgent
from agents.weather.task_manager import AgentTaskManager

# 🌍 Load .env from project root
root_dir = Path(__file__).resolve().parents[3]
dotenv_path = root_dir / ".env"
load_dotenv(dotenv_path=dotenv_path)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option("--host", default="localhost", help="Host to bind the WeatherAgent server.")
@click.option("--port", default=10011, help="Port to serve the WeatherAgent.")
def main(host, port):
    print(f"🌤️ Starting WeatherAgent server at http://{host}:{port}")

    # Uncomment below to validate DeepSeek key if needed
    # if not os.getenv("DEEPSEEK_API_KEY"):
    #     raise MissingAPIKeyError("❌ DEEPSEEK_API_KEY is not set in .env file.")

    capabilities = AgentCapabilities(streaming=False, pushNotifications=True)

    skill = AgentSkill(
        id="get_weather",
        name="Weather Reporter",
        description="Provides weather updates for a city.",
        tags=["weather", "forecast", "climate"],
        examples=["What's the weather in New York?", "Forecast in London?"]
    )

    agent_card = AgentCard(
        name="Weather Agent",
        description="Gives weather information for a given city.",
        url=f"http://{host}:{port}/",
        version="1.0.0",
        defaultInputModes=WeatherAgent.SUPPORTED_CONTENT_TYPES,
        defaultOutputModes=WeatherAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=capabilities,
        skills=[skill]
    )

    notification_sender_auth = PushNotificationSenderAuth()
    notification_sender_auth.generate_jwk()

    server = A2AServer(
        agent_card=agent_card,
        task_manager=AgentTaskManager(agent=WeatherAgent(), notification_sender_auth=notification_sender_auth),
        host=host,
        port=port,
    )

    server.app.add_route(
        "/.well-known/jwks.json", notification_sender_auth.handle_jwks_endpoint, methods=["GET"]
    )

    logger.info(f"✅ WeatherAgent is live at http://{host}:{port}")
    server.start()

if __name__ == "__main__":
    main()
