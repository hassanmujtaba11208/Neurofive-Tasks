# Comparison: Rewrite Formal WITHOUT vs WITH Few-Shot Prompting

This file compares the **Rewrite Formal** mode when the system prompt contains **no examples** (zero-shot) versus **two worked examples** (few-shot, the version used in `prompts.py`).

> **Note:** The outputs below are *representative samples* of typical model behaviour, not recorded API logs. Outputs vary between runs. To make this document fully authentic, run both prompt versions yourself and paste in the real results.

## The Two Prompts

| | Without Few-Shot | With Few-Shot |
|---|------------------|---------------|
| Role | "You are a professional business-writing editor." | Same |
| Task and rules | Rewrite formally, keep meaning | Same rules |
| Examples | None | Two input/output examples |
| Approx. extra input tokens | 0 | about 250 |

## Example 1: Meeting change

**Input:** `hey, the meeting got moved to 3pm cuz the boss is busy. dont be late!`

| | Output | Issues / Strengths |
|---|--------|--------------------|
| **Without few-shot** | "Here's a more formal version: *The meeting has been rescheduled to 3 PM because the boss is occupied. Please do not be late.*" | Adds an introduction; "the boss" is still casual; no greeting or closing |
| **With few-shot** | "Dear Team, Please be advised that the meeting has been rescheduled to 3:00 PM due to the manager's prior commitments. Kindly ensure that you arrive on time. Thank you." | Clean output only; formal register; greeting and closing; consistent with examples |

## Example 2: Late payment

**Input:** `sorry for the delay, i'll send the money by friday i promise`

| | Output | Issues / Strengths |
|---|--------|--------------------|
| **Without few-shot** | "Option 1: I apologize for the delay and will send the payment by Friday. Option 2: Please accept my apologies for the late payment; it will be sent by Friday." | Gives multiple options when one rewrite was requested |
| **With few-shot** | "Dear Sir/Madam, I sincerely apologize for the delay. I will ensure that the payment is sent by Friday. Thank you for your patience." | Single answer; polite and professional; keeps the Friday deadline |

## Example 3: Job application

**Input:** `hi, im interested in the dev job u posted. can i send my cv? thx`

| | Output | Issues / Strengths |
|---|--------|--------------------|
| **Without few-shot** | "Hello, I am interested in the developer position you posted. May I send my CV? Thank you." | Correct but plain; abbreviation "dev" handled, tone only mildly formal; no salutation structure |
| **With few-shot** | "Dear Hiring Manager, I am writing to express my interest in the Developer position that you recently advertised. I would be grateful for the opportunity to submit my CV for your consideration. Thank you for your time." | Fully professional structure matching the examples |

## Summary Table

| Criterion | Without Few-Shot | With Few-Shot |
|-----------|------------------|---------------|
| Extra commentary ("Here's a...") | Common | Rare |
| Multiple options instead of one answer | Sometimes | Rare |
| Greeting and closing | Inconsistent | Consistent |
| Formal vocabulary | Moderate | Strong |
| Meaning preserved | Usually | Usually |
| Consistency across runs | Lower | Higher |
| Input token cost | Lower | Higher (about 250 tokens) |

## Why Few-Shot Improves Results

1. **Showing beats telling.** "Formal" is subjective. Examples define exactly what formal means here: greeting, full sentences, polite closing.
2. **Format is locked in.** The model copies the structure of the examples, which removes introductions and multiple-option answers.
3. **Consistency.** Outputs vary less between runs because the model has concrete patterns to imitate.
4. **Less rule-writing.** Style rules that are hard to describe (tone, politeness level) are conveyed implicitly.
5. **Trade-off.** Examples add input tokens, so each request costs slightly more. For a style-sensitive task like this, the quality gain is worth it, and the token logging feature lets you measure the cost.
