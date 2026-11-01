# Manifest v1 与生成器

生成器只做数据校验、词典提取与模板组装；OCR、题目排除、难句语义分析、图片选择由调用 Skill 的 Codex 在生成前完成。需要 Python 3.10+，无第三方包。最终 HTML 无外部依赖。

JSON 顶层字段：

| 字段 | 说明 |
| --- | --- |
| schemaVersion | 固定整数 1 |
| title / titleOrigin | 英文标题；`original` 原标题或 `editorial` 拟题 |
| subtitle / intro / topic | 中文副标题（可空）、新增简短导语、主题标签 |
| source | `{label, url?}`，原文来源/用户提供/原创示例的真实说明 |
| level | 默认 `考研`，用户指定优先 |
| paragraphs | `[{id: "p1", text: "完整原段落", translation?: "对应中文译文"}, ...]`，ID 唯一且稳定；用户要求全文翻译时为每段提供 translation，长按段落展示浮层，松开保持显示；点击浮层外、关闭按钮或 Escape 关闭；键盘可聚焦段落后按空格 |
| analyses | 按原文顺序排列的难句，可以 `[]` |
| images | `{cover: Image, body: Image}`，文件相对于 manifest 目录 |
| styleSelection | 下述风格候选或沿用选择 |
| context | 可选 `{p1: {word: "该段语境义"}}`，键为小写原词或原形 |
| uiTranslations | 可选 `{title, subtitle, intro}` 中文译文；封面与正文默认显示英文，长按对应内容显示译文 |
| mobileUrl | 可选局域网阅读 URL，由 `scripts/serve.py` 写入；封面 Read on phone 弹窗使用内置二维码库生成二维码 |

Image：`{path, alt, credit, kind, origin, caption?, sourceUrl?, position?, overlaySafe?}`。

- `kind` 是 `photo/illustration/diagram`；`origin` 是 `generated/sourced/user`。
- sourced 必须有 `http(s)` 来源 URL 与署名。生成图 credit 简述概念插画，程序自动加“AI 生成”。
- `position` 默认 `50% 50%`，允许 0–100 的百分比调整主体焦点。
- cinema 的 `overlaySafe` 只有检查叠字可读、不挡主体后设为 true。

风格 ID：`warm/cinema/modern/newspaper/gallery/science/bright`。

```json
{"styleSelection":{"candidates":[
  {"id":"warm","rank":"best","layoutSuitable":true,"reason":"温和的心理说明，照片适合竖向裁切"},
  {"id":"gallery","rank":"usable","layoutSuitable":true,"reason":"文化主题可用，但本文更偏日常说明"}
]}}
```

仅在 best 且 layoutSuitable 的候选均匀随机，其他不参与。缺少可靠候选时 warm 回退。局部编辑已有成品时提供 `{"styleSelection":{"selected":"warm","reason":"沿用原成品风格"}}`。`--style` 仅用于用户明确指定或开发验证模板，不能代替自动判断。

每个 Analysis：

```text
id: S01                       # 从 S01 按原文连续编号
paragraph: p2
start: 0                      # 在 paragraph.text 内的位置
end: 153                      # 左闭右开，Python Unicode 码点数
text: 完整原句                 # 必须逐字符等于段落切片
tags: [让步从句, 嵌套修饰]
reason: 明确的结构难点与误读风险（仅内部校验，不显示）
translation: 完整中文译文
backbone: {en: 英文主干, zh: 中文解释与指代}
key: 白话阅读路径
segments: [{start, end, role, label}, ...]   # 相对于原句，role=main/clause/modifier
blocks: [{start, end, title, meaning, explanation, children?: [Block, ...]}, ...]
readingPath: 连起来理解的概括
restoration?: 只在需要时提供的语序还原
```

位置统一按 Python `len(text)`，不按 JavaScript UTF-16 字符索引。`segments` 为一个展示层，按序不重叠，可以留下标点空白；blocks 可以嵌套，子块范围须在父块内，同级不可重叠。不要根据译文长度切英文结构。生成器会拒绝错位、乱序、重复 ID、不完整解析与无效来源链接；不能以通过程序校验代替语义核对。

调用方法见 SKILL.md。成功返回输出绝对路径、大小、模板 ID、词典覆盖数、未匹配词及难句数。保留 manifest 与生成报告方便局部修改；向读者只交付 HTML。输出已有文件默认拒绝覆盖。

词形以 ECDICT exchange 中的原形及变化形式为依据，不以盲目去掉 -s/-ed/-ing 猜词。通用释义保留原词条内容，缺音标/词性时省略相应字段；查不到显示“词典未收录”。词条数据、语境义、原文均转义；禁止把未经转义的编辑内容插入脚本或 HTML。
