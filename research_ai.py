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

# --- 동적 모델 연결 (할당량 관리 및 에러 방지) ---
@st.cache_resource
def init_gemini():
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None, "API Key 없음"
    try:
        genai.configure(api_key=api_key)
        available_models = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
        # 할당량이 넉넉한 1.5-flash를 기본으로, pro를 보조로 사용
        priority = ["models/gemini-1.5-flash", "models/gemini-1.5-pro"]
        chosen_model = next((m for m in priority if m in available_models), available_models[0])
        return genai.GenerativeModel(chosen_model), chosen_model
    except Exception as e: return None, str(e)

model, model_name = init_gemini()

# 3. PDF 업로드 및 [페이지 전체 추출] 뷰어
uploaded_file = st.file_uploader("분석할 논문(PDF) 업로드", type="pdf")

if uploaded_file:
    col_view, col_tool = st.columns([1.2, 1])
    file_bytes = uploaded_file.getvalue()

    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        total_pages = len(doc)

        with col_view:
            st.subheader("📄 논문 원문 분석기")
            
            # [유지] 아이패드 드래그 해결을 위한 네이티브 호출 버튼
            st.download_button(
                label="🚀 [iPad 필수] 논문 새 창에서 열기 (직접 드래그용)",
                data=file_bytes,
                file_name=uploaded_file.name,
                mime="application/pdf"
            )
            
            page_num = st.select_slider("페이지 이동", options=range(1, total_pages + 1)) - 1
            page = doc.load_page(page_num)

            # 시각적 확인용 고해상도 이미지
            pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2))
            st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)

            st.markdown("---")
            
            # [핵심] 페이지 전체 누락 없는 정밀 추출 섹션
            with st.expander("📋 논문 텍스트 전체 추출 (정밀 포맷팅)", expanded=True):
                
                # 1. AI OCR 판독 (가장 확실한 전체 추출)
                if st.button("🚀 AI로 이 페이지 전체 정밀 판독 (텍스트 누락 시 클릭)"):
                    with st.spinner("AI가 페이지 전체 문맥을 읽어내는 중입니다..."):
                        try:
                            pix_ocr = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                            img_ocr = Image.open(io.BytesIO(pix_ocr.tobytes()))
                            # 전체 내용을 빠짐없이 추출하도록 프롬프트 강화
                            prompt = "이 페이지에 있는 모든 텍스트(제목, 본문, 주석, 표 내용 포함)를 하나도 빠짐없이 추출해줘. 띄어쓰기를 정확히 맞추고, 제목은 ### **제목** 형식으로 표시해줘."
                            response = model.generate_content([prompt, img_ocr])
                            st.session_state[f"ocr_{page_num}"] = response.text
                            st.rerun()
                        except Exception as e:
                            st.error(f"AI 사용량 초과 혹은 오류: {e}")

                if f"ocr_{page_num}" in st.session_state:
                    final_text = st.session_state[f"ocr_{page_num}"]
                else:
                    # 2. 프로그램 방식 전체 추출 (누락 방지 로직)
                    # 모든 텍스트 블록을 읽기 순서대로 가져옵니다.
                    blocks = page.get_text("blocks", sort=True)
                    extracted_parts = []
                    
                    for b in blocks:
                        # b[4]는 텍스트 내용, b[6]은 블록 타입(0은 텍스트)
                        if b[6] == 0:
                            text = b[4].strip()
                            # 줄바꿈 정제 및 띄어쓰기 보정
                            text = text.replace("\n", " ")
                            text = re.sub(r'(\w)-\s+(\w)', r'\1\2', text) # 하이픈 단어 결합
                            if text:
                                extracted_parts.append(text)
                    
                    final_text = "\n\n".join(extracted_parts)
                    
                    # 만약 블록 추출 결과가 너무 적으면 단순 텍스트 추출로 백업
                    if len(final_text) < 100:
                        final_text = page.get_text("text", sort=True)

                # 최종 결과 출력 (박사님 요청대로 복사용 칸 없이 마크다운으로만)
                st.markdown(final_text)

    with col_tool:
        # --- 🧪 텍스트 정밀 분석 도구 ---
        st.subheader("🧪 문단 정밀 분석")
        raw_input = st.text_area("분석할 문단을 아래에 붙여넣으세요", height=200, placeholder="왼쪽에서 추출된 텍스트를 복사해 넣으세요.")

        c1, c2 = st.columns(2)
        
        def safe_gen(prompt):
            try: return model.generate_content(prompt).text
            except Exception as e:
                if "429" in str(e): return "⚠️ 하루 사용량을 초과했습니다. 내일 다시 시도하세요."
                return f"❌ 오류: {e}"

        if c1.button("🌐 전문 직역 실행"):
            if raw_input.strip():
                with st.spinner("번역 중..."):
                    st.info(safe_gen(f"생체역학 전문가로서 한국어로 자연스럽게 직역하세요:\n\n{raw_input}"))

        if c2.button("🧠 심층 역학 분석"):
            if raw_input.strip():
                with st.spinner("기전 분석 중..."):
                    st.success(safe_gen(f"스포츠 생체역학 박사로서 상세 분석하세요:\n\n{raw_input}"))

        st.markdown("---")
        st.subheader("💬 데이터 및 이미지 질의응답")
        data_img = st.file_uploader("📸 그래프/사진 직접 업로드", type=["png", "jpg", "jpeg"])
        if data_img: st.image(data_img, width=300)

        chat_query = st.text_area("질문을 입력하세요", height=100)
        if st.button("🚀 질문 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.append({"role": "user", "content": chat_query})
                with st.spinner("AI 분석 중..."):
                    contents = [f"생체역학 전문가로서 상세히 답변하세요: {chat_query}"]
                    if data_img: contents.append(Image.open(data_img))
                    ans = safe_gen(contents)
                    st.session_state.chat_history.append({"role": "assistant", "content": ans})

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
