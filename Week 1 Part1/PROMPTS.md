# Prompt Design Documentation

This document explains how the prompts in `prompts.py` were designed and why.

## 1. System Prompt Design

Each mode has its own system prompt, passed to Gemini via `system_instruction`. A system prompt sets the model's permanent role and rules, while the user's pasted text is the only thing sent as the message. This separation keeps instructions consistent and makes it harder for the pasted text to change the model's behaviour.

Every prompt follows the same four-part structure:

| Part | Purpose | Example |
|------|---------|---------|
| **Role** | Sets expertise and tone | "You are a professional business-writing editor." |
| **Task** | States the goal in one sentence | "Rewrite the user's text in a formal tone." |
| **Rules** | Numbered, specific constraints | "Keep names, dates and numbers unchanged." |
| **Output format** | Controls the shape of the reply | "Return ONLY the rewritten text." |

## 2. Few-Shot Prompting

Few-shot prompting means showing the model a few examples of the desired input and output instead of only describing the task. `REWRITE_FORMAL_PROMPT` contains two examples:

**Example 1: workplace announcement**

```
Input:  hey team, just wanna let u know the server's gonna be down tmrw night for maintenance, so pls save ur stuff before 6. thx!
Output: Dear Team, I would like to inform you that the server will be unavailable tomorrow evening due to scheduled maintenance. Please ensure that all of your work is saved before 6:00 PM. Thank you for your cooperation.
```

**Example 2: request to a professor**

```
Input:  Hi prof, i couldnt finish the assignment cuz i was sick. can u give me more time? sorry!!
Output: Dear Professor, I regret to inform you that I was unable to complete the assignment by the deadline because I was unwell. I would be grateful if you could grant me an extension. I sincerely apologize for any inconvenience this may cause. Thank you for your understanding.
```

The two examples were chosen to be different (an announcement and a request/apology) so the model learns the general style rather than copying one pattern. Both keep all facts intact, expand abbreviations, add a greeting and closing, and contain no extra commentary.

## 3. Why the Prompts Were Written This Way

- **Numbered rules** are easy for the model to follow and easy for a reviewer to check.
- **"Return ONLY ..."** prevents replies like "Sure! Here is your summary:", which would be annoying in a CLI tool.
- **"Do not add new facts"** reduces hallucination, which matters most when rewriting or summarizing someone else's text.
- **Length limits** (3-5 sentences, under 150 words) make outputs predictable and cheap in tokens.
- **Analogy requirement** in Explain Simple forces concrete, beginner-friendly explanations.
- **Different temperatures** per mode: 0.3 for Summarize (faithful), 0.4 for Rewrite Formal (consistent style), 0.6 for Explain Simple (more creative analogies).

## 4. Prompt Engineering Strategy

1. **Start simple.** Write a clear role and task.
2. **Add constraints** where the first outputs went wrong (too long, chatty, invented facts).
3. **Add examples** when the task is about style, because style is easier to show than describe. That is why only Rewrite Formal uses few-shot.
4. **Keep prompts separate from code** (`prompts.py`) so they can be tested and improved independently.
5. **Measure.** Token logging shows the cost of longer prompts; few-shot examples increase input tokens but improve consistency (see `COMPARISON.md`).

## 5. Benefits of Each Prompt

| Prompt | Main benefit | Key technique |
|--------|--------------|---------------|
| `SUMMARIZE_PROMPT` | Short, faithful, opinion-free summaries | Role + length limit + no-new-info rule |
| `REWRITE_FORMAL_PROMPT` | Consistent professional tone and structure; meaning preserved | Few-shot examples + rules |
| `EXPLAIN_SIMPLE_PROMPT` | Beginner-friendly explanations with an analogy | Audience targeting + analogy rule + word limit |

## Example: Explain Simple

```
Input:  Photosynthesis is the process by which plants convert light energy into chemical energy stored in glucose.
Output: Plants make their own food using sunlight. Think of a leaf like a tiny kitchen that uses sunlight instead of a stove. It mixes water, air and light to cook up sugar, which gives the plant energy to grow. That cooking process is called photosynthesis.
```

*(Illustrative output; actual wording will vary.)*
