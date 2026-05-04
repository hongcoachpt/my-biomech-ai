import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import re

# 1. 페이지 레이아웃 및 세션 초기화
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
    pwd = st.text_input("연구소 비밀번호를 입력하세요", type="password")
    if pwd:
        if pwd == correct_pwd:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ 비밀번호가 다릅니다.")
    st.stop()

check_password()

# 3. 모델 연결 엔진 (강력한 연결 모드)
MODEL_MAP = {
    "⚡ Gemini 1.5 Flash (가성비/OCR추천)": "gemini-1.5-flash",
    "🧠 Gemini 1.5 Pro (심층분석/고성능)": "gemini-1.5-pro",
    "🚀 Gemini 2.0 Flash (최신/초고속)": "gemini-2.0-flash-exp"
}

def load_engine(model_id):
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None
    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(model_id)
    except Exception as e:
        st.error(f"엔진 연결 실패: {e}")
        return None

# 사이드바 엔진 설정
with st.sidebar:
    st.header("🔬 엔진 설정")
    choice = st.selectbox("사용할 모델을 고르세요", list(MODEL_MAP.keys()))
    selected_id = MODEL_MAP[choice]
    model = load_engine(selected_id)
    
    if model:
        st.success(f"✅ {selected_id} 가동 중")
    
    st.markdown("---")
    st.caption("• Flash: 텍스트 추출용 (하루 1500회)\n• Pro: 데이터 심층 해석용 (하루 50회)")

# 4. 메인 UI
st.title("🔬 스마트 생체역학 통합 연구실")

uploaded_file = st.file_uploader("분석할 논문(PDF) 업로드", type="pdf")

if uploaded_file and model:
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

            # 선명한 원문 이미지 출력
            pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2))
            st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)

            st.markdown("---")
            
            # [박사님 요청] 텍스트 자동 추출 및 AI 정밀 판독 통합
            with st.expander("📋 논문 텍스트 추출 (자동/AI)", expanded=True):
                
                # 1. 자동 기본 추출 (무조건 실행됨)
                st.markdown("### [자동 기본 추출본]")
                # [안정성 강화] PyMuPDF의 기본 텍스트 추출 기능을 항상 먼저 보여줍니다.
                raw_text = page.get_text("text", sort=True)
                if raw_text.strip():
                    st.text_area("기본 추출 텍스트 (수정/복사 가능)", value=raw_text, height=200)
                else:
                    st.warning("이 페이지는 이미지로만 구성되어 있어 자동 추출이 어렵습니다. 아래 AI 판독을 실행하세요.")

                st.markdown("---")

                # 2. AI 정밀 판독 (선택 시 실행)
                if st.button("🚀 AI 정밀 판독 실행 (표/다단 편집용)"):
                    with st.spinner("AI가 레이아웃을 분석하여 텍스트를 재구성 중입니다..."):
                        try:
                            pix_ocr = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                            img_ocr = Image.open(io.BytesIO(pix_ocr.tobytes()))
                            prompt = "이 논문 페이지의 텍스트를 제목/본문 구분하여 추출해줘. 굵은 글씨는 **굵게** 표시하고 문단은 유지해줘."
                            response = model.generate_content([prompt, img_ocr])
                            st.session_state[f"ocr_{page_num}"] = response.text
                            st.rerun()
                        except Exception as e:
                            st.error(f"AI 분석 실패: {e}")

                if f"ocr_{page_num}" in st.session_state:
                    st.markdown("### [AI 정밀 판독본]")
                    st.markdown(st.session_state[f"ocr_{page_num}"])

    with col_tool:
        # 전문 분석 도구
        st.subheader("🧪 문단 정밀 분석")
        analysis_input = st.text_area("분석할 문단을 붙여넣으세요", height=200, placeholder="위의 추출된 텍스트를 복사해서 넣어주세요.")

        c1, c2 = st.columns(2)
        
        def safe_gen(prompt):
            try: return model.generate_content(prompt).text
            except Exception as e: return f"❌ 오류: {e}"

        if c1.button("🌐 전문 직역 실행"):
            if analysis_input.strip():
                with st.spinner("번역 중..."):
                    st.info(safe_gen(f"스포츠 생체역학 전문가로서 자연스럽게 한국어로 직역하세요:\n\n{analysis_input}"))

        if c2.button("🧠 심층 역학 분석"):
            if analysis_input.strip():
                with st.spinner("심층 분석 중..."):
                    st.success(safe_gen(f"스포츠 생체역학 박사로서 아래 내용을 상세히 분석하고 현장 적용점을 제안하세요:\n\n{analysis_input}"))

        st.markdown("---")
        # 데이터 및 이미지 질의응답
        st.subheader("💬 데이터 및 이미지 Q&A")
        data_img = st.file_uploader("📸 그래프나 표 사진 업로드", type=["png", "jpg", "jpeg"])
        if data_img: st.image(data_img, width=300)

        chat_query = st.text_area("AI에게 질문하기", height=100)
        if st.button("🚀 질문 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.append({"role": "user", "content": chat_query})
                with st.spinner("답변 생성 중..."):
                    contents = [f"생체역학 전문가로서 답변하세요: {chat_query}"]
                    if data_img: contents.append(Image.open(data_img))
                    ans = safe_gen(contents)
                    st.session_state.chat_history.append({"role": "assistant", "content": ans})

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
