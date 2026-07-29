# Project Description

## SWE AI Agent - Hệ thống quản lý và đánh giá AI Agent Skill

**Software Engineering AI Agent Skill Library and Evaluation Platform**

---

### Tổng quan

SWE AI Agent là hệ thống phần mềm hỗ trợ quản lý thư viện skill cho AI Agent và đánh giá chất lượng của một skill mới dưới dạng file `SKILL.md`. Hệ thống tập trung vào hai khía cạnh chính: **format** của skill và **content** của skill.

Skill trong hệ thống được hiểu là một đơn vị năng lực có thể được AI Agent sử dụng trong quá trình làm việc. Mỗi skill thường bao gồm phần metadata như `name`, `description`, `version`, `level`, `category`, `tags` và phần hướng dẫn chính mô tả cách sử dụng skill trong một ngữ cảnh cụ thể.

Hệ thống được xây dựng theo hướng người dùng có thể tự cấu hình tiêu chí đánh giá thay vì cố định toàn bộ logic trong mã nguồn. LLM chỉ đảm nhận nhiệm vụ trích xuất feature từ nội dung skill, còn quá trình tính điểm được thực hiện bằng rule engine deterministic dựa trên profile do người dùng định nghĩa.

---

### Bài toán giải quyết

Bài toán đánh giá skill đặt ra một số yêu cầu chính:

- Quản lý một thư viện skill thuộc nhiều nhóm khác nhau trong Software Engineering
- Cho phép người dùng upload hoặc paste một file `SKILL.md` mới để đánh giá
- Trích xuất các feature định lượng từ nội dung skill, ví dụ `has_description`, `scenario_count`, `example_count`
- Tính điểm skill dựa trên bộ tiêu chí có thể cấu hình, không hard-code trong code backend
- So sánh các feature dạng số với phân bố của thư viện skill hiện có
- Cho phép người dùng kiểm tra, chỉnh sửa feature đã trích xuất trước khi chấm điểm
- Cache kết quả trích xuất feature để giảm số lần gọi LLM và giảm chi phí

---

### Giải pháp kỹ thuật

**Trích xuất feature bằng LLM**

- Người dùng định nghĩa danh sách feature trong evaluation profile.
- Mỗi feature gồm `id`, `type` và `extraction_guidance`.
- Hệ thống hiện hỗ trợ hai kiểu feature chính: `boolean` và `integer`.
- Backend sinh prompt động từ danh sách feature trong profile, yêu cầu LLM trả về JSON theo đúng schema.
- Kết quả LLM được backend ép kiểu lại để đảm bảo scoring phía sau luôn deterministic.
- Mỗi feature có thể kèm theo `evidence` và `confidence` để người dùng biết vì sao feature đó được gán giá trị như vậy.

**Chấm điểm deterministic bằng rule engine**

- Người dùng cấu hình criteria, condition và action trong evaluation profile.
- Condition hỗ trợ các nhóm logic `all`, `any`, `not` và các toán tử `exists`, `missing`, `eq`, `neq`, `lt`, `lte`, `gt`, `gte`.
- Action hỗ trợ các thao tác như `force_score`, `set_score_from_bucket`, `set_baseline`, `add`, `subtract`, `cap_max`.
- LLM không trực tiếp quyết định điểm cuối cùng.
- Điểm cuối cùng được tính bằng cách chạy các rule step từ trên xuống dưới trên tập feature đã trích xuất.

**Chấm điểm theo phân vị**

- Với các feature dạng số nguyên, hệ thống có thể so sánh giá trị của skill mới với thư viện skill hiện có.
- Thư viện skill đóng vai trò tập tham chiếu để tính các ngưỡng `p25`, `p50`, `p75`, `p90`.
- Cấu hình mặc định:

```text
value < p25  -> 2 điểm
value < p50  -> 4 điểm
value < p75  -> 6 điểm
value < p90  -> 8 điểm
value >= p90 -> 10 điểm
```

- Người dùng có thể chỉnh lại mapping điểm trong phần Bucket Scoring của giao diện.

**Cache feature extraction**

- Cache được tính theo hash nội dung skill và hash evaluation profile.
- Nếu nội dung skill và định nghĩa feature không đổi, hệ thống dùng lại kết quả đã trích xuất.
- Nếu người dùng thêm feature mới hoặc sửa `extraction_guidance`, hệ thống chỉ cần gọi LLM cho phần feature cần cập nhật.
- Quá trình sync feature có log trạng thái như cache hit, llm calling, success, fail.

**Kiến trúc hệ thống**

| Tầng | Công nghệ |
|------|-----------|
| Backend | Python, FastAPI, Pydantic |
| Frontend | React, TypeScript, Vite |
| Evaluation | Configurable rule engine, percentile scoring |
| LLM extraction | DeepSeek-compatible chat completion API |
| Lưu trữ | JSON file-based trong `database/` |
| Triển khai | Docker Compose |

---

### Tính năng chính

**Skill Library**

- Hiển thị danh sách skill trong thư viện
- Phân loại skill theo các category của Software Engineering như backend, frontend, testing, devops, security, architecture
- Tìm kiếm skill theo tên, mô tả, level, category và tags
- Xem chi tiết nội dung `SKILL.md`
- Import file `.md` mới vào thư viện
- Export skill hiện có ra file markdown
- Đồng bộ feature cho từng skill hoặc toàn bộ thư viện skill

**Skill Detail**

- Hiển thị metadata và instruction của một skill
- Hiển thị danh sách format feature được tính bằng parser
- Hiển thị danh sách content feature được trích xuất từ LLM hoặc cache
- Cho phép sync lại feature khi profile hoặc nội dung skill thay đổi
- Nếu cache đã tồn tại, feature được hiển thị ngay mà không cần gọi LLM lại

**Evaluation Profile**

- Cấu hình model, base URL và API key cho LLM
- Định nghĩa feature set dùng để trích xuất
- Cấu hình bucket scoring cho feature dạng số
- Thêm, sửa, xoá criteria chấm điểm
- Xây dựng condition bằng rule builder thay vì nhập biểu thức tự do
- Xây dựng action chấm điểm như cộng điểm, trừ điểm, giới hạn điểm, gán điểm nền
- Lưu profile vào file JSON để sử dụng lại

**Evaluate Skill**

- Upload hoặc paste nội dung `SKILL.md`
- Trích xuất feature từ skill bằng LLM
- Hiển thị evidence và confidence của từng feature
- Cho phép người dùng chỉnh sửa feature trước khi chấm điểm
- Chấm điểm content bằng rule engine deterministic
- Hiển thị điểm từng tiêu chí và các rule step đã được áp dụng
- Export kết quả đánh giá ra file HTML

**Feature Visualization**

- Tổng hợp feature đã sync từ toàn bộ thư viện skill
- Hiển thị phân bố của từng feature trên tập skill
- Với feature boolean, hệ thống có thể quan sát số lượng skill có giá trị true/false
- Với feature integer, hệ thống có thể quan sát phân bố số lượng và các ngưỡng percentile
- Dữ liệu visualization lấy từ cache feature extraction

---

### Quy mô

- 100 skill Software Engineering trong `skill-library`
- 16 nhóm category chính trong thư viện skill
- 2 backend service chính được chạy bằng Docker Compose: `skill-management` và `skill-evaluation`
- 1 frontend React application
- JSON database gồm `skills.json`, `evaluation_feature_cache.json` và `evaluation_profiles/default_distribution.json`
- Các nhóm API chính:
  - Skill CRUD, import, export, search
  - Feature extraction, feature cache, feature sync
  - Configurable profile load/save
  - Markdown evaluation
  - HTML report export
