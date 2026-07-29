# Thiết kế hệ thống

## 1. Tổng quan thiết kế

Hệ thống **SWE AI Agent - Skill Library and Evaluation Platform** được thiết kế theo mô hình ứng dụng web gồm frontend React và các backend service FastAPI. Dữ liệu được lưu bằng file JSON để đơn giản hóa quá trình chạy demo và nộp mã nguồn.

Hai backend service chính trong bản triển khai hiện tại là:

- `skill-management`: quản lý thư viện skill.
- `skill-evaluation`: đánh giá format/content, trích xuất feature, cache feature và quản lý evaluation profile.

Frontend giao tiếp với backend thông qua REST API. Khi chạy bằng Docker Compose, frontend Vite proxy các request:

- `/api/management` tới service `skill-management`.
- `/api/evaluation` tới service `skill-evaluation`.

---

## 2. Kiến trúc tổng thể

```text
+-------------------+
| React Frontend    |
| - Skill Browser   |
| - Skill Detail    |
| - Evaluation Page |
+---------+---------+
          |
          | REST API
          |
+---------+----------------------------+
|                                      |
v                                      v
+----------------------+       +----------------------+
| skill-management     |       | skill-evaluation     |
| FastAPI service      |       | FastAPI service      |
|                      |       |                      |
| - Skill CRUD         |       | - Feature extraction |
| - Import/export      |       | - Rule engine        |
| - Registry search    |       | - Calibration        |
| - Tool definition    |       | - HTML export        |
+----------+-----------+       +----------+-----------+
           |                              |
           |                              |
           v                              v
+----------------------+       +----------------------+
| skill-library/       |       | database/            |
| SKILL.md files       |       | JSON persistence     |
+----------------------+       +----------------------+
                                          |
                                          v
                                +----------------------+
                                | LLM Provider         |
                                | Feature extraction   |
                                +----------------------+
```

---

## 3. Thiết kế thư mục

```text
source_code/
|-- backend/
|   |-- shared/
|   |-- services/
|   |   |-- skill_management/
|   |   |-- skill_evaluation/
|   |   `-- skill_testing/
|   `-- requirements.txt
|
|-- frontend/
|   `-- src/
|       |-- api/
|       |-- pages/
|       `-- main.tsx
|
|-- skill-library/
|   |-- api-backend/
|   |-- frontend/
|   |-- testing/
|   |-- devops-platform/
|   |-- security/
|   `-- ...
|
|-- database/
|   |-- skills.json
|   |-- evaluation_feature_cache.json
|   `-- evaluation_profiles/
|       `-- default_distribution.json
|
`-- docker-compose.yml
```

### `backend/shared`

Gói `shared` chứa các thành phần dùng chung:

- Cấu hình đường dẫn skill library và database.
- Schema Pydantic cho request/response.
- Hàm parse/generate markdown skill.
- Các helper database.

### `backend/services/skill_management`

Service quản lý skill library:

- Scan các file `SKILL.md`.
- Đồng bộ dữ liệu vào `skills.json`.
- Cung cấp API list/search/detail/create/update/delete.
- Import/export markdown.
- Tạo tool definition cho agent runtime.

### `backend/services/skill_evaluation`

Service đánh giá skill:

- Load/save evaluation profile.
- Trích xuất format feature bằng markdown/frontmatter parser.
- Trích xuất content feature bằng LLM.
- Cache feature theo hash nội dung skill và hash profile.
- Tính calibration percentile trên skill library.
- Chạy rule engine để tính điểm.
- Export kết quả ra HTML.

### `frontend/src`

Frontend gồm các màn hình chính:

- `SkillBrowser.tsx`: xem thư viện, lọc, tìm kiếm, sync feature, visualization.
- `SkillDetail.tsx`: xem nội dung skill và extracted features.
- `EvaluationPage.tsx`: cấu hình profile, nhập markdown, extract feature, score và export HTML.
- `api/client.ts`: định nghĩa API client và type dùng chung.

---

## 4. Thiết kế dữ liệu

### Skill record

Skill được lưu trong `database/skills.json`.

```json
{
  "id": "uuid",
  "name": "domain-modeling",
  "version": "1.0.0",
  "category": "architecture-design/domain-modeling",
  "level": "atomic",
  "tags": [],
  "metadata_json": {
    "description": "..."
  },
  "raw_content": "---\nname: domain-modeling\n---\n...",
  "updated_at": "2026-07-26T14:53:35.150730+00:00"
}
```

### Evaluation profile

Evaluation profile được lưu tại `database/evaluation_profiles/default_distribution.json`.

```json
{
  "schema_version": 1,
  "id": "default",
  "name": "Default Distribution Evaluation",
  "llm": {
    "provider": "deepseek",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "api_key": ""
  },
  "bucket_scheme": {
    "p25": 2,
    "p50": 4,
    "p75": 6,
    "p90": 8,
    "above": 10
  },
  "features": [],
  "criteria": [],
  "format_features": [],
  "format_criteria": []
}
```

### Feature cache

Feature cache được lưu trong `database/evaluation_feature_cache.json`.

Cache dùng để tránh gọi LLM lặp lại khi:

- Nội dung skill không đổi.
- Evaluation profile không đổi.
- Feature definition không đổi.

---

## 5. Thiết kế evaluation profile

### Feature definition

Feature definition mô tả dữ liệu cần trích xuất từ skill.

```json
{
  "id": "scenario_count",
  "type": "integer",
  "extraction_guidance": "Đếm số usage scenario cụ thể trong skill."
}
```

Hệ thống hiện hỗ trợ:

- `boolean`: giá trị đúng/sai.
- `integer`: số nguyên.

### Bucket scoring

Bucket scoring dùng để đổi feature dạng integer sang điểm nền dựa trên percentile của skill library.

```text
value < p25  -> 2 điểm
value < p50  -> 4 điểm
value < p75  -> 6 điểm
value < p90  -> 8 điểm
value >= p90 -> 10 điểm
```

Người dùng có thể sửa điểm tương ứng với từng bucket.

### Criterion

Criterion là một tiêu chí chấm điểm.

```json
{
  "id": "usage_scenarios",
  "label": "Usage Scenarios",
  "max_score": 10,
  "steps": []
}
```

Mỗi criterion gồm nhiều rule step. Các rule step chạy từ trên xuống dưới.

### Condition

Condition xác định khi nào một rule step được áp dụng.

```json
{
  "any": [
    { "feature": "has_name", "operator": "eq", "value": false },
    { "feature": "has_description", "operator": "eq", "value": false }
  ]
}
```

Các nhóm logic:

- `all`.
- `any`.
- `not`.

Các toán tử:

- `exists`.
- `missing`.
- `eq`.
- `neq`.
- `lt`.
- `lte`.
- `gt`.
- `gte`.

### Score action

Score action xác định cách thay đổi điểm.

| Action | Ý nghĩa |
|--------|---------|
| `force_score` | Ép điểm về một giá trị cố định. |
| `set_score_from_bucket` | Tính điểm từ percentile bucket. |
| `set_baseline` | Đặt điểm nền. |
| `add` | Cộng điểm. |
| `subtract` | Trừ điểm. |
| `cap_max` | Giới hạn điểm tối đa. |

---

## 6. Luồng đánh giá skill

```text
Người dùng nhập SKILL.md
        |
        v
Frontend gửi markdown tới skill-evaluation
        |
        v
Backend load evaluation profile
        |
        v
Backend tính format features bằng parser
        |
        v
Backend kiểm tra cache content features
        |
        +-- cache hit --> dùng lại feature
        |
        +-- cache miss --> gọi LLM trích xuất feature
        |
        v
Backend tính calibration từ skill-library
        |
        v
Rule engine chấm điểm từng criterion
        |
        v
Frontend hiển thị score, features, evidence, applied steps
```

---

## 7. Luồng sync feature toàn bộ thư viện

```text
Người dùng nhấn Sync Features
        |
        v
Frontend lấy danh sách skill
        |
        v
Frontend chạy lần lượt từng skill
        |
        v
Backend kiểm tra cache theo skill/profile
        |
        +-- cache hit --> trả feature đã có
        |
        +-- cache miss --> gọi LLM
        |
        v
Backend lưu cache nếu thành công
        |
        v
Frontend cập nhật log từng skill
        |
        v
Tiếp tục skill kế tiếp cho đến khi hết danh sách
```

---

## 8. Thiết kế giao diện

### Skill Browser

Màn hình Skill Browser hiển thị toàn bộ skill trong thư viện. Người dùng có thể:

- Chuyển giữa list view, grid view và hierarchy view.
- Tìm kiếm skill.
- Lọc theo level và category.
- Import skill mới.
- Tạo skill mới.
- Sync feature cho toàn bộ thư viện.
- Xem visualization feature.

### Skill Detail

Màn hình Skill Detail hiển thị:

- Metadata của skill.
- Nội dung instruction.
- Format features.
- Content features.
- Evidence và confidence.
- Nút sync lại feature cho skill hiện tại.

Nếu cache đã tồn tại, hệ thống hiển thị feature ngay mà không yêu cầu người dùng sync thủ công.

### Evaluation Page

Màn hình Evaluation Page gồm ba vùng chính:

- Vùng nhập markdown: paste hoặc upload `SKILL.md`.
- Vùng profile editor: model, features, bucket scoring, criteria.
- Vùng kết quả: content review, extracted features, calibration, applied rule steps.

Format review có thể vẫn được backend tính nhưng giao diện tập trung hiển thị content review.

---

## 9. Thiết kế triển khai

Hệ thống chạy bằng Docker Compose với các service:

| Service | Port | Vai trò |
|---------|------|---------|
| `frontend` | `3002` | Giao diện React/Vite |
| `skill-management` | `8001` | API quản lý skill |
| `skill-evaluation` | `8002` | API đánh giá skill |

Các volume chính:

```text
./skill-library -> /data/skills
./database      -> /database
./backend       -> /app
./frontend      -> /app
```

Thiết kế này cho phép sửa code backend/frontend mà không cần build lại image trong quá trình demo và phát triển.

---
