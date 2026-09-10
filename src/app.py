"""
🚀 CORE AGENT APP (Dành cho Role 4: Core Agent Developer)
File chính ghép nối tất cả các thành phần: Tools + Prompts + Test Cases + Multi-Provider.

Cách chạy:
    python src/app.py        -> Chatbot Baseline trả lời toàn bộ test case
    python src/app.py 3      -> ReAct Agent trả lời test case có id = 3
"""

import ast
import json
import os
import re
import sys
from dotenv import load_dotenv

# Đảm bảo import các module cùng thư mục src/ hoạt động mượt mà
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Đảm bảo in ra Tiếng Việt và Emojis không bị lỗi trên Windows Console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Import các thành phần từ file của Role 2, Role 3 & Multi-Provider Adapter
from tools import AVAILABLE_TOOLS, TOOL_PRECONDITIONS
from prompts import (
    CHATBOT_BASELINE_PROMPT,
    REACT_SYSTEM_PROMPT,
    MAX_ITERATIONS,
    MAX_REPEATED_ACTIONS,
)
from providers import get_llm_provider

load_dotenv()


def load_test_cases():
    """Đọc bộ test cases từ config/test_cases.json của Role 1"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "test_cases.json")

    # Fallback kiểm tra nếu file ở thư mục hiện tại
    if not os.path.exists(config_path):
        config_path = "test_cases.json"

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_baseline_chatbot(user_query: str, provider):
    """
    Dựng Chatbot gốc (Baseline) không có công cụ.
    """
    print(f"\n💬 [CHATBOT BASELINE] Câu hỏi: {user_query}")
    print(f"⚙️ System Prompt: {CHATBOT_BASELINE_PROMPT.strip()}")

    # Gọi LLM Provider thực hiện sinh câu trả lời
    response = provider.generate(user_query, system_prompt=CHATBOT_BASELINE_PROMPT)
    print(f"🤖 Chatbot trả lời:\n{response}")


# =====================================================================
# 🧩 MẢNH 1 — ĐỌC "Action:" TRONG CÂU TRẢ LỜI CỦA LLM
# =====================================================================
def parse_action(response: str):
    """
    Tìm dòng Action trong câu trả lời của LLM và tách ra tên tool + tham số.

    Ví dụ:  "Thought: ...\\nAction: create_return_ticket['DH1001', 'Tai nghe rè']"
       ->   {"tool": "create_return_ticket", "args": ["DH1001", "Tai nghe rè"]}

    Không tìm thấy dòng Action đúng khuôn thì trả None.
    Không bắt buộc phải có dòng "Thought:" (LLM đôi khi bỏ qua dòng này).
    """
    # Mẫu cần tìm:  Action: <tên_tool>[<phần tham số>]
    match = re.search(r"Action:\s*([A-Za-z_]\w*)\s*\[(.*?)\]", response, re.DOTALL)
    if not match:
        return None

    tool_name = match.group(1)
    raw_args = match.group(2)

    # Phần tham số dạng  'DH1001', 'Tai nghe rè'  -> biến thành danh sách Python
    try:
        args = ast.literal_eval(f"[{raw_args}]")
    except (ValueError, SyntaxError):
        # LLM quên dấu nháy -> tách thủ công theo dấu phẩy
        args = [a.strip().strip("'\"") for a in raw_args.split(",") if a.strip()]

    return {"tool": tool_name, "args": [str(a) for a in args]}


# =====================================================================
# 🧩 MẢNH 2 — ĐỌC "Final Answer:" TRONG CÂU TRẢ LỜI CỦA LLM
# =====================================================================
def extract_final_answer(response: str):
    """Lấy nội dung phía sau 'Final Answer:'. Không có thì trả None."""
    match = re.search(r"Final Answer:\s*(.*)", response, re.DOTALL)
    return match.group(1).strip() if match else None


# =====================================================================
# 🧩 MẢNH 3 — CHẠY TOOL THEO TÊN
# =====================================================================
def execute_tool(tool_name: str, args: list) -> str:
    """
    Tra tên tool trong danh bạ AVAILABLE_TOOLS rồi gọi hàm tương ứng.
    Gặp lỗi thì trả chuỗi "LỖI: ..." (không làm sập chương trình), vì chuỗi này
    sẽ được đưa vào lịch sử cho LLM đọc và tự sửa ở vòng sau.
    """
    if tool_name not in AVAILABLE_TOOLS:
        return (f"LỖI: Tool '{tool_name}' không tồn tại. "
                f"Chỉ được dùng: {', '.join(AVAILABLE_TOOLS)}.")

    try:
        return AVAILABLE_TOOLS[tool_name](*args)
    except TypeError:
        return (f"LỖI: Gọi '{tool_name}' sai số lượng tham số (đã truyền {len(args)}). "
                f"Hãy xem lại cách gọi trong danh sách công cụ.")
    except Exception as exc:
        return f"LỖI: Tool '{tool_name}' gặp sự cố: {exc}"


# =====================================================================
# 🔄 MẢNH 4 — VÒNG LẶP REACT
# =====================================================================
def run_react_agent(user_query: str, provider):
    """
    Vòng lặp ReAct:  LLM nghĩ -> đọc Action -> chạy tool -> nối Observation vào lịch sử -> lặp lại

    Trả về dict: {"answer": câu trả lời cuối, "tools_used": danh sách tool đã gọi}
    """
    print(f"\n🤖 [REACT AGENT] Câu hỏi: {user_query}")

    # Lịch sử hội thoại. LLM không có trí nhớ, nên mỗi vòng ta gửi lại TOÀN BỘ chuỗi này.
    history = f"Câu hỏi của khách hàng: {user_query}\n"
    tools_used = []           # tool LLM muốn gọi (kể cả lần bị chặn)
    action_counts = {}        # 🛡️ A2: đếm số lần gọi mỗi cặp tool + tham số
    succeeded_tools = set()   # 🛡️ A3: tool đã chạy THÀNH CÔNG (không trả "LỖI:")
    ticket_created = False    # 🛡️ A4: đã có phiếu nào được tạo THÀNH CÔNG chưa

    for step in range(1, MAX_ITERATIONS + 1):
        print(f"\n--- 🔄 Vòng {step}/{MAX_ITERATIONS} ---")

        # 1. LLM đọc luật chơi + lịch sử, rồi viết bước tiếp theo
        raw_response = provider.generate(history, system_prompt=REACT_SYSTEM_PROMPT)

        # 🛡️ A1 — CHỐNG BỊA OBSERVATION: Observation chỉ được đến từ tool thật.
        # LLM tự viết "Observation:" thì cắt bỏ nó và MỌI THỨ phía sau (kể cả Final Answer bịa).
        response = raw_response.split("Observation:")[0].strip()
        print(f"🧠 LLM trả lời:\n{response}")
        if response != raw_response.strip():
            print("🛡️  [A1] LLM tự viết 'Observation:' — đã cắt bỏ phần bịa đặt phía sau.")

        # 2. Có Final Answer -> kiểm tra rồi mới cho xong việc
        final_answer = extract_final_answer(response)
        if final_answer:
            # 🛡️ A4 — CHỐNG NÓI DỐI VỀ HÀNH ĐỘNG: chưa có phiếu THÀNH CÔNG thì không được nói "đã tạo phiếu".
            if "đã tạo phiếu" in final_answer.lower() and not ticket_created:
                observation = ("LỖI: Bạn nói 'đã tạo phiếu' nhưng chưa có lần create_return_ticket nào "
                               "trả về THÀNH CÔNG. Không được nói dối về hành động. "
                               "Hãy trả lời lại khách cho đúng sự thật.")
                print("🛡️  [A4] Final Answer nói 'đã tạo phiếu' nhưng chưa có phiếu thật — không chấp nhận.")
            else:
                print(f"\n🏁 Final Answer: {final_answer}")
                return {"answer": final_answer, "tools_used": tools_used}
        else:
            # 3. Có Action -> kiểm tra rồi mới chạy tool
            action = parse_action(response)
            if action:
                tool = action["tool"]
                tools_used.append(tool)
                print(f"🛠️  LLM muốn gọi: {tool}{action['args']}")

                # 🛡️ A2 — CHỐNG KẸT VÒNG LẶP: đếm số lần gọi đúng tool này với đúng tham số này
                signature = f"{tool}{action['args']}"
                action_counts[signature] = action_counts.get(signature, 0) + 1

                # 🛡️ A3 — CHỐNG ĐI TẮT: các tool bắt buộc phải gọi thành công trước đó
                missing = [t for t in TOOL_PRECONDITIONS.get(tool, []) if t not in succeeded_tools]

                if action_counts[signature] > MAX_REPEATED_ACTIONS:
                    observation = (f"CẢNH BÁO: Bạn đã gọi {signature} {action_counts[signature]} lần với "
                                   f"cùng tham số, kết quả sẽ không đổi. Hãy dùng các Observation đã có "
                                   f"để trả lời bằng Final Answer.")
                    print(f"🛡️  [A2] {signature} bị lặp lần {action_counts[signature]} — không chạy tool.")
                elif missing:
                    observation = (f"LỖI: phải gọi {', '.join(missing)} trước khi gọi {tool}. "
                                   f"Không được đoán dữ liệu.")
                    print(f"🛡️  [A3] Chưa gọi {', '.join(missing)} — không cho chạy {tool}.")
                else:
                    observation = execute_tool(tool, action["args"])
                    if not observation.startswith("LỖI:"):
                        succeeded_tools.add(tool)
                    if tool == "create_return_ticket" and observation.startswith("THÀNH CÔNG"):
                        ticket_created = True
            else:
                observation = ("LỖI: Không đọc được Action hay Final Answer. Hãy viết đúng định dạng: "
                               "Thought + Action: tên_tool['tham số'], hoặc Thought + Final Answer.")

        print(f"👁️  Observation: {observation}")

        # 4. Nối câu trả lời + kết quả tool vào lịch sử -> vòng sau LLM "nhớ" được
        history += f"\n{response}\nObservation: {observation}\n"

    # 🛡️ Hết số vòng cho phép mà chưa có Final Answer
    fallback = ("Xin lỗi anh/chị, em chưa thể xử lý xong yêu cầu này. "
                "Em xin phép chuyển sang nhân viên CSKH để hỗ trợ anh/chị ạ.")
    print(f"\n🛡️ Đã hết {MAX_ITERATIONS} vòng mà chưa xong. Trả câu dự phòng: {fallback}")
    return {"answer": fallback, "tools_used": tools_used}


if __name__ == "__main__":
    print("==================================================")
    print("🏫 ĐẠI HỌC VINUNI - BÀI LAB 3: CHATBOT VS REACT AGENT")
    print("==================================================")

    # Khởi tạo Multi-Provider LLM Adapter (Đọc từ biến môi trường LLM_PROVIDER)
    provider = get_llm_provider()
    model_name = getattr(provider, "model_name", "Offline Mock Mode")
    print(f"🔌 LLM Provider đang hoạt động: {provider.__class__.__name__} (Model: {model_name})")

    tests = load_test_cases()
    print(f"✅ Đã tải thành công {len(tests)} Test Cases từ config/test_cases.json\n")

    if len(sys.argv) > 1:
        # python src/app.py <id>  ->  chạy ReAct Agent cho 1 test case
        try:
            case_id = int(sys.argv[1])
        except ValueError:
            print(f"❌ '{sys.argv[1]}' không phải số. Ví dụ đúng: python src/app.py 3")
            sys.exit(1)

        case = next((c for c in tests if c["id"] == case_id), None)
        if case is None:
            print(f"❌ Không có test case id = {case_id}. Các id hợp lệ: {[c['id'] for c in tests]}")
            sys.exit(1)

        print("=" * 70)
        print(f"🧪 TEST CASE #{case['id']} — {case['category']}")
        print(f"🎯 Kỳ vọng: {case['expected_behavior']}")
        print("=" * 70)

        result = run_react_agent(case["question"], provider)

        print("\n" + "=" * 70)
        print(f"📋 Tool đã gọi : {result['tools_used'] or '(không gọi tool nào)'}")
        print(f"📋 Bắt buộc gọi: {case['expected_tools'] or '(không)'}")
        print(f"📋 Cấm gọi     : {case['forbidden_tools'] or '(không)'}")
        print("=" * 70)
    else:
        # Không có số -> Chatbot Baseline trả lời toàn bộ bộ đề (như Bước 5)
        print("--- DEMO: CHATBOT BASELINE TRẢ LỜI TOÀN BỘ TEST CASE ---")
        for case in tests:
            print("\n" + "=" * 70)
            print(f"🧪 TEST CASE #{case['id']} — {case['category']}")
            print("=" * 70)
            run_baseline_chatbot(case["question"], provider)
