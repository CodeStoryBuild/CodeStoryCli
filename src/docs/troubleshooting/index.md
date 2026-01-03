# Troubleshooting & Tips

Codestory CLI (`cst`) is designed to make Git history management effortless. If you encounter unexpected behavior or want to refine how the tool analyzes your code, use the guide below.

## Common Issues

### 1. The AI grouped things incorrectly

If the `Logical Grouping` step doesn't align with your vision for the commit history:

- **Provide a descriptive hint**: Use `cst commit -m "Refactor the database layer"` to give the LLM specific context.

- **Adjust the grouping logic**: You can fine-tune the similarity threshold in your config to control how closely related changes must be to stay together.

### 2. Relevance Filtering: "It filtered changes I wanted to keep"

By default, Codestory CLI tries to focus on changes that match your current objective. 

- **Finding "Missing" Changes**: If you feel the tool is being too aggressive:

    1. Check your `relevance_filter_similarity_threshold` in `cst config`. Lowering this value allows more loosely related changes through.

    2. Disable relevance filtering for a specific run using `--relevance-filtering false` to see the full set of changes.

### 3. Syntax Error during commit

Codestory CLI will warn you if a file contains syntax errors (e.g., a missing bracket or typo) and perform a fallback semantic analysis. This ensures that the tool can still process your changes, even if the semantic map is incomplete.

- **Early Exit**: If `--fail-on-syntax-errors` is enabled, the tool will exit early upon detecting any syntax errors. This is useful for preventing the commit of broken code.

- **Ignoring Errors**: If you wish to ignore such errors and proceed with the fallback analysis, ensure that `--fail-on-syntax-errors` is disabled (it is disabled by default).

### 4. Secret Scanner False Positives

Codestory CLI scans your diffs to prevent sensitive data (like API keys) from accidentally entering your history.

- If it blocks a legitimate change, you can lower the sensitivity or disable it: `cst --secret-scanner-aggression none commit`.

- **Note**: It's always best practice to use a `.gitignore` file for truly sensitive files.

## Getting Help

If you run into a persistent issue:

1. **Enable Verbose Logging**: Run your command with the `-v` flag to see detailed internal logs.

2. **Check Your Configuration**: Run `cst config` to see all active settings and ensure there are no conflicting overrides.

3. **Community Support**: If you suspect a bug, please open an issue on GitHub with your verbose log output attached.
