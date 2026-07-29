import json
import re
from services.skill_testing.core.registry import semantic_registry
from services.skill_testing.state import AgentState
import httpx

# Dữ liệu fallback dự phòng khi không thể kết nối tới Microservice AG1 (Cổng 8001)
MOCK_SKILL_DETAILS = {
    "debug-java-null-pointer": {
        "name": "debug-java-null-pointer",
        "raw_content": """---
name: debug-java-null-pointer
description: Biên dịch code Java và kiểm tra lỗi Null Pointer
---
## Instructions
Sử dụng công cụ debug-java-null-pointer để thực thi biên dịch (javac) trên file code mục tiêu.
Lưu ý: Nếu nhận diện lỗi thiếu lớp (cannot find symbol: class User), kích hoạt cơ chế tạo stub."""
    },
    "suggest-java-fix": {
        "name": "suggest-java-fix",
        "raw_content": """---
name: suggest-java-fix
description: Ghi bản vá sửa lỗi Java xuống đĩa
---
## Instructions
Vá code lỗi Java."""
    },
    "analyze-stacktrace": {
        "name": "analyze-stacktrace",
        "raw_content": """---
name: analyze-stacktrace
description: Phân tích Stacktrace
---
## Instructions
Phân tích stacktrace lỗi."""
    },
    "read-code-context": {
        "name": "read-code-context",
        "raw_content": """---
name: read-code-context
description: Đọc ngữ cảnh mã nguồn
---
## Instructions
Đọc code."""
    }
}

async def select_skill_node(state: AgentState):
    print("--- [Skill Selection Node] Choosing the best skill for the current task ---")
    current_task = state.plan[state.current_step_idx]
    state.current_task = current_task
    print(f"Nhiệm vụ hiện tại: {current_task}")
    # Semantic Search de tim ung vien skill

    skill_id = semantic_registry.get_id_by_name(current_task)
    if not skill_id:
        print(f"⚠️ Không tìm thấy skill_id cho tác vụ: {current_task}")
        state.selected_skill = None
        return state
    
    AG1_DETAIL_URL = f"http://127.0.0.1:8001/skills/{skill_id}"
    skill_detail = None
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(AG1_DETAIL_URL, timeout=5.0)
            if response.status_code == 200:
                skill_detail = response.json()
            else:
                print(f"⚠️ AG1 API trả về status code {response.status_code}. Thử dùng mock fallback.")
    except Exception as e:
        print(f"❌ Lỗi mạng khi gọi chi tiết AG1: {str(e)}. Sử dụng dữ liệu mock dự phòng.")
        
    if not skill_detail:
        skill_detail = MOCK_SKILL_DETAILS.get(skill_id) or MOCK_SKILL_DETAILS.get(current_task)
        
    if skill_detail:
        # Gán nguyên vẹn cục JSON thô vào user_context
        state.user_context["current_skill_metadata"] = skill_detail
        state.selected_skill = current_task
        print(f"🎯 Khớp thành công và tải xong chỉ thị cho: {current_task} (ID: {skill_id})")
        
        # In log scannable cấu trúc xác thực vật lý
        skill_name = skill_detail.get('name', 'Unknown')
        raw_content = skill_detail.get('raw_content', '')
        
        instructions = raw_content
        inst_match = re.search(r"##\s+(?:🚀\s+)?Instructions?\s*\n(.*?)(?=\n##\s|\Z)", raw_content, re.DOTALL | re.IGNORECASE)
        if inst_match:
            instructions = inst_match.group(1).strip()
        
        print(f"\n" + "="*60)
        print(f"🔍 TÊN KỸ NĂNG: {skill_name}")
        print(f"🔑 ID KỸ NĂNG: {skill_id}")
        print(f"📜 CHỈ THỊ (## Instructions):")
        print("-" * 60)
        print(f"{instructions}")
        print("="*60 + "\n")
    else:
        state.selected_skill = None
        
    return state
