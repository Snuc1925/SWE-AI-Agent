# Đặc tả yêu cầu

## 1. Giới thiệu

Tài liệu này mô tả các yêu cầu chức năng và phi chức năng của hệ thống **SWE AI Agent - Skill Library and Evaluation Platform**. Hệ thống được xây dựng để quản lý thư viện skill cho AI Agent và đánh giá chất lượng của skill mới dựa trên cấu hình do người dùng định nghĩa.

Phạm vi hệ thống tập trung vào:

- Quản lý skill library.
- Cấu hình evaluation profile.
- Trích xuất feature bằng LLM.
- Chấm điểm format và content bằng rule engine deterministic.
- Đồng bộ/cache feature.
- Trực quan hóa phân bố feature.
- Export kết quả đánh giá.

Hệ thống không tập trung vào đánh giá runtime của skill trong phiên bản hiện tại.

---

## 2. Tác nhân

| Tác nhân | Mô tả |
|----------|-------|
| Người dùng | Người trực tiếp sử dụng hệ thống để quản lý skill, cấu hình tiêu chí đánh giá, đồng bộ feature và đánh giá skill mới. |
| LLM Provider | Dịch vụ bên ngoài dùng để trích xuất feature từ nội dung skill theo prompt động. |
| File Storage | Tập file JSON và markdown dùng để lưu skill, profile và cache feature. |

---

## 3. Yêu cầu chức năng

### FR-01 - Xem danh sách skill

Hệ thống phải cho phép người dùng xem danh sách skill trong thư viện.

**Đầu vào**

- Bộ lọc category, level, tag nếu có.

**Xử lý**

- Backend đọc dữ liệu skill từ `database/skills.json`.
- Nếu service khởi động, backend đồng bộ lại dữ liệu từ `skill-library/`.

**Đầu ra**

- Danh sách skill gồm `id`, `name`, `version`, `level`, `category`, `tags`, `metadata`, `updated_at`.

---

### FR-02 - Tìm kiếm skill

Hệ thống phải cho phép người dùng tìm kiếm skill theo từ khóa.

**Đầu vào**

- Từ khóa tìm kiếm `q`.
- Số lượng kết quả `top_k`.

**Xử lý**

- Backend tìm kiếm trong registry skill đã load.

**Đầu ra**

- Danh sách kết quả gồm thông tin skill và điểm tương đồng.

---

### FR-03 - Xem chi tiết skill

Hệ thống phải cho phép người dùng xem chi tiết một skill.

**Đầu vào**

- `skill_id`.

**Đầu ra**

- Metadata.
- Raw markdown.
- Full markdown.
- Extracted features nếu đã có cache.

---

### FR-04 - Import skill mới

Hệ thống phải cho phép người dùng import file `.md` vào thư viện.

**Đầu vào**

- File markdown có frontmatter và nội dung instruction.

**Xử lý**

- Backend parse markdown.
- Backend validate các metadata bắt buộc.
- Backend ghi skill vào JSON database và thư mục skill library.

**Đầu ra**

- Skill vừa được tạo.

---

### FR-05 - Export skill

Hệ thống phải cho phép người dùng export một skill ra file markdown.

**Đầu vào**

- `skill_id`.

**Đầu ra**

- Nội dung markdown của skill.

---

### FR-06 - Cấu hình LLM

Hệ thống phải cho phép người dùng cấu hình thông tin LLM trong evaluation profile.

**Thông tin cấu hình**

- Provider.
- Base URL.
- Model.
- API key.

**Lưu trữ**

- Thông tin được lưu trong `database/evaluation_profiles/default_distribution.json`.

---

### FR-07 - Cấu hình feature definition

Hệ thống phải cho phép người dùng thêm, sửa và xóa feature definition.

**Mỗi feature gồm**

- `id`: mã feature.
- `type`: kiểu dữ liệu, hiện hỗ trợ `boolean` và `integer`.
- `extraction_guidance`: hướng dẫn cho LLM khi trích xuất feature.

**Ràng buộc**

- `id` không được rỗng.
- `type` phải thuộc danh sách kiểu được hỗ trợ.
- `extraction_guidance` phải mô tả rõ cách xác định feature.

---

### FR-08 - Cấu hình bucket scoring

Hệ thống phải cho phép người dùng cấu hình điểm tương ứng với các ngưỡng phân vị.

**Các ngưỡng**

- `p25`.
- `p50`.
- `p75`.
- `p90`.
- `above`.

**Mục đích**

- Chuyển giá trị feature dạng integer thành điểm nền dựa trên phân bố của skill library.

---

### FR-09 - Cấu hình criteria

Hệ thống phải cho phép người dùng thêm, sửa và xóa tiêu chí chấm điểm.

**Mỗi criterion gồm**

- `id`.
- `label`.
- `max_score`.
- Danh sách rule steps.

---

### FR-10 - Cấu hình condition

Hệ thống phải cho phép người dùng tạo condition bằng builder block.

**Condition hỗ trợ**

- Nhóm `all`.
- Nhóm `any`.
- Phủ định `not`.
- Toán tử `exists`, `missing`, `eq`, `neq`, `lt`, `lte`, `gt`, `gte`.

**Ví dụ**

Điều kiện thiếu name hoặc description có thể biểu diễn bằng:

```json
{
  "any": [
    { "feature": "has_name", "operator": "eq", "value": false },
    { "feature": "has_description", "operator": "eq", "value": false }
  ]
}
```

---

### FR-11 - Cấu hình score action

Hệ thống phải cho phép người dùng chọn action cho từng rule step.

**Action hỗ trợ**

- `force_score`.
- `set_score_from_bucket`.
- `set_baseline`.
- `add`.
- `subtract`.
- `cap_max`.

---

### FR-12 - Trích xuất feature từ skill

Hệ thống phải cho phép trích xuất feature từ nội dung `SKILL.md`.

**Đầu vào**

- Markdown content.
- Profile ID.

**Xử lý**

- Backend load evaluation profile.
- Backend sinh prompt từ feature definition.
- LLM trả JSON feature.
- Backend ép kiểu kết quả về boolean hoặc integer.
- Backend trả kèm evidence và confidence nếu có.

**Đầu ra**

- Content features.
- Format features.
- Feature evidence.
- Calibration.
- Metadata fields.

---

### FR-13 - Chỉnh sửa feature trước khi chấm điểm

Hệ thống phải cho phép người dùng chỉnh sửa feature đã trích xuất trước khi chấm điểm.

**Mục đích**

- Người dùng có thể sửa lỗi trích xuất của LLM.
- Backend không gọi LLM lại khi chỉ chấm điểm trên feature đã sửa.

---

### FR-14 - Chấm điểm skill

Hệ thống phải cho phép chấm điểm skill dựa trên feature và evaluation profile.

**Xử lý**

- Format review được tính bằng parser/rule deterministic.
- Content review được tính bằng rule engine deterministic.
- Rule steps được chạy từ trên xuống dưới.
- Điểm từng criterion không vượt quá `max_score`.

**Đầu ra**

- Total score.
- Max score.
- Criteria score.
- Explanation.
- Applied rule steps.
- Features và evidence.

---

### FR-15 - Đồng bộ feature toàn bộ thư viện

Hệ thống phải cho phép sync feature cho toàn bộ skill library.

**Xử lý**

- Duyệt lần lượt các skill.
- Kiểm tra cache.
- Nếu cache hit thì dùng lại.
- Nếu cache miss thì gọi LLM.
- Nếu một skill fail thì tiếp tục skill tiếp theo.

**Đầu ra**

- Log trạng thái từng skill.
- Tổng số cache hit, success, fail.

---

### FR-16 - Cache feature extraction

Hệ thống phải cache kết quả trích xuất feature.

**Cache key dựa trên**

- Hash nội dung skill.
- Hash evaluation profile.
- Feature definition.

**Yêu cầu**

- Khi nội dung skill không đổi và profile không đổi, hệ thống không gọi LLM lại.
- Khi thêm hoặc sửa feature, hệ thống phải phát hiện phần cần trích xuất lại.

---

### FR-17 - Trực quan hóa feature

Hệ thống phải cho phép người dùng xem phân bố feature trên thư viện skill.

**Với feature boolean**

- Hiển thị số lượng true.
- Hiển thị số lượng false.

**Với feature integer**

- Hiển thị phân bố giá trị.
- Hiển thị các ngưỡng percentile nếu có.

---

### FR-18 - Export kết quả đánh giá

Hệ thống phải cho phép export kết quả đánh giá ra file HTML.

**Đầu vào**

- Evaluation result.

**Đầu ra**

- File HTML chứa điểm format, điểm content, criteria và raw JSON.

---

## 4. Yêu cầu phi chức năng

### NFR-01 - Dễ cấu hình

Các tiêu chí đánh giá content không được hard-code hoàn toàn trong code backend. Người dùng phải có khả năng chỉnh sửa feature, criteria, condition và score action thông qua profile.

### NFR-02 - Tính deterministic của scoring

LLM không được quyết định điểm cuối cùng. Điểm cuối cùng phải được tính bằng rule engine dựa trên feature đã trích xuất.

### NFR-03 - Giảm chi phí LLM

Hệ thống phải sử dụng cache để tránh gọi LLM lặp lại với cùng nội dung skill và cùng profile.

### NFR-04 - Khả năng quan sát lỗi

Khi API lỗi, frontend phải hiển thị thông báo lỗi rõ ràng. Backend phải log lỗi trong quá trình evaluate và sync feature.

---


