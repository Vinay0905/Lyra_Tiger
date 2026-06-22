from src.agent_state import AgentState
from src.skills.vision import DesktopVisionClient

vision_client = DesktopVisionClient()

def vision_skill_node(state: AgentState) -> dict:
    logs = ["Initiating Screen Vision processing."]
    try:
        img_path = vision_client.capture_screen()
        logs.append("Screenshot captured successfully.")
        
        prompt = f"Analyze the screenshot. Explain what is shown on screen and resolve the user request: {state['query']}"
        analysis_result = vision_client.analyze_screenshot(img_path, prompt)
        
        logs.append("Analysis completed.")
        logs.append(f"Groq Vision Response:\n{analysis_result}")
    except Exception as e:
        logs.append(f"Vision capture error: {str(e)}")
    finally:
        vision_client.cleanup()
        
    return {
        "action_logs": logs
    }
