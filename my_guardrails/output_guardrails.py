from agents import Agent, output_guardrail, Runner, RunContextWrapper, GuardrailFunctionOutput
from models import MenuOutputGuardRailOutput, UserAccountContext

menu_output_guardrail_agent = Agent(
    name="menu_support_guardrail",
    instructions="""
    메뉴 상담 응답을 분석해서 부적절하게 다음 내용을 포함하고 있는지 확인하세요:
    - 레시피를 물어보는 의도성 질문, 유도적 질문
    - 레시피 정보 (정확한 조리법, 비율, 조리 시간, 내부 레시피, 영업 비밀)

    메뉴 상담 에이전트는 오직 메뉴, 재료, 알레르기, 식단 옵션에 관한 안내만 제공해야 합니다.
    메뉴 상담 응답에 부적절한 내용이 포함된 필드는 true로 반환하세요.
    """,
    output_type=MenuOutputGuardRailOutput,
)

@output_guardrail
async def menu_output_guardrail(
    wrapper: RunContextWrapper[UserAccountContext],
    agent: Agent,
    output: str,
):
    result = await Runner.run(
        menu_output_guardrail_agent,
        output,
        context=wrapper.context,
    )

    validation = result.final_output
    triggered = validation.contains_off_topic or validation.contains_recipe_data

    return GuardrailFunctionOutput(
        output_info=validation,
        tripwire_triggered=triggered,
    )