from agents import Agent, Runner, RunContextWrapper, GuardrailFunctionOutput, input_guardrail
from models import UserAccountContext, InputGuardRailOutput

input_guardrail_agent = Agent(
    name="Input Guardrail Agent",
    instructions="""
    사용자의 요청이 레스토랑 메뉴, 재료, 알레르기, 음식 주문, 테이블 예약, 고객 불만 처리와 명확히 관련되어 있는지 확인하세요.
    요청이 주제에서 벗어난 경우, 트립와이어가 작동한 이유를 반환하세요.

    대화 초반에는 사용자와 간단한 잡담을 나눌 수 있지만,
    레스토랑 메뉴, 재료, 알레르기, 음식 주문, 테이블 예약, 고객 불만 처리와 관련 없는 요청은 도와주지 마세요.
    """,
    output_type=InputGuardRailOutput,
)


@input_guardrail
async def off_topic_guardrail(
    wrapper: RunContextWrapper[UserAccountContext],
    agent: Agent[UserAccountContext],
    input,
):
    result = await Runner.run(input_guardrail_agent, input, context=wrapper.context)
    return GuardrailFunctionOutput(
        output_info=result.final_output,
        tripwire_triggered=result.final_output.is_off_topic,
    )