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
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

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

# 3. 모델 자유 선택 및 연결 시스템
MODEL_MAP = {
    "⚡ Gemini 1.5 Flash (가성비/빠른 추출)": "models/gemini-1.5-flash",
    "🧠 Gemini 1.5 Pro (고성능/심층 분석)": "models/gemini-1.5-pro",
    "🚀 Gemini 2.0 Flash (최신/초고속)": "models/gemini-2.0-flash-exp"
}

@st.cache_resource
def get_engine(model_id):
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None
    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(model_id)
    except Exception as e:
        st.error(f"연결 오류: {e}")
        return None

with st.sidebar:
    st.header("🔬 생체역학 연구실 엔진 설정")
    selected_label = st.selectbox("사용할 AI 모델을 고르세요", list(MODEL_MAP.keys()))
    selected_model_id = MODEL_MAP[selected_label]
    model = get_engine(selected_model_id)

    if model:
        st.success(f"✅ 가동 중: {selected_model_id}")
    else:
        st.error("❌ API Key 확인 필요")

    st.markdown("---")
    st.caption("※ 분석 중 429 에러(할당량 초과)가 발생하면, 즉시 Flash 모델로 변경해서 이어가세요.")

@st.cache_resource
def init_gemini():
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None, "API Key 없음"
    try:
        genai.configure(api_key=api_key)
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority = ["models/gemini-1.5-flash", "models/gemini-1.5-pro"]
        chosen_model = next((m for m in priority if m in available_models), available_models[0])
        return genai.GenerativeModel(chosen_model), chosen_model
    except Exception as e: return None, str(e)

model, model_name = init_gemini()

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

            # ✅ 수정: 논문 형식 보존 추출로 업그레이드
            with st.expander("📋 논문 텍스트 추출 (논문 형식 보존 모드)", expanded=True):

                extract_mode = st.radio(
                    "추출 방식 선택",
                    ["🤖 AI 정밀 판독 (이미지→텍스트)", "⚡ 고속 구조 추출 (PDF 직접 파싱)"],
                    horizontal=True
                )

                if st.button("🚀 추출 실행"):
                    with st.spinner("논문 구조를 분석 중입니다..."):

                        # ── AI 판독 모드 ──────────────────────────
                        if "AI" in extract_mode:
                            try:
                                pix_ocr = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                                img_ocr = Image.open(io.BytesIO(pix_ocr.tobytes()))
                                prompt = """이 논문 페이지를 아래 규칙에 따라 정확히 추출하세요.

[규칙]
1. 제목(가장 큰 글씨) → ## 제목
2. 소제목(중간 글씨) → ### 소제목
3. Abstract/요약 → > (인용 블록으로 감싸기)
4. 본문 → 일반 텍스트, 문단 구분 유지
5. 표 → 마크다운 표(| 형식)로 변환
6. 참고문헌 → #### References 아래 번호 목록
7. 2단 컬럼이면 왼쪽 컬럼 먼저, 오른쪽 컬럼 나중에
8. 수식은 그대로 텍스트로 표현
9. 원문 순서를 절대 바꾸지 말 것

논문 형식을 최대한 살려서 추출하세요."""
                                response = model.generate_content([prompt, img_ocr])
                                st.session_state[f"ocr_{page_num}"] = response.text
                                st.rerun()
                            except Exception as e:
                                st.error(f"분석 오류: {e}")

                        # ── 고속 구조 추출 모드 ───────────────────
                        else:
                            blocks = page.get_text("dict", sort=True)["blocks"]

                            page_width = page.rect.width
                            mid_x = page_width / 2

                            left_blocks  = [b for b in blocks if b.get("type") == 0 and b["bbox"][0] < mid_x - 20]
                            right_blocks = [b for b in blocks if b.get("type") == 0 and b["bbox"][0] >= mid_x - 20]

                            is_two_column = (
                                len(left_blocks) > 1 and len(right_blocks) > 1
                                and max((b["bbox"][2] for b in left_blocks), default=0) < mid_x + 30
                            )

                            sorted_blocks = (left_blocks + right_blocks) if is_two_column else [
                                b for b in blocks if b.get("type") == 0
                            ]

                            extracted_parts = []

                            for b in sorted_blocks:
                                para_text = ""
                                max_size = 0
                                bold_char_count = 0
                                total_char_count = 0

                                for line in b.get("lines", []):
                                    for span in line.get("spans", []):
                                        text = span.get("text", "").strip()
                                        if text:
                                            size = span.get("size", 0)
                                            max_size = max(max_size, size)
                                            chars = len(text)
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

                                # ── 계층별 제목 분류 ─────────────────
                                if total_char_count < 120:
                                    if max_size >= 16:
                                        extracted_parts.append(f"\n## {clean}\n")
                                    elif max_size >= 13 or (bold_char_count / max(total_char_count, 1)) > 0.7:
                                        extracted_parts.append(f"\n### {clean}\n")
                                    elif max_size >= 11 and (bold_char_count / max(total_char_count, 1)) > 0.4:
                                        extracted_parts.append(f"\n#### {clean}\n")
                                    else:
                                        extracted_parts.append(para_text)
                                else:
                                    if any(kw in clean[:30].lower() for kw in ["abstract", "요약", "summary"]):
                                        extracted_parts.append(f"\n> **Abstract**\n> {clean}\n")
                                    elif any(kw in clean[:20].lower() for kw in ["reference", "bibliography", "참고문헌"]):
                                        extracted_parts.append(f"\n#### References\n{clean}")
                                    else:
                                        extracted_parts.append(para_text)

                            st.session_state[f"ocr_{page_num}"] = "\n\n".join(extracted_parts)
                            st.rerun()

                # 결과 출력
                if f"ocr_{page_num}" in st.session_state:
                    final_text = st.session_state[f"ocr_{page_num}"]
                    st.markdown(final_text)

                    with st.expander("📄 텍스트 복사용 (원문 그대로)"):
                        st.text_area("", final_text, height=300, label_visibility="collapsed")

        with col_tool:
            st.subheader("🧪 문단 정밀 분석")
            raw_input = st.text_area("분석할 문단을 여기에 붙여넣으세요", height=200)

            c1, c2 = st.columns(2)

            def safe_gen(prompt):
                try: return model.generate_content(prompt).text
                except Exception as e:
                    if "429" in str(e): return "⚠️ 하루 사용량을 초과했습니다."
                    return f"❌ 오류: {e}"

            if c1.button("🌐 전문 직역 실행"):
                if raw_input.strip():
                    with st.spinner("번역 중..."):
                        st.info(safe_gen(f"스포츠 생체역학 전문가로서 직역하세요:\n\n{raw_input}"))

            if c2.button("🧠 심층 역학 분석"):
                if raw_input.strip():
                    with st.spinner("분석 중..."):
                        st.success(safe_gen(f"생체역학 박사로서 상세 분석하세요:\n\n{raw_input}"))

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

            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]): st.markdown(msg["content"])
