# codestory

Git is a powerful tool. It is also an excellent tool for shooting yourself in the foot.

While Git provides the infrastructure for version control, you rarely need to be down in the pipes for daily work. codestory is a high-level interface that sits on top of Git. It does not replace Git; it allows you to use it effectively without the headache.

Think of this as a natural transition to higher-level version control. You get a clean history without the manual labor.

## The Problem

A common scenario: You have been coding for hours. You have modified hundreds of lines across many files. You are tired. Human laziness wins, so you stage everything and run `git commit -m "added feature x, y, z and fixed bugs"`.

This creates a garbage history that is impossible to debug later.

In the time it takes you to get a cup of coffee, codestory can read those changes, understand the semantics, and generate a linearized history of atomic, logical commits. You gain the benefits of a clean tree without the stress of manually managing the index.

## Design Philosophy

1. **Do Not Touch User Code**  
   codestory operates on a strict read-only basis regarding your source files. It manipulates fake Git index files to construct the history. At no point does it modify the code in your working directory.

2. **Semantic and Logical Grouping**  
   The tool splits large chunks of changes into the smallest possible logical commits.

   - **Semantic Analysis**: It understands the language structure to ensure syntactically dependent changes stick together.
   - **High-Level Analysis**: It uses AI to recognize logical dependencies that code parsers miss. For example, it understands that a change to documentation is logically coupled to a function signature change, even if they share no variable references.

3. **Extensibility**  
   We do not care what language you use. codestory is designed to be language-agnostic. You can add compatibility for a new language by adding 10-20 lines of JSON to define the basic semantics.


## Model Support (BYOK)

We support a Bring Your Own Key model. You are not locked into a specific provider.

- **Cloud**: OpenAI, Anthropic, Google.
- **Local**: Full support for Ollama.

More models will be added as they become useful.

## Usage
When you are finished using codestory, you have a standard Git repository. Nothing special happens.

For detailed api documentation, please reference [cli docs](https://docs.codestory.build/codestorycli/)

## Contributing
If you find a bug, feel free to create a pull request


## License
The code is licensed under GPLv2, just like Git.
