# # from services.skill_testing.nodes import executor_node, planner_node, route_after_executor, route_after_router, router_node
# # from fastapi import FastAPI, HTTPException
# # from pydantic import BaseModel
# # from typing import Optional, List, Dict, Any
# # import asyncio
# # import json
# # import os
# # import httpx
# # from openai import AsyncOpenAI
# # import numpy as np
# # from sklearn.feature_extraction.text import TfidfVectorizer
# # from sklearn.metrics.pairwise import cosine_similarity

# # # LangGraph
# # from langgraph.graph import StateGraph, END
# # from .state import AgentState
# # from .client import BackendClient

# # app = FastAPI(title="AG2 - Agent Orchestrator", version="1.0.0")
# # backend_client = BackendClient()

# # MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")

# # client = AsyncOpenAI(
# #     api_key=os.getenv("OPENAI_API_KEY") or "dummy_key",
# #     base_url=os.getenv("LLM_BASE_URL")
# # )
# # REGISTRY_URL = os.getenv("REGISTRY_URL", "http://skill-management:8001")


# # # --- Khởi tạo LangGraph ---

# # workflow = StateGraph(AgentState)

# # workflow.add_node("router", router_node)
# # workflow.add_node("planner", planner_node)
# # workflow.add_node("executor", executor_node)

# # async def dummy_approval_node(state: AgentState):
# #     print("-> [Human Approval Node] Auto-approving for API flow.")
# #     state.status = "executing"
# #     return state

# # workflow.add_node("human_approval", dummy_approval_node)

# # workflow.set_entry_point("router")
# # workflow.add_conditional_edges("router", route_after_router)
# # workflow.add_edge("planner", "human_approval")
# # workflow.add_edge("human_approval", "executor")
# # workflow.add_conditional_edges("executor", route_after_executor)

# # app_graph = workflow.compile()

# # # --- FastAPI Endpoints ---

# # class TaskRequest(BaseModel):
# #     task: str

# # @app.on_event("startup")
# # async def startup_event():
# #     print("AG2 Orchestrator Starting Up...")
# #     global vectorizer, tfidf_matrix, recipes
    
# #     recipe_path = os.path.join(os.path.dirname(__file__), "recipe.json")
# #     if os.path.exists(recipe_path):
# #         try:
# #             with open(recipe_path, "r", encoding="utf-8") as f:
# #                 recipes = json.load(f)
# #             # Khởi tạo TF-IDF Vectorizer cho Router
# #             texts = [r.get("description", "") for r in recipes]
# #             vectorizer = TfidfVectorizer()
# #             tfidf_matrix = vectorizer.fit_transform(texts)
# #             print("   [Startup] Indexed recipes successfully using TF-IDF.")
# #         except Exception as e:
# #             print(f"   [Startup] Error loading recipe.json: {e}")
# #     else:
# #         print("   [Startup] Warning: recipe.json not found!")

# # @app.post("/orchestrate")
# # async def orchestrate_task(request: TaskRequest):
# #     initial_state = AgentState(
# #         task=request.task,
# #         plan=[],
# #         current_step_index=0,
# #         past_steps=[],
# #         status="init",
# #         final_result=None,
# #         error=None,
# #     )
    
# #     try:
# #         print("--- STARTING LANGGRAPH WORKFLOW ---")
# #         final_state = await app_graph.ainvoke(initial_state)
        
# #         plan_executed = getattr(final_state, "plan", None)
# #         steps_log = getattr(final_state, "past_steps", None)
# #         final_result = getattr(final_state, "final_result", None)

# #         if plan_executed is None and isinstance(final_state, dict):
# #             plan_executed = final_state.get("plan")
# #             steps_log = final_state.get("past_steps")
# #             final_result = final_state.get("final_result")

# #         return {
# #             "status": "success",
# #             "task": request.task,
# #             "plan_executed": plan_executed,
# #             "steps_log": steps_log,
# #             "final_result": final_result
# #         }
# #     except Exception as e:
# #         raise HTTPException(status_code=500, detail=str(e))
# from fastapi import FastAPI, HTTPException, BackgroundTasks
# from pydantic import BaseModel
# from typing import Optional, List, Dict, Any
# import asyncio
# import json
# import os
# import httpx
# from openai import AsyncOpenAI
# import numpy as np
# from sklearn.feature_extraction.text import TfidfVectorizer
# from sklearn.metrics.pairwise import cosine_similarity

# # LangGraph
# from langgraph.graph import StateGraph, END
# from services.skill_testing.state import AgentState
# from services.skill_testing.client import BackendClient

# app = FastAPI(title="AG2 - Agent Orchestrator", version="1.0.0")
# backend_client = BackendClient()

# MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")

# client = AsyncOpenAI(
#     api_key=os.getenv("OPENAI_API_KEY"),
#     base_url=os.getenv("LLM_BASE_URL")
# )
# REGISTRY_URL = os.getenv("REGISTRY_URL", "http://skill-management:8001")

# # --- TF-IDF Router Variables ---
# vectorizer = None
# tfidf_matrix = None
# recipes = []

# # --- Định nghĩa các Node của LangGraph ---

# async def router_node(state: AgentState) -> AgentState:
#     print(f"-> [Router Node] Analyzing task: {state['task']}")
    
#     if tfidf_matrix is not None and len(recipes) > 0:
#         query_vec = vectorizer.transform([state["task"]])
#         similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
#         best_idx = np.argmax(similarities)
        
#         # SỬA TẠI ĐÂY: Lưu lại matched trước khi check threshold
#         best_recipe = recipes[best_idx] 
        
#         if similarities[best_idx] > 0.5:
#             print(f"   [Router] Found matched recipe: {best_recipe.get('recipe_id')}")
#             state["plan"] = best_recipe.get("subtasks", [])
#             # QUAN TRỌNG: Để nhảy sang Executor, status phải là awaiting_approval 
#             # để khớp với logic của route_after_router bên dưới.
#             state["status"] = "awaiting_approval" 
#             return state
#         else:
#             print(f"   [Router] Low score ({similarities[best_idx]:.2f}) for recipe: {best_recipe.get('recipe_id')}")

#     print("   [Router] No semantic match. Forwarding to Planner...")
#     state["status"] = "planning"
#     return state


# async def planner_node(state: AgentState) -> AgentState:
#     if state["status"] != "planning": return state
    
#     url = f"{REGISTRY_URL}/skills/tools"
#     async with httpx.AsyncClient() as http_client:
#         try:
#             resp = await http_client.get(url, timeout=10.0)
#             data = resp.json()
#             # QUAN TRỌNG: Lấy đúng danh sách từ key 'items' hoặc xử lý nếu là list
#             available_skills = data.get("items", data) if isinstance(data, dict) else data
#         except Exception as e:
#             print(f"   [Planner] Error fetching skills: {e}")
#             available_skills = []

#     # Nếu vẫn rỗng, Planner sẽ không có dữ liệu để lập kế hoạch
#     if not available_skills:
#         print("   [Planner] WARNING: No skills fetched from AG1!")
#         state["plan"] = [{"skill_id": "error_fallback", "input": {"reason": "Database AG1 rỗng hoặc lỗi kết nối"}}]
#         state["status"] = "executing"
#         return state
#     # 2. Gọi LLM để lập trình tự thực hiện
#     system_prompt = f"""
# Bạn là kiến trúc sư hệ thống.
# Nhiệm vụ:
# Phân tích 'Yêu cầu người dùng' và trích xuất dữ liệu để điền vào các Skill dưới định dạng JSON.
# DANH SÁCH SKILL:
# {json.dumps(available_skills, ensure_ascii=False, indent=2)}
# QUY TẮC TRÍCH XUẤT:
# 1. Nếu người dùng cung cấp Log lỗi/Traceback, hãy đưa TOÀN BỘ nội dung đó vào trường 'stacktrace'.
# 2. Nếu người dùng chỉ nhắc đến tên file mà không có đường dẫn, hãy giữ nguyên tên file ở trường 'source_path'.
# 3. TUYỆT ĐỐI KHÔNG tự bịa ra các giá trị mẫu hoặc dùng dấu ngoặc nhọn <...>. 
# 4. Nếu dữ liệu bị thiếu trầm trọng, hãy gán giá trị 'MISSING_DATA' cho trường đó để Executor báo lỗi thay vì chạy bậy.
# Format trả về phải là một đối tượng JSON (json object) như sau:
# {{"plan": [
#     {{
#         "skill_id": "tên_skill",
#         "input": {{
#             "trường": "giá trị thật"
#         }}
#     }}
# ]}}
# """
#     response = await client.chat.completions.create(
#         model=MODEL_NAME,
#         messages=[{"role": "system", "content": system_prompt},
#                   {"role": "user", "content": state["task"]}],
#         response_format={"type": "json_object"}
#     )
    
#     plan_data = json.loads(response.choices[0].message.content)
#     state["plan"] = plan_data.get("plan", [])
#     state["status"] = "awaiting_approval"
    
#     print(f"   => Dynamic Plan Created: {[s['skill_id'] for s in state['plan']]}")
#     return state

#     # Tại AG2 - services/agent_orchestrator/main.py

# async def executor_node(state: AgentState) -> Dict:
#     plan = state.get("plan", [])
#     idx = state.get("current_step_index", 0)

#     # 1. Kiểm tra thoát Graph
#     if idx >= len(plan):
#         return {"status": "completed"}

#     current_step = plan[idx]
#     skill_to_find = current_step.get("skill_id") # Có thể là UUID hoặc Name
#     user_input = current_step.get("input", {})

#     # res_content = "No output"
#     step_tag = f"Success: {skill_to_find}"

#     async with httpx.AsyncClient(timeout=30.0) as http_client:
#         try:
#             # Tìm UUID từ  GET (/skills/tools)
#             registry_resp = await http_client.get(f"{REGISTRY_URL}/skills/tools")
#             registry_resp.raise_for_status()
#             reg_data = registry_resp.json()
#             # Lấy list từ key 'items' (nếu AG1 trả về dict) hoặc dùng trực tiếp nếu là list
#             skills_list = reg_data.get("items", reg_data) if isinstance(reg_data, dict) else reg_data

#             target_info = next(
#                 (s for s in skills_list if s.get('skill_id') == skill_to_find or s.get('id') == skill_to_find or s.get('name') == skill_to_find), 
#                 None)
#             if not target_info:
#                 raise ValueError(f"Skill '{skill_to_find}' không tồn tại.")
#             skill_uuid = target_info.get('skill_id') or target_info.get('id')

#             # Lấy Full JSON GET(/skills/{uuid})
#             tool_resp = await http_client.get(f"{REGISTRY_URL}/skills/{skill_uuid}")
#             tool_resp.raise_for_status()
#             full_skill_json = tool_resp.json()

#             # 4. Bóc tách dữ liệu từ 'metadata'
#             metadata = full_skill_json.get("metadata", {})
#             input_schema = metadata.get("input", {})
#             output_schema = metadata.get("output", {})
#             description = full_skill_json.get("description", "")

#             # 5. Build Prompt cho LLM (Sử dụng Blueprint)
#             system_instruction = f"""Bạn là công cụ: {full_skill_json.get('name')}
# Mô tả nhiệm vụ: {description}
# HƯỚNG DẪN THỰC THI (INPUT SCHEMA):
# {json.dumps(input_schema, ensure_ascii=False)}
# ĐỊNH DẠNG TRẢ VỀ (OUTPUT SCHEMA):
# {json.dumps(output_schema, ensure_ascii=False)}
# YÊU CẦU: Xử lý dữ liệu đầu vào và trả về JSON (json) khớp hoàn toàn với Output Schema"""

#             response = await client.chat.completions.create(
#                 model=MODEL_NAME,
#                 messages=[
#                     {"role": "system", "content": system_instruction},
#                     {"role": "user", "content": f"DỮ LIỆU ĐẦU VÀO: {json.dumps(user_input)}"}
#                 ],
#                 response_format={"type": "json_object"}
#             )
#             res_content = response.choices[0].message.content
#             # state["past_steps"].append((f"Success: {skill_to_find}", res_content))
#         except Exception as e:
#             print(f"❌ [Executor Error]: {str(e)}")
#             state["past_steps"].append((f"Failed: {skill_to_find}", str(e)))

#     new_idx = idx + 1
#     new_status = "completed" if new_idx >= len(plan) else "executing"

#     return {
#         "past_steps": [(step_tag, res_content)],
#         "current_step_index": new_idx,
#         "status": new_status,
#         "final_result": res_content if new_status == "completed" else state.get("final_result")
#     }

# # --- Logic Điều Hướng (Conditional Edges) ---

# def route_after_router(state: AgentState) -> str:
#     if state["status"] == "awaiting_approval":
#         return "human_approval"
#     return "planner"

# def route_after_planner(state: AgentState) -> str:
#     return "human_approval"

# def route_after_executor(state: AgentState) -> str:
#     plan = state.get("plan", [])
#     idx = state.get("current_step_index", 0)
#     if idx >= len(plan):
#         return END
#     if state["status"] == "completed":
#         return END
#     return "executor"

# # --- Khởi tạo LangGraph ---

# workflow = StateGraph(AgentState)

# workflow.add_node("router", router_node)
# workflow.add_node("planner", planner_node)
# workflow.add_node("executor", executor_node)

# async def dummy_approval_node(state: AgentState):
#     print("-> [Human Approval Node] Auto-approving for API flow.")
#     state["status"] = "executing"
#     return state

# workflow.add_node("human_approval", dummy_approval_node)

# workflow.set_entry_point("router")
# workflow.add_conditional_edges("router", route_after_router)
# workflow.add_edge("planner", "human_approval")
# workflow.add_edge("human_approval", "executor")
# workflow.add_conditional_edges("executor", route_after_executor)

# app_graph = workflow.compile()

# # --- FastAPI Endpoints ---

# class TaskRequest(BaseModel):
#     task: str

# @app.on_event("startup")
# async def startup_event():
#     print("AG2 Orchestrator Starting Up...")
#     global vectorizer, tfidf_matrix, recipes
    
#     recipe_path = os.path.join(os.path.dirname(__file__), "recipe.json")
#     if os.path.exists(recipe_path):
#         try:
#             with open(recipe_path, "r", encoding="utf-8") as f:
#                 recipes = json.load(f)
#             # Khởi tạo TF-IDF Vectorizer cho Router
#             texts = [r.get("description", "") for r in recipes]
#             vectorizer = TfidfVectorizer()
#             tfidf_matrix = vectorizer.fit_transform(texts)
#             print("   [Startup] Indexed recipes successfully using TF-IDF.")
#         except Exception as e:
#             print(f"   [Startup] Error loading recipe.json: {e}")
#     else:
#         print("   [Startup] Warning: recipe.json not found!")

# @app.post("/orchestrate")
# async def orchestrate_task(request: TaskRequest):
#     initial_state = {
#         "task": request.task,
#         "plan": [],
#         "current_step_index": 0,
#         "past_steps": [],
#         "status": "init",
#         "final_result": None,
#         "error": None
#     }
    
#     try:
#         print("--- STARTING LANGGRAPH WORKFLOW ---")
#         final_state = await app_graph.ainvoke(initial_state)
        
#         return {
#             "status": "success",
#             "task": final_state["task"],
#             "plan_executed": final_state["plan"],
#             "steps_log": final_state["past_steps"],
#             "final_result": final_state["final_result"]
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

import operator
from typing import Annotated, Dict, Union, List

from langgraph.graph import StateGraph, END
from services.skill_testing.core import evaluate_node, execute_node
from services.skill_testing.core.plan_node import plan_node
from services.skill_testing.core.select_skill_node import select_skill_node
from services.skill_testing.state import AgentState


def route_after_select(state: AgentState) -> str:
    """Quyết định đi tiếp tới Execute hay sang Evaluate nếu không tìm thấy skill"""
    if state.selected_skill:
        return "execute"
    return "evaluate"

def route_after_evaluation(state: AgentState) -> str:
    if state.is_finished:
        return END

    if not state.plan or len(state.plan) == 0:
        return "plan"

    if state.retry_count > 0:
        return "execute"

    return "select"


def create_agent_graph():
    workflow = StateGraph(AgentState)

    # Lưu ý: Nếu node cần thêm tham số (như model_client), bạn dùng lambda hoặc partial
    workflow.add_node("plan", plan_node)
    workflow.add_node("select", select_skill_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("evaluate", evaluate_node)


    workflow.set_entry_point("plan")

    workflow.add_edge("plan", "select")

    # Select -> Có thể đi tới Execute hoặc Evaluate (Nếu không thấy skill)
    workflow.add_conditional_edges(
        "select",
        route_after_select,
        {
            "execute": "execute",
            "evaluate": "evaluate"
        }
    )
    workflow.add_edge("execute", "evaluate")

    workflow.add_conditional_edges(
        "evaluate",
        route_after_evaluation,
        {
            "plan": "plan",           # Re-plan
            "execute": "execute",     # Retry
            "select": "select",       # Next task
            END: END                  # Finished
        }
    )

    return workflow.compile()

async def orchestrate_task(request_data: dict, model_client, skill_client):
    """
    Hàm nhận request từ API, khởi tạo state và chạy Graph.
    """
    initial_state = AgentState(
        user_context={
            "code": request_data.get("code", ""),
            "stacktrace": request_data.get("stacktrace", ""),
            "message": request_data.get("message", "")
        },
        # Các giá trị mặc định đã có trong BaseModel
    )

    app = create_agent_graph()
    
    config = {"configurable": {"model_client": model_client, "skill_client": skill_client}}

    # Chạy đồ thị (Stream kết quả hoặc lấy kết quả cuối cùng)
    final_state = await app.ainvoke(initial_state, config=config)
    
    return {
        "status": "success" if final_state.get("final_answer", "").startswith("SUCCESS") else "failed",
        "answer": final_state.get("final_answer"),
        "steps_taken": final_state.get("step_count"),
        "history": final_state.get("history")
    }
