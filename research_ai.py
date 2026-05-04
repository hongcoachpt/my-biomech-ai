import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import base64

# 1. 페이지 레이아웃 및 보안 설정
st.set_page_config(layout="wide", page_title="Biomechanics Master Lab", page_icon="🔬")

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

# --- API 인증 및 모델 설정 ---
api_key = st.secrets.get("GOOGLE_API_KEY")
if api_key:
    try:
        genai.configure(api_key=api_key)
        # 아이패드에서 가장 안정적인 1.5 Pro 모델을 우선 타겟팅합니다.
        model = genai.GenerativeModel('gemini-1.5-pro')
        st.sidebar.success("✅ Gemini 엔진 가동 중")
    except Exception as e:
        st.sidebar.error(f"인증 실패: {e}")
        st.stop()
else:
    st.error("Secrets에서 API Key를 설정해 주세요.")
    st.stop()

if "chat_history" not in st.session_state: st.session_state.chat_history = []

st.title("🔬 스마트 생체역학 통합 연구실")

# 3. PDF 업로드 및 [아이패드 직접 드래그용] 멀티 레이어 뷰어
uploaded_file = st.file_uploader("분석할 논문(PDF) 업로드", type="pdf")

if uploaded_file:
    col_view, col_tool = st.columns([1.2, 1])
    file_bytes = uploaded_file.getvalue()
    
    # PDF 문서 열기
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    with col_view:
        st.subheader("📄 논문 원문 (직접 드래그 시도)")
        
        # [아이패드 최적화] 뷰어 모드 전환
        v_mode = st.radio("뷰어 선택", ["네이티브 뷰어 (드래그 가능)", "텍스트 추출 모드 (전체 누락 방지)"], horizontal=True)
        
        if v_mode == "네이티브 뷰어 (드래그 가능)":
            # Base64 변환 후 임베딩 (아이패드 사파리에서 가장 드래그가 잘 되는 방식)
            base64_pdf = base64.b64encode(file_bytes).decode('utf-8')
            pdf_display = f'<embed src="data:application/pdf;base64,{base64_pdf}" width="100%" height="900" type="application/pdf">'
            st.markdown(pdf_display, unsafe_allow_html=True)
            st.info("💡 아이패드 팁: 직접 드래그가 안 될 경우, 주소창의 'AA' 버튼을 눌러 '데스크탑 웹사이트 요청'을 켜주세요.")
        else:
            # 글씨 누락 방지를 위한 고정밀 텍스트 추출 뷰
            page_num = st.select_slider("페이지 이동", options=range(1, len(doc) + 1)) - 1
            page = doc.load_page(page_num)
            
            # 이미지와 텍스트를 동시에 보여줌
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)
            
            with st.expander("📝 현재 페이지 모든 글자 읽기 (누락 없음)", expanded=True):
                # 블록 단위가 아닌 정밀 텍스트 추출로 변경
                full_text = page.get_text("text", sort=True)
                st.text_area("추출된 텍스트", value=full_text, height=400)

    with col_tool:
        # --- 분석 도구 ---
        st.subheader("🧪 문단 정밀 분석")
        raw_input = st.text_area("분석할 문단을 여기에 붙여넣으세요", height=200, placeholder="왼쪽에서 긁은 내용을 붙여넣으세요.")
        
        c1, c2 = st.columns(2)
        if c1.button("🌐 전문 직역 실행"):
            if raw_input:
                with st.spinner("전문 용어 최적화 직역 중..."):
                    try:
                        res = model.generate_content(f"당신은 생체역학 전공 번역가입니다. 다음을 한국어로 정확히 직역하세요:\n\n{raw_input}")
                        st.info(f"**[직역 결과]**\n\n{res.text}")
                    except Exception as e:
                        st.error(f"분석 오류: {e}")
        
        if c2.button("🧠 심층 역학 분석"):
            if raw_input:
                with st.spinner("생체역학적 기전 분석 중..."):
                    try:
                        res = model.generate_content(f"당신은 생체역학 박사입니다. Kinetics/Kinematics 관점에서 상세 분석하세요:\n\n{raw_input}")
                        st.success(f"**[역학 분석 결과]**\n\n{res.text}")
                    except Exception as e:
                        st.error(f"분석 오류: {e}")

        st.markdown("---")
        st.subheader("💬 이미지/그래프 통합 분석")
        data_img = st.file_uploader("📸 그래프/사진 업로드", type=["png", "jpg", "jpeg"])
        if data_img: st.image(data_img, width=300)

        chat_query = st.text_area("궁금한 점을 질문하세요", height=100)
        if st.button("🚀 분석 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.insert(0, {"role": "user", "content": chat_query})
                with st.spinner("AI 분석 중..."):
                    try:
                        prompt = [f"생체역학 전문가로서 답변하세요: {chat_query}"]
                        if data_img: prompt.append(Image.open(data_img))
                        response = model.generate_content(prompt)
                        st.session_state.chat_history.insert(0, {"role": "assistant", "content": response.text})
                    except Exception as e:
                        st.error(f"에러 발생: {e}")

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
