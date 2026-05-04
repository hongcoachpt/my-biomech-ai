import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import streamlit.components.v1 as components

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

# --- [해결] 404 에러 방지: 유연한 모델 선택 로직 ---
api_key = st.secrets.get("GOOGLE_API_KEY")
if api_key:
    try:
        genai.configure(api_key=api_key)
        # 사용 가능한 모델 목록을 조회하여 가장 적합한 것을 자동 선택합니다.
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # gemini-1.5-pro가 있으면 우선 사용, 없으면 첫 번째 가용 모델 사용
        target_model = next((m for m in models if "gemini-1.5-pro" in m), models[0])
        model = genai.GenerativeModel(target_model)
        st.sidebar.success(f"✅ 엔진 가동 중: {target_model}")
    except Exception as e:
        st.sidebar.error(f"❌ 연결 오류: {e}")
        st.stop()
else:
    st.info("👈 Secrets에서 API Key를 설정하거나 사이드바에 입력하세요.")
    st.stop()

if "chat_history" not in st.session_state: st.session_state.chat_history = []

st.title("🔬 스마트 생체역학 통합 연구실")

# 3. PDF 업로드 및 멀티 뷰어
uploaded_file = st.file_uploader("분석할 논문(PDF) 업로드", type="pdf")

if uploaded_file:
    col_pdf, col_tool = st.columns([1.1, 1])
    file_bytes = uploaded_file.getvalue()
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    with col_pdf:
        st.subheader("📄 논문 뷰어")
        
        # [해결] 원문 그대로 보기 vs 드래그 가능 모드 선택
        v_mode = st.radio("보기 모드 선택", ["원본 이미지 (아이패드 안정성)", "인터랙티브 (드래그 시도)"], horizontal=True)
        
        if v_mode == "원본 이미지 (아이패드 안정성)":
            page_idx = st.select_slider("페이지 이동", options=range(1, len(doc) + 1)) - 1
            page = doc.load_page(page_idx)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5)) # 고해상도 렌더링
            st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)
        else:
            base64_pdf = base64.b64encode(file_bytes).decode('utf-8')
            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
            st.info("💡 드래그가 안 될 경우 '데스크탑 웹사이트 요청'을 켜주세요.")

        # [해결] 텍스트 가독성 최적화 추출 (제목 강조 및 띄어쓰기 정제)
        st.markdown("---")
        with st.expander("📋 논문 텍스트 추출 (가독성 최적화 버전)", expanded=True):
            if 'page_idx' not in locals(): page_idx = 0
            curr_page = doc.load_page(page_idx)
            blocks = curr_page.get_text("dict")["blocks"]
            
            structured_text = ""
            for b in blocks:
                if "lines" in b:
                    line_texts = []
                    is_header = False
                    for l in b["lines"]:
                        for s in l["spans"]:
                            if s["size"] > 11: # 제목급 크기 감지
                                is_header = True
                            line_texts.append(s["text"])
                    
                    paragraph = " ".join(line_texts).strip()
                    if is_header:
                        structured_text += f"\n### **{paragraph}**\n\n"
                    else:
                        structured_text += f"{paragraph}\n\n"
            
            st.markdown(structured_text)
            st.text_area("복사용 텍스트", value=structured_text, height=300)

    with col_tool:
        # --- 🧪 텍스트 분석 (에러 방지 로직 강화) ---
        st.subheader("🧪 문단 정밀 분석")
        raw_input = st.text_area("분석할 문단을 아래에 붙여넣으세요", height=200)
        
        c1, c2 = st.columns(2)
        if c1.button("🌐 전문 용어 직역"):
            if raw_input:
                with st.spinner("전문 번역 중..."):
                    try:
                        res = model.generate_content(f"스포츠 생체역학 전공자로서 다음 내용을 한국어로 자연스럽게 번역하세요. 전문 용어는 유지하되 문맥을 살리세요:\n\n{raw_input}")
                        st.info(res.text)
                    except Exception as e:
                        st.error(f"연결 오류: {e}")
        
        if c2.button("🧠 심층 역학 분석"):
            if raw_input:
                with st.spinner("역학적 기전 분석 중..."):
                    try:
                        res = model.generate_content(f"생체역학 박사로서 다음 연구 내용의 Kinetics/Kinematics적 의미와 시사점을 분석하세요:\n\n{raw_input}")
                        st.success(res.text)
                    except Exception as e:
                        st.error(f"연결 오류: {e}")

        st.markdown("---")
        
        # [해결] 이미지 붙여넣기(Ctrl+V) 및 업로드 복구
        st.subheader("💬 데이터 및 이미지 질의응답")
        st.caption("캡처 후 아래 박스 클릭 후 **Ctrl+V** 하거나 파일을 올리세요.")

        paste_html = """
        <div id="p-area" style="border:2px dashed #4CAF50; padding:15px; text-align:center; cursor:pointer; border-radius:10px; background-color:#f9f9f9;">
            여기를 클릭 후 <b>Ctrl+V</b>로 붙여넣기 (미리보기)
        </div>
        <div id="p-view" style="margin-top:10px; display:none; text-align:center;">
            <img id="p-img" style="max-width:100%; border-radius:5px; border:1px solid #ccc;"/>
        </div>
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

        data_img = st.file_uploader("📸 그래프/사진 직접 선택", type=["png", "jpg", "jpeg"])
        if data_img: st.image(data_img, width=300)

        chat_query = st.text_area("질문을 입력하세요", height=100)
        if st.button("🚀 분석 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.insert(0, {"role": "user", "content": chat_query})
                with st.spinner("AI 분석 중..."):
                    try:
                        content = [f"생체역학 전문가로서 상세히 답변하세요: {chat_query}"]
                        if data_img: content.append(Image.open(data_img))
                        response = model.generate_content(content)
                        st.session_state.chat_history.insert(0, {"role": "assistant", "content": response.text})
                    except Exception as e:
                        st.error(f"에러 발생: {e}")

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
