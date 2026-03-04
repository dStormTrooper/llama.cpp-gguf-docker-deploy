#!/bin/bash

# 从环境变量获取模型文件路径（docker-compose 传入）
MODEL_FILE="${MODEL_PATH}"
THREADS=$(($(nproc) / 2)) 
echo "🔍 Checking for GGUF model file: $MODEL_FILE"

if [ -z "$MODEL_FILE" ]; then
    echo "❌ MODEL_PATH environment variable not set!"
    exit 1
fi

if [ ! -f "$MODEL_FILE" ]; then
    echo "❌ Model file not found: $MODEL_FILE"
    exit 1
fi

echo "✅ Found model: $(basename $MODEL_FILE)"

# 直接启动 llama.cpp 服务器（已经 OpenAI 兼容）
echo "🚀 Starting llama.cpp server on port 8000..."
echo "📡 OpenAI API: http://localhost:8000/v1/chat/completions"
echo "🌐 Web UI: http://localhost:8000"
echo ""

./llama.cpp/build/bin/llama-server \
    -m "$MODEL_FILE" \
    --host 0.0.0.0 \
    --port 8000 \
    --ctx-size 4096 \
    --threads $THREADS \
    --batch-size 2048
      # 尝试增大 batch 以加速 prompt 处理，或者减小以测试带宽瓶颈
