import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="Biomechanics Pro Lab", page_icon="🔬")

# 2. 보안 잠금 (박사님 전용)
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def check_password():
    if st.session_state.authenticated: return
    st.title("🔒 Lab Access Control")
    pwd = st.text_input("비밀번호를 입력하세요", type="password")
    if pwd == st.secrets.get("LAB_PASSWORD", "1234"):
        st.session_state.authenticated = True
        st.rerun()
    st.stop()

check_password()

# 3. [핵심] 사용 가능한 모델 자동 감지 시스템
@st.cache_resource
def get_working_model(is_pro=False):
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None
    genai.configure(api_key=api_key)
    
    try:
        # 현재 API 키로 사용 가능한 모든 모델 목록 확인
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Pro 모델과 Flash 모델 중 최신 버전을 자동으로 탐색
        pro_models = [m for m in available_models if 'pro' in m.lower()]
        flash_models = [m for m in available_models if 'flash' in m.lower()]
        
        if is_pro and pro_models:
            target = pro_models[0] # 가장 첫 번째 Pro 모델 선택
        elif flash_models:
            target = flash_models[0] # 가장 첫 번째 Flash 모델 선택
        else:
            target = available_models[0] # 둘 다 없으면 사용 가능한 아무 모델이나 선택
            
        return genai.GenerativeModel(target), target
    except Exception as e:
        st.error(f"모델 탐색 실패: {e}")
        return None, None

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 엔진 진단")
    mode = st.toggle("심층 분석 모드 (Pro)", value=False)
    model, model_name = get_working_model(is_pro=mode)
    
    if model:
        st.success(f"✅ 연결됨: {model_name}")
    else:
        st.error("❌ 연결 실패 (API 키 확인 요망)")

# 4. 메인 UI
st.title("🔬 스마트 생체역학 통합 연구실")

uploaded_file = st.file_uploader("논문 PDF 업로드", type="pdf")

if uploaded_file and model:
    col_view, col_tool = st.columns([1.2, 1])
    file_bytes = uploaded_file.getvalue()

    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        with col_view:
            st.subheader("📄 논문 원문")
            page_num = st.select_slider("페이지", options=range(1, len(doc) + 1)) - 1
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)

            if st.button("🚀 AI 텍스트 추출 실행"):
                with st.spinner("AI가 분석 중..."):
                    img = Image.open(io.BytesIO(page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5)).tobytes()))
                    res = model.generate_content(["이 논문 페이지 텍스트를 추출해. 굵은 글씨는 **굵게** 표시해.", img])
                    st.session_state[f"ocr_{page_num}"] = res.text
            
            if f"ocr_{page_num}" in st.session_state:
                st.markdown("---")
                st.markdown(st.session_state[f"ocr_{page_num}"])

    with col_tool:
        st.subheader("🧪 생체역학 심층 분석")
        raw_text = st.text_area("분석할 텍스트를 붙여넣으세요", height=200)
        
        if st.button("🧠 분석 시작"):
            if raw_text:
                with st.spinner("전문가 분석 중..."):
                    ans = model.generate_content(f"스포츠 생체역학 박사로서 상세히 분석하세요:\n\n{raw_text}")
                    st.info(ans.text)
