import json
import re
import os
from services.skill_testing.state import AgentState

async def evaluate_node(state: AgentState, model_client, skill_client=None):
    state.step_count += 1
    if state.step_count > state.max_total_steps:
        state.is_finished = True
        state.final_answer = f"TERMINATED: Safety limit reached ({state.max_total_steps} steps). Potential infinite loop."
        return state

    if not state.plan or state.current_step_idx >= len(state.plan):
        state.is_finished = True
        state.final_answer = "TERMINATED: No active plan to evaluate."
        return state

    current_task = state.plan[state.current_step_idx]
    
    # --- [TASK 5] Error-driven Stub Generation ---
    # Khi nhận diện last_observation chứa từ khóa "error: cannot find symbol: class User", không được crash hệ thống.
    if state.last_observation and "error: cannot find symbol: class User" in state.last_observation:
        print("⚠️ [ERROR-DRIVEN STUB GENERATION] Detected missing class User in compilation output. Generating stub...")
        
        # Bẻ luồng ép LLM sinh ra nội dung file giữ chỗ (User.java rỗng)
        system_prompt = "You are a Java Stub Code Generator."
        user_prompt = (
            "The compiler failed because 'class User' is missing. "
            "Please generate a minimal Java class definition for 'User' (e.g. package declarations if any, public class User with empty constructor or minimal stub methods like getName() returning String or empty string). "
            "Output ONLY the Java code, no markdown block syntax, no extra text."
        )
        
        try:
            stub_code = await model_client.call(system_prompt, user_prompt)
            # Remove any markdown format code block if present
            if "```" in stub_code:
                code_match = re.search(r"```(?:java)?\s*(.*?)\s*```", stub_code, re.DOTALL)
                if code_match:
                    stub_code = code_match.group(1)
            stub_code = stub_code.strip()
        except Exception as e:
            print(f"❌ LLM call failed for Stub Generation: {e}. Falling back to default stub.")
            stub_code = "public class User {\n    public String getName() { return \"\"; }\n}"
            
        # Điều hướng skill_client ghi file vật lý xuống ổ cứng workspace/ cạnh file cũ
        if skill_client:
            skill_client.setup_initial_workspace(stub_code, "User.java")
            print("💾 [STUB GENERATOR] Wrote stub User.java using skill_client.")
        else:
            # Fallback direct file write
            fallback_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "workspace", "src", "main", "java")
            )
            os.makedirs(fallback_dir, exist_ok=True)
            with open(os.path.join(fallback_dir, "User.java"), "w", encoding="utf-8") as f:
                f.write(stub_code)
            print("💾 [STUB GENERATOR] Wrote stub User.java directly.")
            
        # Thiết lập để chạy lại biên dịch ở bước tiếp theo mà không crash
        state.retry_count = 1
        state.reflection.append("🔄 Stub User.java generated due to missing class compilation error. Retrying compiler.")
        state.last_observation = "Stub User.java created. Retrying compiler step."
        return state

    system_prompt = f"""
    You are a Quality Assurance Engineer. Evaluate if the task was completed successfully based on the observation.
    GOAL: {state.goal or state.user_context['message']}
    CURRENT TASK: {current_task}
    OBSERVATION: {state.last_observation}
    INSTRUCTIONS:
    - If the observation shows the task succeeded or the goal for this step is met, return {{"is_success": true, "analysis": "..."}}
    - If it failed, timed out, or returned an error, return {{"is_success": false, "analysis": "..."}}
    - Output ONLY JSON.
    """
    response = await model_client.call(system_prompt, "Evaluate the result.")
    try:
        evaluation = json.loads(response)
        is_success = evaluation.get("is_success", False)
        analysis = evaluation.get("analysis", "No analysis provided.")
    except Exception as e:
        is_success = False 
        analysis = f"Failed to parse evaluation JSON: {str(e)}"

    
    if is_success:
        state.retry_count = 0 
        state.reflection.append(f"✅ Step {state.current_step_idx + 1} Success: {analysis}")
        state.current_step_idx += 1
        
        if state.current_step_idx >= len(state.plan):
            state.is_finished = True
            state.final_answer = f"SUCCESS: All steps completed. Final analysis: {analysis}"
        else:
            state.selected_skill = None
            state.last_observation = None
    
    else:
        state.reflection.append(f"❌ Step {state.current_step_idx + 1} Failed: {analysis}")
        
        if state.retry_count < 1: # Cho phép thử lại 1 lần (tổng 2 lần chạy)
            state.retry_count += 1

        elif state.replan_count < state.max_replans:
            state.replan_count += 1
            state.retry_count = 0
            state.plan = []
            state.current_step_idx = 0
            state.reflection.append(f"🔄 Re-planning attempt {state.replan_count}/{state.max_replans} due to failure.")
        
        else:
            state.is_finished = True
            state.final_answer = generate_fallback_suggestion(state)

    return state

def generate_fallback_suggestion(state: AgentState) -> str:
    """Tạo báo cáo lỗi và gợi ý (Helper function - không dùng 'self')"""
    summary = "❌ FAILED: I have exhausted all retries and re-planning attempts.\n"
    summary += f"- Steps attempted: {state.step_count}\n"
    summary += f"- Last failure: {state.reflection[-1] if state.reflection else 'Unknown'}\n"
    if hasattr(state, 'missing_skills_log') and state.missing_skills_log:
        summary += f"- Missing tools for: {', '.join(state.missing_skills_log)}\n"
    summary += "\nSUGGESTION: The task might require a skill not currently in the library, or the provided source code/context is insufficient."
    return summary