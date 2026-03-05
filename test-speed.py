import time
import requests
import json
import sys

# ================= 配置区域 =================

# 在这里填入你要测试的 API 列表
# model_name: 模型标识符 (根据后端不同，可能是模型文件名或模型ID)
# url: 接口地址
# prompt: 测试用的提示词
API_LIST = [

    {
        "name": "ubuntu-simple (Port 8086)",
        "url": "http://localhost:8086/v1/chat/completions",
        "model": "Qwen3.5-4B-Q4_K_M.gguf", 
        "prompt": "请简述 MySQL, Oracle, PostgreSQL 等数据库的优缺点，并对比它们的适用场景。在100字以内"
    },

    {
        "name": "debian (Port 8085)",
        "url": "http://localhost:8085/v1/chat/completions",
        "model": "Qwen3.5-4B-Q4_K_M.gguf", 
        "prompt": "请简述 MySQL, Oracle, PostgreSQL 等数据库的优缺点，并对比它们的适用场景。在100字以内"
    },

    # 你可以复制上面的字典块，添加更多测试目标
]

# 是否尝试使用 tiktoken 进行精确计数 (建议安装: pip install tiktoken)
USE_TIKTOKEN = True
TIKTOKEN_ENCODING = "cl100k_base" # 适用于大多数现代模型，如 Qwen, Llama 3, GPT-4

# ===========================================

def count_tokens(text, model_name=None):
    """尝试多种方法计算 Token 数量"""
    # 1. 优先尝试 tiktoken
    if USE_TIKTOKEN:
        try:
            import tiktoken
            # 注意：不同模型可能需要不同的 encoding，这里用通用的 cl100k_base 作为近似
            # 对于 Qwen 系列，官方推荐使用其特定的 tokenizer，但 tiktoken 误差通常在可接受范围用于测速
            enc = tiktoken.get_encoding(TIKTOKEN_ENCODING)
            return len(enc.encode(text))
        except ImportError:
            pass
        except Exception as e:
            print(f"  [Warning] Tiktoken 计算失败: {e}")

    # 2. Fallback: 粗略估算 (中文约 1.5 字符/token, 英文约 4 字符/token)
    # 混合文本简单按 2.5 字符/token 估算，仅作保底
    estimated = len(text) / 2.5
    return int(estimated)

def test_single_api(config):
    """测试单个 API 端点"""
    name = config.get("name", "Unknown")
    url = config["url"]
    model = config["model"]
    prompt = config["prompt"]

    print(f"\n🚀 开始测试: {name}")
    print(f"   地址: {url}")
    print(f"   模型: {model}")
    
    headers = {"Content-Type": "application/json"}
    
    # 构造 Payload: 开启 stream 以测量 TTFT 和 纯解码速度
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "stream": True, 
        "max_tokens": 512 # 限制生成长度，避免测试时间过长
    }

    start_time = time.time()
    first_token_time = None
    received_content = ""
    total_tokens_from_backend = 0
    
    try:
        with requests.post(url, headers=headers, json=payload, stream=True) as r:
            r.raise_for_status()
            
            for line in r.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('data: '):
                        data_str = decoded_line[6:]
                        if data_str.strip() == '[DONE]':
                            break
                        
                        try:
                            data = json.loads(data_str)
                            
                            # 提取内容
                            choices = data.get('choices', [])
                            if choices:
                                delta = choices[0].get('delta', {})
                                content = delta.get('content', '')
                                if content:
                                    received_content += content
                                    
                                    # 记录第一个 Token 的时间
                                    if first_token_time is None:
                                        first_token_time = time.time()
                            
                            # 尝试从后端获取累计 token 数 (部分后端在 stream 中不返回，只在最后返回)
                            if 'usage' in data and data['usage']:
                                total_tokens_from_backend = data['usage'].get('completion_tokens', 0)
                                
                        except json.JSONDecodeError:
                            continue

        end_time = time.time()
        
        # --- 计算指标 ---
        total_duration = end_time - start_time
        
        # 计算 TTFT (Time To First Token)
        if first_token_time:
            ttft = first_token_time - start_time
        else:
            ttft = 0 # 如果没有流式内容
            
        # 计算解码耗时 (总时间 - 首字延迟)
        decoding_duration = total_duration - ttft if ttft > 0 else total_duration
        
        # 确定 Token 总数
        output_tokens = total_tokens_from_backend
        if output_tokens == 0 and received_content:
            output_tokens = count_tokens(received_content, model)
        
        # 计算速度
        # 1. 平均速度 (包含等待首字的时间)
        avg_tps = output_tokens / total_duration if total_duration > 0 else 0
        
        # 2. 纯解码速度 (排除首字延迟，更能反映显卡生成能力)
        decoding_tps = output_tokens / decoding_duration if decoding_duration > 0 else 0

        return {
            "name": name,
            "status": "Success",
            "total_tokens": output_tokens,
            "total_time": total_duration,
            "ttft": ttft,
            "avg_tps": avg_tps,
            "decoding_tps": decoding_tps,
            "error": None
        }

    except Exception as e:
        return {
            "name": name,
            "status": "Failed",
            "total_tokens": 0,
            "total_time": 0,
            "ttft": 0,
            "avg_tps": 0,
            "decoding_tps": 0,
            "error": str(e)
        }

def main():
    results = []
    
    print("="*80)
    print("🔥 开始批量模型吞吐测速 (Stream Mode)")
    print("="*80)
    
    for i, config in enumerate(API_LIST):
        res = test_single_api(config)
        results.append(res)
        
        # 实时打印单个结果
        if res['status'] == "Success":
            print(f"✅ [{res['name']}] 完成")
            print(f"   - 生成 Token: {res['total_tokens']}")
            print(f"   - 总耗时: {res['total_time']:.2f}s | 首字延迟 (TTFT): {res['ttft']:.2f}s")
            print(f"   - 平均速度: {res['avg_tps']:.2f} tokens/s")
            print(f"   - 🔥 纯解码速度: {res['decoding_tps']:.2f} tokens/s")
        else:
            print(f"❌ [{res['name']}] 失败: {res['error']}")
            
        # 可选：在每个测试之间加一点缓冲，防止端口占用冲突
        time.sleep(0.5)

    # 打印汇总表格
    print("\n" + "="*80)
    print("📊 测速结果汇总")
    print("="*80)
    print(f"{'模型名称':<30} | {'状态':<8} | {'Tokens':<6} | {'TTFT(s)':<8} | {'解码 TPS':<10} | {'平均 TPS':<10}")
    print("-" * 95)
    
    for res in results:
        status_str = "✅ OK" if res['status'] == "Success" else "❌ Fail"
        if res['status'] == "Success":
            print(f"{res['name']:<30} | {status_str:<8} | {res['total_tokens']:<6} | {res['ttft']:<8.2f} | {res['decoding_tps']:<10.2f} | {res['avg_tps']:<10.2f}")
        else:
            # 截断过长的错误信息
            err_msg = res['error'][:20] + "..." if len(res['error']) > 20 else res['error']
            print(f"{res['name']:<30} | {status_str:<8} | {'-':<6} | {'-':<8} | {'-':<10} | {'-':<10} (Err: {err_msg})")
            
    print("="*80)

if __name__ == "__main__":
    # 检查依赖
    try:
        import requests
    except ImportError:
        print("错误: 缺少 requests 库，请运行: pip install requests")
        sys.exit(1)
        
    main()