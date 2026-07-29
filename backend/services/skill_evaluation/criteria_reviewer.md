Dưới đây là một bản rubric hoàn chỉnh theo hướng định lượng + thống kê, bạn có thể mang đi trao đổi với cô.

**Rubric Đề Xuất**
Thang điểm cho mỗi criterion: `0, 2, 4, 6, 8, 10`

Nguyên tắc chung:
- Điểm không do LLM quyết định trực tiếp
- Hệ thống trích xuất feature đo được
- Với feature dạng đếm, dùng percentile trên toàn bộ benchmark
- Với feature bắt buộc, dùng `gate rule`
- Điểm cuối = `base score theo percentile` + `adjustment theo rule tuyệt đối`

---

**1. Name & Description Clarity**

Mục tiêu:
- Đo mức độ đầy đủ và cụ thể của phần mô tả skill

Feature:
- `has_name`: có `name` hay không
- `has_description`: có `description` hay không
- `description_word_count`: số từ trong `description`
- `description_has_domain_term`: có nhắc domain/tool/framework/artifact cụ thể
- `description_has_action_verb`: có động từ nhiệm vụ như `debug`, `test`, `migrate`, `secure`
- `description_has_trigger_phrase`: có tín hiệu khi nào nên dùng skill

Cách chấm:
- Nếu thiếu `name` hoặc `description` -> `0`
- Base score theo `description_word_count`:
  - `< p25` -> `2`
  - `p25 - < p50` -> `4`
  - `p50 - < p75` -> `6`
  - `p75 - < p90` -> `8`
  - `>= p90` -> `10`
- Điều chỉnh:
  - thiếu `domain term` -> `-2`
  - thiếu `action verb` -> `-2`
  - thiếu `trigger phrase` -> `-2`
- Clamp về `0..10`

Cách diễn giải:
- Điểm cao khi description không chỉ dài hơn mức trung bình mà còn có domain cụ thể, nêu hành động chính và có tín hiệu usage.

---

**2. Input & Output Fitness**

Mục tiêu:
- Đo mức độ đầy đủ và phù hợp của schema đầu vào/đầu ra

Feature:
- `has_input_schema`
- `has_output_schema`
- `input_field_count`
- `output_field_count`
- `input_required_count`
- `output_required_count`
- `schema_term_overlap`: độ trùng từ khóa giữa schema và body skill

Cách chấm:
- Không có cả `input` và `output` -> `0`
- Chỉ có một trong hai -> tối đa `4`
- Có cả hai:
  - base `4`
  - `input_field_count` theo percentile:
    - `< p50` -> `+0`
    - `p50 - < p90` -> `+2`
    - `>= p90` -> `+4`
  - `output_field_count` theo percentile:
    - `< p50` -> `+0`
    - `p50 - < p90` -> `+2`
    - `>= p90` -> `+4`
  - `input_required_count > 0` hoặc `output_required_count > 0` -> `+1`
  - `schema_term_overlap >= p75` -> `+1`
- Cap ở `10`

Phiên bản dễ nói với cô:
- Có đủ input/output là điều kiện nền
- Độ chi tiết của field và độ khớp với nội dung skill mới quyết định điểm cao

---

**3. Usage Scenarios**

Mục tiêu:
- Đo skill có nêu các tình huống sử dụng cụ thể hay không

Feature:
- `scenario_section_present`
- `scenario_count`
- `scenario_with_action_count`
- `scenario_with_artifact_count`
- `scenario_with_action_ratio`
- `scenario_with_artifact_ratio`
- `has_non_goal_or_boundary`

Cách chấm:
- Không có section trigger/scenario -> `0`
- Base score theo `scenario_count`:
  - `< p25` -> `2`
  - `p25 - < p50` -> `4`
  - `p50 - < p75` -> `6`
  - `p75 - < p90` -> `8`
  - `>= p90` -> `10`
- Điều chỉnh:
  - `scenario_with_action_ratio < 0.5` -> `-2`
  - `scenario_with_artifact_ratio < 0.5` -> `-2`
  - `has_non_goal_or_boundary = 1` -> `+2`
- Clamp `0..10`

Cách diễn giải:
- Không chỉ đếm số scenario, mà còn xem scenario có thật sự cụ thể hay không và có nói khi nào không nên dùng skill không.

---

**4. Step-by-Step Process**

Mục tiêu:
- Đo mức độ quy trình của skill, tức là AI có thể làm theo từng bước hay không

Feature:
- `ordered_step_count`
- `actionable_step_count`
- `actionable_step_ratio`
- `has_analysis_step`
- `has_execution_step`
- `has_verification_step`

Cách chấm:
- `ordered_step_count = 0` -> `0`
- `ordered_step_count < 3` -> tối đa `4`
- Base score theo `ordered_step_count`:
  - `< p25` -> `2`
  - `p25 - < p50` -> `4`
  - `p50 - < p75` -> `6`
  - `p75 - < p90` -> `8`
  - `>= p90` -> `10`
- Điều chỉnh:
  - `actionable_step_ratio < 0.6` -> `-2`
  - thiếu `analysis_step` -> `-2`
  - thiếu `execution_step` -> `-2`
  - thiếu `verification_step` -> `-2`
- Clamp `0..10`

Cách diễn giải:
- Điểm cao khi skill có quy trình đủ dài, các bước có tính hành động, và có đủ pha phân tích, thực thi, kiểm tra.

---

**5. Examples Clarity**

Mục tiêu:
- Đo ví dụ có đủ cấu trúc để người dùng hoặc AI tái sử dụng

Feature:
- `example_count`
- `example_with_code_count`
- `example_with_context_count`
- `example_with_output_count`
- `example_linked_to_rule_count`
- `example_with_code_ratio`
- `example_with_context_ratio`
- `example_with_output_ratio`

Cách chấm:
- `example_count = 0` -> `0`
- Base score theo `example_count`:
  - `< p25` -> `2`
  - `p25 - < p50` -> `4`
  - `p50 - < p75` -> `6`
  - `p75 - < p90` -> `8`
  - `>= p90` -> `10`
- Điều chỉnh:
  - `example_with_context_ratio >= 0.5` -> `+2`
  - `example_with_output_ratio >= 0.5` -> `+2`
  - `example_with_code_ratio >= 0.5` -> `+2`
  - `example_linked_to_rule_count >= 1` -> `+2`
- Cap ở `10`

Phiên bản cân bằng hơn:
- base tối đa `4`
- mỗi evidence cộng `2`
- tổng tối đa `10`

Cách này thường đẹp hơn vì tránh việc chỉ nhiều example là đã điểm cao.

---

**Bảng Tóm Tắt**
| Criterion | Feature chính | Gate rule | Thành phần thống kê |
|---|---|---|---|
| Name & Description Clarity | `description_word_count`, domain/action/trigger signals | thiếu `name` hoặc `description` -> 0 | percentile của `description_word_count` |
| Input & Output Fitness | schema presence, field counts, required count, overlap | thiếu cả input/output -> 0 | percentile của `input_field_count`, `output_field_count`, `schema_term_overlap` |
| Usage Scenarios | scenario count, action/artifact ratio, boundary | không có scenario section -> 0 | percentile của `scenario_count` |
| Step-by-step Process | ordered steps, actionable ratio, analysis/execution/verify | không có step -> 0 | percentile của `ordered_step_count` |
| Examples Clarity | example count, code/context/output ratios | không có example -> 0 | percentile của `example_count` |

---

**Câu Mô Tả Phương Pháp Cho Báo Cáo**
Bạn có thể viết kiểu này:

> Content quality is evaluated using a distribution-based scoring rubric.  
> Instead of asking the LLM to assign subjective scores directly, the system first extracts measurable structural features from each `SKILL.md`, such as the number of usage scenarios, number of ordered steps, number of examples, and schema completeness.  
> These features are then normalized against the benchmark distribution using percentile buckets. Final criterion scores are computed by combining relative statistical position with absolute rule-based gates.

Nếu muốn viết ngắn hơn:

> Hệ thống chấm nội dung theo hướng thống kê: trích xuất các đặc trưng định lượng từ tài liệu, chuẩn hóa chúng theo phân phối của toàn bộ tập benchmark, rồi tính điểm bằng công thức cố định thay vì để LLM cho điểm cảm tính.

---

**Khuyến Nghị Khi Trao Đổi Với Cô**
Mình nghĩ bạn nên nói rõ 2 ý:
- Phần “thống kê” nằm ở bước chuẩn hóa feature bằng percentile trên toàn bộ benchmark
- Phần “đảm bảo chất lượng tối thiểu” nằm ở gate rules tuyệt đối

Như vậy rubric của bạn sẽ:
- có tính định lượng
- có tính thống kê
- vẫn tránh được chuyện benchmark yếu làm méo điểm

Nếu bạn muốn, bước tiếp theo mình có thể làm tiếp mục `2`: phân loại rõ feature nào extract bằng code thuần, feature nào cần LLM hỗ trợ.