import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import re

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
        model = genai.GenerativeModel("gemini-1.5-pro")
        st.sidebar.success("✅ Gemini 엔진 가동 중")
    except Exception as e:
        st.sidebar.error(f"인증 실패: {e}")
        st.stop()
else:
    st.error("Secrets에서 API Key를 설정해 주세요.")
    st.stop()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

st.title("🔬 스마트 생체역학 통합 연구실")

uploaded_file = st.file_uploader("분석할 논문(PDF) 업로드", type="pdf")

if uploaded_file:
    col_view, col_tool = st.columns([1.2, 1])
    file_bytes = uploaded_file.getvalue()

    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        total_pages = len(doc)

        with col_view:
            st.subheader("📄 논문 원문")
            
            page_num = st.select_slider("페이지 이동", options=range(1, total_pages + 1)) - 1
            page = doc.load_page(page_num)

            # 고해상도 이미지 렌더링 (AI 판독 및 확인용)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
            page_img = Image.open(io.BytesIO(pix.tobytes()))
            st.image(page_img, use_container_width=True)

            # --- [핵심] 텍스트 추출 섹션 보강 ---
            st.markdown("---")
            with st.expander("📝 현재 페이지 텍스트 추출 및 AI 판독", expanded=True):
                
                # 방법 1: AI OCR (이미지를 보고 텍스트 추출) - 가장 확실한 방법
                if st.button("🚀 AI 정밀 판독 실행 (텍스트 추출 안 될 때 클릭)"):
                    with st.spinner("AI가 페이지 이미지를 직접 읽고 있습니다..."):
                        try:
                            # 이미지를 Gemini에게 보내서 텍스트 추출 요청
                            ocr_prompt = "이 이미지에 있는 논문 내용을 텍스트로 추출해줘. 제목과 소제목은 굵게 표시하고, 문단 구분을 명확히 해줘. 표가 있다면 텍스트로 잘 정리해줘."
                            response = model.generate_content([ocr_prompt, page_img])
                            st.session_state[f"ocr_{page_num}"] = response.text
                            st.rerun()
                        except Exception as e:
                            st.error(f"AI 판독 실패: {e}")

                # AI 판독 결과가 있으면 먼저 보여줌
                if f"ocr_{page_num}" in st.session_state:
                    result_text = st.session_state[f"ocr_{page_num}"]
                    st.info("💡 AI가 이미지를 분석하여 추출한 텍스트입니다.")
                else:
                    # 방법 2: 기본 프로그램 방식 추출 (박사님이 보신 방식)
                    try:
                        blocks = page.get_text("dict")["blocks"]
                        structured_lines = []
                        for b in blocks:
                            if b.get("type") != 0: continue
                            for line in b.get("lines", []):
                                line_text = "".join([s.get("text", "") for s in line.get("spans", [])])
                                max_size = max([s.get("size", 0) for s in line.get("spans", [])])
                                
                                # 가독성 처리
                                if max_size >= 13: structured_lines.append(f"\n### **{line_text.strip()}**\n")
                                elif max_size >= 11: structured_lines.append(f"\n**{line_text.strip()}**\n")
                                else: structured_lines.append(line_text.strip())
                        
                        result_text = "\n".join(structured_lines)
                        if not result_text.strip():
                            result_text = page.get_text("text")
                    except:
                        result_text = page.get_text("text")

                st.markdown(result_text)
                st.text_area("✂️ 드래그 복사용", value=result_text, height=350, key=f"text_area_{page_num}")

    with col_tool:
        st.subheader("🧪 문단 정밀 분석")
        raw_input = st.text_area("분석할 문단을 여기에 붙여넣으세요", height=200)

        c1, c2 = st.columns(2)
        if c1.button("🌐 전문 직역 실행"):
            if raw_input.strip():
                with st.spinner("전문 번역 중..."):
                    res = model.generate_content(f"생체역학 전문가로서 한국어로 번역하세요:\n\n{raw_input}")
                    st.info(f"**[직역 결과]**\n\n{res.text}")

        if c2.button("🧠 심층 역학 분석"):
            if raw_input.strip():
                with st.spinner("생체역학 분석 중..."):
                    res = model.generate_content(f"생체역학 박사로서 분석하세요:\n\n{raw_input}")
                    st.success(f"**[분석 결과]**\n\n{res.text}")

        st.markdown("---")
        st.subheader("💬 이미지/그래프 통합 분석")
        data_img = st.file_uploader("📸 그래프/사진 업로드", type=["png", "jpg", "jpeg"])
        if data_img: st.image(data_img, width=300)

        chat_query = st.text_area("질문을 입력하세요", height=100)
        if st.button("🚀 질문 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.append({"role": "user", "content": chat_query})
                with st.spinner("AI 분석 중..."):
                    prompt = [f"생체역학 전문가로서 답변하세요: {chat_query}"]
                    if data_img: prompt.append(Image.open(data_img))
                    response = model.generate_content(prompt)
                    st.session_state.chat_history.append({"role": "assistant", "content": response.text})

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
