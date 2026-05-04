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

# --- 동적 모델 연결 (에러 대응) ---
@st.cache_resource
def init_gemini():
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None, "API Key 없음"
    try:
        genai.configure(api_key=api_key)
        available_models = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
        # 쿼터가 넉넉한 1.5-flash를 기본으로, 없으면 pro 사용
        target = next((m for m in available_models if "gemini-1.5-flash" in m), available_models[0])
        return genai.GenerativeModel(target), target
    except Exception as e: return None, str(e)

model, model_name = init_gemini()

# 3. PDF 업로드 및 [아이패드 전용] 뷰어
uploaded_file = st.file_uploader("분석할 논문(PDF) 업로드", type="pdf")

if uploaded_file:
    col_view, col_tool = st.columns([1.2, 1])
    file_bytes = uploaded_file.getvalue()

    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        total_pages = len(doc)

        with col_view:
            st.subheader("📄 논문 원문 분석기")
            
            # [해결] 아이패드 드래그 차단 우회: 네이티브 뷰어 강제 호출
            base64_pdf = base64.b64encode(file_bytes).decode("utf-8")
            pdf_url = f"data:application/pdf;base64,{base64_pdf}"
            
            st.markdown(f"""
                <a href="{pdf_url}" target="_blank" style="text-decoration:none;">
                    <div style="background-color:#4CAF50; color:white; padding:15px; text-align:center; border-radius:10px; font-weight:bold; margin-bottom:15px; border: 2px solid #2E7D32;">
                        🚀 [아이패드 필수] 여기를 눌러 논문 새 창 열기 (직접 드래그용)
                    </div>
                </a>
            """, unsafe_allow_html=True)
            
            page_num = st.select_slider("페이지 이동", options=range(1, total_pages + 1)) - 1
            page = doc.load_page(page_num)

            # 고해상도 이미지 (시각적 확인용)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2))
            st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)

            st.markdown("---")
            
            # [해결] 띄어쓰기 및 가독성 최적화 추출 로직
            with st.expander("📋 논문 텍스트 정밀 추출 (띄어쓰기 보정 완료)", expanded=True):
                if st.button("🚀 AI 정밀 판독 실행 (텍스트가 엉망일 때 클릭)"):
                    with st.spinner("AI가 문맥을 분석하여 글자를 재배열 중..."):
                        try:
                            pix_ocr = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                            img_ocr = Image.open(io.BytesIO(pix_ocr.tobytes()))
                            response = model.generate_content(["이 논문의 내용을 띄어쓰기를 맞춰서 텍스트로 추출해줘. 제목은 굵게 표시해.", img_ocr])
                            st.session_state[f"ocr_{page_num}"] = response.text
                            st.rerun()
                        except Exception as e:
                            st.error(f"AI 사용량 초과 혹은 에러: {e}")

                if f"ocr_{page_num}" in st.session_state:
                    structured_text = st.session_state[f"ocr_{page_num}"]
                else:
                    # 프로그램 방식 띄어쓰기 보정 추출
                    blocks = page.get_text("blocks")
                    blocks.sort(key=lambda b: (b[1], b[0])) # 위에서 아래로 정렬
                    extracted_parts = []
                    for b in blocks:
                        text = b[4].replace("\n", " ").strip()
                        if text: extracted_parts.append(text)
                    structured_text = "\n\n".join(extracted_parts)

                st.markdown(structured_text)
                st.text_area("✂️ 복사용 칸", value=structured_text, height=300, key=f"area_{page_num}")

    with col_tool:
        st.subheader("🧪 문단 정밀 분석")
        raw_input = st.text_area("분석할 문단을 여기에 붙여넣으세요", height=200)

        c1, c2 = st.columns(2)
        
        def safe_gen(prompt):
            try: return model.generate_content(prompt).text
            except Exception as e:
                if "429" in str(e): return "⚠️ 하루 사용량을 초과했습니다. 내일 다시 시도하거나 다른 API Key를 사용하세요."
                return f"❌ 오류: {e}"

        if c1.button("🌐 전문 직역 실행"):
            if raw_input.strip():
                with st.spinner("번역 중..."):
                    st.info(safe_gen(f"생체역학 전문가로서 직역하세요:\n\n{raw_input}"))

        if c2.button("🧠 심층 역학 분석"):
            if raw_input.strip():
                with st.spinner("분석 중..."):
                    st.success(safe_gen(f"생체역학 박사로서 분석하세요:\n\n{raw_input}"))

        st.markdown("---")
        st.subheader("💬 데이터 통합 질의응답")
        data_img = st.file_uploader("📸 그래프/사진 업로드", type=["png", "jpg", "jpeg"])
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
