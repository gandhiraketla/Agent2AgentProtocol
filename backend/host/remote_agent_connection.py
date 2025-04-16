from typing import Callable
import uuid
from common.types import (
    AgentCard,
    Task,
    TaskSendParams,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    TaskStatus,
    TaskState,
)
from common.client import A2AClient

TaskCallbackArg = Task | TaskStatusUpdateEvent | TaskArtifactUpdateEvent
TaskUpdateCallback = Callable[[TaskCallbackArg], Task]

class RemoteAgentConnections:
  """A class to hold the connections to the remote agents."""

  def __init__(self, agent_card: AgentCard):
    self.agent_client = A2AClient(agent_card)
    self.card = agent_card

    self.conversation_name = None
    self.conversation = None
    self.pending_tasks = set()

  def get_agent(self) -> AgentCard:
    return self.card

  async def send_task(
      self,
      request: TaskSendParams,
      task_callback: TaskUpdateCallback | None,
  ) -> Task | None:
    if self.card.capabilities.streaming:
      print("Streaming")
      task = None
      if task_callback:
        task_callback(Task(
            id=request.id,
            sessionId=request.sessionId,
            status=TaskStatus(
                state=TaskState.SUBMITTED,
                message=request.message,
            ),
            history=[request.message],
        ))
      async for response in self.agent_client.send_task_streaming(request.model_dump()):
        merge_metadata(response.result, request)
        # For task status updates, we need to propagate metadata and provide
        # a unique message id.
        if (hasattr(response.result, 'status') and
            hasattr(response.result.status, 'message') and
            response.result.status.message):
          merge_metadata(response.result.status.message, request.message)
          m = response.result.status.message
          if not m.metadata:
            m.metadata = {}
          if 'message_id' in m.metadata:
            m.metadata['last_message_id'] = m.metadata['message_id']
          m.metadata['message_id'] = str(uuid.uuid4())
        if task_callback:
          task = task_callback(response.result)
        if hasattr(response.result, 'final') and response.result.final:
          break
      return response.result
    else: # Non-streaming
      try:
        print("🚀 Non-streaming task initiated")
        response = await self.agent_client.send_task(request.model_dump())
        print("✅ Raw response:", response)

        if not response or not response.result:
            print("❌ No result in response")
            return {
                "error": "Empty result received from agent.",
                "status": "failed",
                "agent": self.card.name,
            }

        result = response.result

        # Safe metadata merge
        if hasattr(result, 'status') and result.status.message:
            print("📦 Merging metadata")
            merge_metadata(result.status.message, request.message)
            m = result.status.message
            m.metadata = m.metadata or {}
            if 'message_id' in m.metadata:
                m.metadata['last_message_id'] = m.metadata['message_id']
            m.metadata['message_id'] = str(uuid.uuid4())

        if task_callback:
            print("🔄 Invoking task callback")
            task_callback(result)

        print("✅ Task completed successfully")
        return result

      except Exception as e:
        print(f"❌ Exception in send_task: {str(e)}")
        return {
            "error": str(e),
            "status": "failed",
            "agent": self.card.name,
        }

def merge_metadata(target, source):
  if not hasattr(target, 'metadata') or not hasattr(source, 'metadata'):
    return
  if target.metadata and source.metadata:
    target.metadata.update(source.metadata)
  elif source.metadata:
    target.metadata = dict(**source.metadata)