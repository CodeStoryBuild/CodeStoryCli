# How It Works

So, you’re curious about the magic behind the scenes? It starts with a simple concept: capturing your intent and transforming it into a clean history. Here is how Codestory analyzes your changes and prepares them for the world.

### 1. The "New State" Snapshot
First, we need to understand what you have changed. We create a temporary commit to reference as the "new state." This is specific to the commit command, but it serves as the anchor for our analysis. 
*   *Note: If we are simply fixing a previous commit, we skip this as we already have the necessary new state reference.*

### 2. Getting the Diff
Next, we get the difference by comparing the **Old Commit** vs. the **New Commit**. These are the raw changes you’ve made. If you are using the commit command, this is also where you can filter by specifying a target.

### 3. Mechanical Chunking
We take that diff and split it into the **smallest possible mechanically robust pieces**. 

You can think of this as the foundation for all other steps. If we can ensure that no matter what combination of these mechanical pieces we make (we can arbitrarily pick which pieces we want in any order, into any arbitrary groups), then all downstream steps can really do what they want with these fundamental building blocks.

**[Read here why and how we create the smallest possible mechanical chunks](./mechanical-chunking.md)**

### 4. Semantic Grouping
Next, we semantically group changes based on links in the code. You could imagine that if I modified a function, let's say `funcA`, I would want any usages of that function to be linked to it. Furthermore, I would want code in the same scope to stay together, otherwise I risk invalid syntax. 

Semantic grouping is what handles this by using a powerful tool called **tree-sitter**.

**[Learn more about how we peform semantic grouping](./semantic-grouping.md)**

### 5. Filtering (The Safety Net)
Now, before we proceed, we have a decision to make based on what mode we are in.

**If we are creating new commits:**
We might want to filter out unwanted changes—like things that expose `api_keys`, unwanted debug statements, etc. This can all be configured exactly as you like. We scan the current semantic groups, and if a filter matches, we reject the **entire** semantic group.
*   *Why the whole group? If we only rejected part of a group, then as mentioned before, we risk creating semantically invalid changes.*

**If we are fixing a past commit:**
We skip this step entirely. 
*   *Why? Well, if we try to exclude any changes but are fixing a past commit, then later commits might depend on those changes! Thus, we cannot be selective about which changes we want.*

**[Change filtering deep dive in progress...](#5-filtering-the-safety-net)**

### 6. Logical Grouping
Once we have our filtered semantic groups, we are almost ready to turn these changes into nice, clean commits. However, there is one step missing! 

Let's say I write an integration test for some new feature, and I have the feature code too. These changes might not be *semantically* related (e.g., I might be able to have valid code if I commit one but not the other), but they might be *logically* related!

Thus, we can run an optional final grouping step where we look for such logical changes to keep your history coherent.

**[How we use AI to create logical groups](./logical-grouping.md)**

### 7. Creating the History
Now, we finally have our groups for which we want to create individual commits. But actually applying them to the file system without breaking things?

**[Read here to see how we solve the "Impossible Commit" problem.](./commit-strategy.md)**
