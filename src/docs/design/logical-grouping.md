# Logical Grouping

### Why do we create logical groups?
As mentioned in the [How It Works](./how-it-works.md) page, there are some relations between changes that you simply cannot grasp using only semantics. 

For example, imagine you are writing documentation in Markdown (`.md`) for a new feature, while the actual code is written in Python (`.py`). These two files might not share variables or functions—meaning our semantic grouping engine won't see a link—but they are deeply related! To correctly create groups in these scenarios, we need to look at the **higher-level relation** between files. 

This is where we use **Large Language Models (LLMs)** to bridge the gap.

### Why Language Models? 
You might be wondering: what makes an LLM good at this specific task? To understand our approach, it helps to look at the difference between **Interpolation** and **Extrapolation**.

*   **Extrapolation (Prediction):** This is what you see when you ask an AI to write code for you. It takes a prompt and tries to predict or "invent" what you want. It is making a guess based on patterns.
*   **Interpolation (Analysis):** This is using existing data to draw a conclusion about that data.

When we use language models for logical grouping, we aren't asking them to invent anything. We are asking them to **summarize**.

At every point in time, the model has all the information it needs right in front of it: your current codebase state and your new changes. It doesn't need to make wild guesses about the relations between changes because the logic is defined right there in the diffs. By asking the model to analyze rather than generate, we get highly accurate logical groupings.

### A Note on Commit Messages
While the model is great at grouping, it does have to use some assumptions when generating the **commit messages** for those groups. This is never going to be perfect, as a perfect commit message often relies on intent or context that exists only in your head.

That is why you can always override the custom commit messages with your own. You can also add arguments to the command to ensure the model understands your specific intent with the changes.

### Supported Models
We currently support most major providers, as well as local options. You can also specify a custom baseurl for custom endpoints
Currently Supported Providers:
- Ollama
- Cohere
- OpenAI
- Google
- Cerebras
- XAI
- Nebius
- Hugging Face
- Together
- AWS
- Anthropic
- LMStudio
- Groq
- SambaNova
- WatsonX
- Inception
- Fireworks
- Azure
- Deepseek
- Mistral
