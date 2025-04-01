import os
import random
import json
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage
from common.log import logger
from config import conf
from plugins import Plugin, Event, EventContext, EventAction, register

# 调试模式开关，设置为False关闭调试日志，需要时改为True启用
DEBUG_MODE = False

@register(name="RandomReply", desc="根据概率随机回复群聊消息", version="0.2", author="user")
class RandomReply(Plugin):
    def __init__(self):
        super().__init__()
        # 处理 ON_RECEIVE_MESSAGE 事件，比 ON_HANDLE_CONTEXT 更早触发
        self.handlers[Event.ON_RECEIVE_MESSAGE] = self.on_receive_message
        # 添加装饰回复的处理器，处理特殊字符和格式问题
        self.handlers[Event.ON_DECORATE_REPLY] = self.on_decorate_reply
        # 添加监控发送回复的处理器，诊断发送问题
        self.handlers[Event.ON_SEND_REPLY] = self.on_send_reply
        
        # 加载插件配置
        try:
            curdir = os.path.dirname(__file__)
            config_path = os.path.join(curdir, "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            else:
                self.config = {
                    "enabled": True,
                    "probability": 0.1,
                    "blacklist_groups": [],
                    "blacklist_users": [],
                    "protect_private_msgs": True,  # 新增：保护私聊消息
                    "min_msg_length": 5,  # 新增：最小消息长度
                    "max_msg_length": 100,  # 新增：最大消息长度
                    "trigger_keywords": [],  # 触发关键词列表
                    "use_keyword_plugin": False,  # 是否使用keyword插件的关键词
                    "excluded_keywords": []  # 排除的关键词
                }
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=4)
            
            # 确保配置中有protect_private_msgs字段
            if "protect_private_msgs" not in self.config:
                self.config["protect_private_msgs"] = True
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=4)
                    
            # 初始化关键词列表
            self.keyword_triggers = self.config.get("trigger_keywords", [])
            # 加载keyword插件的关键词
            self.load_keyword_triggers_from_config()
                    
            logger.info(f"[RandomReply] 插件配置加载成功: {self.config}")
        except Exception as e:
            logger.warning(f"[RandomReply] 加载配置文件失败: {e}")
            self.config = {
                "enabled": True,
                "probability": 0.1,
                "blacklist_groups": [],
                "blacklist_users": [],
                "protect_private_msgs": True,  # 新增：保护私聊消息
                "min_msg_length": 5,  # 新增：最小消息长度
                "max_msg_length": 100,  # 新增：最大消息长度
                "trigger_keywords": [],  # 触发关键词列表
                "use_keyword_plugin": False,  # 是否使用keyword插件的关键词
                "excluded_keywords": []  # 排除的关键词
            }
            # 初始化默认关键词列表
            self.keyword_triggers = []
            
        logger.info(f"[RandomReply] 插件已初始化，随机回复概率: {self.config.get('probability', 0.8)}, 私聊消息保护: {self.config.get('protect_private_msgs', True)}, 最小消息长度: {self.config.get('min_msg_length', 5)}, 最大消息长度: {self.config.get('max_msg_length', 100)}, 关键词数量: {len(self.keyword_triggers)}")
    
    def load_keyword_triggers_from_config(self):
        """根据配置决定是否加载keyword插件的关键词"""
        # 检查是否启用keyword自动匹配
        if self.config.get("use_keyword_plugin", False):
            keyword_triggers = self.load_keyword_triggers()
            
            # 合并配置中的触发关键词
            config_triggers = self.config.get("trigger_keywords", [])
            if config_triggers and isinstance(config_triggers, list):
                # 去重合并
                all_triggers = list(set(keyword_triggers + config_triggers))
                self.keyword_triggers = all_triggers
            else:
                self.keyword_triggers = keyword_triggers
    
    def load_keyword_triggers(self):
        """从keyword插件配置文件中加载关键词"""
        try:
            # 获取keyword插件配置文件路径
            keyword_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "keyword", "config.json")
            if os.path.exists(keyword_config_path):
                with open(keyword_config_path, "r", encoding="utf-8") as f:
                    keyword_config = json.load(f)
                    
                # 从keyword配置中提取关键词
                keywords = []
                if "keyword" in keyword_config and isinstance(keyword_config["keyword"], dict):
                    # 获取所有的关键词键
                    keywords = list(keyword_config["keyword"].keys())
                    # 过滤掉空字符串
                    keywords = [k for k in keywords if k.strip()]
                    
                    # 过滤掉指定的关键词（从配置中获取）
                    excluded_keywords = self.config.get("excluded_keywords", [])
                    if excluded_keywords and isinstance(excluded_keywords, list):
                        keywords = [k for k in keywords if k not in excluded_keywords]
                    
                    logger.info(f"[RandomReply] 从keyword插件加载了{len(keywords)}个触发关键词")
                    return keywords
                else:
                    logger.warning("[RandomReply] keyword配置文件格式不正确")
            else:
                logger.warning(f"[RandomReply] 未找到keyword插件配置文件: {keyword_config_path}")
        except Exception as e:
            logger.error(f"[RandomReply] 加载keyword配置文件时出错: {e}")
        
        return []
    
    def on_receive_message(self, e_context: EventContext):
        """
        处理 ON_RECEIVE_MESSAGE 事件，在消息进入处理链前进行处理
        """
        try:
            context = e_context["context"]
            
            # 检查消息是否为空
            if context is None:
                if DEBUG_MODE:
                    logger.debug("[RandomReply] 收到空上下文，跳过处理")
                return
    
            # 检查是否已经被随机回复插件触发过，避免重复处理
            if context.get("random_reply_triggered", False):
                if DEBUG_MODE:
                    logger.debug("[RandomReply] 消息已被随机回复插件触发过，跳过处理")
                e_context.action = EventAction.CONTINUE
                return
    
            # 安全地检查是否是群聊消息
            is_group = context.get("isgroup", False)
            if not is_group:
                if DEBUG_MODE:
                    logger.debug("[RandomReply] 不是群聊消息，跳过处理")
                # 确保不影响私聊消息处理
                e_context.action = EventAction.CONTINUE
                return
                
            # 确保消息类型存在并且是文本消息
            if not hasattr(context, 'type') or context.type is None or context.type != ContextType.TEXT:
                if DEBUG_MODE:
                    logger.debug("[RandomReply] 不是文本消息，跳过处理")
                # 设置EventAction.CONTINUE确保消息能被其他插件处理
                e_context.action = EventAction.CONTINUE
                return
            
            # 检查消息内容是否为空
            content = context.content
            if not content:
                if DEBUG_MODE:
                    logger.debug("[RandomReply] 消息内容为空，跳过处理")
                e_context.action = EventAction.CONTINUE
                return

            # 获取消息信息 - 去除前后空白
            cleaned_content = content.strip()
            
            # 在长度检查前先检查关键词触发
            keyword_triggered = False
            # 使用合并后的关键词列表
            trigger_keywords = self.keyword_triggers
            
            if trigger_keywords and isinstance(trigger_keywords, list) and cleaned_content:
                # 优先进行完全匹配检查
                for keyword in trigger_keywords:
                    if cleaned_content == keyword:
                        keyword_triggered = True
                        logger.info(f"[RandomReply] 检测到完全匹配的触发关键词: '{keyword}'，自动回复")
                        break
                
                # 如果没有完全匹配，检查第一个空格前的部分
                if not keyword_triggered and " " in cleaned_content:
                    first_word = cleaned_content.split(" ", 1)[0]
                    for keyword in trigger_keywords:
                        if first_word == keyword:
                            keyword_triggered = True
                            logger.info(f"[RandomReply] 检测到第一个词匹配触发关键词: '{keyword}'，自动回复")
                            break
            
            # 只有在非关键词触发的情况下才检查消息长度
            if not keyword_triggered:
                # 从配置中获取最小消息长度，如果未设置则默认为5
                min_msg_length = self.config.get("min_msg_length", 5)
                if len(cleaned_content) < min_msg_length:
                    if DEBUG_MODE:
                        logger.debug(f"[RandomReply] 消息内容太短({len(cleaned_content)}字符 < {min_msg_length}字符)，跳过处理")
                    e_context.action = EventAction.CONTINUE
                    return
                
            if not self.config.get("enabled", True):
                if DEBUG_MODE:
                    logger.debug("[RandomReply] 插件已禁用，跳过处理")
                # 设置EventAction.CONTINUE确保消息能被其他插件处理
                e_context.action = EventAction.CONTINUE
                return
            
            # 安全地获取消息对象
            msg = context.get("msg")
            if not msg:
                logger.warning("[RandomReply] 消息对象为空，跳过处理")
                # 设置EventAction.CONTINUE确保消息能被其他插件处理
                e_context.action = EventAction.CONTINUE
                return
                
            # 检查必要的属性是否存在
            required_attrs = ['actual_user_nickname', 'other_user_nickname', 'other_user_id', 'actual_user_id']
            for attr in required_attrs:
                if not hasattr(msg, attr) or getattr(msg, attr) is None:
                    logger.warning(f"[RandomReply] 消息缺少关键属性 {attr}，跳过处理")
                    # 设置EventAction.CONTINUE确保消息能被其他插件处理
                    e_context.action = EventAction.CONTINUE
                    return
                
            try:
                logger.info(f"[RandomReply] 收到消息: content='{content}', from='{msg.actual_user_nickname}', group='{msg.other_user_nickname}'")
            except Exception as e:
                logger.warning(f"[RandomReply] 无法获取消息详情: {e}")
                # 设置EventAction.CONTINUE确保消息能被其他插件处理
                e_context.action = EventAction.CONTINUE
                return
                                
            group_id = msg.other_user_id
            user_id = msg.actual_user_id
            
            # 检查群组黑名单
            blacklist_groups = self.config.get("blacklist_groups", [])
            if group_id in blacklist_groups:
                if DEBUG_MODE:
                    logger.debug(f"[RandomReply] 群组 {group_id} 在黑名单中，跳过随机回复")
                # 设置EventAction.CONTINUE确保消息能被其他插件处理
                e_context.action = EventAction.CONTINUE
                return
                
            # 检查用户黑名单
            blacklist_users = self.config.get("blacklist_users", [])
            if user_id in blacklist_users:
                if DEBUG_MODE:
                    logger.debug(f"[RandomReply] 用户 {user_id} 在黑名单中，跳过随机回复")
                # 设置EventAction.CONTINUE确保消息能被其他插件处理
                e_context.action = EventAction.CONTINUE
                return
            
            # 检查消息是否已经匹配了前缀或关键词
            match_prefix = False
            match_contain = False
            is_at = False
            
            # 检查是否已经匹配了前缀
            group_chat_prefix = conf().get("group_chat_prefix", [])
            for prefix in group_chat_prefix:
                if content.startswith(prefix):
                    match_prefix = True
                    if DEBUG_MODE:
                        logger.info(f"[RandomReply] 消息匹配前缀 '{prefix}'，跳过随机判断")
                    # 设置EventAction.CONTINUE确保消息能被其他插件处理
                    e_context.action = EventAction.CONTINUE
                    return
            

            # 检查是否被@
            if hasattr(msg, 'is_at') and msg.is_at:
                is_at = True
                if DEBUG_MODE:
                    logger.info("[RandomReply] 消息含有@，跳过随机判断")
                # 设置EventAction.CONTINUE确保消息能被其他插件处理
                e_context.action = EventAction.CONTINUE
                return
                
            # 输出一些调试信息
            if DEBUG_MODE:
                logger.info(f"[RandomReply] 开始随机判断: content='{content}'")
                
            # 获取配置的随机回复概率
            probability = self.config.get("probability", 0.8)
            
            # 如果匹配关键词则直接触发，否则根据概率决定是否回复
            random_value = random.random()
            if keyword_triggered or random_value < probability:
                # 记录触发原因
                if keyword_triggered:
                    logger.info(f"[RandomReply] 关键词触发成功！匹配方式: {'完全匹配' if cleaned_content == content.strip() else '首词匹配'}")
                else:
                    logger.info(f"[RandomReply] 随机触发成功！概率: {probability}, 随机值: {random_value}")
                
                try:
                    # 使用原始的ChatChannel处理流程
                    from channel.chat_channel import ChatChannel
                    from bridge.context import Context
                    
                    # 确保使用正确的GeWeChatChannel实例
                    from channel.gewechat.gewechat_channel import GeWeChatChannel
                    
                    # 获取当前的channel实例 - 首选使用GeWeChatChannel
                    gewechat_channel = GeWeChatChannel()  # 直接使用子类实例
                    
                    # 创建一个新的Context对象，复制原始上下文的关键属性
                    new_context = Context(ContextType.TEXT)
                    new_context.content = content
                    
                    # 复制原始上下文的关键属性
                    for key in context.kwargs:
                        new_context[key] = context[key]
                    
                    # 添加前缀匹配标记，绕过前缀检查
                    new_context["content_prefix_matched"] = True
                    
                    # 重要：添加标记表明这是AI需要实际回应的消息
                    new_context["need_reply"] = True
                    
                    # 添加标记，表示这是随机触发的消息，避免在后续处理中被再次触发
                    new_context["random_reply_triggered"] = True
                    
                    # 添加自定义ON_DECORATE_REPLY处理器用于处理回复中的特殊格式
                    class CustomReplyProcessor:
                        @staticmethod
                        def process_reply(reply):
                            if reply and reply.type == ReplyType.TEXT and reply.content:
                                # 简化处理内容
                                content = reply.content.strip()
                                
                                # 移除外层引号(单引号、双引号)
                                if (content.startswith('"') and content.endswith('"')) or \
                                   (content.startswith("'") and content.endswith("'")):
                                    content = content[1:-1].strip()
                                
                                # 检查是否是JSON格式并尝试解析
                                if (content.startswith('{') and content.endswith('}')) or \
                                   (content.startswith('[') and content.endswith(']')):
                                    try:
                                        import json
                                        parsed = json.loads(content)
                                        # 如果是对象且只有一个键为"content"的值，提取它
                                        if isinstance(parsed, dict) and len(parsed) == 1 and "content" in parsed:
                                            content = str(parsed["content"])
                                    except:
                                        # 解析失败，保持原样
                                        pass
                                
                                # 获取配置的最大消息长度，如果未设置则默认为100
                                max_msg_length = CustomReplyProcessor.get_max_length()
                                
                                # 限制长度
                                if len(content) > max_msg_length:
                                    content = content[:max_msg_length-3] + "..."
                                
                                # 清理多余的引号
                                content = content.replace('"', '')
                                reply.content = content.strip()
                                
                                # 记录处理后的内容
                                if DEBUG_MODE:
                                    logger.debug(f"[RandomReply] 处理后的回复内容: '{reply.content}'")
                            return reply
                        
                        @staticmethod
                        def get_max_length():
                            """获取配置的最大消息长度"""
                            # 由于无法直接访问插件实例，使用try-except加载配置
                            try:
                                # 尝试从文件中读取配置
                                config_path = os.path.join(os.path.dirname(__file__), "config.json")
                                if os.path.exists(config_path):
                                    with open(config_path, "r", encoding="utf-8") as f:
                                        config = json.load(f)
                                    return config.get("max_msg_length", 100)
                            except:
                                # 读取失败时使用默认值
                                pass
                            return 100
                    
                    # 存储处理器到上下文
                    new_context["custom_reply_processor"] = CustomReplyProcessor.process_reply
                    
                    
                    # 由于PluginManager不支持动态注册事件处理器，我们使用替代方案
                    # 将处理器直接添加到Context对象中，在_decorate_reply方法中处理
                    
                    # 记录请求的关键信息
                    logger.info(f"[RandomReply] 将消息'{content}'作为需要AI回复的上下文提交处理")
                    
                    # 设置超时处理，避免请求阻塞太久
                    import threading
                    
                    def timeout_handler():
                        # 这个函数在超时后执行
                        logger.warning("[RandomReply] 请求处理超时，可能需要检查服务状态")
                    
                    # 创建超时处理线程，30秒后触发
                    timer = threading.Timer(30.0, timeout_handler)
                    timer.daemon = True  # 设为守护线程，避免阻塞程序退出
                    timer.start()
                    
                    try:
                        # 直接使用已有的channel实例，避免创建新实例
                        from channel.gewechat.gewechat_channel import GeWeChatChannel
                        
                        # 特别关注上下文中的channel，确保引用正确
                        if "channel" in context.kwargs:
                            # 使用已存在的channel实例，而不是创建新的
                            if DEBUG_MODE:
                                logger.debug(f"[RandomReply] 使用上下文提供的channel实例: {type(context.kwargs['channel']).__name__}")
                            
                            # 检查channel的send方法
                            if hasattr(context.kwargs['channel'], 'send'):
                                if DEBUG_MODE:
                                    logger.debug(f"[RandomReply] channel实例具有send方法")
                                
                                # 检查是否为GeWeChatChannel类型
                                if isinstance(context.kwargs['channel'], GeWeChatChannel):
                                    if DEBUG_MODE:
                                        logger.debug(f"[RandomReply] 确认是GeWeChatChannel实例")
                                    
                                    # 检查GeWeChatChannel实例的基本属性
                                    channel_obj = context.kwargs['channel']
                                    if DEBUG_MODE:
                                        logger.debug(f"[RandomReply] GeWeChatChannel属性检查: base_url={getattr(channel_obj, 'base_url', None)}, token={bool(getattr(channel_obj, 'token', None))}, app_id={getattr(channel_obj, 'app_id', None)}, client={bool(getattr(channel_obj, 'client', None))}")
                            else:
                                logger.warning(f"[RandomReply] channel实例缺少send方法")
                            
                        # 防止后续出现超时问题，增加超时监视器
                        def send_error_monitor():
                            # 增加对随机回复发送请求的状态监控
                            logger.warning(f"[RandomReply] 消息发送可能超时，请检查gewechat_channel.post_text实现")
                        
                        # 设置发送错误监视器，5秒后触发
                        monitor_timer = threading.Timer(5.0, send_error_monitor)
                        monitor_timer.daemon = True
                        monitor_timer.start()
                            
                        # 添加额外信息确保上下文完整
                        new_context["no_need_at"] = True  # 设置不需要@，避免@格式问题
                        
                        # 在发送前记录详细的上下文信息
                        if DEBUG_MODE:
                            logger.debug(f"[RandomReply] 准备提交的上下文: type={new_context.type}, content={new_context.content}，主要属性: isgroup={new_context.get('isgroup')}, session_id={new_context.get('session_id')}, receiver={new_context.get('receiver')}")
                        
                        # 通过produce方法将上下文发送给channel处理
                        gewechat_channel.produce(new_context)
                        logger.info("[RandomReply] 已成功提交上下文进行处理")
                        
                        # 请求开始处理，取消定时器
                        timer.cancel()
                        monitor_timer.cancel()
                        
                        # 中断原始消息的处理链
                        e_context.action = EventAction.BREAK
                        
                        # 在这里显式返回，避免后续代码执行
                        return
                    except Exception as e:
                        # 捕获produce过程中的异常
                        logger.error(f"[RandomReply] 提交请求时发生错误: {e}")
                        # 取消超时定时器
                        timer.cancel()
                        if 'monitor_timer' in locals():
                            monitor_timer.cancel()
                            
                        # 出现错误时不中断原始处理链
                        e_context.action = EventAction.CONTINUE
                except Exception as e:
                    logger.error(f"[RandomReply] 创建和处理新上下文失败: {e}")
                    # 打印详细的异常信息
                    import traceback
                    logger.error(f"[RandomReply] 异常详情: {traceback.format_exc()}")
                    
                    # 出现错误时不中断原始处理链
                    e_context.action = EventAction.CONTINUE
            else:
                # 不处理该消息
                if DEBUG_MODE:
                    logger.debug(f"[RandomReply] 随机触发失败，跳过此消息。概率: {probability}, 随机值: {random_value}")
                # 显式设置为CONTINUE确保后续处理
                e_context.action = EventAction.CONTINUE
                
        except Exception as e:
            logger.error(f"[RandomReply] 处理消息时发生错误: {e}")
            # 发生任何未捕获的异常时，确保不中断原始处理链
            e_context.action = EventAction.CONTINUE
            
        # 明确返回，确保不会有隐式返回值
        return 

    def on_decorate_reply(self, e_context: EventContext):
        """
        处理 ON_DECORATE_REPLY 事件，在回复被发送前处理格式
        """
        try:
            reply = e_context["reply"]
            context = e_context["context"]
            
            # 记录回复对象的详细信息，便于调试
            if DEBUG_MODE and reply and hasattr(reply, 'type') and hasattr(reply, 'content'):
                logger.debug(f"[RandomReply] on_decorate_reply处理的回复: type={reply.type}, content_len={len(reply.content) if reply.content else 0}, content='{reply.content}'")
                
            # 检查上下文中的channel信息
            if context and "channel" in context:
                channel = context["channel"]
                if DEBUG_MODE:
                    logger.debug(f"[RandomReply] on_decorate_reply处理的上下文channel: {type(channel).__name__}")
                
                # 检查channel类型，如果不是GeWeChatChannel，发出警告
                if not str(type(channel).__name__).lower().endswith('gewechatchannel'):
                    logger.warning(f"[RandomReply] 上下文中的channel不是GeWeChatChannel，可能导致消息发送问题")
                    
                    # 尝试检查是否需要替换为正确的channel类型
                    try:
                        from channel.gewechat.gewechat_channel import GeWeChatChannel
                        
                        # 只在确定不会影响其他处理逻辑的情况下修改
                        if hasattr(context, 'kwargs') and context['random_reply_triggered']:
                            # 只替换我们自己触发的消息中的channel
                            context['channel'] = GeWeChatChannel()
                            logger.info(f"[RandomReply] 已将上下文中的channel替换为GeWeChatChannel实例")
                    except Exception as channel_fix_error:
                        logger.error(f"[RandomReply] 尝试修复channel时出错: {channel_fix_error}")
            
            # 检查是否是我们的随机回复消息
            if context and context.get("random_reply_triggered", False):
                # 检查上下文是否包含我们的处理器
                if "custom_reply_processor" in context.kwargs:
                    processor = context.kwargs["custom_reply_processor"]
                    # 应用自定义处理器，同时记录处理前后的差异
                    original_content = reply.content if reply and hasattr(reply, 'content') else ""
                    processed_reply = processor(reply)
                    e_context["reply"] = processed_reply
                    
                    # 记录处理前后的变化
                    if DEBUG_MODE and processed_reply and hasattr(processed_reply, 'content'):
                        processed_content = processed_reply.content if processed_reply.content else ""
                        if original_content != processed_content:
                            logger.debug(f"[RandomReply] 处理前内容: '{original_content}'")
                            logger.debug(f"[RandomReply] 处理后内容: '{processed_content}'")
                            # 如果内容长度发生变化，额外记录长度信息
                            if len(original_content) != len(processed_content):
                                logger.debug(f"[RandomReply] 内容长度变化: {len(original_content)} -> {len(processed_content)}")
                else:
                    # 如果没有处理器，但是确实是随机回复消息，做一些基本处理
                    if reply and reply.type == ReplyType.TEXT and reply.content:
                        original_content = reply.content
                        content = reply.content.strip()
                        
                        # 移除外层引号
                        if (content.startswith('"') and content.endswith('"')) or \
                           (content.startswith("'") and content.endswith("'")):
                            content = content[1:-1].strip()
                        
                        # 限制长度
                        if len(content) > 100:
                            content = content[:97] + "..."
                            
                        reply.content = content
                        
                        # 记录处理过程
                        if DEBUG_MODE and original_content != content:
                            logger.debug(f"[RandomReply] 基本处理前内容: '{original_content}'")
                            logger.debug(f"[RandomReply] 基本处理后内容: '{content}'")
            
            # 尝试检查gewechat_channel最终发送的消息内容
            try:
                if DEBUG_MODE and "channel" in context and reply and reply.type == ReplyType.TEXT:
                    logger.debug(f"[RandomReply] 即将发送的消息内容: '{reply.content}'")
                    
                    # 尝试检查接收者信息
                    receiver = context.get("receiver")
                    if receiver:
                        logger.debug(f"[RandomReply] 消息接收者: {receiver}")
            except Exception as send_check_error:
                logger.warning(f"[RandomReply] 检查发送信息时出错: {send_check_error}")
            
            # 不修改动作，让事件继续处理
            return
        except Exception as e:
            logger.error(f"[RandomReply] 处理回复时出错: {e}")
            import traceback
            logger.error(f"[RandomReply] 处理回复异常详情: {traceback.format_exc()}")
            # 继续事件处理链
            return

    def on_send_reply(self, e_context: EventContext):
        """
        处理 ON_SEND_REPLY 事件，监控消息发送过程
        """
        try:
            # 获取关键信息
            reply = e_context["reply"]
            context = e_context["context"]
            channel = e_context["channel"]
            
            # 记录详细的发送信息
            if DEBUG_MODE:
                logger.debug(f"[RandomReply] 监控消息发送: channel类型={type(channel).__name__}")
            
                if reply:
                    logger.debug(f"[RandomReply] 要发送的回复: type={reply.type}, content='{reply.content if hasattr(reply, 'content') else 'N/A'}'")
            
                if context:
                    receiver = context.get("receiver")
                    session_id = context.get("session_id")
                    isgroup = context.get("isgroup")
                    logger.debug(f"[RandomReply] 消息上下文: receiver={receiver}, session_id={session_id}, isgroup={isgroup}")
                
            # 检查channel的send方法
            if hasattr(channel, 'send'):
                # 获取原始send方法，用于后续恢复
                original_send = channel.send
                
                # 定义包装后的send方法，用于捕获发送错误
                def wrapped_send(self_ref, reply_obj, context_obj):
                    try:
                        if DEBUG_MODE:
                            logger.debug(f"[RandomReply] 准备通过{type(self_ref).__name__}.send发送消息: {reply_obj}")
                        
                        # 检查是否为基类引用，如果是，则应该直接使用GeWeChatChannel
                        if type(self_ref).__name__ == 'ChatChannel' and not hasattr(self_ref, '_send'):
                            logger.warning("[RandomReply] 检测到使用的是ChatChannel基类，尝试修正为GeWeChatChannel实例")
                            from channel.gewechat.gewechat_channel import GeWeChatChannel
                            
                            # 创建一个新的GeWeChatChannel实例
                            gewechat_instance = GeWeChatChannel()
                            
                            # 使用子类实例的send方法
                            logger.info("[RandomReply] 改用GeWeChatChannel实例发送消息")
                            result = gewechat_instance.send(reply_obj, context_obj)
                            return result
                        
                        # 检查client属性
                        if DEBUG_MODE and hasattr(self_ref, 'client'):
                            client = self_ref.client
                            if hasattr(client, 'post_text'):
                                logger.debug(f"[RandomReply] client.post_text方法存在")
                            else:
                                logger.warning(f"[RandomReply] client.post_text方法不存在")
                        
                        # 调用原始send方法
                        result = original_send(reply_obj, context_obj)
                        if DEBUG_MODE:
                            logger.debug(f"[RandomReply] 消息发送成功: {result}")
                        return result
                    except NotImplementedError:
                        # 专门处理未实现异常
                        logger.error("[RandomReply] 发现NotImplementedError - Channel基类方法被调用")
                        
                        # 尝试直接使用GeWeChatChannel
                        try:
                            from channel.gewechat.gewechat_channel import GeWeChatChannel
                            logger.info("[RandomReply] 尝试使用GeWeChatChannel发送消息")
                            
                            # 创建新的GeWeChatChannel实例并发送消息
                            gewechat_instance = GeWeChatChannel()
                            # 合成新的回复对象，确保不会出现引用问题
                            from bridge.reply import Reply, ReplyType
                            
                            # 只复制重要属性
                            new_reply = Reply(reply_obj.type, reply_obj.content)
                            result = gewechat_instance.send(new_reply, context_obj)
                            
                            logger.info("[RandomReply] 使用GeWeChatChannel发送成功")
                            return result
                        except Exception as recovery_error:
                            logger.error(f"[RandomReply] 恢复发送失败: {recovery_error}")
                            import traceback
                            logger.error(f"[RandomReply] 恢复发送异常详情: {traceback.format_exc()}")
                            raise
                    except Exception as e:
                        # 记录详细的异常信息
                        import traceback
                        logger.error(f"[RandomReply] 监控到消息发送异常: {e}")
                        logger.error(f"[RandomReply] 发送异常详情: {traceback.format_exc()}")
                        # 重新抛出异常，不影响原来的错误处理流程
                        raise
                
                # 应用补丁
                channel.send = wrapped_send.__get__(channel, type(channel))
                
                # 注册恢复原始方法的定时器，确保不会永久更改send方法
                import threading
                def restore_send():
                    try:
                        channel.send = original_send
                        if DEBUG_MODE:
                            logger.debug("[RandomReply] 已恢复原始send方法")
                    except:
                        pass
                
                restore_timer = threading.Timer(30.0, restore_send)
                restore_timer.daemon = True
                restore_timer.start()
                
            # 不修改动作，继续事件处理链
            return
        
        except Exception as e:
            logger.error(f"[RandomReply] 监控消息发送过程中发生错误: {e}")
            import traceback
            logger.error(f"[RandomReply] 监控异常详情: {traceback.format_exc()}")
            # 继续事件处理链
            return