import streamlit as st
import pypdf
import anthropic
import json
from datetime import datetime
from io import BytesIO
import csv

# ページ設定
st.set_page_config(
    page_title="PDF穴埋め問題生成システム",
    page_icon="📝",
    layout="wide"
)

# ==========================================
# 💰 課金管理・費用警告機能（内部管理用）
# ==========================================
WELCOME_CREDIT = 5.0  # ウェルカムクレジット額
ESTIMATED_COST_PER_RUN = 0.01  # 1回あたりの推定費用

if 'usage_count' not in st.session_state:
    st.session_state.usage_count = 0

estimated_used = st.session_state.usage_count * ESTIMATED_COST_PER_RUN
remaining_credit = WELCOME_CREDIT - estimated_used

# ==========================================
# ステータス表示（ユーザーに見える部分）
# ==========================================
if remaining_credit < 0.5:
    st.error("❌ **システムが利用不可です** - クレジット不足\n\n管理者に連絡してください。")
    st.stop()
elif remaining_credit < 1.0:
    st.warning("⚠️ **システムはもうすぐ利用不可になります** - クレジット残量不足")
else:
    st.info("✅ **システムは正常に動作しています**")

st.title("📝 PDF穴埋め問題自動生成システム")
st.markdown("PDFをアップロードして、AI自動で穴埋め問題を生成します")

# サイドバー設定
st.sidebar.header("⚙️ 設定")

# Streamlit Cloud での秘密キー読み込み
# ローカルテスト時は手動入力、デプロイ時は自動読み込み
if "CLAUDE_API_KEY" in st.secrets:
    api_key = st.secrets["CLAUDE_API_KEY"]
else:
    api_key = st.sidebar.text_input("Claude API Key", type="password", help="Claude APIキーを入力してください（ローカルテスト用）")

question_count = st.sidebar.slider("問題数", min_value=3, max_value=20, value=5)
difficulty = st.sidebar.selectbox("難易度", ["易しい", "普通", "難しい"])

# メインエリア
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📄 PDFアップロード")
    uploaded_file = st.file_uploader(
        "PDFファイルをアップロード",
        type="pdf",
        help="英語のPDFファイルを選択してください"
    )

# PDF処理関数
def extract_text_from_pdf(pdf_file):
    """PDFからテキストを抽出"""
    try:
        pdf_reader = pypdf.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        st.error(f"PDF処理エラー: {e}")
        return None

def generate_quiz_with_claude(text, question_count, difficulty, api_key):
    """Claude APIを使用して穴埋め問題を生成"""
    if not api_key:
        st.error("Claude APIキーを入力してください")
        return None
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        
        # 難易度の説明
        difficulty_desc = {
            "易しい": "基本的な単語や概念を対象とした簡単な穴埋め問題",
            "普通": "一般的な理解力が必要な穴埋め問題",
            "難しい": "深い理解と専門知識が必要な高度な穴埋め問題"
        }
        
        prompt = f"""次の英文テキストから、日本語での穴埋め問題を{question_count}問生成してください。
難易度レベル: {difficulty_desc[difficulty]}

【生成ルール】
1. テキストの内容から重要な部分を抽出して穴埋め問題にする
2. 各問題の形式:
   - 「問題文（___は穴埋め部分）」
   - 正解の日本語訳
   - 選択肢（4つ）
3. 問題は段階的に難しくする
4. JSON形式で出力する

【テキスト】
{text[:3000]}

【出力形式（JSON）】
{{
  "quiz": [
    {{
      "id": 1,
      "question": "問題文で___が穴埋め部分",
      "correct_answer": "正解",
      "choices": ["選択肢1", "選択肢2", "選択肢3", "正解"],
      "explanation": "解説"
    }}
  ]
}}

JSON配列のみを出力してください。"""

        message = client.messages.create(
            model="claude-opus-4-1",
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        response_text = message.content[0].text
        
        # JSONを抽出
        try:
            # JSONが```で囲まれている場合に対応
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()
            
            quiz_data = json.loads(json_str)
            return quiz_data
        except json.JSONDecodeError as e:
            st.error(f"JSON解析エラー: {e}")
            st.write("レスポンス:", response_text[:500])
            return None
            
    except Exception as e:
        st.error(f"Claude API エラー: {e}")
        return None

# ファイル出力関数
def generate_html_output(quiz_data, filename):
    """HTML形式で出力"""
    html_content = """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <title>穴埋め問題</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 900px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            h1 {
                color: #2c3e50;
                text-align: center;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
            }
            .quiz-container {
                background-color: white;
                padding: 20px;
                margin: 20px 0;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .question-number {
                background-color: #3498db;
                color: white;
                padding: 5px 10px;
                border-radius: 4px;
                font-weight: bold;
                display: inline-block;
                margin-bottom: 10px;
            }
            .question-text {
                font-size: 16px;
                margin: 15px 0;
                line-height: 1.6;
                color: #2c3e50;
            }
            .blank {
                background-color: #fff3cd;
                padding: 2px 6px;
                border-bottom: 2px solid #ffc107;
                font-weight: bold;
            }
            .choices {
                margin: 15px 0;
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
            }
            .choice {
                background-color: #ecf0f1;
                padding: 10px;
                border-radius: 4px;
                border-left: 4px solid #95a5a6;
            }
            .answer {
                margin-top: 15px;
                padding: 10px;
                background-color: #d5f4e6;
                border-left: 4px solid #27ae60;
                border-radius: 4px;
            }
            .explanation {
                margin-top: 10px;
                padding: 10px;
                background-color: #e8f4f8;
                border-left: 4px solid #3498db;
                border-radius: 4px;
                font-size: 14px;
            }
            .generated-info {
                text-align: center;
                color: #7f8c8d;
                font-size: 12px;
                margin-top: 20px;
                padding-top: 20px;
                border-top: 1px solid #ecf0f1;
            }
        </style>
    </head>
    <body>
        <h1>穴埋め問題テスト</h1>
    """
    
    if "quiz" in quiz_data:
        for idx, q in enumerate(quiz_data["quiz"], 1):
            html_content += f"""
            <div class="quiz-container">
                <div class="question-number">問題 {q.get('id', idx)}</div>
                <div class="question-text">{q.get('question', '')}</div>
                <div class="choices">
            """
            # 選択肢をシャッフル表示
            for choice in q.get('choices', []):
                html_content += f'<div class="choice">□ {choice}</div>'
            
            html_content += """
                </div>
            """
            
            if 'correct_answer' in q:
                html_content += f"""
                <div class="answer">
                    <strong>正解:</strong> {q['correct_answer']}
                </div>
                """
            
            if 'explanation' in q:
                html_content += f"""
                <div class="explanation">
                    <strong>解説:</strong> {q['explanation']}
                </div>
                """
            
            html_content += "</div>"
    
    html_content += f"""
        <div class="generated-info">
            生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}
        </div>
    </body>
    </html>
    """
    
    return html_content

def generate_csv_output(quiz_data):
    """CSV形式で出力"""
    from io import StringIO
    output = StringIO()
    if "quiz" in quiz_data:
        writer = csv.writer(output)
        writer.writerow(['問題番号', '問題文', '選択肢1', '選択肢2', '選択肢3', '選択肢4', '正解', '解説'])
        
        for q in quiz_data["quiz"]:
            choices = q.get('choices', [])
            writer.writerow([
                q.get('id', ''),
                q.get('question', ''),
                choices[0] if len(choices) > 0 else '',
                choices[1] if len(choices) > 1 else '',
                choices[2] if len(choices) > 2 else '',
                choices[3] if len(choices) > 3 else '',
                q.get('correct_answer', ''),
                q.get('explanation', '')
            ])
    
    return output.getvalue().encode('utf-8-sig')

# メイン処理
if uploaded_file is not None:
    with st.spinner("📖 PDFを処理中..."):
        extracted_text = extract_text_from_pdf(uploaded_file)
    
    if extracted_text:
        st.success(f"✅ テキスト抽出完了: {len(extracted_text)}文字")
        
        with st.expander("📋 抽出されたテキストを確認"):
            st.text(extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text)
        
        if st.button("🤖 穴埋め問題を生成", use_container_width=True):
            with st.spinner(f"問題を生成中... ({question_count}問、難易度: {difficulty})"):
                quiz_data = generate_quiz_with_claude(extracted_text, question_count, difficulty, api_key)
            
            if quiz_data:
                # 使用回数をカウント
                st.session_state.usage_count += 1
                
                st.success("✅ 問題生成完了！")
                
                # 問題表示
                st.subheader("📚 生成された穴埋め問題")
                
                if "quiz" in quiz_data:
                    for q in quiz_data["quiz"]:
                        with st.container(border=True):
                            st.markdown(f"**問題 {q.get('id', '')}**")
                            st.markdown(q.get('question', ''))
                            
                            st.write("**選択肢:**")
                            cols = st.columns(2)
                            for idx, choice in enumerate(q.get('choices', [])):
                                with cols[idx % 2]:
                                    st.write(f"□ {choice}")
                            
                            with st.expander("答え・解説を表示"):
                                st.success(f"**正解:** {q.get('correct_answer', '')}")
                                st.info(f"**解説:** {q.get('explanation', '')}")
                
                # ダウンロード機能
                st.subheader("📥 ファイルダウンロード")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    html_output = generate_html_output(quiz_data, "quiz.html")
                    st.download_button(
                        label="📄 HTMLでダウンロード",
                        data=html_output,
                        file_name=f"quiz_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                        mime="text/html",
                        use_container_width=True
                    )
                
                with col2:
                    csv_output = generate_csv_output(quiz_data)
                    st.download_button(
                        label="📊 CSVでダウンロード",
                        data=csv_output,
                        file_name=f"quiz_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                
                # JSON形式でも提供
                st.download_button(
                    label="📋 JSONでダウンロード",
                    data=json.dumps(quiz_data, ensure_ascii=False, indent=2),
                    file_name=f"quiz_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True
                )

# 使用方法
with st.expander("📖 使い方", expanded=False):
    st.markdown("""
    ### 📖 操作手順
    1. Claude APIキーをサイドバーに入力
    2. 問題数と難易度を設定
    3. PDFファイルをアップロード
    4. 「🤖 穴埋め問題を生成」ボタンをクリック
    5. 生成された問題を確認
    6. 希望の形式でダウンロード
    
    ### 💾 出力形式
    - **HTML**: ブラウザで見やすい形式
    - **CSV**: Excelで編集可能
    - **JSON**: プログラムで処理可能
    """)
