import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import streamlit.components.v1 as components

# 1. 페이지 레이아웃 설정
st.set_page_config(layout="wide", page_title="Biomechanics Master Lab", page_icon="🔬")

# 2. 지능형 인증 시스템 (배포 서버 및 로컬 공용)
# Streamlit Cloud의 'Secrets'에서 키를 먼저 찾습니다.
api_key = st.secrets.get("GOOGLE_API_KEY")

# 금고에 키가 없다면 사이드바에서 입력을 받습니다.
if not api_key:
    st.sidebar.header("🔑 연구원 인증")
    api_key = st.sidebar.text_input("Gemini API Key를 입력하세요", type="password")

if api_key:
    try:
        genai.configure(api_key=api_key)
        # 현재 키로 호출 가능한 가장 성능 좋은 모델 자동 탐색
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority_list = [
            'models/gemini-2.0-flash-thinking-exp', 
            'models/gemini-1.5-pro-002', 
            'models/gemini-1.5-pro', 
            'models/gemini-1.5-flash'
        ]
        target_model = next((p for p in priority_list if p in all_models), all_models[0] if all_models else None)
        
        if target_model:
            model = genai.GenerativeModel(target_model)
            st.sidebar.success(f"✅ 가동 중: {target_model}")
        else:
            st.sidebar.error("사용 가능한 모델이 없습니다.")
            st.stop()
    except Exception as e:
        st.sidebar.error(f"인증 오류: {e}")
        st.stop()
else:
    st.info("👈 왼쪽 사이드바에 API Key를 입력하거나 Streamlit Cloud의 Secrets 설정을 완료해 주세요.")
    st.stop()

# 대화 기록 저장소
if "chat_history" not in st.session_state: st.session_state.chat_history = []

st.title("🔬 스포츠 생체역학 지능형 분석 연구실")

# 3. PDF 업로드 및 멀티 뷰어 섹션
uploaded_file = st.file_uploader("분석할 논문(PDF) 업로드", type="pdf")

if uploaded_file:
    col_pdf, col_tool = st.columns([1.1, 1])
    file_bytes = uploaded_file.getvalue()
    
    with col_pdf:
        st.subheader("📄 논문 원문 뷰어")
        v_mode = st.radio("뷰어 모드 선택", ["안전 모드 (이미지)", "인터랙티브 (드래그 가능)"], horizontal=True)
        
        if v_mode == "인터랙티브 (드래그 가능)":
            base64_pdf = base64.b64encode(file_bytes).decode('utf-8')
            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="900" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
        else:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page_num = st.select_slider("페이지 이동", options=range(1, len(doc) + 1)) - 1
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2))
            st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)

        st.download_button(label="💾 원문 파일 다운로드 (별도 창 열기용)", data=file_bytes, file_name=uploaded_file.name, mime="application/pdf")
        
        st.markdown("---")
        with st.expander("📋 현재 페이지 텍스트 복사 (가독성 최적화 완료)", expanded=True):
            if 'doc' not in locals(): doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc.load_page(page_num if 'page_num' in locals() else 0)
            blocks = page.get_text("blocks")
            blocks.sort(key=lambda b: (b[1], b[0]))
            
            clean_text = ""
            for b in blocks:
                text = b[4].replace("\n", " ").strip()
                if text: clean_text += text + "\n\n"
            st.text_area("정제된 텍스트 내용", value=clean_text, height=300)

    with col_tool:
        st.subheader("🧪 문단 정밀 분석 (토큰 효율화)")
        raw_input = st.text_area("분석할 문단을 아래에 붙여넣으세요", height=200)
        
        btn_col1, btn_col2 = st.columns(2)
        if btn_col1.button("🌐 전문 직역 실행"):
            if raw_input:
                with st.spinner("전문 용어 최적화 직역 중..."):
                    tr = model.generate_content(f"당신은 생체역학 전공 번역가입니다. 전문 용어를 살려 깔끔하게 한국어로 직역하세요:\n\n{raw_input}").text
                    st.info(f"**[전문 직역 결과]**\n\n{tr}")
        
        if btn_col2.button("🧠 심층 역학 분석 실행"):
            if raw_input:
                with st.spinner("역학적 기전 분석 중..."):
                    an = model.generate_content(f"당신은 스포츠 생체역학 박사급 연구원입니다. Kinetics/Kinematics 관점에서 기전을 분석하고 시사점을 요약하세요:\n\n{raw_input}").text
                    st.success(f"**[심층 역학 분석 결과]**\n\n{an}")

        st.markdown("---")
        st.subheader("💬 데이터 및 이미지 질의응답")
        st.caption("그래프 캡처(Win+Shift+S) 후 아래 클릭하고 Ctrl+V 하거나 파일을 올리세요.")

        paste_html = """
        <div id="p-area" style="border:2px dashed #4CAF50; padding:15px; text-align:center; cursor:pointer; border-radius:10px; background-color:#f9f9f9;">
            여기를 클릭 후 <b>Ctrl+V</b>로 그래프 붙여넣기 (미리보기)
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

        data_img = st.file_uploader("📸 분석할 그래프/이미지 파일 업로드", type=["png", "jpg", "jpeg"])
        if data_img: st.image(data_img, caption="업로드됨", width=300)

        chat_query = st.text_area("궁금한 질문을 입력하세요", height=100)
        
        if st.button("🚀 질문 및 데이터 분석 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.insert(0, {"role": "user", "content": chat_query})
                with st.spinner("전문 AI 연구원이 분석 중..."):
                    try:
                        req = [f"생체역학 전문가로서 답변하세요: {chat_query}"]
                        if data_img: req.append(Image.open(data_img))
                        response = model.generate_content(req)
                        st.session_state.chat_history.insert(0, {"role": "assistant", "content": response.text})
                    except Exception as e:
                        st.error(f"오류: {e}")
            else:
                st.warning("질문이나 이미지를 넣어주세요.")

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
