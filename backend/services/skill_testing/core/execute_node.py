# import json
# from services.skill_testing.state import AgentState
# from services.skill_testing.core.registry import semantic_registry

# async def execute_node(state: AgentState, model_client, skill_client):
#     """
#     Node thuc thi: 
#     1. Lay schema cua skill tu RAM Cache.
#     2. Dung LLM de boc tach tham so tu context.
#     3. Goi API thuc thi skill.
#     """
#     skill_name = state.selected_skill
#     skill_info = semantic_registry.get_skill_by_name(skill_name)
    
#     if not skill_info:
#         state.last_observation = f"Error: Skill '{skill_name}' not found in cache."
#         return state

#     state.step_count += 1
#     input_schema = skill_info.get("input", {})
    
#     system_prompt = f"""
#     You are a Parameter Extractor. Your task is to extract arguments for the skill '{skill_name}' 
#     based on its JSON Schema and the provided user context.
#     SKILL INPUT SCHEMA:
#     {json.dumps(input_schema, indent=2)}
#     INSTRUCTIONS:
#     - Look at the code, error, and message in the context.
#     - Extract exact values for each required field in the schema.
#     - Output ONLY a JSON object containing the arguments.
#     """
    
#     user_prompt = f"""
#     USER CONTEXT:
#     Code: {state.user_context['code']}
#     Error: {state.user_context['stacktrace']}
#     Message: {state.user_context['message']}
#     """
    
    
#     arg_response = model_client.call(system_prompt, user_prompt)
    
#     try:
#         args = json.loads(arg_response)
#         state.last_thought = f"Extracted arguments for {skill_name}: {args}"
        
#         print(f"DEBUG: Executing skill {skill_name} (ID: {skill_info.id}) via API...")
        
#         # Gia su skill_client la BackendClient ma chung ta da ban o cac cau truoc
#         execution_result = await skill_client.execute_skill(skill_name, args)
        
#         # Luu ket qua vao observation
#         state.last_observation = json.dumps(execution_result)
#         print(f"📦 [OBSERVATION] -> Kết quả thô từ hệ thống: {state.last_observation}")
        
#     except Exception as e:
#         state.last_observation = f"Execution failed: {str(e)}"
#         print(f"❌ [SYSTEM ERROR] -> Quá trình thực thi kỹ năng bị gián đoạn: {str(e)}")
        
#     state.history.append({
#         "step": state.current_step_idx,
#         "task": state.current_task,
#         "skill": skill_name,
#         "observation": state.last_observation
#     })
    
#     return state

# services/skill_testing/core/execute_node.py
import json
from services.skill_testing.state import AgentState
from services.skill_testing.core.registry import semantic_registry

async def execute_node(state: AgentState, model_client, skill_client):
    """
    Node thực thi (Executor): 
    1. Xác thực tên kỹ năng dạng chuỗi (str) từ Registry.
    2. Dùng LLM bóc tách tham số đầu vào tương ứng dựa theo ngữ cảnh lỗi của User.
    3. Gọi API thực thi kỹ năng ngầm và lưu kết quả.
    """
    skill_name = state.selected_skill
    state.step_count += 1
    print(f"\n🚀 [EXECUTE NODE] -> Đang kích hoạt kỹ năng: '{skill_name}' (Bước tổng thể: {state.step_count})")
    skill_info = state.user_context.get("current_skill_metadata", {})
    
    if not skill_info:
        state.last_observation = json.dumps({"status": "FAILED", "message": "Thiếu dữ liệu SOP"})
        return state
    
    skill_instructions = skill_info.get("raw_content") or skill_info.get("full_markdown") or ""
    metadata = skill_info.get("metadata", {})
    input_schema = metadata.get("input", {})


    # 2. Thiết lập Prompt tối giản giúp LLM tự định hình tham số dựa theo Tên kỹ năng
    system_prompt = f"""
    You are a Software Engineering Parameter Extractor for the skill: '{skill_name}'.
    Your job is to look at the user's code context, error log, and request to extract the precise arguments required to run this skill.
    
    EXPECTED ARGUMENTS LOGIC BASED ON SKILL NAME:
    - If skill is 'analyze-stacktrace' or 'debug-java-null-pointer': extract 'stacktrace' and 'source_path'.
    - If skill is 'read-code-context': extract 'file' and 'line' (as integer).
    - If skill is 'suggest-java-fix': extract 'file', 'line' (as integer), and 'variable'.
    
    INSTRUCTIONS:
    1. Generate a flat JSON object containing only the key-value pairs of extracted parameters.
    2. Do NOT add any extra conversational text. Output ONLY valid JSON.
    """
    
    user_prompt = f"""
    USER CONTEXT TO EXTRACT FROM:
    - Source Code: {state.user_context.get('code', '')}
    - Stacktrace/Error: {state.user_context.get('stacktrace', '')}
    - User Message: {state.user_context.get('message', '')}
    """
    
    # Gọi LLM xử lý bóc tách tham số
    arg_response = await model_client.call(system_prompt, user_prompt)
    
    try:
        # Giải mã tham số cấu trúc JSON
        args = json.loads(arg_response)
        state.last_thought = f"Extracted arguments for {skill_name}: {args}"
        print(f"💡 [AGENT THOUGHT] -> Tham số bóc tách thành công cho '{skill_name}': {args}")
        
        print(f"🤖 [SYSTEM ACTION] -> Bắn lệnh thực thi kỹ năng '{skill_name}' qua Client...")
        
        # 3. Gọi sang client độc lập (Sử dụng tên skill_name làm định danh chính)
        execution_result = await skill_client.execute_skill(skill_name, args)
        
        # Lưu kết quả thô nhận được từ hệ thống vào observation để mồi cho evaluate_node
        state.last_observation = json.dumps(execution_result, ensure_ascii=False)
        print(f"📦 [OBSERVATION] -> Kết quả thô từ hệ thống: {state.last_observation}")
        
    except Exception as e:
        state.last_observation = json.dumps({"status": "FAILED", "stdout": "", "stderr": str(e), "message": "Gãy định dạng JSON"}, ensure_ascii=False)
        print(f"❌ [SYSTEM ERROR] -> Quá trình thực thi kỹ năng bị gián đoạn: {str(e)}")
        
    # Ghi nhận vết lịch sử chạy ngầm của hệ thống
    state.history.append({
        "step": state.current_step_idx,
        "task": state.current_task,
        "skill": skill_name,
        "observation": state.last_observation
    })
    
    return state