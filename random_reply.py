import os
import random
import json
import threading
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage
from common.log import logger
from config import conf
from plugins import Plugin, Event, EventContext, EventAction, register

# 调试模式开关，设置为False关闭调试日志，需要时改为True启用
DEBUG_MODE = False

@register(name="RandomReply", desc="根据概率随机回复群聊消息", version="0.3", author="memor221")
class RandomReply(Plugin):
    def __init__(self):
        super().__init__()
        # 处理 ON_RECEIVE_MESSAGE 事件，比 ON_HANDLE_CONTEXT 更早触发
        self.handlers[Event.ON_RECEIVE_MESSAGE] = self.on_receive_message
        # 添加装饰回复的处理器，处理特殊字符和格式问题
        self.handlers[Event.ON_DECORATE_REPLY] = self.on_decorate_reply
        # 添加监控发送回复的处理器，诊断发送问题
        self.handlers[Event.ON_SEND_REPLY] = self.on_send_reply
        
        # 配置文件锁
        self._config_lock = threading.Lock()
        
        # 加载插件配置
        self._load_config()
    
    def _load_config(self):
        """加载配置文件，带并发控制"""
        with self._config_lock:
            try:
                curdir = os.path.dirname(__file__)
                config_path = os.path.join(curdir, "config.json")
                if os.path.exists(config_path):
                    with open(config_path, "r", encoding="utf-8") as f:
                        self.config = json.load(f)
                else:
                    self.config = {
                        "enabled": True,
                        "probability": 5,
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
                        json.dump(self.config, f, indent=4, ensure_ascii=False)
                
                # 确保配置中有protect_private_msgs字段
                if "protect_private_msgs" not in self.config:
                    self.config["protect_private_msgs"] = True
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(self.config, f, indent=4, ensure_ascii=False)
                    
                # 初始化关键词列表
                self.keyword_triggers = self.config.get("trigger_keywords", [])
                # 加载keyword插件的关键词
                self.load_keyword_triggers_from_config()
                    
                logger.info(f"[RandomReply] 插件配置加载成功: {self.config}")
            except Exception as e:
                logger.warning(f"[RandomReply] 加载配置文件失败: {e}")
                self.config = {
                    "enabled": True,
                    "probability": 5,
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
            
            logger.info(f"[RandomReply] 插件已初始化，随机回复概率: {self.config.get('probability', 5)}, 私聊消息保护: {self.config.get('protect_private_msgs', True)}, 最小消息长度: {self.config.get('min_msg_length', 5)}, 最大消息长度: {self.config.get('max_msg_length', 100)}, 关键词数量: {len(self.keyword_triggers)}")
    
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
        """处理 ON_RECEIVE_MESSAGE 事件"""
        try:
            context = e_context["context"]
            
            # 检查消息是否为空
            if context is None:
                if DEBUG_MODE:
                    logger.debug("[RandomReply] 收到空上下文，跳过处理")
                return
    
            # 检查是否已经被随机回复插件触发过
            if context.get("random_reply_triggered", False):
                if DEBUG_MODE:
                    logger.debug("[RandomReply] 消息已被随机回复插件触发过，跳过处理")
                e_context.action = EventAction.CONTINUE
                return
    
            # 安全地检查是否是群聊消息
            is_group = context.get("isgroup", False)
            
            # 处理私聊消息
            if not is_group:
                # 检查是否启用私聊消息保护
                if self.config.get("protect_private_msgs", True):
                    if DEBUG_MODE:
                        logger.debug("[RandomReply] 私聊消息保护已启用，跳过处理")
                    e_context.action = EventAction.CONTINUE
                    return
                else:
                    if DEBUG_MODE:
                        logger.debug("[RandomReply] 私聊消息保护已禁用，继续处理")
            else:
                if DEBUG_MODE:
                    logger.debug("[RandomReply] 群聊消息，继续处理")
                
            # 确保消息类型存在并且是文本消息
            if not hasattr(context, 'type') or context.type is None or context.type != ContextType.TEXT:
                if DEBUG_MODE:
                    logger.debug("[RandomReply] 不是文本消息，跳过处理")
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
            
            # 检查关键词触发
            keyword_triggered = self._check_keyword_match(cleaned_content)
            
            # 只有在非关键词触发的情况下才检查消息长度
            if not keyword_triggered and not self._check_message_length(cleaned_content):
                e_context.action = EventAction.CONTINUE
                return
            
            if not self.config.get("enabled", True):
                if DEBUG_MODE:
                    logger.debug("[RandomReply] 插件已禁用，跳过处理")
                e_context.action = EventAction.CONTINUE
                return
            
            # 安全地获取消息对象
            msg = context.get("msg")
            if not msg:
                logger.warning("[RandomReply] 消息对象为空，跳过处理")
                e_context.action = EventAction.CONTINUE
                return
                
            # 检查必要的属性是否存在
            required_attrs = ['actual_user_nickname', 'other_user_nickname', 'other_user_id', 'actual_user_id']
            for attr in required_attrs:
                if not hasattr(msg, attr) or getattr(msg, attr) is None:
                    logger.warning(f"[RandomReply] 消息缺少关键属性 {attr}，跳过处理")
                    e_context.action = EventAction.CONTINUE
                    return
                
            try:
                if DEBUG_MODE:
                    logger.debug(f"[RandomReply] 收到消息: content='{content}', from='{msg.actual_user_nickname}', group='{msg.other_user_nickname}'")
            except Exception as e:
                logger.warning(f"[RandomReply] 无法获取消息详情: {e}")
                e_context.action = EventAction.CONTINUE
                return
                                
            group_id = msg.other_user_id
            user_id = msg.actual_user_id
            
            # 检查黑名单
            if self._check_blacklist(group_id, user_id):
                e_context.action = EventAction.CONTINUE
                return
            
            # 检查前缀匹配
            if self._check_prefix_match(content):
                e_context.action = EventAction.CONTINUE
                return
                
            # 检查是否被@
            if hasattr(msg, 'is_at') and msg.is_at:
                if DEBUG_MODE:
                    logger.debug("[RandomReply] 消息含有@，跳过随机判断")
                e_context.action = EventAction.CONTINUE
                return
                
            # 输出一些调试信息
            if DEBUG_MODE:
                logger.debug(f"[RandomReply] 开始随机判断: content='{content}'")
                
            # 获取配置的随机回复概率（0-1000）
            probability = self.config.get("probability", 0)  # 默认为0
            if probability < 0:
                probability = 0
            elif probability > 1000:
                probability = 1000
                
            # 如果匹配关键词则直接触发，否则根据概率决定是否回复
            if keyword_triggered or probability == 1000 or (probability > 0 and random.randint(1, 1000) <= probability):
                # 记录触发原因
                if keyword_triggered:
                    logger.info(f"[RandomReply] 关键词触发成功！匹配方式: {'完全匹配' if cleaned_content == content.strip() else '首词匹配'}")
                else:
                    logger.info(f"[RandomReply] 随机触发成功！概率: {probability/10}%")
                
                try:
                    # 使用原始的ChatChannel处理流程
                    from channel.chat_channel import ChatChannel
                    from bridge.context import Context
                    
                    # 确保使用正确的GeWeChatChannel实例
                    from channel.gewechat.gewechat_channel import GeWeChatChannel
                    
                    # 获取当前的channel实例
                    gewechat_channel = self._check_channel_type(context.kwargs.get('channel', GeWeChatChannel()))
                    
                    # 创建一个新的Context对象
                    new_context = Context(ContextType.TEXT)
                    new_context.content = content
                    
                    # 确保正确复制群聊信息和用户信息
                    new_context["session_id"] = msg.other_user_id    # 群组ID
                    new_context["receiver"] = msg.other_user_id      # 接收者为群组
                    new_context["group_name"] = msg.other_user_nickname
                    new_context["user_id"] = msg.actual_user_id      # 实际发送者ID
                    new_context["user_nickname"] = msg.actual_user_nickname  # 发送者昵称
                    new_context["isgroup"] = is_group  # 添加群聊标记
                    
                    # 复制原始上下文的关键属性
                    for key in context.kwargs:
                        if key not in ["session_id", "receiver", "group_name", "user_id", "user_nickname", "isgroup"]:
                            new_context[key] = context[key]
                    
                    # 添加前缀匹配标记，绕过前缀检查
                    new_context["content_prefix_matched"] = True
                    
                    # 重要：添加标记表明这是AI需要实际回应的消息
                    new_context["need_reply"] = True
                    
                    # 添加标记，表示这是随机触发的消息
                    new_context["random_reply_triggered"] = True
                    
                    # 记录请求的关键信息
                    if DEBUG_MODE:
                        logger.debug(f"[RandomReply] 将消息'{content}'作为需要AI回复的上下文提交处理")
                        logger.debug(f"[RandomReply] 消息信息: 用户={msg.actual_user_nickname}({msg.actual_user_id}), 群组={msg.other_user_nickname}({msg.other_user_id}), 类型={'群聊' if is_group else '私聊'}")
                    
                    # 设置超时处理
                    import threading
                    
                    def timeout_handler():
                        logger.warning("[RandomReply] 请求处理超时，可能需要检查服务状态")
                    
                    timer = threading.Timer(30.0, timeout_handler)
                    timer.daemon = True
                    timer.start()
                    
                    try:
                        # 通过produce方法将上下文发送给channel处理
                        gewechat_channel.produce(new_context)
                        if DEBUG_MODE:
                            logger.debug("[RandomReply] 已成功提交上下文进行处理")
                        
                        # 请求开始处理，取消定时器
                        timer.cancel()
                        
                        # 中断原始消息的处理链
                        e_context.action = EventAction.BREAK
                        return
                    except Exception as e:
                        logger.error(f"[RandomReply] 提交请求时发生错误: {e}")
                        timer.cancel()
                        e_context.action = EventAction.CONTINUE
                except Exception as e:
                    logger.error(f"[RandomReply] 创建和处理新上下文失败: {e}")
                    import traceback
                    logger.error(f"[RandomReply] 异常详情: {traceback.format_exc()}")
                    e_context.action = EventAction.CONTINUE
            else:
                # 不处理该消息
                if DEBUG_MODE:
                    logger.debug(f"[RandomReply] 随机触发失败，跳过此消息。概率: {probability/10}%")
                e_context.action = EventAction.CONTINUE
                
        except Exception as e:
            logger.error(f"[RandomReply] 处理消息时发生错误: {e}")
            e_context.action = EventAction.CONTINUE
            
        return

    def on_decorate_reply(self, e_context: EventContext):
        """处理 ON_DECORATE_REPLY 事件，在回复被发送前处理格式"""
        try:
            reply = e_context["reply"]
            context = e_context["context"]
            
            # 记录回复对象的详细信息，便于调试
            if DEBUG_MODE and reply and hasattr(reply, 'type') and hasattr(reply, 'content'):
                logger.debug(f"[RandomReply] on_decorate_reply处理的回复: type={reply.type}, content_len={len(reply.content) if reply.content else 0}, content='{reply.content}'")
                
                # 检查上下文的用户ID和群组ID
                user_id = context.get("user_id")
                session_id = context.get("session_id")
                user_nickname = context.get("user_nickname")
                group_name = context.get("group_name")
                
                if user_id and session_id:
                    logger.debug(f"[RandomReply] 回复关联: 用户={user_nickname}({user_id}), 群组={group_name}({session_id})")
                
            # 检查上下文中的channel信息
            if context and "channel" in context:
                channel = context["channel"]
                if DEBUG_MODE:
                    logger.debug(f"[RandomReply] on_decorate_reply处理的上下文channel: {type(channel).__name__}")
                
                # 检查channel类型
                channel = self._check_channel_type(channel)
                context["channel"] = channel
            
            # 检查是否是我们的随机回复消息
            if context and context.get("random_reply_triggered", False):
                # 确保用户ID存在，用于正确关联回复
                if "user_id" not in context and "msg" in context:
                    msg = context["msg"]
                    if hasattr(msg, "actual_user_id"):
                        context["user_id"] = msg.actual_user_id
                        if DEBUG_MODE:
                            logger.debug(f"[RandomReply] 补充用户ID: {msg.actual_user_id}")
                    
                # 处理回复内容
                reply = self._process_reply(reply)
                e_context["reply"] = reply
                
                # 记录处理前后的变化
                if DEBUG_MODE and reply and hasattr(reply, 'content'):
                    logger.debug(f"[RandomReply] 处理后的回复内容: '{reply.content}'")
            
            # 尝试检查gewechat_channel最终发送的消息内容
            try:
                if DEBUG_MODE and "channel" in context and reply and reply.type == ReplyType.TEXT:
                    logger.debug(f"[RandomReply] 即将发送的消息内容: '{reply.content}'")
                    
                    # 尝试检查接收者信息
                    receiver = context.get("receiver")
                    user_id = context.get("user_id")
                    if receiver:
                        logger.debug(f"[RandomReply] 消息接收者: {receiver}, 关联用户ID: {user_id}")
            except Exception as send_check_error:
                logger.warning(f"[RandomReply] 检查发送信息时出错: {send_check_error}")
            
            return
        except Exception as e:
            logger.error(f"[RandomReply] 处理回复时出错: {e}")
            import traceback
            logger.error(f"[RandomReply] 处理回复异常详情: {traceback.format_exc()}")
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

    def _check_channel_type(self, channel):
        """检查channel类型并返回正确的channel实例"""
        try:
            from channel.gewechat.gewechat_channel import GeWeChatChannel
            if not str(type(channel).__name__).lower().endswith('gewechatchannel'):
                logger.warning(f"[RandomReply] 上下文中的channel不是GeWeChatChannel，尝试修正")
                return GeWeChatChannel()
            return channel
        except Exception as e:
            logger.error(f"[RandomReply] 检查channel类型时出错: {e}")
            return channel
    
    def _check_keyword_match(self, content):
        """优化后的关键词匹配算法"""
        if not self.keyword_triggers or not content:
            return False
            
        # 使用集合存储关键词，提高查找效率
        keyword_set = set(self.keyword_triggers)
        
        # 完全匹配检查
        if content in keyword_set:
            if DEBUG_MODE:
                logger.debug(f"[RandomReply] 检测到完全匹配的触发关键词: '{content}'，自动回复")
            return True
            
        # 首词匹配检查
        if " " in content:
            first_word = content.split(" ", 1)[0]
            if first_word in keyword_set:
                if DEBUG_MODE:
                    logger.debug(f"[RandomReply] 检测到第一个词匹配触发关键词: '{first_word}'，自动回复")
                return True
                
        return False
    
    def _check_blacklist(self, group_id, user_id):
        """检查黑名单"""
        blacklist_groups = self.config.get("blacklist_groups", [])
        blacklist_users = self.config.get("blacklist_users", [])
        
        if group_id in blacklist_groups:
            if DEBUG_MODE:
                logger.debug(f"[RandomReply] 群组 {group_id} 在黑名单中，跳过随机回复")
            return True
            
        if user_id in blacklist_users:
            if DEBUG_MODE:
                logger.debug(f"[RandomReply] 用户 {user_id} 在黑名单中，跳过随机回复")
            return True
            
        return False
    
    def _check_message_length(self, content):
        """检查消息长度"""
        min_msg_length = self.config.get("min_msg_length", 5)
        if len(content) < min_msg_length:
            if DEBUG_MODE:
                logger.debug(f"[RandomReply] 消息内容太短({len(content)}字符 < {min_msg_length}字符)，跳过处理")
            return False
        return True
    
    def _check_prefix_match(self, content):
        """检查前缀匹配"""
        group_chat_prefix = conf().get("group_chat_prefix", [])
        if not group_chat_prefix:
            return False
            
        valid_prefixes = [p for p in group_chat_prefix if p.strip() != ""]
        for prefix in valid_prefixes:
            if content.startswith(prefix):
                if DEBUG_MODE:
                    logger.debug(f"[RandomReply] 消息匹配前缀 '{prefix}'，跳过随机判断")
                return True
        return False
    
    def _process_reply(self, reply):
        """处理回复内容"""
        if not reply or not hasattr(reply, 'content'):
            return reply
            
        content = reply.content.strip()
        
        # 移除外层引号
        if (content.startswith('"') and content.endswith('"')) or \
           (content.startswith("'") and content.endswith("'")):
            content = content[1:-1].strip()
        
        # 限制长度
        max_msg_length = self.config.get("max_msg_length", 100)
        if len(content) > max_msg_length:
            content = content[:max_msg_length-3] + "..."
            
        reply.content = content
        return reply