# Hold-out test log

`sample_questions.json` (37 questions) was used while building, so its pass rate shows the system works on the
cases it was tuned for. To check generalization, 12 new questions (`holdout_questions.json`) were written after
development and run once before any fix.

## First run (offline pipeline, 4 Nov 2026): 8 of 12 passed

| ID | Question | Problem | Fix |
|---|---|---|---|
| H2 | Is there any charge if I withdraw from HDFC ELSS early? | "withdraw early" wasn't recognized as exit load, so it asked for clarification | Added early-withdrawal phrasings to the exit-load topic |
| H7 | Can I call someone to get my HDFC MF statement? | "statement" alone wasn't a service topic, so it was out of scope | Plain "statement" now maps to account statements |
| H9 | Will HDFC Flexi Cap NAV go up next month? | Prediction wording not caught, so it was answered as "not found" instead of a refusal | Added "go up/down, next month, will ... increase" to performance detection |
| H10 | What's the exit load? | Treated as a definition question; it is a scheme fact with no scheme | "the exit load / the expense ratio ..." without a scheme now asks which scheme |

## After fixes: 12 of 12 passed; full test suite and the 37-question set still pass.

These results were produced by actually running the code. The hold-out set is now also tuned, so it no longer measures
generalization; a fresh set would be needed for that.
