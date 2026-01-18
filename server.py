from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 這行非常重要，允許 GitHub Pages 連到你家

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get("message", "")
    print(f"收到訊息: {user_message}")
    
    # 回傳給網頁的內容
    return jsonify({"reply": f"本地電腦已收到：{user_message}"})

if __name__ == '__main__':
    app.run(port=5000)