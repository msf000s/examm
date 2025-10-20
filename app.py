from flask import Flask, request, jsonify, send_from_directory
import google.generativeai as genai
import os
import base64
from io import BytesIO
from PIL import Image

app = Flask(__name__, static_folder='static')

# تكوين مفتاح Gemini من متغير البيئة
GOOGLE_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GEMINI_API_KEY غير مضبوط في متغيرات البيئة")

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

@app.route('/')
def serve_frontend():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/correct', methods=['POST'])
def correct_answers():
    try:
        # التحقق من وجود الصورة
        if 'image' not in request.files:
            return jsonify({"success": False, "error": "لم يتم تحميل صورة"}), 400

        image_file = request.files['image']
        num_questions = int(request.form.get('num_questions', 10))
        options_per_q = int(request.form.get('options_per_q', 4))

        # تحويل الصورة إلى PIL Image
        img = Image.open(image_file.stream)

        # إنشاء التعليمات (prompt)
        options_str = "A, B, C, D" if options_per_q == 4 else "A, B, C, D, E"
        prompt = f"""
هذه صورة لورقة إجابة اختبار متعدد الخيارات.
عدد الأسئلة: {num_questions}
عدد الخيارات لكل سؤال: {options_per_q} ({options_str})
مهم جدًا: أجب فقط بقائمة JSON من الإجابات، مثل: ["A", "B", "فراغ", "C", ...]
استخدم "فراغ" إذا لم يتم تظليل أي خيار.
لا تكتب أي شرح أو نص إضافي. فقط القائمة.
        """.strip()

        # إرسال الصورة + التعليمات إلى Gemini
        response = model.generate_content([prompt, img])

        if not response.text:
            return jsonify({"success": False, "error": "لم يتم استلام إجابة من Gemini"}), 500

        raw_text = response.text.strip()

        # تنظيف النص واستخراج القائمة
        import json
        try:
            # محاولة تحليل JSON مباشرة
            answers = json.loads(raw_text)
        except json.JSONDecodeError:
            # إذا فشل، نحاول استخراج الحروف يدويًا
            import re
            matches = re.findall(r'"([A-E])"|فراغ', raw_text.replace('"فراغ"', 'فراغ'))
            if len(matches) == num_questions:
                answers = matches
            else:
                letters = re.findall(r'[A-E]|فراغ', raw_text)
                if len(letters) == num_questions:
                    answers = letters
                else:
                    return jsonify({"success": False, "error": "تنسيق غير متوقع من Gemini"}), 500

        if len(answers) != num_questions:
            return jsonify({"success": False, "error": f"عدد الإجابات ({len(answers)}) لا يطابق عدد الأسئلة ({num_questions})"}), 500

        return jsonify({"success": True, "answers": answers})

    except Exception as e:
        print("Error in /api/correct:", str(e))
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))