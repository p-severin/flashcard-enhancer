# Pydantic AI Guide for Flashcard Enhancer

## Overview

This guide explains how we're using **Pydantic AI** to enhance flashcards by generating additional fields using AI.

## Key Concepts

### 1. **Pydantic Models for Data Structure**

We define three Pydantic models to structure our data:

```python
class RawCard(BaseModel):
    """Original flashcard data from CSV"""
    front: str
    back: str
    deck_name: str

class AdditionalFields(BaseModel):
    """AI-generated additional fields"""
    example_sentence_front: str = Field(
        description="An example sentence using the word/phrase from 'front'"
    )
    example_sentence_back: str = Field(
        description="Translation of the example sentence in the back language"
    )

class EnhancedCard(BaseModel):
    """Complete flashcard with original and AI-generated fields"""
    front: str
    back: str
    deck_name: str
    example_sentence_front: str
    example_sentence_back: str
```

### 2. **Creating an Agent**

The `Agent` is the core of Pydantic AI. It's configured with:
- A **model** (e.g., `openai:gpt-4o`)
- An **output_type** (the Pydantic model for structured output)
- **instructions** (system prompt to guide the AI)

```python
agent = Agent(
    model="openai:gpt-4o",
    output_type=AdditionalFields,  # ← AI will return data in this structure
    instructions=(
        "You are a language learning assistant. Generate natural, contextually "
        "appropriate example sentences for flashcard vocabulary and phrases."
    ),
)
```

**Key Point**: The `output_type=AdditionalFields` tells Pydantic AI to:
1. Generate a JSON schema from the `AdditionalFields` model
2. Send this schema to the LLM so it knows the expected structure
3. Validate the LLM's response against this schema
4. Return a properly typed `AdditionalFields` object

### 3. **Running the Agent**

To get AI-generated data:

```python
# Create a prompt with context
prompt = f"""
Create example sentences for this flashcard:

Front (question): {raw_card.front}
Back (answer): {raw_card.back}

The front is in one language and the back is in another (likely Italian based on context).
Generate a natural example sentence in the front language that uses the concept,
and its translation in the back language.
"""

# Run the agent (async)
result = await agent.run(prompt)

# Extract the structured output
additional_fields = result.output  # This is an AdditionalFields object!
```

**Important**:
- Use `result.output` to get the structured data
- The `output` is automatically validated and typed as `AdditionalFields`
- The agent handles JSON parsing, validation, and retries if the LLM returns invalid data

### 4. **Type Safety**

Pydantic AI is fully type-safe. The agent's type signature is:

```python
Agent[None, AdditionalFields]
#      ↑         ↑
#      |         └─ Output type (what agent.run() returns)
#      └─ Dependencies type (None in this case, more on this below)
```

This means:
- IDEs know that `result.output` is an `AdditionalFields`
- Type checkers can verify you're using the data correctly
- You get autocomplete for all fields

### 5. **Combining Data**

After getting the AI-generated fields, we merge them with the original data:

```python
enhanced_card = EnhancedCard(
    front=raw_card.front,
    back=raw_card.back,
    deck_name=raw_card.deck_name,
    example_sentence_front=additional_fields.example_sentence_front,
    example_sentence_back=additional_fields.example_sentence_back,
)
```

### 6. **CSV Processing Workflow**

The complete workflow:

1. **Read CSV** → Parse rows into `RawCard` objects
2. **For each card**:
   - Create a prompt with the card's data
   - Run the agent to get `AdditionalFields`
   - Combine into `EnhancedCard`
3. **Write CSV** → Export `EnhancedCard` objects to a new CSV

```python
# Read
with open(input_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        raw_card = RawCard(
            front=row['Front'],
            back=row['Back'],
            deck_name=row['deck_name']
        )
        cards_to_process.append(raw_card)

# Process
for raw_card in cards_to_process:
    enhanced_card = await process_card(agent, raw_card)
    enhanced_cards.append(enhanced_card)

# Write
with open(output_path, 'w', encoding='utf-8', newline='') as f:
    fieldnames = list(EnhancedCard.model_fields.keys())
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for card in enhanced_cards:
        writer.writerow(card.model_dump())
```

## Advanced Features (Not Yet Used)

### Dependencies

Pydantic AI supports **dependency injection** for passing context to tools and instructions:

```python
@dataclass
class Dependencies:
    db_connection: DatabaseConn
    user_id: int

agent = Agent(
    model="openai:gpt-4o",
    deps_type=Dependencies,  # ← Define dependency type
    output_type=AdditionalFields,
)

# Use dependencies in instructions
@agent.instructions
async def get_user_context(ctx: RunContext[Dependencies]) -> str:
    user = await ctx.deps.db_connection.get_user(ctx.deps.user_id)
    return f"User preferences: {user.preferences}"

# Run with dependencies
deps = Dependencies(db_connection=db, user_id=123)
result = await agent.run("Generate examples", deps=deps)
```

### Tools

You can register functions that the LLM can call:

```python
@agent.tool
async def lookup_translation(
    ctx: RunContext[Dependencies],
    word: str
) -> str:
    """Look up the translation of a word."""
    return await ctx.deps.db_connection.get_translation(word)
```

The LLM can decide to call this tool while processing the prompt.

### Streaming

For real-time output:

```python
async with agent.run_stream(prompt) as result:
    async for message in result.stream():
        print(message)
    final_output = result.output
```

## Best Practices

1. **Use descriptive field descriptions** with `Field(description=...)`
   - This helps the LLM understand what to generate

2. **Provide clear instructions** to the agent
   - Be specific about the expected behavior

3. **Test with small batches first**
   - Use the `limit` parameter to test on a few cards

4. **Handle rate limits**
   - Add delays between requests if needed
   - Consider batching or parallel processing

5. **Validate outputs**
   - Pydantic automatically validates, but you may want additional checks

## Running the Code

```bash
# Install dependencies
pip install pydantic-ai python-dotenv

# Set up your API key
export OPENAI_API_KEY="your-key-here"
# or add to .env file

# Run the script
python agent.py
```

The script will:
1. Read from `output/Włoski.csv`
2. Process 3 cards (configurable with `limit` parameter)
3. Write enhanced cards to `output/Włoski_enhanced.csv`

## Expected Output Format

**Input CSV:**
```csv
Front,Back,deck_name
"Twierdzić, potwierdzić",affermare,Włoski całość::Włoski A1::Włoski
ile,"quanto, quanti, quanta, quante",Włoski całość::Włoski A1::Włoski
```

**Output CSV:**
```csv
front,back,deck_name,example_sentence_front,example_sentence_back
"Twierdzić, potwierdzić",affermare,Włoski całość::Włoski A1::Włoski,"I affirm that this is true.","Affermo che questo è vero."
ile,"quanto, quanti, quanta, quante",Włoski całość::Włoski A1::Włoski,"How much does it cost?","Quanto costa?"
```

## References

- [Pydantic AI Documentation](https://ai.pydantic.dev/)
- [Pydantic AI Agent API](https://ai.pydantic.dev/api/agent/)
- [Structured Output Guide](https://ai.pydantic.dev/output/)
