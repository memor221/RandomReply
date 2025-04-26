# RandomReply 插件

dow（dify-on-wechat）项目插件，功能（不需要@bot）：随机回复消息、关键词直接调用插件、直接回复keyword配置的关键词

## 功能

- 当消息没有触发前缀或@机器人时，会根据设定的概率随机决定是否回复
- 支持设置关键词直接调用插件，不需要前缀或@机器人触发
- 支持自动从keyword插件配置中读取关键词进行回复
- 可以设置黑名单，对特定群组或用户不进行随机回复

## 安装

1. 使用管理员命令安装
```
#installp https://github.com/memor221/RandomReply.git
```
2. 扫描新插件
```
#scanp
```
3. 启用插件
```
#enablep RandomReply
```

## 配置说明

编辑 `plugins/random_reply/config.json` 文件，可以进行以下配置：

```json
{
    "enabled": true,                // 是否启用插件
    "protect_private_msgs": false,  // 是否关闭私聊启用插件
    "probability": 10,              // 随机回复概率，范围0-1000，10表示1%的概率
    "blacklist_groups": [],         // 随机回复群黑名单
    "blacklist_users": [],          // 随机回复用户黑名单
    "min_msg_length": 7,            // 触发随机回复的最小消息长度，小于此长度的消息会被跳过
    "max_msg_length": 10000,        // 随机回复处理的最大消息长度，超过此长度的消息会被截断
    "trigger_keywords": [],         // 插件的关键词，不需要@bot直接调用插件
    "use_keyword_plugin": false,    // 是否从keyword插件配置中加载关键词
    "excluded_keywords": []         // 从keyword插件中排除的关键词，这些关键词不会触发回复
}
```

### 关键词完全匹配说明

`trigger_keywords`列表中的关键词支持两种匹配方式：

1. **完全匹配**：消息内容完全等于关键词时触发

2. **首词匹配**：消息的第一个词等于关键词时触发
   - 如果消息包含空格，会检查第一个空格前的内容是否匹配关键词
   - 例如，关键词设置为"天气"，消息"天气 北京"将被触发
   - 首词匹配在完全匹配检查后进行，只有完全匹配失败时才会尝试首词匹配


### Keyword插件集成说明

RandomReply插件可以自动从Keyword插件的配置文件中加载关键词作为触发词：

1. **启用自动加载功能**
   - 设置`use_keyword_plugin: true`启用该功能
   - 插件会自动从`plugins/keyword/config.json`中读取所有关键词作为触发词

2. **过滤不需要的关键词**
   - 通过`excluded_keywords`列表可以指定哪些关键词不触发回复

3. **关键词优先级**
   - Keyword插件的关键词会与`trigger_keywords`中的关键词合并
   - 当消息匹配任何关键词时，都会100%触发回复
   - 如果同时在keyword插件中有对应回复内容，keyword插件的回复优先


## 使用方法

插件安装并启用后会自动运行，无需特殊命令触发。它会对没有使用前缀的群聊消息进行随机回复判断。

### 例

1. 消息："今天天气怎么样？"（无前缀，根据概率随机回复）
2. 消息："#help"（假设"#help"在trigger_keywords中，插件godcmd回复）
3. 消息："菜单"（假设从keyword插件加载的关键词，keyword关键词回复）

## 其他
本人不懂代码，插件完全由ai生成，勉强能用，分享给大家，如果有什么问题的话，还望见谅
![赞赏码](https://i.ibb.co/F4NM1Pg3/zsm.png)

