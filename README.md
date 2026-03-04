# llama.cpp + Docker 部署方案

这个方案使用原生的 llama.cpp (C++) 获得最佳性能，并用 Python 代理提供 OpenAI API 兼容接口。

## 文件结构

```
llamacpp-deploy/
├── Dockerfile          # Docker 构建文件
├── docker-compose.yml  # Docker Compose 配置
├── launch.sh          # 启动脚本（获取 MODEL_PATH 环境变量）
├── llama-proxy.py     # Python 代理服务器
└── .dockerignore      # Docker 构建忽略文件
```

## 快速开始

### 1. 准备模型文件

将你的 GGUF 模型文件放在 `llamacpp-deploy/models/` 目录下：

```bash
# 示例
mkdir -p ../llamacpp-deploy/models
cp /path/to/your/model.gguf ../llamacpp-deploy/models/model.gguf
```

### 2. 配置模型路径

编辑 `docker-compose.yml` 中的 `MODEL_PATH` 环境变量：

```yaml
environment:
  - MODEL_PATH=/models/your-model-file.gguf  # 修改为你的模型文件名
```

### 3. 构建并运行

```bash
cd llamacpp-deploy
docker-compose up -d --build
```

### 4. 验证运行

```bash
# 检查服务状态
docker-compose ps

# 测试健康检查
curl http://localhost:8000/health

# 测试 API 调用
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen","messages":[{"role":"user","content":"Hello!"}]}'
```

## API 端点

- **OpenAI 兼容 API**: `http://localhost:8000/v1/chat/completions`
- **健康检查**: `http://localhost:8000/health`
- **模型列表**: `http://localhost:8000/v1/models`
- **llama.cpp 原生**: `http://localhost:8080` (可选)

## 配置说明

### CPU 资源限制

在 `docker-compose.yml` 中调整：

```yaml
deploy:
  resources:
    limits:
      cpus: '8.0'      # 根据你的 CPU 核心数调整
      memory: 12G      # 根据你的内存调整
```

### 模型参数

在 `launch.sh` 中调整 llama.cpp 参数：

```bash
./llama.cpp/main \
    -m "$MODEL_FILE" \
    --ctx-size 4096      # 上下文大小
    --threads $(nproc)   # 使用所有 CPU 核心
    --batch-size 512     # 批次大小
```

### 支持不同的模型

只需更改 `docker-compose.yml` 中的 `MODEL_PATH` 变量：

```yaml
environment:
  - MODEL_PATH=/models/qwen2.5-7b-instruct-q4_k_m.gguf
```

## 性能优化

### 1. ARM 处理器优化

Dockerfile 中使用了 `LLAMA_NATIVE=1`，会自动针对 ARM 优化。

### 2. 内存优化

如果内存不足，可以调低参数：
- `--ctx-size 2048`  # 减小上下文
- `--batch-size 256`   # 减小批次

### 3. 并发处理

llama.cpp 默认单请求处理。如需并发，可以：
- 增加批次大小
- 使用队列和负载均衡

## 故障排除

### 模型文件未找到

```
❌ Model file not found: /models/model.gguf
```

检查：
1. 模型文件是否正确放置在 `llamacpp-deploy/models/` 目录
2. `MODEL_PATH` 环境变量是否正确设置

### 服务启动失败

```bash
# 查看日志
docker-compose logs

# 进入容器调试
docker-compose exec llama-api bash
```

### 内存不足

如果系统内存不足，会 OOM。解决方案：
- 使用量化程度更高的模型（Q4_0 而不是 Q8_0）
- 调小上下文大小和批次大小
- 增加 swap 空间

## 注意事项

1. **llama.cpp 版本**：确保使用最新分支以支持 Qwen3.5
2. **模型兼容性**：目前 Qwen3.5 可能需要等待 llama.cpp 支持
3. **性能监控**：使用 `docker stats` 监控资源使用

## 更新模型

### 1. 停止服务
```bash
docker-compose down
```

### 2. 更新模型文件
```bash
# 替换模型文件
cp /path/to/new-model.gguf models/model.gguf
```

### 3. 重新启动
```bash
docker-compose up -d
```# llama.cpp-gguf-docker-deploy
