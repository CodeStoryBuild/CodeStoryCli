## CodeStory Cli

CodeStory Cli is likely what you will use most often if you are a developer. It contains the core functionality you will need to create and maintain clean commit histories. Once again, the cli does not replace the git command, but rather allows you not have to worry about the semantics of git in 99% of cases.
Using the cli, you can: Automatically create commits out of your working directory, with configurable guardrails around things like not commitng sensitive information, or unwanted changes. Fix previous commits by rewriting them into smaller logical commits. Automatically clean up your entire history from start to end. To ensure robustness, the cli was built with a couple core principles in mind:
1. Every operation is atomic, commands will either succeed or fail as a whole. This means that if a command does not finish/succeed, no changes will be made to your repository.
2. The final state of your code will never change, rather the history will be rewritten to show cleaner steps of how you got there. 
For more information, visit:
[CodeStory Cli Reference](reference/root.md)
[CodeStory Home](codestory.build)