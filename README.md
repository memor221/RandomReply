# RandomReply 插件

dow（dify-on-wechat）项目插件，功能（不需要@bot）：随机回复消息、关键词直接调用插件、关键词直接回复keyword配置的回复

## 功能

- 在群聊中，当消息没有触发前缀或@机器人时，会根据设定的概率随机决定是否回复
- 支持设置关键词完全匹配功能，当消息内容完全等于关键词时会100%触发回复
- 支持自动从keyword插件配置中读取关键词，统一管理触发词
- 可以设置黑名单，对特定群组或用户不进行随机回复
- 概率可在配置文件中灵活调整

## 安装

1. 将插件文件夹 `random_reply` 复制到 `plugins` 目录下
2. 复制 `config.json.template` 为 `config.json` 并根据需要调整配置
3. 使用管理员命令 `#scanp` 扫描并加载新插件
4. 使用 `#enablep RandomReply` 启用插件

## 配置说明

编辑 `plugins/random_reply/config.json` 文件，可以进行以下配置：

```json
{
    "enabled": true,            // 是否启用插件
    "probability": 0.1,         // 随机回复概率，范围0-1，0.1表示10%的概率
    "blacklist_groups": [],     // 不进行随机回复的群组ID列表
    "blacklist_users": [],      // 不对其消息进行随机回复的用户ID列表
    "protect_private_msgs": true, // 是否保护私聊消息，确保私聊消息始终被正确处理
    "min_msg_length": 5,        // 触发随机回复的最小消息长度，小于此长度的消息会被跳过
    "max_msg_length": 100,      // 随机回复处理的最大消息长度，超过此长度的消息会被截断
    "trigger_keywords": [],     // 完全匹配的触发关键词列表，消息内容与关键词完全相同时会100%触发回复
    "use_keyword_plugin": false, // 是否从keyword插件配置中加载关键词
    "excluded_keywords": []     // 从keyword插件中排除的关键词，这些关键词不会触发随机回复
}
```

### 关键词完全匹配说明

`trigger_keywords`列表中的关键词支持两种匹配方式：

1. **完全匹配**：消息内容完全等于关键词时触发
   - 只有当消息内容**完全等于**关键词时才会触发（会忽略前后空白字符）
   - 例如，关键词设置为"帮助"，则只有消息内容为"帮助"时才会触发
   - 关键词对大小写敏感，"Help"和"help"被视为不同的关键词

2. **首词匹配**：消息的第一个词等于关键词时触发
   - 如果消息包含空格，会检查第一个空格前的内容是否匹配关键词
   - 例如，关键词设置为"天气"，消息"天气 北京"将被触发
   - 首词匹配在完全匹配检查后进行，只有完全匹配失败时才会尝试首词匹配

完全匹配和首词匹配都会100%触发机器人回复，无需依赖随机概率。

### Keyword插件集成说明

RandomReply插件可以自动从Keyword插件的配置文件中加载关键词作为触发词：

1. **启用自动加载功能**
   - 设置`use_keyword_plugin: true`启用该功能
   - 插件会自动从`plugins/keyword/config.json`中读取所有关键词作为触发词

2. **过滤不需要的关键词**
   - 通过`excluded_keywords`列表可以指定哪些关键词不触发随机回复

3. **关键词优先级**
   - Keyword插件的关键词会与`trigger_keywords`中的关键词合并
   - 当消息匹配任何关键词时，都会100%触发回复
   - 如果同时在keyword插件中有对应回复内容，keyword插件的回复优先

这种集成方式的好处是只需要在keyword插件中维护一份关键词列表，既可以让keyword插件返回固定回复，也可以让RandomReply插件触发AI回复，实现更灵活的交互。

## 使用方法

插件安装并启用后会自动运行，无需特殊命令触发。它会对没有使用前缀的群聊消息进行随机回复判断。

### 例

1. 消息："机器人 今天天气怎么样？"（使用前缀，100%触发回复）
2. 消息："今天天气怎么样？"（无前缀，根据概率随机回复）
3. 消息："#help"（假设"#help"在trigger_keywords中，100%触发回复）
4. 消息："菜单"（假设从keyword插件加载的关键词，100%触发回复）

## 其他
本人不懂代码，插件完全由ai生成，勉强能用，分享给大家，如果有什么问题的话，还望见谅
![赞赏码](https://i.ibb.co/F4NM1Pg3/zsm.png)

