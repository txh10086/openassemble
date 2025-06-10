from openai import OpenAI
import json
from typing import List, Dict, Any

from rag.Document_Loading import split_into_20_chunks, document_text

# Initialize OpenAI client
client = OpenAI()


def route_chunks(question: str, chunks: List[Dict[str, Any]],
                 depth: int, scratchpad: str = "") -> Dict[str, Any]:
    """
    Ask the model which chunks contain information relevant to the question.
    Maintains a scratchpad for the model's reasoning.
    Uses structured output for chunk selection and required tool calls for scratchpad.

    Args:
        question: The user's question
        chunks: List of chunks to evaluate
        depth: Current depth in the navigation hierarchy
        scratchpad: Current scratchpad content

    Returns:
        Dictionary with selected IDs and updated scratchpad
    """
    print(f"\n==== ROUTING AT DEPTH {depth} ====")
    print(f"Evaluating {len(chunks)} chunks for relevance")

    # Build system message
    system_message = """You are an expert document navigator. Your task is to:
1. Identify which text chunks might contain information to answer the user's question
2. Record your reasoning in a scratchpad for later reference
3. Choose chunks that are most likely relevant. Be selective, but thorough. Choose as many chunks as you need to answer the question, but avoid selecting too many.

First think carefully about what information would help answer the question, then evaluate each chunk.
"""

    # Build user message with chunks and current scratchpad
    user_message = f"QUESTION: {question}\n\n"

    if scratchpad:
        user_message += f"CURRENT SCRATCHPAD:\n{scratchpad}\n\n"

    user_message += "TEXT CHUNKS:\n\n"

    # Add each chunk to the message
    for chunk in chunks:
        user_message += f"CHUNK {chunk['id']}:\n{chunk['text']}\n\n"

    # Define function schema for scratchpad tool calling
    tools = [
        {
            "type": "function",
            "name": "update_scratchpad",
            "description": "Record your reasoning about why certain chunks were selected",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Your reasoning about the chunk(s) selection"
                    }
                },
                "required": ["text"],
                "additionalProperties": False
            }
        }
    ]

    # Define JSON schema for structured output (selected chunks)
    text_format = {
        "format": {
            "type": "json_schema",
            "name": "selected_chunks",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "chunk_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "IDs of the selected chunks that contain information to answer the question"
                    }
                },
                "required": [
                    "chunk_ids"
                ],
                "additionalProperties": False
            }
        }
    }

    # First pass: Call the model to update scratchpad (required tool call)
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user",
         "content": user_message + "\n\nFirst, you must use the update_scratchpad function to record your reasoning."}
    ]

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=messages,
        tools=tools,
        tool_choice="required"
    )

    # Process the scratchpad tool call
    new_scratchpad = scratchpad

    for tool_call in response.output:
        if tool_call.type == "function_call" and tool_call.name == "update_scratchpad":
            args = json.loads(tool_call.arguments)
            scratchpad_entry = f"DEPTH {depth} REASONING:\n{args.get('text', '')}"
            if new_scratchpad:
                new_scratchpad += "\n\n" + scratchpad_entry
            else:
                new_scratchpad = scratchpad_entry

            # Add function call and result to messages
            messages.append(tool_call)
            messages.append({
                "type": "function_call_output",
                "call_id": tool_call.call_id,
                "output": "Scratchpad updated successfully."
            })

    # Second pass: Get structured output for chunk selection
    messages.append({"role": "user",
                     "content": "Now, select the chunks that could contain information to answer the question. Return a JSON object with the list of chunk IDs."})

    response_chunks = client.responses.create(
        model="gpt-4.1-mini",
        input=messages,
        text=text_format
    )

    # Extract selected chunk IDs from structured output
    selected_ids = []
    if response_chunks.output_text:
        try:
            # The output_text should already be in JSON format due to the schema
            chunk_data = json.loads(response_chunks.output_text)
            selected_ids = chunk_data.get("chunk_ids", [])
        except json.JSONDecodeError:
            print("Warning: Could not parse structured output as JSON")

    # Display results
    print(f"Selected chunks: {', '.join(str(id) for id in selected_ids)}")
    print(f"Updated scratchpad:\n{new_scratchpad}")

    return {
        "selected_ids": selected_ids,
        "scratchpad": new_scratchpad
    }


def navigate_to_paragraphs(document_text: str, question: str, max_depth: int = 1) -> Dict[str, Any]:
    """
    Navigate through the document hierarchy to find relevant paragraphs.

    Args:
        document_text: The full document text
        question: The user's question
        max_depth: Maximum depth to navigate before returning paragraphs (default: 1)

    Returns:
        Dictionary with selected paragraphs and final scratchpad
    """
    scratchpad = ""

    # Get initial chunks with min 500 tokens
    chunks = split_into_20_chunks(document_text, min_tokens=500)

    # Navigator state - track chunk paths to maintain hierarchy
    chunk_paths = {}  # Maps numeric IDs to path strings for display
    for chunk in chunks:
        chunk_paths[chunk["id"]] = str(chunk["id"])

    # Navigate through levels until max_depth or until no chunks remain
    for current_depth in range(max_depth + 1):
        # Call router to get relevant chunks
        result = route_chunks(question, chunks, current_depth, scratchpad)

        # Update scratchpad
        scratchpad = result["scratchpad"]

        # Get selected chunks
        selected_ids = result["selected_ids"]
        selected_chunks = [c for c in chunks if c["id"] in selected_ids]

        # If no chunks were selected, return empty result
        if not selected_chunks:
            print("\nNo relevant chunks found.")
            return {"paragraphs": [], "scratchpad": scratchpad}

        # If we've reached max_depth, return the selected chunks
        if current_depth == max_depth:
            print(f"\nReturning {len(selected_chunks)} relevant chunks at depth {current_depth}")

            # Update display IDs to show hierarchy
            for chunk in selected_chunks:
                chunk["display_id"] = chunk_paths[chunk["id"]]

            return {"paragraphs": selected_chunks, "scratchpad": scratchpad}

        # Prepare next level by splitting selected chunks further
        next_level_chunks = []
        next_chunk_id = 0  # Counter for new chunks

        for chunk in selected_chunks:
            # Split this chunk into smaller pieces
            sub_chunks = split_into_20_chunks(chunk["text"], min_tokens=200)

            # Update IDs and maintain path mapping
            for sub_chunk in sub_chunks:
                path = f"{chunk_paths[chunk['id']]}.{sub_chunk['id']}"
                sub_chunk["id"] = next_chunk_id
                chunk_paths[next_chunk_id] = path
                next_level_chunks.append(sub_chunk)
                next_chunk_id += 1

        # Update chunks for next iteration
        chunks = next_level_chunks

# Run the navigation for a sample question
question = "What format should a motion to compel discovery be filed in? How should signatures be handled?"
navigation_result = navigate_to_paragraphs(document_text, question, max_depth=2)

# Sample retrieved paragraph
print("\n==== FIRST 3 RETRIEVED PARAGRAPHS ====")
for i, paragraph in enumerate(navigation_result["paragraphs"][:3]):
    display_id = paragraph.get("display_id", str(paragraph["id"]))
    print(f"\nPARAGRAPH {i+1} (ID: {display_id}):")
    print("-" * 40)
    print(paragraph["text"])
    print("-" * 40)