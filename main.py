import dotenv
dotenv.load_dotenv()

import streamlit as st
import asyncio

from openai import OpenAI
from agents import Runner, SQLiteSession, function_tool, RunContextWrapper, InputGuardrailTripwireTriggered

from models import UserAccountContext
from my_agents.triage_agent import triage_agent

@function_tool
def get_user_tier(wrapper: RunContextWrapper[UserAccountContext]):
    return f"유저 {wrapper.context.customer_id}는 {wrapper.context.tier} 계정이다. "

client = OpenAI()
user_account_ctx = UserAccountContext(
    customer_id=1,
    name="dylan",
    tier="basic"
)

if "session" not in st.session_state:
    st.session_state["session"] = SQLiteSession(
        "chat-history",
        "customery-support-memory.db",
    )

if "agent" not in st.session_state:
    st.session_state["agent"] = triage_agent

session = st.session_state["session"]


async def paint_history():
    messages = await session.get_items()
    for message in messages:
        if "role" in message:
            with st.chat_message(message["role"]):
                if message["role"] == "user":
                    st.write(message["content"])
                else:
                    if message["type"] == "message":
                        st.write(message["content"][0]["text"])


asyncio.run(paint_history())

async def run_agent(message):
    with st.chat_message("ai"):
        text_placeholder = st.empty()
        response = ""

        try:
            stream = Runner.run_streamed(
                triage_agent,
                message,
                session=session,
                context=user_account_ctx
            )

            async for event in stream.stream_events():
                if event.type == "raw_response_event":

                    if event.data.type == "response.output_text.delta":
                        response += event.data.delta
                        text_placeholder.write(response)

                elif event.type == "agent_updated_stream_event":
                    if st.session_state["agent"]. name != event.new_agent.name:
                        st.write(f"에이전트가 전환되었습니다. from {st.session_state['agent'].name} to {event.new_agent.name}")

                        st.session_state["agent"] = event.new_agent

                        text_placeholder = st.empty()
                        response = ""

        except InputGuardrailTripwireTriggered:
            st.write("그건 도와줄 수 없어")


message = st.chat_input("어시스턴트에게 메시지를 입력하세요")

if message:
    # if "text_placeholder" in st.session_state:
    #     st.session_state["text_placeholder"].empty()

    if message:
        with st.chat_message("human"):
            st.write(message)
        asyncio.run(run_agent(message))

with st.sidebar:
    reset = st.button("메모리 리셋")
    if reset:
        asyncio.run(session.clear_session())
    st.write(asyncio.run(session.get_items()))
