import asyncio

from src.agent_state import AgentState
from src.schemas import VisionResult
from src.skills.vision import DesktopVisionClient

vision_client = DesktopVisionClient()


async def vision_skill_node(state: AgentState) -> dict:
    """
    Captures the screen and analyzes it with the Groq vision model. The model's
    answer IS the user-facing response, so it is returned directly and
    ``direct_response`` is set to skip the redundant formatter LLM call (A1).
    """
    logs = ["Initiating Screen Vision processing."]
    updates: dict = {"action_logs": logs}
    try:
        img_path = await asyncio.to_thread(vision_client.capture_screen)
        logs.append("Screenshot captured successfully.")

        prompt = (
            "Analyze the screenshot. Explain what is shown on screen and resolve "
            f"the user request: {state['query']}"
        )
        analysis_result = await vision_client.analyze_screenshot(img_path, prompt)
        logs.append("Analysis completed.")

        updates["skill_result"] = VisionResult(analysis=analysis_result).model_dump()
        updates["final_response"] = analysis_result
        updates["direct_response"] = True
    except Exception as e:
        logs.append(f"Vision capture error: {str(e)}")
        updates["skill_result"] = VisionResult(error=str(e)).model_dump()
    finally:
        vision_client.cleanup()

    return updates
