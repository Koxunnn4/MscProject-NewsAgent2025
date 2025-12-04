import os
from dify_client.client import ChatClient

# --- 配置信息 ---
# 1. 替换为您的 Dify 应用的实际 API Key
# 建议通过环境变量设置，这里为了演示直接写死
DIFY_API_KEY = "app-gLefZ3jUBGpMEXZ4RR2ggAUz"

# 2. Dify 服务的基地址
# 如果是本地部署，需要修改 ChatClient 的 base_url
DIFY_BASE_URL = "http://localhost/v1"

# 3. (可选) 用户 ID，用于会话跟踪
USER_ID = "user_123" 
# ------------------

def chat_with_dify(query: str):
    """
    使用 Dify SDK 调用聊天机器人并打印回复。
    """
    
    # 初始化 ChatClient
    try:
        client = ChatClient(DIFY_API_KEY)
        # 如果是本地部署，需要修改 base_url
        client.base_url = DIFY_BASE_URL
    except Exception as e:
        print(f"❌ ChatClient 初始化失败。请检查 DIFY_API_KEY。错误: {e}")
        return

    print(f"👤 User: {query}")
    print("-" * 30)

    try:
        # 调用 create_chat_message 方法发送聊天消息
        response = client.create_chat_message(
            inputs={},  # 如果应用需要额外输入参数，在这里添加
            query=query,
            user=USER_ID,
            response_mode="blocking",  # 阻塞模式，等待完整回复
        )

        # 检查响应状态并提取文本
        if response.status_code == 200:
            data = response.json()
            answer = data.get('answer', '未找到回复文本')
            print(f"🤖 Dify: {answer}")
            
            # 可选：打印会话ID，用于后续对话
            conversation_id = data.get('conversation_id')
            if conversation_id:
                print(f"📝 会话ID: {conversation_id}")
        else:
            print(f"❌ Dify API 调用失败。状态码: {response.status_code}")
            print(f"响应内容: {response.text}")

    except Exception as e:
        print(f"❌ 调用 Dify API 过程中发生错误。请检查网络连接或 API 配置。")
        print(f"错误信息: {e}")


if __name__ == "__main__":
    # --- 实际调用 ---
    if DIFY_API_KEY == "YOUR_DIFY_API_KEY":
        print("⚠️ 请修改代码中的 DIFY_API_KEY 为您的实际值后再运行。")
    else:
        chat_with_dify("介绍一下你自己吧。")