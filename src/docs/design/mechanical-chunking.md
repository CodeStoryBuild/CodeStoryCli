# Mechanical Grouping: The Foundation

Before we can do any of the fancy semantic analysis or intelligent grouping, we need to solve a fundamental problem with how Git sees the world. This step is the bedrock of our system.

### The "Hunk" Problem
In the world of Git, the most granular level you can manage changes with is called a **Hunk**.
*   [Read more about Git Hunks here](https://medium.com/@michotall95/hunk-in-git-f7b7855d47ae)

However, generic Git hunks are often not ideal when you want to create small, logical commits. 

**Why?**
Let's say you have created a new file with a dozen different functions inside it, or perhaps you have deleted a massive file that contained multiple features. To Git, the "hunk" for these changes is just one massive block—the entire file change.

Git is not able to split those changes any smaller by design. But for our system, we want to have granular changes that we can actually manipulate.

### Breaking it Down
To solve this, we take those massive Git hunks and split them into the **smallest possible mechanical pieces**, provided it is safe to do so.

Instead of one giant block representing a new file, we might split it into ten smaller blocks. By doing this, we gain the ability to arbitrarily pick and choose which pieces we want to group together later.

*Note: Based on your configuration, you can choose how aggressively you want us to try and break these down.*

### The Critical Rule: Pairwise Disjoint
When we split a hunk, we create smaller hunks that must themselves be valid. The most critical constraint we follow is that every hunk must be **pairwise disjoint**.

**What does this mean?**
It means that only one hunk can modify a specific range of lines in a file—and *only* that one. No two changes can ever fight over the same line of code.

We also have to be incredibly careful with how we manage added and removed lines to ensure that the sum of these small parts actually equals the original whole.

### The Guarantee
Why go through all this trouble?

By ensuring that these smaller hunks are valid and independent, we guarantee that **no matter how you order or combine these pieces**, they can be applied validly.

This mechanical robustness is what allows the rest of our system to work its magic without breaking your code.

*   [See how we re-assemble these pieces in the Commit Strategy](./commit-strategy.md)