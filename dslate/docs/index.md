## Philosophy

dslate is a command-line tool that sits on top of your git repository and provides a set of commands to help you manage your codebase. It is not a git extension, but rather a smart controller on top of git commands. The primary goal is to make it easier to work with git, and to let you focus on the code. 

dslate was built with a couple core principles in mind:

1. Every operation is atomic, commands will either succeed or fail as a whole. This means that if a command does not finish/succeed, no changes will be made to your repository.
2. The state of your repository will never change, rather only the history will be rewritten. 
3. the current state of a project is not the only thing that matters, the steps taken to get there are just as important.

## Why do you need this?

Many times, when working on a project, you will make a change, and then make another change, and then make another change, and so on. Now you can either make one big commit, or you can embark on the tedious process of making small commits. With large changes this can take hours, and be error prone. With dslate, you can go grab a drink, and once you come back it will automatically be done for you. Focus on the code, and let dslate handle the rest.

## How it works
In the background, dslate essentially cuts up your changes into small pieces, where each piece is a logical unit of work. To do this, it not only analzes your code structure, but also uses AI to understand high level logical relationships between your files. For example, if you have documentation, tests, and source code, dslate will understand that they are all related, and will try to keep them together. 

Finally, it will create a new commit for each of those pieces with a clear commit message, and rewrite your history to reflect these changes, all without any manual intervention.