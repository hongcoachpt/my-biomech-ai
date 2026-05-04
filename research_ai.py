import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import streamlit.components.v1 as components
import re
import hashlib

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="Biomechanics Pro Lab", page_icon="🔬")

# 2. 보안 잠금 (해시 비교 + 시도 횟수 제한)
MAX_ATTEMPTS = 5

def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()

def check_password():
    if st.session_state.get("authenticated"):
        return

    if "login_attempts" not in st.session_state:
        st.session_state.login_attempts = 0

    st.title("🔒 Biomechanics Lab 보안")

    if st.session_state.login_attempts >= MAX_ATTEMPTS:
        st.error("⛔ 로그인 시도 횟수를 초과했습니다. 관리자에게 문의하세요.")
        st.stop()

    pwd = st.text_input("연구소 비밀번호를 입력하세요", type="password", key="pwd_input")

    if pwd:
        # Secrets에 LAB_PASSWORD_HASH가 없으면 기본값 '1234'의 해시 사용
        stored_hash = st.secrets.get("LAB_PASSWORD_HASH", hash_password("1234"))
        if hash_password(pwd) == stored_hash:
            st.session_state.authenticated = True
            st.session_state.login_attempts = 0
            st.rerun()
        else:
            st.session_state.login_attempts += 1
            remaining = MAX_ATTEMPTS - st.session_state.login_attempts
            st.error(f"비밀번호가 틀렸습니다. (남은 시도: {remaining}회)")
    st.stop()

check_password()

# 3. Gemini 모델 연결 (fallback 우선순위 + 캐싱)
PREFERRED_MODELS = ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-pro"]

@st.cache_resource
def load_model():
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key:
        return None, "API Key가 설정되지 않았습니다."
    try:
        genai.configure(api_key=api_key)
        available = [
            m.name for m in genai.list_models()
            if "generateContent" in m.supported_generation_methods
        ]
        chosen = next(
            (m for pref in PREFERRED_MODELS for m in available if pref in m),
            available[0] if available else None
        )
        if not chosen:
            return None, "사용 가능한 모델이 없습니다."
        return genai.GenerativeModel(chosen), chosen
    except Exception as e:
        return None, str(e)

model, model_info = load_model()
if model is None:
    st.sidebar.error(f"❌ 연결 오류: {model_info}")
    st.stop()
else:
    st.sidebar.success(f"✅ 엔진 연결됨: {model_info}")

# 4. 세션 상태 초기화
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_uploaded_name" not in st.session_state:
    st.session_state.last_uploaded_name = None

# 5. UI 메인
st.title("🔬 스마트 생체역학 통합 연구실")

uploaded_file = st.file_uploader("분석할 논문(PDF) 업로드", type="pdf")

if uploaded_file and uploaded_file.name != st.session_state.last_uploaded_name:
    st.session_state.chat_history = []
    st.session_state.last_uploaded_name = uploaded_file.name

if uploaded_file:
    file_bytes = uploaded_file.getvalue()
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        total_pages = len(doc)
        col_pdf, col_tool = st.columns([1.1, 1])

        with col_pdf:
            st.subheader("📄 논문 뷰어")
            file_size_mb = len(file_bytes) / (1024 * 1024)
            if file_size_mb < 10:
                base64_pdf = base64.b64encode(file_bytes).decode("utf-8")
                pdf_data_url = f"data:application/pdf;base64,{base64_pdf}"
                st.markdown(
                    f'<a href="{pdf_data_url}" target="_blank" style="text-decoration:none;">'
                    f'<div style="background:#4CAF50;color:white;padding:12px;text-align:center;'
                    f'border-radius:8px;font-weight:bold;margin-bottom:10px;">'
                    f'🚀 [iPad] 원문 크게 보기 및 직접 드래그 (새 창)</div></a>',
                    unsafe_allow_html=True,
                )
            else:
                st.warning(f"⚠️ 파일 크기({file_size_mb:.1f}MB)가 커서 새 창 보기는 비활성화됩니다.")
                pdf_data_url = None

            v_mode = st.radio("보기 모드", ["원본 이미지 모드", "인터랙티브 모드"], horizontal=True)
            page_idx = st.select_slider("페이지 이동", options=range(1, total_pages + 1)) - 1
            page = doc.load_page(page_idx)

            if v_mode == "원본 이미지 모드":
                pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2))
                st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)
            else:
                if pdf_data_url:
                    st.markdown(f'<iframe src="{pdf_data_url}" width="100%" height="800"></iframe>', unsafe_allow_html=True)
                else:
                    st.error("이미지 모드를 사용하세요.")

            st.markdown("---")
            with st.expander("📋 논문 텍스트 정밀 추출 (가독성 최적화)", expanded=True):
                try:
                    blocks = page.get_text("dict", flags=11)["blocks"]
                    structured_text = ""
                    for b in blocks:
                        if b.get("type") != 0: continue
                        lines = b.get("lines", [])
                        if not lines: continue
                        block_text = ""
                        max_font_size = 0
                        for line in lines:
                            for span in line.get("spans", []):
                                max_font_size = max(max_font_size, span.get("size", 0))
                                block_text += span.get("text", "") + " "
                        clean_block = re.sub(r"(\w)-\s+(\w)", r"\1\2", block_text).strip()
                        if not clean_block: continue
                        if max_font_size > 11.5:
                            structured_text += f"\n### **{clean_block}**\n\n"
                        else:
                            structured_text += f"{clean_block}\n\n"
                    if not structured_text.strip():
                        structured_text = page.get_text("text")
                    st.markdown(structured_text)
                    st.text_area("드래그 복사용 영역", value=structured_text, height=300)
                except Exception as e:
                    st.error(f"텍스트 추출 중 오류 발생: {e}")

        with col_tool:
            st.subheader("🧪 문단 정밀 분석")
            raw_input = st.text_area("분석할 문단을 아래에 붙여넣으세요", height=200)
            c1, c2 = st.columns(2)
            if c1.button("🌐 전문 용어 직역"):
                if raw_input.strip():
                    with st.spinner("전문 번역 중..."):
                        try:
                            res = model.generate_content(f"스포츠 생체역학 전문가로서 다음 내용을 한국어로 자연스럽게 번역하세요:\n\n{raw_input}")
                            st.info(res.text)
                        except Exception as e: st.error(f"번역 오류: {e}")
                else: st.warning("문단을 먼저 입력하세요.")
            if c2.button("🧠 심층 역학 분석"):
                if raw_input.strip():
                    with st.spinner("기전 분석 중..."):
                        try:
                            res = model.generate_content(f"생체역학 박사로서 다음 연구 내용의 역학적 의미를 분석하세요:\n\n{raw_input}")
                            st.success(res.text)
                        except Exception as e: st.error(f"분석 오류: {e}")
                else: st.warning("문단을 먼저 입력하세요.")

            st.markdown("---")
            st.subheader("📸 데이터 및 이미지 질의응답")
            st.caption("AI 분석은 아래 '파일 선택'으로 업로드한 이미지만 전송됩니다.")
            paste_html = """
            <div id="p-area" style="border:2px dashed #4CAF50; padding:15px; text-align:center; cursor:pointer; border-radius:10px; background-color:#f9f9f9;">여기 클릭 후 <b>Ctrl+V</b>로 미리보기</div>
            <div id="p-view" style="margin-top:10px; display:none; text-align:center;"><img id="p-img" style="max-width:100%; border-radius:5px; border:1px solid #ccc;"/></div>
            <script>
                document.addEventListener('paste', function(e) {
                    var items = e.clipboardData.items;
                    for (var i = 0; i < items.length; i++) {
                        if (items[i].type.indexOf('image') !== -1) {
                            var blob = items[i].getAsFile();
                            var reader = new FileReader();
                            reader.onload = function(event) {
                                document.getElementById('p-img').src = event.target.result;
                                document.getElementById('p-view').style.display = 'block';
                            };
                            reader.readAsDataURL(blob);
                        }
                    }
                });
            </script>
            """
            components.html(paste_html, height=220)
            data_img = st.file_uploader("📸 AI 분석용 이미지 선택", type=["png", "jpg", "jpeg"])
            if data_img: st.image(data_img, width=300)
            chat_query = st.text_area("질문을 입력하세요", height=100)
            if st.button("🚀 분석 전송"):
                if not chat_query.strip() and not data_img: st.warning("질문 또는 이미지를 입력하세요.")
                else:
                    st.session_state.chat_history.append({"role": "user", "content": chat_query})
                    with st.spinner("AI 분석 중..."):
                        try:
                            content_parts = [f"생체역학 전문가로서 답변하세요: {chat_query}"]
                            if data_img: content_parts.append(Image.open(data_img))
                            response = model.generate_content(content_parts)
                            st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                        except Exception as e: st.error(f"전송 에러: {e}")
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]): st.markdown(msg["content"])
