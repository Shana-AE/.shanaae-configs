---
name: maimemo-daily-story
description: "MaiMemo (墨墨背单词) daily vocabulary story generator. Fetch today's study words from MaiMemo Open API, generate a bilingual English story with collapsible Chinese translations, and save to Obsidian. Triggers on: 墨墨, maimemo, 背单词, daily vocabulary, vocabulary story, word article, 生成文章, 今日单词. Requires MAIMEMO_TOKEN environment variable and obsidian CLI."
---

# MaiMemo Daily Story Generator

Generate bilingual vocabulary stories from MaiMemo daily study data and save to Obsidian.

## Prerequisites

- **memo-api skill** — Use for fetching MaiMemo study data (words, progress, etc.)
- `MAIMEMO_TOKEN` — Required by memo-api. Get from MaiMemo app: 我的 → 更多设置 → 实验功能 → 开放 API
- `obsidian` CLI — Obsidian must be running. See: https://help.obsidian.md/cli
- Optional env vars (support `{YYYY}`, `{YY}`, `{MM}`, `{DD}` date placeholders):
  - `MAIMEMO_OBSIDIAN_PATH` — Directory path template (default: `Inbox/ai-skills/english-learning/{YYYY}/{MM}`)
  - `MAIMEMO_FILE_TEMPLATE` — File name template (default: `MaiMemo Daily Story - {YYYY}-{MM}-{DD}.md`)

> **Date placeholders**: `{YYYY}`=2026, `{YY}`=26, `{MM}`=04, `{DD}`=16. Full path example: `Inbox/ai-skills/english-learning/2026/04/MaiMemo Daily Story - 2026-04-16.md`

## Workflow

### 1. Fetch Today's Words

Load the **memo-api** skill, then use `get_study_progress` and `get_today_items` endpoints to get today's word lists. Categorize by `first_response` field:

- `FORGET` → highest priority targets
- `VAGUE` → secondary targets
- `FAMILIAR` → selectively use hard/rare ones

> **Note**: This skill assumes you have set up the **memo-api** skill and have the required environment variables set. if you haven't install memo-api skill, you can install it by running `npx skills add maimemo/memo-skills`.
> **Note**: MaiMemo's day starts at **4:00 AM Beijing time** (UTC+8). If current time is between 00:00-4:00 Beijing time, use yesterday's date for file naming.

### 2. Generate Article

Using the word list from step 1, generate an English story that:

- **FORGET words**: Highest priority targets, always bolded with `**word**` 🗑️ marker — these are words you completely forgot
- **VAGUE words**: Secondary targets, always bolded with `**word**` — these are words you vaguely remembered
- **FAMILIAR words**: Selectively include hard/rare familiar words (above CET-6 or with tricky usage) — also bolded and annotated in Word Notes. Common familiar words used naturally without bold.
- Uses collapsible callout blocks for Chinese translations:
  ```
  English paragraph here with **vague_word** and **forget_word** 🗑️.

  > [!quote]- 中文翻译
  > 中文翻译段落，目标词用加粗标注。🗑️ 标记的为忘记的词。
  ```
- After each story section, adds **Word Notes** for ALL target words in that section

#### Word Notes Format

After each story section, include a `> [!note]- Word Notes` callout annotating **every** FORGET, VAGUE, and selected hard FAMILIAR word from that section:

```
> [!note]- 📖 Word Notes
> **word** /wɜːrd/
> - **Meaning**: 中文释义
> - **Usage note**: Register (formal/informal/academic), collocation tips
> - **Common contexts**: Where you'll encounter this word (e.g., news, academic writing, daily conversation)
> - **Example**: A short example sentence different from the story
> - **Confusable**: Similar words that are easily confused (e.g., *affect* vs *effect*)
> - **Memory tip**: A mnemonic or association to help remember
```

Priority for Word Notes:
1. FORGET words — always include
2. VAGUE words — always include
3. Hard FAMILIAR words — above CET-6, rare register, or commonly confused

### 3. Article Structure

```
---
date: YYYY-MM-DD
tags:
  - maimemo
  - vocabulary
  - english-learning
vague_count: N
forget_count: N
familiar_count: N
---

# MaiMemo Daily Story — YYYY-MM-DD

> [!info] 📊 Today's Review Summary
> - **Studied**: N words | **Time**: N min
> - 🗑️ **Forgot**: N words — **converge, converse, countenance**
> - 🌀 **Vague**: N words — **bleak, colossal, connoisseur, ...**
> - ✅ **Familiar**: N words

## Part 1: [Section Title]

English paragraph with **vague_word** and **forget_word** 🗑️.

Another paragraph weaving in more target vocabulary naturally.

> [!quote]- 中文翻译
> 中文翻译段落。

> [!note]- 📖 Word Notes
> (Detailed notes for 2-3 key words from this section)

## Part 2–6: ...

(Repeat pattern for 5-6 sections, embedding all FORGET and VAGUE words)

## 🗑️ Forget Words Review

> [!danger] These words were completely forgotten — review them carefully!
>
> | Word | Meaning | Quick Tip |
> |------|---------|-----------|
> | converge | ... | ... |
> | converse | ... | ... |
> | countenance | ... | ... |

## 📚 Vocabulary Table

| Word | POS | Meaning | Register | Key Collocation |
|------|-----|---------|----------|-----------------|
| ... | ... | ... | formal/neutral/informal | ... |

(Include all FORGET + up to 25 hardest VAGUE words)

## 💡 Review Tips

> [!tip] Review Strategy
> - 🗑️ **FORGET words**: Review immediately, create separate mnemonics
> - 🌀 **VAGUE words**: Re-read the story sections focusing on bolded words
> - Try to recall the story context when you see these words again
> - Pay attention to **register** (formal vs informal) — using a formal word casually sounds unnatural
```

### 4. Save to Obsidian

Use the helper script (reads from file or stdin):

```bash
python3 scripts/maimemo_story.py save --file /tmp/article.md
python3 scripts/maimemo_story.py save --file /tmp/article.md --date 2026-04-14
```

Or directly via `obsidian` CLI:

```bash
obsidian create path="Inbox/ai-skills/english-learning/2026/04/MaiMemo Daily Story - 2026-04-16.md" content="$(cat /tmp/maimemo-story.md)" silent overwrite
```

### 5. Cleanup (Optional)

```bash
python3 scripts/maimemo_story.py delete "Inbox/ai-skills/english-learning/2026/04/MaiMemo Daily Story - 2026-04-14.md"
# Or directly:
obsidian trash path="Inbox/ai-skills/english-learning/2026/04/MaiMemo Daily Story - 2026-04-14.md"
```

## Complete One-Shot Example

1. Load **memo-api** skill to get today's words via API
2. Generate article based on word lists (Claude generates content)
3. Save to Obsidian:
   ```bash
   # Write article to temp file, then save
   python3 scripts/maimemo_story.py save --file /tmp/maimemo-story.md
   ```

## Key Concepts

- **FORGET words** (忘记 🗑️): **Highest priority** — you completely forgot these. Always bolded + 🗑️ marker. Include in dedicated review section and every Word Notes opportunity.
- **VAGUE words** (模糊 🌀): Secondary targets, always bolded. These need reinforcement through context.
- **FAMILIAR words** (认识 ✅): Selectively annotate hard/rare ones. Common ones used naturally without bold.
- **Word Notes**: Detailed annotations for target words — includes meaning, register, collocations, confusables, and memory tips
- **Register**: Indicates formality level — academic, formal, neutral, informal, slang. Crucial for natural English.
- **Collocations**: Words that naturally go together (e.g., "heavy rain" not "strong rain")
- **Collapsible callouts**: `[!quote]-` for Chinese, `[!note]-` for word notes
- **MaiMemo day boundary**: 4:00 AM Beijing time (UTC+8). Before 4AM = previous day.
