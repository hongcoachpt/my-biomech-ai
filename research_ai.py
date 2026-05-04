import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import streamlit.components.v1 as components
import re

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="Biomechanics Pro Lab", page_icon="🔬")

# 2. 보안 잠금 (평문 방식 - Secrets에 LAB_PASSWORD 설정 필요)
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

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

# 3. 모델 연결 (429 에러 및 404 방지용 유연한 선택)
@st.cache_resource
def load_model():
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None, "API Key 없음"
    try:
        genai.configure(api_key=api_key)
        # 사용 가능한 모델 목록 확인
        models = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
        target = next((m for m in models if "gemini-1.5-pro" in m), models[0])
        return genai.GenerativeModel(target), target
    except Exception as e: return None, str(e)

model, model_name = load_model()
if model:
    st.sidebar.success(f"✅ 엔진 가동: {model_name}")
else:
    st.sidebar.error("❌ AI 연결 실패")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# 5. UI 메인
st.title("🔬 스마트 생체역학 통합 연구실")

uploaded_file = st.file_uploader("분석할 논문(PDF) 업로드", type="pdf")

if uploaded_file:
    file_bytes = uploaded_file.getvalue()
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        col_pdf, col_tool = st.columns([1.1, 1])

        with col_pdf:
            st.subheader("📄 논문 뷰어")
            
            # [기능] 원문 그대로 보기 (이미지) vs 드래그 가능 (인터랙티브)
            v_mode = st.radio("보기 모드", ["원본 이미지 모드", "인터랙티브 모드"], horizontal=True)
            page_idx = st.select_slider("페이지 이동", options=range(1, len(doc) + 1)) - 1
            page = doc.load_page(page_idx)

            if v_mode == "원본 이미지 모드":
                pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2))
                st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)
            else:
                base64_pdf = base64.b64encode(file_bytes).decode("utf-8")
                pdf_data_url = f"data:application/pdf;base64,{base64_pdf}"
                st.markdown(f'<iframe src="{pdf_data_url}" width="100%" height="800"></iframe>', unsafe_allow_html=True)

            st.markdown("---")
            # [해결] 텍스트 가독성 최적화 추출 (제목은 굵게, 띄어쓰기 정제)
            with st.expander("📋 논문 텍스트 정밀 추출 (제목 강조 및 정렬)", expanded=True):
                try:
                    blocks = page.get_text("dict", flags=11)["blocks"]
                    structured_text = ""
                    for b in blocks:
                        if b.get("type") != 0: continue # 텍스트가 아니면 패스
                        block_text = ""
                        max_size = 0
                        for line in b.get("lines", []):
                            for span in line.get("spans", []):
                                max_size = max(max_size, span.get("size", 0))
                                block_text += span.get("text", "") + " "
                        
                        # 띄어쓰기 및 하이픈 정제
                        clean_block = re.sub(r"(\w)-\s+(\w)", r"\1\2", block_text).strip()
                        
                        # 글자 크기가 12 이상이면 소제목으로 처리 (굵게)
                        if max_size > 11.5:
                            structured_text += f"\n### **{clean_block}**\n\n"
                        else:
                            structured_text += f"{clean_block}\n\n"
                    
                    st.markdown(structured_text)
                    st.text_area("드래그 복사용 텍스트", value=structured_text, height=300)
                except Exception as e:
                    st.error(f"추출 오류: {e}")

        with col_tool:
            # 🧪 분석 도구 (429 쿼터 에러 대응)
            st.subheader("🧪 문단 정밀 분석")
            raw_input = st.text_area("분석할 문단을 아래에 붙여넣으세요", height=180)
            c1, c2 = st.columns(2)
            
            def safe_generate(prompt):
                try:
                    res = model.generate_content(prompt)
                    return res.text
                except Exception as e:
                    if "429" in str(e): return "⚠️ 현재 AI 사용량이 너무 많습니다. 1분만 기다렸다가 다시 시도해 주세요."
                    return f"❌ 오류 발생: {str(e)}"

            if c1.button("🌐 전문 용어 직역"):
                if raw_input:
                    with st.spinner("번역 중..."):
                        st.info(safe_generate(f"생체역학 전문가로서 직역해줘:\n{raw_input}"))
            
            if c2.button("🧠 심층 역학 분석"):
                if raw_input:
                    with st.spinner("기전 분석 중..."):
                        st.success(safe_generate(f"생체역학 박사로서 역학적 의미를 분석해줘:\n{raw_input}"))

            st.markdown("---")
            # [해결] 이미지 붙여넣기(Ctrl+V) 기능 복구
            st.subheader("📸 데이터/그래프 분석")
            st.caption("그래프 캡처 후 아래 박스 클릭하고 Ctrl+V 하세요. (AI 분석은 아래 파일 선택 필수)")
            
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

            data_img = st.file_uploader("📸 AI 분석용 이미지 선택 (사진첩/캡처)", type=["png", "jpg", "jpeg"])
            if data_img: st.image(data_img, width=300)
            
            chat_query = st.text_area("질문을 입력하세요", height=100)
            if st.button("🚀 분석 전송"):
                if chat_query or data_img:
                    st.session_state.chat_history.append({"role": "user", "content": chat_query})
                    with st.spinner("AI 분석 중..."):
                        content = [f"생체역학 전문가로서 답변하세요: {chat_query}"]
                        if data_img: content.append(Image.open(data_img))
                        ans = safe_generate(content)
                        st.session_state.chat_history.append({"role": "assistant", "content": ans})
            
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]): st.markdown(msg["content"])
