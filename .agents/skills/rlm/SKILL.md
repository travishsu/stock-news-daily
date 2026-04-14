---
name: rlm
description: "Process large codebases (>100 files) using the Recursive Language Model pattern. Orchestrates parallel sub-agents to map-reduce across files without context rot. Use when: analyzing large repositories; auditing security or auth across many files; finding patterns across 50+ files; processing large log files or data dumps"
license: MIT
metadata:
  author: ClawFu
  version: 2.1.0
  mcp-server: "@clawfu/mcp-skills"
---

# Recursive Language Model (RLM)

**"Context is an external resource, not a local variable."**

You are the **Root Node**. Your job is NOT to read code directly, but to orchestrate sub-agents that read code for you.

## The RLM Loop

### Phase 1: Index & Filter
Identify relevant files without loading them into context.

```bash
# Find candidate files
grep -rl "pattern" src/ --include="*.ts"
find . -name "*.py" -newer last_check
```

### Phase 2: Parallel Map
Split work into atomic units, spawn parallel agents.

- Launch **3-5+ agents** in parallel for broad tasks
- Give each agent **ONE specific file or chunk**
- Each agent returns a structured summary

**Model selection (重要，省 token)**：
- Leaf map 任務預設用 `model: "haiku"`：單檔摘要、抽取 endpoint/標的、情緒分類、逐字稿重點整理等「讀一份內容 → 吐結構化結果」的工作。
- 需要較深推理才升級 `model: "sonnet"`：跨段落因果推論、需要判斷矛盾、需要領域判斷（例如財報數字解讀）的單檔任務。
- `model: "opus"` 只保留給 Root node 的 Phase 3 reduce／跨來源交叉比對。不要在 map 階段用 Opus。

Example spawn（注意 `model` 參數）:
```
Agent({
  description: "Summarize routes.ts endpoints",
  model: "haiku",
  prompt: "Read src/api/routes.ts. List all endpoints with their auth decorators. Return as a markdown table."
})
Agent({
  description: "Summarize users.ts endpoints",
  model: "haiku",
  prompt: "Read src/api/users.ts. List all endpoints with their auth decorators. Return as a markdown table."
})
```

字幕／逐字稿範例（Market Digest 日報場景）：
```
Agent({
  description: "Summarize @kukantieh transcript",
  model: "haiku",
  prompt: "讀 subtitles/2026-04-14/kukantieh_XXX_zh-TW.txt。逐字稿是語音辨識產生的，有錯字照語意理解。輸出：3-5 個重點、提及的標的清單、市場情緒（偏多／偏空／中性）＋一句話理由。"
})
```

### Phase 3: Reduce & Synthesize
Collect all agent outputs, find patterns, compile into a coherent answer.

If incomplete, recurse: run a second RLM pass on the specific gaps.

## Critical Rules

1. **NEVER** read more than 3-5 files into your main context
2. **ALWAYS** use parallel agents when file count > 5
3. **Write Python scripts** for state tracking across 50+ files — let the script scan and summarize
4. If parallel agents are unavailable, fall back to iterative Python scripting
5. **Map 階段不要用 Opus**。Haiku 預設，Sonnet 例外，Opus 只留給 Root reduce。

## Example: "Find all API endpoints, check for Auth"

**Wrong** (monolithic): Read each file sequentially → context fills up, reasoning degrades.

**RLM Way**:
1. `grep -l "@Controller" src/**/*.ts` → 20 files
2. Spawn 20 agents, each extracts endpoints + auth status
3. Collect outputs, compile table, identify missing auth

## Output Format

Return a structured summary:
- **Findings table** (file, pattern, status)
- **Gaps identified** (what needs deeper investigation)
- **Confidence level** (how complete the scan was)

## Skill Boundaries

**Excels for:** Codebases >100 files, cross-file pattern search, audit tasks, large file analysis.

**Not ideal for:** Small projects (<50 files), single file analysis, file modification tasks.
