## CodeStory CLI

The **CodeStory CLI** is likely the tool you will use most often as a developer. It contains the core functionality needed to create and maintain clean commit histories.  

The CLI does not replace Git commands. Instead, it allows you to focus on your work without worrying about Git semantics in 99% of cases.  

Using the CLI, you can:  
- Automatically create commits from your working directory, with configurable guardrails to avoid committing sensitive information or unwanted changes.  
- Fix previous commits by rewriting them into smaller, logical commits.  
- Automatically clean up your entire project history from start to finish.  

To ensure robustness, the CLI was built with a few core principles:  
1. **Atomic operations:** Commands either succeed or fail as a whole. If a command doesn’t complete successfully, no changes are made to your repository.  
2. **Preserve code state:** The final state of your code never changes; only the history is rewritten to show cleaner, logical steps.  

For more information, visit:  
- [CodeStory CLI Reference](reference/root.md)  
- [CodeStory Home](codestory.build)
