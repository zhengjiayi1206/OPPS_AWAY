import os

from flask import Flask, jsonify, request
from flask_cors import CORS
from dashscope import MultiModalConversation
from openai import OpenAI
from dotenv import load_dotenv

"""
Simple Flask proxy to call DashScope ASR (qwen3-asr-flash).

Usage:
  export DASHSCOPE_API_KEY=sk-xxx
  VITE_ASR_ENDPOINT=http://localhost:5000/api/asr npm run dev   # front-end
  # Packaged/same-origin: no VITE_ASR_ENDPOINT needed, defaults to /api/asr
  FLASK_APP=server/python_asr_server.py flask run --host=0.0.0.0 --port=5000
"""

load_dotenv(override=True)

app = Flask(__name__)
CORS(app)


@app.after_request
def add_cors_headers(response):
  response.headers["Access-Control-Allow-Origin"] = "*"
  response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
  response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
  return response


@app.route("/api/asr", methods=["POST"])
def asr():
  api_key = "sk-dfb5d9295ee94adeafc438d18c7d4900"
  if not api_key:
    return jsonify({"error": "未配置 DASHSCOPE_API_KEY 环境变量"}), 500

  payload = request.get_json(silent=True) or {}
  audio_base64 = payload.get("audioBase64")
  fmt = payload.get("format", "webm")
  if not audio_base64:
    return jsonify({"error": "缺少音频数据"}), 400

  cleaned = audio_base64.split("base64,", 1)[-1] if isinstance(audio_base64, str) else ""
  data_url_prefix = f"data:audio/{fmt};base64,"
  audio_string = f"{data_url_prefix}{cleaned}"

  messages = [
    {
      "role": "system",
      "content": [{"text": ""}],
    },
    {
      "role": "user",
      "content": [
        {
          # Pass base64 as a data URL string to satisfy SDK expectations
          "audio": audio_string,
        }
      ],
    },
  ]

  try:
    resp = MultiModalConversation.call(
      api_key=api_key,
      model="qwen3-asr-flash",
      messages=messages,
      result_format="message",
      asr_options={"enable_lid": True, "enable_itn": False},
    )
  except Exception as exc:  # noqa: BLE001
    return jsonify({"error": f"调用 DashScope 失败: {exc}"}), 500

  if getattr(resp, "status_code", 500) != 200:
    return jsonify(
      {
        "error": resp.get("message") if isinstance(resp, dict) else "阿里云返回错误",
        "detail": getattr(resp, "output", None) or getattr(resp, "__dict__", None),
      }
    ), getattr(resp, "status_code", 500)

  output = getattr(resp, "output", {}) or {}
  choices = output.get("choices") or []
  content = choices[0].get("message", {}).get("content", []) if choices else []
  text = " ".join([item["text"] for item in content if isinstance(item, dict) and "text" in item]).strip()
  return jsonify({"text": text, "raw": output})


@app.route("/api/diagnose", methods=["POST", "OPTIONS"])
def diagnose():
  if request.method == "OPTIONS":
    return ("", 204)
  api_key = "sk-dfb5d9295ee94adeafc438d18c7d4900"
  if not api_key:
    return jsonify({"error": "未配置 DASHSCOPE_API_KEY 环境变量"}), 500

  payload = request.get_json(silent=True) or {}
  answers = payload.get("answers")
  if not isinstance(answers, list) or len(answers) == 0:
    return jsonify({"error": "缺少回答内容"}), 400

  prompt = "你是语法检测人员，帮忙找语法/用词问题并给出简短建议。输出每题：问题类型、问题解析（最多3条，简明短句），总体建议一段，最后给一个最终修改之后的答案，叫做‘答案’。格式用Markdown。"
  content_lines = []
  for idx, item in enumerate(answers, start=1):
    question = item.get("question", "")
    answer = item.get("answer", "")
    content_lines.append(f"{idx}. 问题：{question}\n回答：{answer}")
  user_content = "\n\n".join(content_lines)

  client = OpenAI(
    api_key=api_key,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
  )
  try:
    completion = client.chat.completions.create(
      model="qwen-flash",
      messages=[
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_content},
      ],
      extra_body={"enable_thinking": True},
      stream=False,
    )
    text = completion.choices[0].message.content
    return jsonify({"text": text})
  except Exception as exc:  # noqa: BLE001
    return jsonify({"error": f"调用大模型失败: {exc}"}), 500


@app.route("/api/gram-check", methods=["POST", "OPTIONS"])
def gram_check():
  if request.method == "OPTIONS":
    return ("", 204)
  api_key = "sk-dfb5d9295ee94adeafc438d18c7d4900"
  if not api_key:
    return jsonify({"error": "未配置 DASHSCOPE_API_KEY 环境变量"}), 500

  payload = request.get_json(silent=True) or {}
  question = payload.get("question") or ""
  answer = payload.get("answer") or ""
  if not answer.strip():
    return jsonify({"error": "缺少回答内容"}), 400

  prompt = (
    "请作为HSKK口语考官，用中文检查回答的语法/用词问题。"
    "务必只输出严格的JSON对象，字段包括："
    "“问题” (回答的原文), “问题类型” (概括错误类别，如语法/用词/结构/流畅度)，"
    "“问题解析” (简短说明错误点并给出如何改进), “优化表达” (给出修改后的更自然答案)。"
    "不要输出多余文本。"
  )

  client = OpenAI(
    api_key=api_key,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
  )
  try:
    completion = client.chat.completions.create(
      model="qwen-flash",
      messages=[
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"题目：{question}\n回答：{answer}"},
      ],
      stream=False,
    )
    text = completion.choices[0].message.content
    # Try parse JSON; if fail, return raw text
    try:
      import json

      parsed = json.loads(text)
    except Exception:
      parsed = None
    return jsonify({"question": question, "answer": answer, "result": parsed or text})
  except Exception as exc:  # noqa: BLE001
    return jsonify({"error": f"调用大模型失败: {exc}"}), 500


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
