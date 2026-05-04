import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import re

# 1. 페이지 레이아웃 및 보안 설정
st.set_page_config(layout="wide", page_title="Biomechanics Pro Lab", page_icon="🔬")

# --- 보안 잠금 시스템 ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def check_password():
    if not st.session_state.authenticated:
        st.title("🔒 Biomechanics Lab 보안")
        pwd = st.text_input("연구소 비밀번호를 입력하세요", type="password")
        if pwd == st.secrets.get("LAB_PASSWORD", "1234"):
            st.session_state.authenticated = True
            st.rerun()
        elif pwd:
            st.error("비밀번호가 틀렸습니다.")
        st.stop()

check_password()

# --- [해결] 429 에러 방지용 모델 우선순위 조정 ---
@st.cache_resource
def init_gemini():
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None, "API Key 없음"
    try:
        genai.configure(api_key=api_key)
        available_models = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
        # 무료 할당량이 가장 넉넉한 1.5-flash를 1순위로 설정하여 끊김을 방지합니다.
        priority = ["models/gemini-1.5-flash", "models/gemini-1.5-pro"]
        chosen_model = next((m for m in priority if m in available_models), available_models[0])
        return genai.GenerativeModel(chosen_model), chosen_model
    except Exception as e: return None, str(e)

model, model_name = init_gemini()

# 3. PDF 업로드 및 [아이패드 완벽 대응] 뷰어
uploaded_file = st.file_uploader("분석할 논문(PDF) 업로드", type="pdf")

if uploaded_file:
    col_view, col_tool = st.columns([1.2, 1])
    file_bytes = uploaded_file.getvalue()

    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        total_pages = len(doc)

        with col_view:
            st.subheader("📄 논문 원문 분석기")
            
            # [해결] 아이패드 드래그 차단 우회: 다운로드 버튼을 통한 네이티브 뷰어 호출
            # 아이패드에서 이 버튼을 누르면 브라우저가 '보기'를 제안하며, 거기서 100% 드래그가 가능합니다.
            st.download_button(
                label="🚀 [iPad 필수] 논문 새 창에서 열기 (직접 드래그용)",
                data=file_bytes,
                file_name=uploaded_file.name,
                mime="application/pdf",
                help="클릭 후 '보기(View)'를 선택하면 새 탭에서 드래그 가능한 원문이 열립니다."
            )
            
            page_num = st.select_slider("페이지 이동", options=range(1, total_pages + 1)) - 1
            page = doc.load_page(page_num)

            # 고해상도 이미지 (시각적 확인용)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2))
            st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)

            st.markdown("---")
            
            # [해결] 띄어쓰기 뭉개짐 및 전체 페이지 누락 해결 로직
            with st.expander("📋 논문 텍스트 정밀 추출 (전체 페이지 로드)", expanded=True):
                # 1. AI OCR 판독 버튼 (가장 정확함)
                if st.button("🚀 AI 정밀 판독 실행 (텍스트가 엉망일 때 클릭)"):
                    with st.spinner("AI가 페이지 전체를 읽고 있습니다..."):
                        try:
                            pix_ocr = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                            img_ocr = Image.open(io.BytesIO(pix_ocr.tobytes()))
                            response = model.generate_content(["이 페이지의 모든 텍스트를 누락 없이 추출해줘. 특히 단어 사이 띄어쓰기를 완벽하게 맞춰서 한국인이 읽기 좋게 정리해.", img_ocr])
                            st.session_state[f"ocr_{page_num}"] = response.text
                            st.rerun()
                        except Exception as e:
                            st.error(f"AI 사용량 초과 혹은 에러: {e}")

                if f"ocr_{page_num}" in st.session_state:
                    structured_text = st.session_state[f"ocr_{page_num}"]
                else:
                    # [해결] 기본 추출 방식 강화: 띄어쓰기 보정 알고리즘 적용
                    # 단순히 긁는 것이 아니라 블록 단위로 재조합하여 띄어쓰기를 살립니다.
                    blocks = page.get_text("blocks")
                    blocks.sort(key=lambda b: (b[1], b[0])) # 위에서 아래로 정렬
                    extracted_parts = []
                    for b in blocks:
                        # 줄바꿈을 공백으로 바꾸고 불필요한 연속 공백 제거
                        text = b[4].replace("\n", " ").strip()
                        # 문장 끝 하이픈 제거 로직 추가
                        text = re.sub(r'(\w)-\s+(\w)', r'\1\2', text)
                        if text: extracted_parts.append(text)
                    structured_text = "\n\n".join(extracted_parts)

                # [박사님 요청] 불필요한 복사 칸을 없애고 마크다운으로 깔끔하게 표시
                st.markdown(structured_text)

    with col_tool:
        # --- 🧪 텍스트 정밀 분석 ---
        st.subheader("🧪 문단 정밀 분석")
        raw_input = st.text_area("분석할 문단을 아래에 붙여넣으세요", height=200, placeholder="왼쪽에서 직접 드래그하거나 위 판독 결과를 복사해 넣으세요.")

        c1, c2 = st.columns(2)
        
        def safe_gen(prompt):
            try: return model.generate_content(prompt).text
            except Exception as e:
                if "429" in str(e): return "⚠️ 하루 할당량을 초과했습니다. 내일 다시 시도하세요."
                return f"❌ 오류: {e}"

        if c1.button("🌐 전문 직역 실행"):
            if raw_input.strip():
                with st.spinner("번역 중..."):
                    st.info(safe_gen(f"스포츠 생체역학 전문가로서 한국어로 직역하세요:\n\n{raw_input}"))

        if c2.button("🧠 심층 역학 분석"):
            if raw_input.strip():
                with st.spinner("분석 중..."):
                    st.success(safe_gen(f"생체역학 박사로서 상세 분석하세요:\n\n{raw_input}"))

        st.markdown("---")
        st.subheader("💬 데이터 통합 질의응답")
        data_img = st.file_uploader("📸 그래프/사진 직접 선택", type=["png", "jpg", "jpeg"])
        if data_img: st.image(data_img, width=300)

        chat_query = st.text_area("질문을 입력하세요", height=100)
        if st.button("🚀 분석 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.append({"role": "user", "content": chat_query})
                with st.spinner("AI 분석 중..."):
                    contents = [f"생체역학 전문가로서 답변하세요: {chat_query}"]
                    if data_img: contents.append(Image.open(data_img))
                    ans = safe_gen(contents)
                    st.session_state.chat_history.append({"role": "assistant", "content": ans})

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
