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

# 3. [핵심] 사용 가능 모델 자동 감지 시스템 (404 에러 방지)
@st.cache_resource
def get_working_engine(is_pro=False):
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None, "API Key 없음"
    try:
        genai.configure(api_key=api_key)
        # 현재 API 키로 사용 가능한 모델 목록 확인
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Pro와 Flash 모델 중 최신 버전을 자동으로 탐색
        pro_list = [m for m in models if 'pro' in m.lower()]
        flash_list = [m for m in models if 'flash' in m.lower()]
        
        if is_pro and pro_list:
            target = pro_list[0]
        elif flash_list:
            target = flash_list[0]
        else:
            target = models[0]
            
        return genai.GenerativeModel(target), target
    except Exception as e:
        return None, str(e)

# 사이드바 엔진 설정
with st.sidebar:
    st.header("🔬 Lab 엔진 설정")
    use_pro = st.toggle("🧠 고성능 Pro 모드 (하루 50회 제한)", value=False)
    model, model_name = get_working_engine(is_pro=use_pro)
    
    if model:
        st.success(f"✅ 엔진 가동 중: {model_name}")
    else:
        st.error(f"❌ 연결 실패: {model_name}")
    st.caption("가벼운 작업은 Flash를, 심층 분석은 Pro를 권장합니다.")

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
            
            st.download_button(
                label="🚀 [iPad 필수] 논문 새 창에서 열기 (직접 드래그용)",
                data=file_bytes,
                file_name=uploaded_file.name,
                mime="application/pdf"
            )
            
            page_num = st.select_slider("페이지 이동", options=range(1, total_pages + 1)) - 1
            page = doc.load_page(page_num)

            # 고해상도 이미지 출력
            pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2))
            st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)

            st.markdown("---")
            
            # [기능 복구] 정밀 텍스트 추출 (박사님 요청 양식 적용)
            with st.expander("📋 논문 텍스트 전체 추출 (원본 양식 유지)", expanded=True):
                if st.button("🚀 AI 정밀 판독 실행"):
                    with st.spinner("AI가 원본 형태 그대로 문자를 추출 중입니다..."):
                        try:
                            pix_ocr = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                            img_ocr = Image.open(io.BytesIO(pix_ocr.tobytes()))
                            prompt = "이 논문 페이지를 읽어서 추출해줘. 굵은 글씨는 **굵게** 표시하고, 들여쓰기나 줄바꿈은 원본 그대로 유지해줘."
                            response = model.generate_content([prompt, img_ocr])
                            st.session_state[f"ocr_{page_num}"] = response.text
                            st.rerun()
                        except Exception as e:
                            st.error(f"분석 오류: {e}")

                if f"ocr_{page_num}" in st.session_state:
                    st.markdown(st.session_state[f"ocr_{page_num}"])
                else:
                    # 기본 파이썬 추출 로직 (양식 최대한 보존)
                    blocks = page.get_text("dict", sort=True)["blocks"]
                    extracted_parts = []
                    for b in blocks:
                        if b.get("type") != 0: continue
                        block_x0 = b["bbox"][0]
                        para_text = ""
                        for line in b.get("lines", []):
                            line_x0 = line["bbox"][0]
                            if (line_x0 - block_x0) > 10: # 들여쓰기 시 줄바꿈
                                para_text += "\n\n"
                            for span in line.get("spans", []):
                                text = span.get("text", "")
                                if span.get("flags", 0) & 2**4: # 굵은 글씨
                                    text = f"**{text.strip()}**"
                                para_text += text
                            para_text += " "
                        extracted_parts.append(para_text.strip())
                    st.markdown("\n\n".join(extracted_parts))

    with col_tool:
        # [기능 복구] 전문 분석 도구 섹션
        st.subheader("🧪 문단 정밀 분석")
        raw_input = st.text_area("분석할 문단을 여기에 붙여넣으세요", height=200)

        c1, c2 = st.columns(2)
        
        def safe_gen(prompt_text, image_data=None):
            try:
                content = [prompt_text]
                if image_data: content.append(image_data)
                return model.generate_content(content).text
            except Exception as e:
                return f"❌ 오류 발생: {e}"

        if c1.button("🌐 전문 직역 실행"):
            if raw_input.strip():
                with st.spinner("번역 중..."):
                    res = safe_gen(f"스포츠 생체역학 전문가로서 한국어로 자연스럽게 직역하세요:\n\n{raw_input}")
                    st.info(res)

        if c2.button("🧠 심층 역학 분석"):
            if raw_input.strip():
                with st.spinner("심층 분석 중..."):
                    res = safe_gen(f"스포츠 생체역학 박사로서 아래 내용을 상세히 분석하고 현장 적용점을 제시하세요:\n\n{raw_input}")
                    st.success(res)

        st.markdown("---")
        # [기능 복구] 이미지 및 데이터 질의응답
        st.subheader("💬 데이터 및 이미지 질의응답")
        data_img = st.file_uploader("📸 그래프나 표 사진 업로드", type=["png", "jpg", "jpeg"])
        if data_img: st.image(data_img, width=300)

        chat_query = st.text_area("질문을 입력하세요", height=100)
        if st.button("🚀 분석 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.append({"role": "user", "content": chat_query})
                with st.spinner("AI 분석 중..."):
                    img_data = Image.open(data_img) if data_img else None
                    ans = safe_gen(f"생체역학 전문가로서 답변하세요: {chat_query}", img_data)
                    st.session_state.chat_history.append({"role": "assistant", "content": ans})

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
