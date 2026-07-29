import json
from services.skill_testing.state import AgentState

from .skill_manager import SkillManager
from .registry import semantic_registry

async def plan_node(state: AgentState, model_client):
    print("--- [Planning Node] Generating plan based on user context and available skills ---")
    
    available_tools = semantic_registry.get_all_tools()
    capabilities = SkillManager.get_capabilities(available_tools)
    
    # Sửa lại system_prompt bên trong plan_node.py của ní
    system_prompt = f"""
    You are the Lead Software Architect AI. Your job is to analyze a Java software issue and generate a sequential plan to fix it.
    CRITICAL RULE:
    You must ONLY use the exact tool names listed in the  AVAILABLE TOOLS catalog below to build your plan.
    Do NOT create custom text, instructions, or sub-steps like 'check_user_object_for_null'. 
    Every element in your plan list MUST match one of the available tool names perfectly.
    AVAILABLE TOOLS CATALOG FROM AG1 REGISTRY:
        {capabilities}
    Output a valid JSON object containing exactly one field 'plan', which is a list of strings representing the selected tool names in order.
    Example: {{"plan": ["analyze-stacktrace", "suggest-java-fix", "debug-java-null-pointer"]}}
    """
    user_prompt = f"""
    CONTEXT:
    Code: {state.user_context['code']}
    Error: {state.user_context['stacktrace']}
    Request: {state.user_context['message']}
    PREVIOUS REFLECTION (IF ANY):
    {state.reflection}
    """
    response = await model_client.call(system_prompt, user_prompt) #TODOS: xem lai interface cua model_client
    if not state.goal:
        state.goal = state.user_context.get('message')
        
    try:
        plan_data = json.loads(response)
        state.plan = plan_data.get("plan", [])
        state.current_step_idx = 0
        print(f"📝 [PLANNER LOG] Kế hoạch được thiết lập thành công: {state.plan}")
    except Exception as e:
        print(f"⚠️ [PLANNER ERROR] Không thể phân tích JSON từ LLM. Kích hoạt fallback thủ công. Lỗi: {e}")
        state.plan = ["Manual_analysis_fallback_task"]
        state.current_step_idx = 0
    return state