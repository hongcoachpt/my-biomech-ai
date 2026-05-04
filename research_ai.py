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

# --- 동적 모델 연결 시스템 (404/429 대응) ---
@st.cache_resource
def init_gemini():
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None, "API Key 없음"
    try:
        genai.configure(api_key=api_key)
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority = ["models/gemini-1.5-pro", "models/gemini-1.5-flash", "models/gemini-pro"]
        chosen_model = next((m for m in priority if m in available_models), available_models[0])
        return genai.GenerativeModel(chosen_model), chosen_model
    except Exception as e: return None, str(e)

model, model_name = init_gemini()

if model:
    st.sidebar.success(f"✅ 엔진 가동: {model_name}")
else:
    st.sidebar.error(f"❌ AI 연결 실패: {model_name}")
    st.stop()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

st.title("🔬 스마트 생체역학 통합 연구실")

# 3. PDF 업로드 및 멀티 레이어 뷰어
uploaded_file = st.file_uploader("분석할 논문(PDF) 업로드", type="pdf")

if uploaded_file:
    col_view, col_tool = st.columns([1.2, 1])
    file_bytes = uploaded_file.getvalue()

    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        total_pages = len(doc)

        with col_view:
            st.subheader("📄 논문 원문 분석기")
            
            # [핵심] 보기 방식 선택지 추가
            v_mode = st.radio("보기 방식 선택", ["안전 이미지 모드", "직접 드래그 모드 (iPad 권장)"], horizontal=True)
            
            page_num = st.select_slider("페이지 이동", options=range(1, total_pages + 1)) - 1
            page = doc.load_page(page_num)

            if v_mode == "안전 이미지 모드":
                # 고해상도 이미지 렌더링
                pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                page_img = Image.open(io.BytesIO(pix.tobytes()))
                st.image(page_img, use_container_width=True)
            else:
                # [박사님 요청] 논문에서 직접 드래그할 수 있도록 PDF 네이티브 임베딩
                base64_pdf = base64.b64encode(file_bytes).decode('utf-8')
                # 아이패드 최적화를 위해 embed 대신 iframe/object 혼합 방식 사용
                pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}#page={page_num+1}" width="100%" height="900px"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
                st.info("💡 드래그가 안 될 경우: 주소창 'AA' 버튼 → '데스크탑 웹사이트 요청'을 켜주세요.")

            st.markdown("---")
            # [수정] 텍스트 에어리어 삭제하고 OCR 판독 결과만 표시
            with st.expander("📝 AI 정밀 텍스트 판독 결과", expanded=True):
                if st.button("🚀 AI 정밀 판독 실행 (텍스트 누락 시 클릭)"):
                    with st.spinner("AI가 페이지를 읽고 있습니다..."):
                        try:
                            # 이미지 렌더링 (OCR용)
                            pix_ocr = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                            page_img_ocr = Image.open(io.BytesIO(pix_ocr.tobytes()))
                            ocr_prompt = "이 이미지의 논문 내용을 텍스트로 추출해줘. 제목/소제목은 굵게 표시하고 문단을 잘 나눠줘."
                            response = model.generate_content([ocr_prompt, page_img_ocr])
                            st.session_state[f"ocr_{page_num}"] = response.text
                            st.rerun()
                        except Exception as e:
                            st.error(f"AI 판독 오류: {e}")

                if f"ocr_{page_num}" in st.session_state:
                    st.markdown(st.session_state[f"ocr_{page_num}"])
                else:
                    st.caption("AI 판독 버튼을 누르면 이 페이지의 본문이 여기에 나타납니다.")

    with col_tool:
        # --- 🧪 정밀 분석 도구 ---
        st.subheader("🧪 문단 정밀 분석")
        raw_input = st.text_area("분석할 문단을 여기에 붙여넣으세요", height=200, placeholder="왼쪽에서 직접 드래그하거나 OCR 결과를 복사해 넣으세요.")

        c1, c2 = st.columns(2)
        
        def safe_gen(prompt):
            try:
                return model.generate_content(prompt).text
            except Exception as e:
                if "429" in str(e): return "⚠️ 사용량 초과입니다. 1분 뒤 시도하세요."
                return f"❌ 오류: {e}"

        if c1.button("🌐 전문 직역 실행"):
            if raw_input.strip():
                with st.spinner("번역 중..."):
                    st.info(safe_gen(f"스포츠 생체역학 전문가로서 직역하세요:\n\n{raw_input}"))

        if c2.button("🧠 심층 역학 분석"):
            if raw_input.strip():
                with st.spinner("역학적 기전 분석 중..."):
                    st.success(safe_gen(f"생체역학 박사로서 상세 분석하세요:\n\n{raw_input}"))

        st.markdown("---")
        st.subheader("💬 데이터 통합 질의응답")
        data_img = st.file_uploader("📸 그래프/사진 업로드", type=["png", "jpg", "jpeg"])
        if data_img: st.image(data_img, width=300)

        chat_query = st.text_area("질문을 입력하세요", height=100)
        if st.button("🚀 질문 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.append({"role": "user", "content": chat_query})
                with st.spinner("AI 분석 중..."):
                    contents = [f"생체역학 전문가로서 답변하세요: {chat_query}"]
                    if data_img: contents.append(Image.open(data_img))
                    ans = safe_gen(contents)
                    st.session_state.chat_history.append({"role": "assistant", "content": ans})

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
