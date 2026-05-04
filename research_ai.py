import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
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

# 🚀 [박사님 요청] 하이브리드 모델 연결 시스템 (무료 쿼터 선택형)
@st.cache_resource
def get_gemini_model(model_name):
    """지정된 이름의 제미나이 모델 엔진을 가동합니다."""
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        return model
    except Exception: return None

# 사이드바에 모델 선택 메뉴 추가
with st.sidebar:
    st.header("🔬 Lab 엔진 설정")
    # 박사님이 골라 쓰실 수 있는 두 가지 핵심 무기
    model_choice = st.radio(
        "사용할 AI 엔진을 선택하세요",
        [
            "⚡ Gemini 1.5 Flash (가성비 / 하루 1500회)",
            "🧠 Gemini 1.5 Pro (고성능 / 하루 50회)"
        ]
    )
    
    # 선택된 라디오 버튼에 따라 실제 내부 모델 이름 매핑
    chosen_model_name = "models/gemini-1.5-flash" if "Flash" in model_choice else "models/gemini-1.5-pro"
    
    model = get_gemini_model(chosen_model_name)
    
    st.markdown("---")
    if model:
        st.success(f"✅ 엔진 가동 중")
    else:
        st.error(f"❌ API Key 확인 필요")
    
    st.caption("Flash는 번역/텍스트 추출용, Pro는 심층 역학 분석용으로 아껴 쓰세요.")

# 4. 메인 UI
st.title("🔬 스마트 생체역학 통합 연구실")

uploaded_file = st.file_uploader("분석할 논문(PDF) 업로드", type="pdf")

if uploaded_file:
    col_view, col_tool = st.columns([1.2, 1])
    file_bytes = uploaded_file.getvalue()

    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        total_pages = len(doc)

        with col_view:
            st.subheader("📄 논문 원문 분석기")
            
            # [유지] 아이패드 네이티브 뷰어 호출
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
            
            # [수정] 텍스트 전체 추출 (가급적 Flash 엔진 권장)
            with st.expander("📋 논문 텍스트 전체 추출 (원본 형식 유지)", expanded=True):
                
                btn_ocr = st.button("🚀 AI 정밀 판독 실행 (텍스트가 엉망일 때 클릭)")
                if btn_ocr:
                    with st.spinner("AI가 원본 형태 그대로 문자를 추출 중입니다..."):
                        try:
                            # 현재 선택된 모델(Flash or Pro)을 사용하여 텍스트 추출
                            pix_ocr = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                            img_ocr = Image.open(io.BytesIO(pix_ocr.tobytes()))
                            prompt = """이 학술 논문 페이지의 텍스트를 보이는 그대로 추출해. 제목이나 소제목은 굵은 글씨로 마크다운(**제목**) 처리하고, 작은 글씨라도 들여쓰기나 엔터(줄바꿈)가 쳐진 곳은 그대로 줄을 바꿔줘."""
                            response = model.generate_content([prompt, img_ocr])
                            st.session_state[f"ocr_{page_num}"] = response.text
                            st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ 할당량 초과 혹은 분석 오류입니다. Pro 모델은 하루 50번 제한이 있으니 Flash로 바꿔서 시도해보세요. ({e})")

                if f"ocr_{page_num}" in st.session_state:
                    final_text = st.session_state[f"ocr_{page_num}"]
                else:
                    # 기본 파이썬 추출 로직 (무료 API 전혀 사용 안 함)
                    blocks = page.get_text("dict", sort=True)["blocks"]
                    extracted_parts = []
                    for b in blocks:
                        if b.get("type") != 0: continue
                        para_text = ""
                        for line in b.get("lines", []):
                            for span in line.get("spans", []):
                                text = span.get("text", "")
                                if span.get("flags", 0) & 2**4:
                                    text = f"**{text.strip()}**"
                                para_text += text
                            para_text += " "
                        extracted_parts.append(para_text.strip())
                    final_text = "\n\n".join(extracted_parts)

                st.markdown(final_text)

    with col_tool:
        # --- 🧪 정밀 분석 도구 (여기서 Flash/Pro 선택 효율 극대화) ---
        st.subheader("🧪 문단 정밀 분석")
        raw_input = st.text_area("분석할 문단을 여기에 붙여넣으세요", height=200, placeholder="왼쪽에서 추출된 텍스트를 복사해 넣으세요.")

        c1, c2 = st.columns(2)
        
        # 429 할당량 에러 대응용 안전 판독 함수
        def safe_gen(prompt):
            try: return model.generate_content(prompt).text
            except Exception as e:
                if "429" in str(e): return "🛑 현재 모델의 하루 무료 할당량을 모두 소진했습니다. 왼쪽에서 다른 모델 엔진을 선택해보세요."
                return f"❌ 오류: {e}"

        # 가벼운 번역은 가급적 Flash로 유도
        if c1.button("🌐 전문 직역 실행"):
            if raw_input.strip():
                with st.spinner("번역 중..."):
                    prompt = f"당신은 스포츠 생체역학 전문가입니다. 아래 논문 문단을 한국어로 자연스럽게 직역하세요. 문맥이 매끄러워야 합니다:\n\n{raw_input}"
                    st.info(safe_gen(prompt))

        # 깊은 역학 분석은 아껴둔 Pro 모델 사용 권장
        if c2.button("🧠 심층 역학 분석"):
            if raw_input.strip():
                with st.spinner("생체역학 전문 분석 중..."):
                    prompt = f"""당신은 세계적인 생체역학 박사입니다. 아래 논문 문단에서 **역학적 기전(Injury/Performance Mechanism)**을 비판적으로 분석하십시오. 
                    - 주요 Kinematics/Kinetics 수치 분석 
                    - 부상 위험과의 연관성
                    - 현장 적용(훈련법)을 위한 실무적 조언을 포함하십시오:
                    \n\n{raw_input}"""
                    st.success(safe_gen(prompt))

        st.markdown("---")
        # 💬 데이터 통합 질의응답 (이미지 분석은 가급적 Pro 모델 권장)
        st.subheader("💬 데이터 및 이미지 질의응답")
        data_img = st.file_uploader("📸 사진 업로드 (그래프, 표)", type=["png", "jpg", "jpeg"])
        if data_img: st.image(data_img, width=300)

        chat_query = st.text_area("질문을 입력하세요", height=100)
        if st.button("🚀 분석 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.append({"role": "user", "content": chat_query})
                with st.spinner("AI가 분석 중입니다..."):
                    contents = [f"당신은 생체역학 전문가로서 상세히 답변하세요: {chat_query}"]
                    if data_img: contents.append(Image.open(data_img))
                    ans = safe_gen(contents)
                    st.session_state.chat_history.append({"role": "assistant", "content": ans})

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
