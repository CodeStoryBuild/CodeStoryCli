# The Incremental Strategy

If you have read the [How It Works](./how-it-works.md) page, you know that we have successfully separated your changes into valid groups and now its time to turn those groups into a clean commit history.

Note that all the way back in our mechanical chunking step, we ensured that no matter how the changes inside these groups are structured, they will always be valid. So, it seems like we can just apply changes one by one, create a commit each time, and call it a day, right?

**It’s quite a bit more complicated than that.** If you try to do that, you will run into problems very early.

### The Problem: Overlapping Contexts
Let's take the following situation where I have two files, `A` and `B`, with two respective changes in each file (`A1`, `A2` and `B1`, `B2`).

Let's say for whatever reason we have decided to make groups `G1` and `G2` such that:
*   **G1** contains `A1` and `B2`
*   **G2** contains `A2` and `B1`

Note that each of these changes takes some part of the project from **Old State -> New State**.

**The Naive Approach Fail:**
1.  Let's say I choose to apply **G1** first. I apply `A1` to file `A` with no problem. Next, I apply `B2` to file `B`—no problem either (remember, each chunk is mechanically valid and independent). Now my files are in an **Intermediate State**.
2.  Now I want to apply **G2**.
3.  I apply `B1` to file `B` just fine, as `B1` comes *before* `B2`, so any changes to the file would be below `B1`'s range.
4.  **Aha, a problem occurs.** Now I need to apply `A2` to file `A`. But I've already applied `A1`, which might (or might not) have changed the file state for the lines below it. I cannot possibly keep track of the changes `A1` made to the file (imagine if I have hundreds of chunks all affecting different parts of the file, with no order).

So, this simple application does not work.

### The Solution: Accumulation
To solve this, Codestory uses an **incremental strategy**. When creating each subsequent commit, we accumulate all changes into a growing list.

What do I mean? Let's go back to the example where we have change groups `G1` and `G2` taking us from **Old State -> New State**.

1.  **State 1 (s1):** I will proceed the same for `G1`, applying changes off of the **Old State** and creating a commit.
2.  **State 2 (s2):** Here's the critical part. To create the changes for `G2`, I add the changes from **both G1 and G2** and apply that to the **Old State**.

The beauty of this is if I compare the difference of `s2` and `s1`, it is exactly the changes of `G2`!

### The Result
We repeat this over and over until we have no more groups, and then can chain our states (`s1 -> s2… -> sN`) to get our new commit history off of the old state.

Then, with some more git tricks, we update our branch with the new changes, and with that, we are done!