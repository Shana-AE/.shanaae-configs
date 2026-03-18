# OpenCode Global Rules

## English Practice

- You must always answer me in English and when some sentences are long and difficult to understand or some words are not commonly used, annotate them in Chinese 请用英文回答我，如果有长难句或不常用的单词，用中文注释
- 列出难于大学英语六级的单词

## Git Pull for Context

When you need to better understand a library, tool, or framework to assist the user:

1. **Clone the Repository**: You are encouraged to pull the corresponding git repository to `~/.ai-git-pulls`.
2. **Analyze Source Code**: Read the source code, README, and documentation in the cloned repository to gain a deeper understanding of its functionality, API, and usage patterns.
3. **Use Context**: Apply the knowledge gained from the source code to the user's task.

## Learning and Study

- Explain the thought processing of the problem 解释一下解题思路
 concepts and ideas 突出重点概念和- Highlight the key思想
- List the key concepts and ideas 列出重点概念和思想
- Ask me whether to save the list to obsidian 询问我是否把这个清单保存到obsidian

## Save to Eudic

When the user asks to save words to Eudic (欧路词典):

1. **Identify Words**: Extract the list of English words to be saved from the context.
2. **Check Token**: Verify if `EUDIC_TOKEN` is set in the environment.
    - If not, ask the user to provide it or set it via `export EUDIC_TOKEN='...'`.
    - Tell the user they can get the token from: <https://my.eudic.net/OpenAPI/Authorization>

## Save to Obsidian

- If save to obsidian save file under /Inbox/ai-skills 如果保存到obsidian，保存在 /Inbox/ai-skills

## MCP Tools Usage

- Use `context7` tools when you need to search documentation
- Use `Git` tools for git operations
- Use `Filesystem` tools for file operations
- Use `Sequential Thinking` tools for complex problem solving
