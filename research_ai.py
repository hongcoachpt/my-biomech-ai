import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="Biomechanics Pro Lab", page_icon="🔬")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# 2. 보안 시스템
def check_password():
    if st.session_state.authenticated: return
    st.title("🔒 Lab Access Control")
    pwd = st.text_input("연구소 비밀번호", type="password")
    if pwd == st.secrets.get("LAB_PASSWORD", "1234"):
        st.session_state.authenticated = True
        st.rerun()
    st.stop()

check_password()

# 3. [박사님 요청] 최신 정예 모델 - 연결 안정성 극대화
# 'models/' 접두사를 붙여 NotFound 에러를 원천 차단합니다.
MODEL_MAP = {
    "🚀 Gemini 2.0 Flash (최신/초고속)": "models/gemini-2.0-flash",
    "🧠 Gemini 1.5 Pro (정밀 분석/Pro)": "models/gemini-1.5-pro",
    "⚡ Gemini 1.5 Flash (가성비/Flash)": "models/gemini-1.5-flash"
}

@st.cache_resource
def load_engine(model_id):
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None
    try:
        genai.configure(api_key=api_key)
        # 404/NotFound 에러 방지를 위한 최적화된 호출
        return genai.GenerativeModel(model_name=model_id)
    except Exception as e:
        st.error(f"엔진 연결 실패: {e}")
        return None

# 사이드바 설정
with st.sidebar:
    st.header("🔬 연구실 엔진 설정")
    choice = st.selectbox("사용할 AI 모델을 선택하세요", list(MODEL_MAP.keys()))
    selected_id = MODEL_MAP[choice]
    model = load_engine(selected_id)
    
    if model:
        st.success(f"✅ {selected_id} 가동 중")
    
    st.markdown("---")
    st.caption("※ 2.0 모델이 막히면 1.5 Flash로 전환하여 연구를 계속하세요.")

# 4. 메인 UI
st.title("🔬 스마트 생체역학 통합 연구실")

uploaded_file = st.file_uploader("분석할 논문 PDF 업로드", type="pdf")

if uploaded_file and model:
    col_view, col_tool = st.columns([1.2, 1])
    file_bytes = uploaded_file.getvalue()

    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        with col_view:
            st.subheader("📄 논문 원문 분석기")
            page_num = st.select_slider("페이지 이동", options=range(1, len(doc) + 1)) - 1
            page = doc.load_page(page_num)

            # 고해상도 이미지 렌더링
            pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2))
            img_main = Image.open(io.BytesIO(pix.tobytes()))
            st.image(img_main, use_container_width=True)

            st.markdown("---")
            
            # [박사님 요청] 텍스트 자동 AI 추출 (논문 형식 복원)
            st.subheader("📋 논문 텍스트 자동 복원")
            
            # 페이지가 바뀔 때마다 자동으로 AI 판독 수행 (세션 스토리지 활용)
            ocr_key = f"auto_ocr_{page_num}_{selected_id}"
            
            if ocr_key not in st.session_state:
                with st.spinner("AI가 학술지 양식으로 텍스트를 자동 복원 중입니다..."):
                    try:
                        # OCR 품질을 위해 해상도 상향
                        pix_ocr = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                        img_ocr = Image.open(io.BytesIO(pix_ocr.tobytes()))
                        
                        prompt = """당신은 전문 학술지 편집자이자 생체역학 박사입니다. 
                        이 페이지의 이미지를 읽고 텍스트를 추출하되 다음 형식을 엄수하세요:
                        1. 제목(Title), 초록(Abstract), 서론(Introduction) 등 섹션 제목은 **굵게** 처리.
                        2. 다단 편집(Double Column)을 무시하고, 논문 흐름에 맞게 문단을 순서대로 재구성.
                        3. 역학 수치(p-value, Nm/kg 등)는 절대 변형 없이 정확히 기재.
                        4. 실제 논문 원본을 읽는 것처럼 깔끔하게 줄바꿈을 적용할 것."""
                        
                        res = model.generate_content([prompt, img_ocr])
                        st.session_state[ocr_key] = res.text
                    except Exception as e:
                        st.session_state[ocr_key] = f"❌ 자동 판독 오류: {e}\n\n사이드바에서 다른 모델(예: 1.5 Flash)을 선택해 보세요."

            # 결과 출력 (복사하기 편하도록 text_area와 markdown 동시 제공)
            st.markdown(st.session_state[ocr_key])
            with st.expander("📝 텍스트 전체 복사하기"):
                st.text_area("Copy Link", value=st.session_state[ocr_key], height=300)

    with col_tool:
        # [기존 분석 도구 유지]
        st.subheader("🧪 생체역학 정밀 분석")
        analysis_input = st.text_area("분석할 문단을 여기에 붙여넣으세요", height=200)

        c1, c2 = st.columns(2)
        if c1.button("🌐 전문 직역"):
            if analysis_input:
                with st.spinner("번역 중..."):
                    res = model.generate_content(f"스포츠 생체역학 전문가로서 한국어로 자연스럽게 직역하세요:\n\n{analysis_input}")
                    st.info(res.text)

        if c2.button("🧠 심층 역학 분석"):
            if analysis_input:
                with st.spinner("역학적 해석 중..."):
                    res = model.generate_content(f"스포츠 생체역학 박사로서 아래 내용을 상세히 분석하고 훈련 현장 적용점을 제시하세요:\n\n{analysis_input}")
                    st.success(res.text)

        st.markdown("---")
        st.subheader("💬 데이터 및 이미지 Q&A")
        data_img = st.file_uploader("📸 그래프/표 사진 업로드", type=["png", "jpg", "jpeg"])
        chat_query = st.text_input("AI에게 직접 질문하세요")
        if st.button("🚀 분석 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.append({"role": "user", "content": chat_query})
                with st.spinner("답변 생성 중..."):
                    contents = [f"생체역학 전문가로서 답변하세요: {chat_query}"]
                    if data_img: contents.append(Image.open(data_img))
                    ans = model.generate_content(contents)
                    st.session_state.chat_history.append({"role": "assistant", "content": ans.text})

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
