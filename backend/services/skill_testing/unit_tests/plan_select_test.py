import datetime
import json
from backend.services.skill_testing.core.plan_node import plan_node
from backend.services.skill_testing.core.select_skill_node import select_skill_node
from backend.services.skill_testing.state import AgentState
from backend.services.skill_testing.core.registry import semantic_registry
from backend.services.skill_testing.unit_tests.mock_client import MockModelClient
from backend.shared.schemas import SkillRead

def test_nodes_workflow():
    # --- BƯỚC 1: GIẢ LẬP DỮ LIỆU SKILL ---
    from datetime import datetime

    mock_skills = [
    SkillRead(
        id="1",
        name="analyze-stacktrace",
        version="1.0",
        level="basic",
        category="debug",
        tags=["java"],
        metadata={
            "description": "Analyzes Java stacktrace to find error line"
        },
        updated_at=datetime.now(),
        raw_content="...",
        full_markdown="..."
    ),
    SkillRead(
        id="2",
        name="read-file",
        version="1.0",
        level="basic",
        category="file",
        tags=["io"],
        metadata={
            "description": "Reads content of a source file"
        },
        updated_at=datetime.now(),
        raw_content="...",
        full_markdown="..."
    )
    ]
    semantic_registry.build_index(mock_skills)

    # --- BƯỚC 2: GIẢ LẬP PHẢN HỒI LLM ---
    responses = {
        "expert Software Engineer": json.dumps({"plan": ["Analyze the Java crash log", "Read the source code"]}),
        "Task Dispatcher": json.dumps({"thought": "The task is about logs, choosing analyzer", "selected_skill": "analyze-stacktrace"})
    }
    mock_llm = MockModelClient(responses)

    # --- BƯỚC 3: KHỞI TẠO STATE ---
    state = AgentState(
        user_context={
            "code": "public class Main...",
            "stacktrace": "NullPointerException at line 10",
            "message": "Fix this bug"
        }
    )

    # Trong file plan_select_test.py
    print(f"DEBUG: Type of state is {type(state)}")
    print(f"DEBUG: Attributes of state: {state.__dict__.keys()}")
    state = plan_node(state, mock_llm)
    print(f"Plan created: {state.plan}")
    # --- BƯỚC 4: TEST PLAN_NODE ---
    print("\n--- Testing Plan Node ---")
    state = plan_node(state, mock_llm)
    print(f"Plan created: {state.plan}")
    assert len(state.plan) == 2
    assert state.plan[0] == "Analyze the Java crash log"

    # --- BƯỚC 5: TEST SELECT_SKILL_NODE (Lần 1) ---
    print("\n--- Testing Select Skill Node (Step 0) ---")
    state = select_skill_node(state, mock_llm, semantic_registry)
    print(f"Task: {state.current_task}")
    print(f"Thought: {state.last_thought}")
    print(f"Selected Skill: {state.selected_skill}")
    
    assert state.selected_skill == "analyze-stacktrace"
    
    print("\n✅ Unit Test Passed: Plan and Selection work together!")

if __name__ == "__main__":
    test_nodes_workflow()