import os
import uuid
import aiohttp
import asyncio
from ..provider import TTSProvider
from ..entities import ProviderType
from ..register import register_provider_adapter
from astrbot.core import logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

"""
自定义TTS服务提供商
支持通过HTTP API调用自定义的TTS服务

功能特性:
- 支持角色和情感配置的TTS合成
- 支持语速参数调节 (0.1-3.0)
- 完善的错误处理和日志记录
- 支持连接测试功能
- 自动生成WAV格式音频文件

API接口要求:
- POST /get_role_music: TTS合成接口
- 请求格式: {"role": "角色名", "emotion": "情感", "content": "文本", "speed": 1.0}
- 响应格式: WAV音频文件

作者: AstrBot开发团队
创建时间: 2024年
"""


@register_provider_adapter(
    "custom_tts_api", 
    "Custom TTS API", 
    provider_type=ProviderType.TEXT_TO_SPEECH
)
class ProviderCustomTTS(TTSProvider):
    """
    自定义TTS提供商类
    
    继承自TTSProvider基类，实现自定义TTS服务的调用逻辑
    支持通过HTTP API调用外部TTS服务，并返回WAV格式音频文件
    """
    
    def __init__(
        self,
        provider_config: dict,
        provider_settings: dict,
    ) -> None:
        """
        初始化自定义TTS提供商
        
        Args:
            provider_config: 提供商配置字典，包含API地址、密钥等配置
            provider_settings: 提供商设置字典
        """
        super().__init__(provider_config, provider_settings)
        
        # 基础配置 - API服务地址 (适配你的TTS服务)
        self.api_base = provider_config.get("api_base", "http://127.0.0.1:50042")
        if self.api_base.endswith("/"):
            self.api_base = self.api_base[:-1]  # 移除末尾的斜杠
        
        # API认证配置
        self.api_key = provider_config.get("api_key", "")  # API密钥，可选
        self.timeout = provider_config.get("timeout", 30)  # 请求超时时间（秒）
        
        # TTS合成参数配置 (适配你的API接口)
        self.role = provider_config.get("role", "缪尔赛斯")        # 角色名称
        self.emotion = provider_config.get("emotion", "平常")      # 情感类型
        self.speed = provider_config.get("speed", 1.0)            # 语速倍数 (0.1-3.0)
        
        # HTTP请求头配置
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "AstrBot-CustomTTS/1.0"
        }
        # 如果配置了API密钥，添加到请求头中
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"
        
        # 设置模型名称
        self.set_model(provider_config.get("model", "custom_tts"))

    async def get_audio(self, text: str) -> str:
        """
        实现TTS核心方法，调用自定义TTS服务生成音频
        
        Args:
            text: 要合成的文本内容
            
        Returns:
            str: 生成的WAV音频文件路径
            
        Raises:
            ValueError: 当文本为空时
            RuntimeError: 当API请求失败或音频生成失败时
        """
        if not text.strip():
            raise ValueError("[Custom TTS] TTS文本不能为空")
        
        # 创建临时文件路径 - 使用UUID确保文件名唯一性
        temp_dir = os.path.join(get_astrbot_data_path(), "temp")
        os.makedirs(temp_dir, exist_ok=True)
        audio_path = os.path.join(temp_dir, f"custom_tts_{uuid.uuid4().hex}.wav")
        
        # 构建TTS请求数据 - 适配你的API接口格式
        request_data = {
            "role": self.role,               # 角色名称
            "emotion": self.emotion,         # 情感类型
            "content": text,                 # 要合成的文本内容
            "speed": self.speed              # 语速参数 (0.1-3.0)
        }
        
        # 构建API端点URL - 使用你的实际端点
        endpoint = f"{self.api_base}/get_role_music"
        
        logger.debug(f"[Custom TTS] 正在调用TTS接口: {endpoint}")
        logger.debug(f"[Custom TTS] 请求参数: {request_data}")
        
        try:
            # 创建HTTP会话 - 设置超时时间
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    endpoint,
                    json=request_data,
                    headers=self.headers
                ) as response:
                    
                    if response.status == 200:
                        # 成功响应，读取音频数据并保存到文件
                        audio_data = await response.read()
                        with open(audio_path, "wb") as f:
                            f.write(audio_data)
                        
                        # 验证生成的音频文件
                        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                            logger.info(f"[Custom TTS] 音频生成成功: {audio_path}")
                            return audio_path
                        else:
                            raise RuntimeError("[Custom TTS] 生成的音频文件为空或不存在")
                    
                    else:
                        # 处理API错误响应
                        error_text = await response.text()
                        logger.error(f"[Custom TTS] API请求失败，状态码: {response.status}")
                        logger.error(f"[Custom TTS] 错误信息: {error_text}")
                        raise RuntimeError(f"[Custom TTS] API请求失败: {response.status} - {error_text}")
        
        except aiohttp.ClientError as e:
            # 处理网络连接错误
            logger.error(f"[Custom TTS] 网络请求失败: {e}")
            raise RuntimeError(f"[Custom TTS] 网络请求失败: {e}")
        
        except asyncio.TimeoutError:
            # 处理请求超时
            logger.error(f"[Custom TTS] 请求超时 (超时时间: {self.timeout}秒)")
            raise RuntimeError(f"[Custom TTS] 请求超时")
        
        except Exception as e:
            # 处理其他未知错误
            logger.error(f"[Custom TTS] 未知错误: {e}")
            raise RuntimeError(f"[Custom TTS] 未知错误: {e}")
    
    async def test_connection(self) -> bool:
        """
        测试TTS服务连接状态
        
        Returns:
            bool: 连接成功返回True，失败返回False
        """
        try:
            # 尝试访问健康检查端点 - 使用你的实际健康检查端点
            # 如果没有健康检查端点，可以尝试调用一个简单的TTS请求来测试连接
            endpoint = f"{self.api_base}/get_role_music"
            timeout = aiohttp.ClientTimeout(total=10)
            
            # 发送一个简单的测试请求
            test_data = {
                "role": self.role,
                "emotion": self.emotion,
                "content": "测试",
                "speed": 1.0
            }
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(endpoint, json=test_data, headers=self.headers) as response:
                    # 即使返回错误，只要能连接就说明服务可用
                    return response.status in [200, 400, 422]  # 200成功，400/422参数错误但服务可用
        except Exception as e:
            logger.warning(f"[Custom TTS] 连接测试失败: {e}")
            return False
