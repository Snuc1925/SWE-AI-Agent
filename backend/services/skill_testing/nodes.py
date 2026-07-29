from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import json
import os
import httpx
from openai import AsyncOpenAI
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# LangGraph
from .state import AgentState
from .client import BackendClient

app = FastAPI(title="AG2 - Agent Orchestrator", version="1.0.0")
backend_client = BackendClient()

MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")

client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL")
)
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://skill-management:8001")

# --- TF-IDF Router Variables ---
vectorizer = None
tfidf_matrix = None
recipes = []

# --- Định nghĩa các Node của LangGraph ---

async def router_node(state: AgentState) -> AgentState:
    print(f"-> [Router Node] Analyzing task: {state.task}")
    
    if tfidf_matrix is not None and len(recipes) > 0:
        query_vec = vectorizer.transform([state.task])
        similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
        best_idx = np.argmax(similarities)
        
        # SỬA TẠI ĐÂY: Lưu lại matched trước khi check threshold
        best_recipe = recipes[best_idx] 
        
        if similarities[best_idx] > 0.5:
            print(f"   [Router] Found matched recipe: {best_recipe.get('recipe_id')}")
            state.plan = best_recipe.get("subtasks", [])
            # QUAN TRỌNG: Để nhảy sang Executor, status phải là awaiting_approval 
            # để khớp với logic của route_after_router bên dưới.
            state.status = "awaiting_approval" 
            return state
        else:
            print(f"   [Router] Low score ({similarities[best_idx]:.2f}) for recipe: {best_recipe.get('recipe_id')}")

    print("   [Router] No semantic match. Forwarding to Planner...")
    state.status = "planning"
    return state


async def planner_node(state: AgentState) -> AgentState:
    if state.status != "planning":
        return state
    
    url = f"{REGISTRY_URL}/skills/tools"
    async with httpx.AsyncClient() as http_client:
        try:
            resp = await http_client.get(url, timeout=10.0)
            data = resp.json()
            # QUAN TRỌNG: Lấy đúng danh sách từ key 'items' hoặc xử lý nếu là list
            available_skills = data.get("items", data) if isinstance(data, dict) else data
        except Exception as e:
            print(f"   [Planner] Error fetching skills: {e}")
            available_skills = []

    # Nếu vẫn rỗng, Planner sẽ không có dữ liệu để lập kế hoạch
    if not available_skills:
        print("   [Planner] WARNING: No skills fetched from AG1!")
        state.plan = [{"skill_id": "error_fallback", "input": {"reason": "Database AG1 rỗng hoặc lỗi kết nối"}}]
        state.status = "executing"
        return state

    system_prompt = f"""
Bạn là kiến trúc sư hệ thống.
Nhiệm vụ:
Phân tích 'Yêu cầu người dùng' và trích xuất dữ liệu để điền vào các Skill dưới định dạng JSON.
DANH SÁCH SKILL:
{json.dumps(available_skills, ensure_ascii=False, indent=2)}
QUY TẮC TRÍCH XUẤT:
1. Nếu người dùng cung cấp Log lỗi/Traceback, hãy đưa TOÀN BỘ nội dung đó vào trường 'stacktrace'.
2. Nếu người dùng chỉ nhắc đến tên file mà không có đường dẫn, hãy giữ nguyên tên file ở trường 'source_path'.
3. TUYỆT ĐỐI KHÔNG tự bịa ra các giá trị mẫu hoặc dùng dấu ngoặc nhọn <...>. 
4. Nếu dữ liệu bị thiếu trầm trọng, hãy gán giá trị 'MISSING_DATA' cho trường đó để Executor báo lỗi thay vì chạy bậy.
Format trả về phải là một đối tượng JSON (json object) như sau:
{{"plan": [
    {{
        "skill_id": "tên_skill",
        "input": {{
            "trường": "giá trị thật"
        }}
    }}
]}}
"""
    response = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "system", "content": system_prompt},
                  {"role": "user", "content": state.task}],
        response_format={"type": "json_object"}
    )
    
    plan_data = json.loads(response.choices[0].message.content)
    state.plan = plan_data.get("plan", [])
    state.status = "awaiting_approval"
    
    print(f"   => Dynamic Plan Created: {[s['skill_id'] for s in state.plan]}")
    return state

    # Tại AG2 - services/agent_orchestrator/main.py

async def executor_node(state: AgentState) -> Dict:
    plan = state.plan or []
    idx = state.current_step_index or 0

    # 1. Kiểm tra thoát Graph
    if idx >= len(plan):
        return {"status": "completed"}

    current_step = plan[idx]
    skill_to_find = current_step.get("skill_id") # Có thể là UUID hoặc Name
    user_input = current_step.get("input", {})

    # res_content = "No output"
    step_tag = f"Success: {skill_to_find}"

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        try:
            # Tìm UUID từ  GET (/skills/tools)
            registry_resp = await http_client.get(f"{REGISTRY_URL}/skills/tools")
            registry_resp.raise_for_status()
            reg_data = registry_resp.json()
            # Lấy list từ key 'items' (nếu AG1 trả về dict) hoặc dùng trực tiếp nếu là list
            skills_list = reg_data.get("items", reg_data) if isinstance(reg_data, dict) else reg_data

            target_info = next(
                (s for s in skills_list if s.get('skill_id') == skill_to_find or s.get('id') == skill_to_find or s.get('name') == skill_to_find), 
                None)
            if not target_info:
                raise ValueError(f"Skill '{skill_to_find}' không tồn tại.")
            skill_uuid = target_info.get('skill_id') or target_info.get('id')

            # Lấy Full JSON GET(/skills/{uuid})
            tool_resp = await http_client.get(f"{REGISTRY_URL}/skills/{skill_uuid}")
            tool_resp.raise_for_status()
            full_skill_json = tool_resp.json()

            # 4. Bóc tách dữ liệu từ 'metadata'
            metadata = full_skill_json.get("metadata", {})
            input_schema = metadata.get("input", {})
            output_schema = metadata.get("output", {})
            description = full_skill_json.get("description", "")

            # 5. Build Prompt cho LLM (Sử dụng Blueprint)
            system_instruction = f"""Bạn là công cụ: {full_skill_json.get('name')}
Mô tả nhiệm vụ: {description}
HƯỚNG DẪN THỰC THI (INPUT SCHEMA):
{json.dumps(input_schema, ensure_ascii=False)}
ĐỊNH DẠNG TRẢ VỀ (OUTPUT SCHEMA):
{json.dumps(output_schema, ensure_ascii=False)}
YÊU CẦU: Xử lý dữ liệu đầu vào và trả về JSON (json) khớp hoàn toàn với Output Schema"""

            response = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": f"DỮ LIỆU ĐẦU VÀO: {json.dumps(user_input)}"}
                ],
                response_format={"type": "json_object"}
            )
            res_content = response.choices[0].message.content
            # state["past_steps"].append((f"Success: {skill_to_find}", res_content))
        except Exception as e:
            print(f"❌ [Executor Error]: {str(e)}")
            state.past_steps.append((f"Failed: {skill_to_find}", str(e)))
            res_content = str(e)

    new_idx = idx + 1
    new_status = "completed" if new_idx >= len(plan) else "executing"

    return {
        "past_steps": [(step_tag, res_content)],
        "current_step_index": new_idx,
        "status": new_status,
        "final_result": res_content if new_status == "completed" else state.final_result
    }

# --- Logic Điều Hướng (Conditional Edges) ---

def route_after_router(state: AgentState) -> str:
    if state.status == "awaiting_approval":
        return "human_approval"
    return "planner"

def route_after_planner(state: AgentState) -> str:
    return "human_approval"

def route_after_executor(state: AgentState) -> str:
    plan = state.plan or []
    idx = state.current_step_index or 0
    if idx >= len(plan):
        return END
    if state.status == "completed":
        return END
    return "executor"