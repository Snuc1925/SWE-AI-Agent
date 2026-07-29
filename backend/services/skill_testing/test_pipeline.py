import asyncio
import json
from typing import List, Dict, Any

from langgraph.graph import StateGraph, END

from services.skill_testing.core.llm_client import OpenAIClient
from services.skill_testing.state import AgentState
from services.skill_testing.core.registry import semantic_registry
from services.skill_testing.core.skill_client import SkillExecutionClient

from services.skill_testing.core.plan_node import plan_node
from services.skill_testing.core.select_skill_node import select_skill_node
from services.skill_testing.core.execute_node import execute_node
from services.skill_testing.core.evaluate_node import evaluate_node

import os
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("Missing OPENAI_API_KEY environment variable")

# Định nghĩa bộ Router Edge điều phối rẽ nhánh & Tối ưu chi phí (AG2 CORE LOGIC)
def route_decision(state: AgentState):
    # Nếu cờ báo kết thúc được bật từ Node Evaluator
    if state.is_finished:
        print(f"\n🏁 [SYSTEM END] -> Vòng lặp khép kín kết thúc!")
        print(f"📄 Kết quả cuối cùng: {state.final_answer}")
        print(f"📊 Chỉ số thực thi: Total Steps attempted: {state.step_count}")
        return END
        
    # Cơ chế Circuit Breaker tự động ngắt nếu số bước hành động vượt quá giới hạn an toàn
    if state.step_count >= state.max_total_steps:
        print(f"\n🚨 [CIRCUIT BREAKER] Cảnh báo lặp vô hạn! Ngắt luồng tại bước thứ {state.step_count} để bảo vệ ví của User.")
        return END

    # Thuật toán rẽ nhánh Error-driven: Nếu last_observation chứa chuỗi "error: cannot find symbol" và "class User", điều hướng luồng về evaluate_node
    if state.last_observation and "error: cannot find symbol" in state.last_observation and "class User" in state.last_observation:
        print("🔄 [AG2 ROUTER] Detected missing User class error. Routing to evaluate_node for stub generation.")
        return "evaluate_node"

    # Nếu phát hiện lỗi và retry_count được kích hoạt -> Quay lại Executor chạy lại
    if state.retry_count > 0:
        print(f"🔄 [AG2 ROUTER] Phát hiện lỗi. Kích hoạt Retry vòng {state.retry_count}. Chuyển hướng quay lại Node Executor.")
        return "executor_node"

    # Nếu phát hiện kế hoạch trống (do vừa reset để Re-plan) -> Quay lại Planner
    if not state.plan:
        print(f"🔄 [AG2 ROUTER] Kế hoạch trống (đang yêu cầu Re-plan). Chuyển hướng về Node Planner.")
        return "plan_node"

    # Happy Path: Chuyển sang Task tiếp theo trong Kế hoạch
    print(f"➡️ [AG2 ROUTER] Tác vụ hiện tại hoàn tất. Di chuyển tới bước tiếp theo trong kế hoạch.")
    return "select_skill_node"


import httpx
async def run_pipeline(code_content: str = None, filename: str = "LoginService.java", stacktrace: str = "NullPointerException at LoginService:42", message: str = "Sửa lỗi login"):
    print("=========================================================")
    print("🚀 KÍCH HOẠT ĐỒ THỊ ĐIỀU PHỐI AG2 ──> KẾT NỐI REAL AG1 🚀")
    print("=========================================================\n")
    
    # 1. Gọi sang cổng 8001 của Skill Management để bốc danh sách skill động
    AG1_ENDPOINT = "http://127.0.0.1:8001/skills"
    AG1_TOOLS_ENDPOINT = "http://127.0.0.1:8001/skills/tools"
    print(f"api key:  {api_key}\n")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(AG1_TOOLS_ENDPOINT, timeout=10.0)
            if response.status_code == 200:
                tool_list = response.json()
                print(f"✅ Tải thành công {len(tool_list)} kỹ năng từ Microservice AG1!")
            else:
                print(f"⚠️ Lỗi kết nối API đầu ra.")
                tool_list = [
                    {"name": "analyze-stacktrace", "description": "Phân tích java stacktrace", "skill_id": "analyze-stacktrace"},
                    {"name": "read-code-context", "description": "Đọc mã nguồn Java xung quanh dòng chỉ định", "skill_id": "read-code-context"},
                    {"name": "suggest-java-fix", "description": "Ghi đè bản vá lỗi Java", "skill_id": "suggest-java-fix"},
                    {"name": "debug-java-null-pointer", "description": "Biên dịch javac kiểm tra lỗi cú pháp Java", "skill_id": "debug-java-null-pointer"}
                ]
        except Exception as e:
            print(f"❌ Không thể kết nối AG1 ({str(e)}). Dùng dữ liệu dự phòng.")
            tool_list = [
                {"name": "analyze-stacktrace", "description": "Phân tích java stacktrace", "skill_id": "analyze-stacktrace"},
                {"name": "read-code-context", "description": "Đọc mã nguồn Java xung quanh dòng chỉ định", "skill_id": "read-code-context"},
                {"name": "suggest-java-fix", "description": "Ghi đè bản vá lỗi Java", "skill_id": "suggest-java-fix"},
                {"name": "debug-java-null-pointer", "description": "Biên dịch javac kiểm tra lỗi cú pháp Java", "skill_id": "debug-java-null-pointer"}
            ]

    # 2. Nạp mảng dữ liệu thật này vào Registry để Planner phân rã nhiệm vụ
    semantic_registry.build_index(tool_list)
    skill_client = SkillExecutionClient()
    llm_client = OpenAIClient(api_key=api_key)
    
    # 3. Kích hoạt luồng chạy LangGraph với initial_state
    if code_content is None:
        code_content = """class User {
    private String name;
    public User(String name) { this.name = name; }
    public String getName() { return this.name; }
}

public class LoginService {
    public void login(User user) {
        if (user != null) {
            String name = user.getName();
        }
    }
}"""
    skill_client.setup_initial_workspace(code_content, filename)
    
    initial_state = {
        "user_context": {
            "code": code_content,
            "stacktrace": stacktrace,
            "message": message
        },
        "plan": [],
        "current_step_idx": 0,
        "step_count": 0,
        "history": []
    }
    
    
    async def p_node(state):
        return await plan_node(state, llm_client)

    async def s_node(state):
        return await select_skill_node(state)

    async def ex_node(state):
        return await execute_node(state, llm_client, skill_client)

    async def ev_node(state):
        return await evaluate_node(state, llm_client, skill_client)

    workflow = StateGraph(AgentState)
    
    workflow.add_node("plan_node", p_node)
    workflow.add_node("select_skill_node", s_node)
    workflow.add_node("executor_node", ex_node)
    workflow.add_node("evaluate_node", ev_node)

    workflow.set_entry_point("plan_node")
    workflow.add_edge("plan_node", "select_skill_node")
    workflow.add_edge("select_skill_node", "executor_node")
    workflow.add_edge("executor_node", "evaluate_node")
    
    # Thiết lập Cạnh điều kiện từ Node Evaluator (Đóng vai trò Router AG2)
    workflow.add_conditional_edges("evaluate_node", route_decision)

    app = workflow.compile()
    
    final_output = await app.ainvoke(initial_state)
    print("\n🏁 [SYSTEM END] Luồng chạy tích hợp thực tế hoàn thành rực rỡ!")
    return final_output
if __name__ == "__main__":
    asyncio.run(run_pipeline())
