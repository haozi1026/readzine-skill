# ReadZine Skill

把英语文章或文章截图制作成一个可离线分享的 HTML 阅读杂志，包含杂志封面、ECDICT 离线查词和中文长难句解析。

生成阶段由 Codex 完成编辑、分析和组装；生成后的 HTML 不需要模型、API Key 或服务器，直接用浏览器打开即可阅读和分享。

## 安装

需要：

- Codex 或其他兼容 [Agent Skills](https://agentskills.io/) 的智能体
- Python 3.10 或更高版本
- 首次生成时可访问网络，以下载 ECDICT 和取得或生成文章配图
- 可选：Node.js，用于交付前的 JavaScript 语法检查

在 macOS 或 Linux 上安装到 Codex 的个人 skills 目录：

```sh
git clone https://github.com/haozi1026/readzine-skill.git "${CODEX_HOME:-$HOME/.codex}/skills/readzine"
```

安装后新建一个 Codex 对话，让 Codex 使用 `$readzine`，并粘贴英文文章或附上文章截图。例如：

```text
使用 $readzine，把这篇英语文章做成可离线阅读的杂志 HTML：
<粘贴文章或附上截图>
```

更新：

```sh
git -C "${CODEX_HOME:-$HOME/.codex}/skills/readzine" pull --ff-only
```

## 产物

ReadZine 交付一个自包含的 `magazine.html`：

- 封面和正文图片已内嵌
- 本文所需 ECDICT 词条已内嵌
- 选词即可离线查词
- 难句解析、译文和阅读交互均在本地运行
- 可以把单个 HTML 文件直接发给他人

ECDICT 完整词库不会提交到本仓库。Skill 在首次使用时通过 `scripts/fetch_dictionary.py` 下载固定提交的 `ecdict.csv` 和对应 `LICENSE`，并校验文件完整性。

## 目录

```text
readzine/
├── SKILL.md
├── assets/          # 阅读器模板、样式、交互和二维码依赖
├── references/      # 编辑规则与 manifest 数据协议
└── scripts/         # 词典获取、HTML 构建、预览与交付验证
```

`assets/reader.html` 是源模板，不是可直接交付的阅读成品。

## 安全说明

Skill 会指导智能体读取用户提供的文章、获取图片、下载 ECDICT，并在本地运行仓库中的 Python 脚本。和使用任何第三方 Skill 一样，安装前应检查 `SKILL.md` 和脚本内容，并只授予完成当前任务所需的权限。

## 第三方组件

第三方组件及其许可证说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 许可证

ReadZine Skill 使用 [MIT License](LICENSE) 发布。

