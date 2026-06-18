import dotenv

dotenv.load_dotenv()

import streamlit as st
import asyncio
import base64
from openai import OpenAI

from agents import Agent, Runner, SQLiteSession, WebSearchTool, FileSearchTool, ImageGenerationTool

VECTOR_STORE_ID = "vs_6a32c6999a6c81918aa9acc26f58d106"
client = OpenAI()

if "agent" not in st.session_state:
    st.session_state["agent"] = Agent(
        name="ChatGPT Clone",
        instructions="""
        너는 인생 코치다.

        다음은 사용자에 대한 응답으로 반드시 해야하는 지침이다:
        - 질문에 대한 답을 할 때는 반드시 조언, 팁을 제공해야한다.
        - 조언과 팁은 항상 최신 정보를 바탕으로 근거가 있어야 한다.
        - 사용자가 목표를 달성하면 축하 이미지를 그려야 한다.

        너는 다음 도구들을 사용할 수 있다:
        Web Search Tool: 
          - 조언, 팁에 대한 정보 검색을 해야할 때 사용.

        File Search Tool: 
          - 사용자가 자신과 관련된 사실에 대해 질문하거나, 특정 파일에 대해 질문할 때 사용.

        Image Generation Tool:
          - 축하 이미지를 그려줄 때 사용.
        """,
        tools=[
            WebSearchTool(),
            FileSearchTool(
                vector_store_ids=[VECTOR_STORE_ID],
                max_num_results=3,
            ),
            ImageGenerationTool(
                tool_config = {
                    "type": "image_generation",
                    "quality": "high",
                    "output_format": "jpeg",
                    "moderation": "low",
                    "partial_images": 1
                }
            )
        ],
    )

agent = st.session_state["agent"]

if "session" not in st.session_state:
    st.session_state["session"] = SQLiteSession(
        "chat-history",
        "chat-gpt-clone-memory.db",
    )

session = st.session_state["session"]


async def paint_history():
    messages = await session.get_items()

    for message in messages:
        if "role" in message:
            with st.chat_message(message["role"]):
                if message["role"] == "user":
                    content = message["content"]

                    if isinstance(content, str):
                        st.write(content)
                    elif isinstance(content, list):
                        for part in content:
                            if "image_url" in part:
                                st.image(part["image_url"])

                else:
                    if message["type"] == "message":
                        st.write(message["content"][0]["text"])

        if "type" in message:
            if message["type"] == "web_search_call":
                with st.chat_message("ai"):
                    st.write("웹 검색했음")
            elif message["type"] == "file_search_call":
                with st.chat_message("ai"):
                    st.write("파일 검색했음")
            elif message["type"] == "image_generation_call":
                image = base64.b64decode(message["result"])
                with st.chat_message("ai"):
                    st.image(image)


def update_status(status_container, event):
    status_messages = {
        "response.web_search_call.completed": ("웹 검색 완료", "complete"),
        "response.web_search_call.in_progress": (
            "웹 검색 시작",
            "running",
        ),
        "response.web_search_call.searching": ("웹 검색중...", "running"),
        "response.file_search_call.completed": (
            "파일 검색 완료.",
            "complete",
        ),
        "response.file_search_call.in_progress": (
            "파일 검색 시작",
            "running",
        ),
        "response.file_search_call.searching": (
            "파일 검색 중...",
            "running",
        ),
        "response.image_generation_call.generating": (
            "이미지 그리는 중...",
            "running",
        ),
        "response.image_generation_call.in_progress": (
            "이미지 그리는 중...",
            "running",
        ),
        "response.completed": ("", "complete"),
    }

    if event in status_messages:
        label, state = status_messages[event]
        status_container.update(label=label, state=state)


asyncio.run(paint_history())


async def run_agent(message):
    with st.chat_message("ai"):
        status_container = st.status("", expanded=False)
        text_placeholder = st.empty()
        image_placeholder = st.empty()
        response = ""

        stream = Runner.run_streamed(
            agent,
            message,
            session=session,
        )

        async for event in stream.stream_events():
            if event.type == "raw_response_event":
                update_status(status_container, event.data.type)

                if event.data.type == "response.output_text.delta":
                    response += event.data.delta
                    text_placeholder.write(response)
                elif event.data.type == "response.image_generation_call.partial_image":
                    image = base64.b64decode(event.data.partial_image_b64)
                    image_placeholder.image(image)


prompt = st.chat_input(
    "어시스턴트에게 메시지를 입력하세요",
    accept_file=True,
    file_type=["txt", "jpg", "jpeg", "png"],
)

if prompt:
    if "image_placeholder" in st.session_state:
        st.session_state["image_placeholder"].empty()
    if "text_placeholder" in st.session_state:
        st.session_state["text_placeholder"].empty()

    message = prompt.text

    for file in prompt.files:
        if file.type.startswith("text/"):
            with st.chat_message("ai"):
                with st.status("파일 업로드 중...") as status:
                    uploaded_file = client.files.create(
                        file=(file.name, file.getvalue()),
                        purpose="user_data",
                    )

                    status.update(label="파일 연결 중...")

                    client.vector_stores.files.create(
                        vector_store_id=VECTOR_STORE_ID,
                        file_id=uploaded_file.id,
                    )

                    status.update(label="파일 업로드 완료", state="complete")
        elif file.type.startswith("image/"):
            with st.status("이미지 업로드 중...") as status:
                file_bytes = file.getvalue()
                base64_data = base64.b64encode(file_bytes).decode("utf-8")
                data_uri = f"data:{file.type};base64,{base64_data}"

                asyncio.run(
                    session.add_items(
                        [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "input_image",
                                        "detail": "auto",
                                        "image_url": data_uri,
                                    }
                                ],
                            }
                        ]
                    )
                )

                status.update(label="이미지 업로드 완료", state="complete")
            with st.chat_message("human"):
                st.image(data_uri)

    if message:
        with st.chat_message("human"):
            st.write(message)

        asyncio.run(run_agent(message))

with st.sidebar:
    reset = st.button("메모리 리셋")
    if reset:
        asyncio.run(session.clear_session())
    st.write(asyncio.run(session.get_items()))
