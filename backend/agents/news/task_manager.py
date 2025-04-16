import os
import logging
from dotenv import load_dotenv
import sys
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from typing import AsyncIterable, Union
import asyncio
import logging
import traceback

from common.types import (
    SendTaskRequest,
    SendTaskResponse,
    TaskSendParams,
    TaskState,
    TaskStatus,
    Message,
    Artifact,
    TextPart,
    InternalError,
    InvalidParamsError,
    JSONRPCResponse,
    SendTaskStreamingRequest,
    SendTaskStreamingResponse,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
    Task,
    TaskIdParams,
    PushNotificationConfig,
)
from common.server.task_manager import InMemoryTaskManager
from common.utils.push_notification_auth import PushNotificationSenderAuth
import common.server.utils as utils

from agents.news.agent import NewsAgent  # 👈 your specific agent

logger = logging.getLogger(__name__)


class AgentTaskManager(InMemoryTaskManager):
    def __init__(self, agent: NewsAgent, notification_sender_auth: PushNotificationSenderAuth):
        super().__init__()
        self.agent = agent
        self.notification_sender_auth = notification_sender_auth

    async def _run_streaming_agent(self, request: SendTaskStreamingRequest):
        task_send_params: TaskSendParams = request.params
        query = self._get_user_query(task_send_params)

        try:
            async for item in self.agent.stream(query, task_send_params.sessionId):
                is_task_complete = item["is_task_complete"]
                require_user_input = item["require_user_input"]
                parts = [{"type": "text", "text": item["content"]}]
                end_stream = is_task_complete or require_user_input

                task_status = TaskStatus(
                    state=TaskState.COMPLETED if is_task_complete else
                          TaskState.INPUT_REQUIRED if require_user_input else
                          TaskState.WORKING,
                    message=Message(role="agent", parts=parts)
                )

                artifact = Artifact(parts=parts) if is_task_complete else None

                task = await self.update_store(
                    task_send_params.id, task_status, [artifact] if artifact else None
                )

                await self.send_task_notification(task)

                if artifact:
                    await self.enqueue_events_for_sse(
                        task_send_params.id,
                        TaskArtifactUpdateEvent(id=task_send_params.id, artifact=artifact)
                    )

                await self.enqueue_events_for_sse(
                    task_send_params.id,
                    TaskStatusUpdateEvent(id=task_send_params.id, status=task_status, final=end_stream)
                )

        except Exception as e:
            logger.error(f"❌ Error in stream: {e}")
            await self.enqueue_events_for_sse(
                task_send_params.id,
                InternalError(message=f"Streaming error: {str(e)}")
            )

    def _validate_request(self, request: Union[SendTaskRequest, SendTaskStreamingRequest]) -> JSONRPCResponse | None:
        task_send_params: TaskSendParams = request.params
        if not utils.are_modalities_compatible(
            task_send_params.acceptedOutputModes, NewsAgent.SUPPORTED_CONTENT_TYPES
        ):
            return utils.new_incompatible_types_error(request.id)

        if task_send_params.pushNotification and not task_send_params.pushNotification.url:
            return JSONRPCResponse(id=request.id, error=InvalidParamsError(message="Push notification URL is missing"))

        return None

    async def on_send_task(self, request: SendTaskRequest) -> SendTaskResponse:
        if (error := self._validate_request(request)):
            return SendTaskResponse(id=request.id, error=error.error)

        if request.params.pushNotification:
            if not await self.set_push_notification_info(request.params.id, request.params.pushNotification):
                return SendTaskResponse(id=request.id, error=InvalidParamsError(message="Invalid push notification URL"))

        await self.upsert_task(request.params)

        task = await self.update_store(
            request.params.id, TaskStatus(state=TaskState.WORKING), None
        )
        await self.send_task_notification(task)

        query = self._get_user_query(request.params)
        try:
            agent_response = await self.agent.invoke(query, request.params.sessionId)
        except Exception as e:
            logger.exception("Agent invocation failed")
            raise ValueError(f"Agent invocation failed: {e}")

        return await self._process_agent_response(request, agent_response)

    async def on_send_task_subscribe(self, request: SendTaskStreamingRequest) -> AsyncIterable[SendTaskStreamingResponse] | JSONRPCResponse:
        try:
            if (error := self._validate_request(request)):
                return error

            await self.upsert_task(request.params)

            if request.params.pushNotification:
                if not await self.set_push_notification_info(request.params.id, request.params.pushNotification):
                    return JSONRPCResponse(id=request.id, error=InvalidParamsError(message="Invalid push URL"))

            sse_queue = await self.setup_sse_consumer(request.params.id, False)
            asyncio.create_task(self._run_streaming_agent(request))
            return self.dequeue_events_for_sse(request.id, request.params.id, sse_queue)

        except Exception as e:
            logger.error(f"❌ Error in stream: {e}")
            return JSONRPCResponse(id=request.id, error=InternalError(message="Streaming setup failed"))

    async def _process_agent_response(self, request: SendTaskRequest, agent_response: dict) -> SendTaskResponse:
        parts = [{"type": "text", "text": agent_response["content"]}]
        task_status = TaskStatus(
            state=TaskState.INPUT_REQUIRED if agent_response["require_user_input"] else TaskState.COMPLETED,
            message=Message(role="agent", parts=parts)
        )
        artifact = Artifact(parts=parts) if task_status.state == TaskState.COMPLETED else None

        task = await self.update_store(request.params.id, task_status, [artifact] if artifact else None)
        task_result = self.append_task_history(task, request.params.historyLength)
        await self.send_task_notification(task)
        return SendTaskResponse(id=request.id, result=task_result)

    def _get_user_query(self, task_send_params: TaskSendParams) -> str:
        part = task_send_params.message.parts[0]
        if not isinstance(part, TextPart):
            raise ValueError("Only text input is supported.")
        return part.text

    async def send_task_notification(self, task: Task):
        if not await self.has_push_notification_info(task.id):
            logger.info(f"ℹ️ No push info for task {task.id}")
            return
        info = await self.get_push_notification_info(task.id)
        await self.notification_sender_auth.send_push_notification(
            info.url, data=task.model_dump(exclude_none=True)
        )

    async def on_resubscribe_to_task(self, request) -> AsyncIterable[SendTaskStreamingResponse] | JSONRPCResponse:
        try:
            sse_queue = await self.setup_sse_consumer(request.params.id, True)
            return self.dequeue_events_for_sse(request.id, request.params.id, sse_queue)
        except Exception as e:
            logger.exception("Resubscribe failed")
            return JSONRPCResponse(id=request.id, error=InternalError(message=f"Resubscribe failed: {e}"))

    async def set_push_notification_info(self, task_id: str, push_notification_config: PushNotificationConfig):
        if not await self.notification_sender_auth.verify_push_notification_url(push_notification_config.url):
            return False
        await super().set_push_notification_info(task_id, push_notification_config)
        return True
