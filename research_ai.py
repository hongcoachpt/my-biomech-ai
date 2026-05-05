import streamlit as st
import pandas as pd
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import re
from streamlit_paste_button import paste_image_button

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="Biomechanics Pro Lab", page_icon="🔬")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "translation_result" not in st.session_state:
    st.session_state.translation_result = ""
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = ""
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "token_used_today" not in st.session_state:
    st.session_state.token_used_today = 0
if "request_count_today" not in st.session_state:
    st.session_state.request_count_today = 0

# 2. 보안 잠금 시스템
def check_password():
    if st.session_state.authenticated:
        return
    st.title("🔒 Biomechanics Lab 보안")
    correct_pwd = st.secrets.get("LAB_PASSWORD", "1234")
    pwd = st.text_input("홍박사 연구소 비밀번호를 입력하세요", type="password")
    if pwd:
        if pwd == correct_pwd:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ 비밀번호가 다릅니다.")
    st.stop()

check_password()

# 3. 모델 설정
# ✅ 2025년 5월 기준 정상 작동 모델명으로 교체
MODEL_MAP = {
    "⚡ Gemini 2.5 Flash (기본 추천)":  "gemini-2.5-flash-preview-04-17",
    "🚀 Gemini 2.0 Flash (안정)":       "gemini-2.0-flash",
    "🧠 Gemini 2.5 Pro (심층 분석)":    "gemini-2.5-pro-preview-03-25",
}

MODEL_LIMIT = {
    "gemini-2.5-flash-preview-04-17": 500,
    "gemini-2.0-flash":               1500,
    "gemini-2.5-pro-preview-03-25":   25,
}

# ✅ 핵심 수정: @st.cache_resource 제거 → 캐시 문제 완전 해결
def get_engine(model_id):
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(model_id)
    except Exception as e:
        st.error(f"연결 오류: {e}")
        return None

# ── 사이드바 ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔬 생체역학 연구실 엔진 설정")
    selected_label = st.selectbox("사용할 AI 모델을 고르세요", list(MODEL_MAP.keys()))
    selected_model_id = MODEL_MAP[selected_label]

    # ✅ 매번 새로 연결 (캐시 없음)
    model = get_engine(selected_model_id)

    if model:
        st.success(f"✅ 가동 중: {selected_model_id}")
    else:
        st.error("❌ API Key 확인 필요")

    st.markdown("---")

    # 실시간 사용량 표시
    daily_limit = MODEL_LIMIT.get(selected_model_id, 1500)
    used = st.session_state.request_count_today
    remaining = max(daily_limit - used, 0)
    usage_pct = min(used / daily_limit, 1.0)

    st.markdown("### 📊 오늘 사용량")

    if usage_pct < 0.5:
        bar_color = "🟢"
        status = "여유"
    elif usage_pct < 0.8:
        bar_color = "🟡"
        status = "주의"
    else:
        bar_color = "🔴"
        status = "위험"

    st.progress(usage_pct)
    st.markdown(f"""
| 항목 | 값 |
|---|---|
| {bar_color} 상태 | **{status}** |
| 사용 요청 | **{used}회** |
| 남은 요청 | **{remaining}회** |
| 하루 한도 | **{daily_limit}회** |
""")

    if st.button("🔄 사용량 초기화"):
        st.session_state.request_count_today = 0
        st.session_state.token_used_today = 0
        st.rerun()

    st.markdown("---")
    st.caption("※ 사용량은 앱 세션 기준입니다. 매일 자정 Google 서버에서 자동 초기화됩니다.")
    st.caption("※ 429 오류 시 Flash 모델로 변경하세요.")

# ── safe_gen ─────────────────────────────────────────────────────────
def safe_gen(prompt):
    try:
        response = model.generate_content(prompt)
        st.session_state.request_count_today += 1
        return response.text
    except Exception as e:
        err = str(e)
        if "429" in err:
            return "⚠️ 하루 사용량을 초과했습니다. Flash 모델로 변경해 주세요."
        if "404" in err:
            return "⚠️ 모델을 찾을 수 없습니다. 다른 모델로 변경해 주세요."
        return f"❌ 오류: {err}"

# ── PDF 표 추출 함수 ─────────────────────────────────────────────────
def extract_tables_from_page(page):
    tables = page.find_tables()
    table_md_list = []
    table_bboxes = []
    if tables and tables.tables:
        for table in tables.tables:
            try:
                df = table.to_pandas()
                if df.empty:
                    continue
                md = df.to_markdown(index=False)
                table_md_list.append((table.bbox, md))
                table_bboxes.append(table.bbox)
            except Exception:
                pass
    return table_md_list, table_bboxes

# ── 고속 구조 추출 함수 ──────────────────────────────────────────────
def extract_structured_text(page):
    table_md_list, table_bboxes = extract_tables_from_page(page)
    blocks = page.get_text("dict", sort=True)["blocks"]
    page_width = page.rect.width
    mid_x = page_width / 2

    def in_table(bbox):
        for tb in table_bboxes:
            if (bbox[0] >= tb[0] - 5 and bbox[1] >= tb[1] - 5
                    and bbox[2] <= tb[2] + 5 and bbox[3] <= tb[3] + 5):
                return True
        return False

    text_blocks = [b for b in blocks if b.get("type") == 0 and not in_table(b["bbox"])]
    left_blocks  = [b for b in text_blocks if b["bbox"][0] < mid_x - 20]
    right_blocks = [b for b in text_blocks if b["bbox"][0] >= mid_x - 20]
    is_two_column = (
        len(left_blocks) > 1 and len(right_blocks) > 1
        and max((b["bbox"][2] for b in left_blocks), default=0) < mid_x + 30
    )
    sorted_blocks = (left_blocks + right_blocks) if is_two_column else text_blocks

    all_items = [(b["bbox"][1], "block", b) for b in sorted_blocks]
    for bbox, md in table_md_list:
        all_items.append((bbox[1], "table", md))
    all_items.sort(key=lambda x: x[0])

    extracted_parts = []

    for _, item_type, content in all_items:
        if item_type == "table":
            extracted_parts.append(f"\n{content}\n")
            continue

        b = content
        para_text = ""
        max_size = 0
        bold_char_count = 0
        total_char_count = 0

        for line in b.get("lines", []):
            for span in line.get("spans", []):
                t = span.get("text", "").strip()
                if t:
                    max_size = max(max_size, span.get("size", 0))
                    chars = len(t)
                    total_char_count += chars
                    is_bold = (span.get("flags", 0) & 2**4) or ("Bold" in span.get("font", ""))
                    if is_bold:
                        bold_char_count += chars

        for line in b.get("lines", []):
            line_text = ""
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text.strip():
                    line_text += text
                    continue
                is_bold = (span.get("flags", 0) & 2**4) or ("Bold" in span.get("font", ""))
                if is_bold:
                    m = re.match(r'^(\s*)(.*?)(\s*)$', text)
                    if m:
                        leading, core, trailing = m.groups()
                        if core:
                            text = f"{leading}**{core}**{trailing}"
                line_text += text
            line_text = line_text.strip()
            if not line_text: continue
            if para_text.endswith("-"):
                para_text = para_text[:-1] + line_text
            else:
                para_text = (para_text + " " + line_text).strip() if para_text else line_text

        if not para_text.strip():
            continue

        clean = para_text.replace("**", "").strip()
        bold_ratio = bold_char_count / max(total_char_count, 1)

        if total_char_count < 150:
            if max_size >= 16:
                extracted_parts.append(f"\n---\n**{clean}**\n")
            elif max_size >= 13 or bold_ratio > 0.75:
                extracted_parts.append(f"\n**{clean}**\n")
            elif max_size >= 11 and bold_ratio > 0.4:
                extracted_parts.append(f"\n***{clean}***\n")
            else:
                extracted_parts.append(para_text)
        else:
            lower_clean = clean[:40].lower()
            if any(kw in lower_clean for kw in ["abstract", "요약", "summary"]):
                extracted_parts.append(f"\n> 📌 **Abstract**\n>\n> {clean}\n")
            elif any(kw in lower_clean for kw in ["reference", "bibliography", "참고문헌"]):
                extracted_parts.append(f"\n---\n**References**\n\n{clean}")
            elif any(kw in lower_clean for kw in ["keyword", "key word", "키워드"]):
                extracted_parts.append(f"\n> 🔑 {clean}\n")
            else:
                extracted_parts.append(para_text)

    return "\n\n".join(extracted_parts)


# 4. 메인 UI
st.title("🔬 홍박사 스마트 생체역학 연구실")

uploaded_file = st.file_uploader("분석할 논문(PDF) 업로드", type="pdf")

if uploaded_file:
    col_view, col_tool = st.columns([1.2, 1])
    file_bytes = uploaded_file.getvalue()

    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        total_pages = len(doc)

        with col_view:
            st.subheader("📄 논문 원문 분석기")

            st.download_button(
                label="🚀 [iPad 필수] 논문 새 창에서 열기 (직접 드래그용)",
                data=file_bytes,
                file_name=uploaded_file.name,
                mime="application/pdf"
            )

            page_num = st.select_slider("페이지 이동", options=range(1, total_pages + 1)) - 1
            page = doc.load_page(page_num)

            pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2))
            st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)

            st.markdown("---")

            with st.expander("📋 논문 텍스트 추출 (논문 형식 보존 모드)", expanded=True):

                extract_mode = st.radio(
                    "추출 방식 선택",
                    ["⚡ 고속 구조 추출 (PDF 직접 파싱, 토큰 0)", "🤖 AI 정밀 판독 (토큰 1회 소진)"],
                    horizontal=True
                )

                if st.button("🚀 추출 실행"):
                    with st.spinner("논문 구조를 분석 중입니다..."):
                        if "AI" in extract_mode:
                            try:
                                pix_ocr = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                                img_ocr = Image.open(io.BytesIO(pix_ocr.tobytes()))
                                prompt = """이 논문 페이지를 아래 규칙에 따라 정확히 추출하세요.
[규칙]
1. 논문 대제목 → --- 구분선 후 **굵게**
2. 섹션 제목 → **굵게**
3. 소소제목 → ***굵게이탤릭***
4. Abstract → > 📌 **Abstract** 인용블록
5. Keywords → > 🔑 인용블록
6. 본문 → 일반 텍스트, 문단 구분 유지
7. 표 → 마크다운 표(| col |) 형식으로 변환
8. 참고문헌 → --- 후 **References**
9. 2단 컬럼이면 왼쪽 먼저, 오른쪽 나중에
10. 원문 순서 절대 바꾸지 말 것"""
                                response = model.generate_content([prompt, img_ocr])
                                st.session_state.request_count_today += 1
                                st.session_state[f"ocr_{page_num}"] = response.text
                                st.rerun()
                            except Exception as e:
                                st.error(f"분석 오류: {e}")
                        else:
                            result_text = extract_structured_text(page)
                            st.session_state[f"ocr_{page_num}"] = result_text
                            st.rerun()

                if f"ocr_{page_num}" in st.session_state:
                    final_text = st.session_state[f"ocr_{page_num}"]
                    st.markdown(final_text)
                    with st.expander("📄 텍스트 복사용 (원문 그대로)"):
                        st.text_area("", final_text, height=300, label_visibility="collapsed")

        with col_tool:
            st.subheader("🧪 문단 정밀 분석")
            raw_input = st.text_area("분석할 문단을 여기에 붙여넣으세요", height=200)

            c1, c2 = st.columns(2)

            if c1.button("🌐 전문 직역 실행"):
                if raw_input.strip():
                    with st.spinner("번역 중..."):
                        st.session_state.translation_result = safe_gen(
                            f"스포츠 생체역학 전문가로서 직역하세요:\n\n{raw_input}"
                        )

            if c2.button("🧠 심층 역학 분석"):
                if raw_input.strip():
                    with st.spinner("분석 중..."):
                        st.session_state.analysis_result = safe_gen(
                            f"생체역학 박사로서 상세 분석하세요:\n\n{raw_input}"
                        )

            if st.session_state.translation_result or st.session_state.analysis_result:
                st.markdown("---")
                r1, r2 = st.columns(2)
                with r1:
                    if st.session_state.translation_result:
                        st.markdown("#### 🌐 전문 직역")
                        st.info(st.session_state.translation_result)
                with r2:
                    if st.session_state.analysis_result:
                        st.markdown("#### 🧠 심층 역학 분석")
                        st.success(st.session_state.analysis_result)

                if st.button("🗑️ 결과 초기화"):
                    st.session_state.translation_result = ""
                    st.session_state.analysis_result = ""
                    st.rerun()

            st.markdown("---")
            st.subheader("💬 데이터 및 이미지 질의응답")

            st.info("📋 아래 버튼 클릭 후 Ctrl+V 하면 캡처 이미지가 바로 들어갑니다")
            paste_result = paste_image_button(
                label="📋 캡처 이미지 붙여넣기 (Ctrl+V)",
                background_color="#f0fdf4",
                hover_background_color="#dcfce7",
            )

            if paste_result.image_data is not None:
                st.image(paste_result.image_data, width=300)
                data_img = paste_result.image_data
            else:
                data_img = None

            uploaded_img = st.file_uploader("📂 또는 파일로 업로드", type=["png", "jpg", "jpeg"])
            if uploaded_img:
                st.image(uploaded_img, width=300)
                data_img = Image.open(uploaded_img)

            chat_query = st.text_area("질문을 입력하세요", height=100)

            if st.button("🚀 분석 전송"):
                if chat_query or data_img:
                    st.session_state.chat_history.append({"role": "user", "content": chat_query})
                    with st.spinner("AI 분석 중..."):
                        if data_img is not None:
                            try:
                                if isinstance(data_img, Image.Image):
                                    img_for_gemini = data_img.convert("RGB")
                                else:
                                    img_for_gemini = Image.open(data_img).convert("RGB")
                                contents = [
                                    f"생체역학 전문가로서 이미지를 보고 답변하세요: {chat_query}",
                                    img_for_gemini
                                ]
                            except Exception as e:
                                st.error(f"이미지 변환 오류: {e}")
                                contents = f"생체역학 전문가로서 답변하세요: {chat_query}"
                        else:
                            contents = f"생체역학 전문가로서 답변하세요: {chat_query}"

                        ans = safe_gen(contents)
                        st.session_state.chat_history.append({"role": "assistant", "content": ans})

            if st.session_state.chat_history:
                st.markdown("---")
                st.markdown("#### 💬 질의응답 결과")
                for msg in st.session_state.chat_history:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

                if st.button("🗑️ 대화 초기화"):
                    st.session_state.chat_history = []
                    st.rerun()
