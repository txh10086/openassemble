from typing import List, Dict, Any, Literal
from pydantic import BaseModel

from rag.Answer_Generation import LegalAnswer, answer, cited_paragraphs
from rag.Router import client, question


class VerificationResult(BaseModel):
    """Verification result format"""
    is_accurate: bool
    explanation: str
    confidence: Literal["high", "medium", "low"]


def verify_answer(question: str, answer: LegalAnswer,
                  cited_paragraphs: List[Dict[str, Any]]) -> VerificationResult:
    """
    Verify if the answer is grounded in the cited paragraphs.

    Args:
        question: The user's question
        answer: The generated answer
        cited_paragraphs: Paragraphs cited in the answer

    Returns:
        Verification result with accuracy assessment, explanation, and confidence level
    """
    print("\n==== VERIFYING ANSWER ====")

    # Prepare context with the cited paragraphs
    context = ""
    for paragraph in cited_paragraphs:
        display_id = paragraph.get("display_id", str(paragraph["id"]))
        context += f"PARAGRAPH {display_id}:\n{paragraph['text']}\n\n"

    # Prepare system prompt
    system_prompt = """You are a fact-checker for legal information.
Your job is to verify if the provided answer:
1. Is factually accurate according to the source paragraphs
2. Uses citations correctly

Be critical and look for any factual errors or unsupported claims.
Assign a confidence level based on how directly the paragraphs answer the question:
- high: The answer is comprehensive, accurate, and directly supported by the paragraphs
- medium: The answer is mostly accurate but may be incomplete or have minor issues
- low: The answer has significant gaps, inaccuracies, or is poorly supported by the paragraphs
"""

    response = client.responses.parse(
        model="o4-mini",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"""
QUESTION: {question}

ANSWER TO VERIFY:
{answer.answer}

CITATIONS USED: {', '.join(answer.citations)}

SOURCE PARAGRAPHS:
{context}

Is this answer accurate and properly supported by the source paragraphs?
Assign a confidence level (high, medium, or low) based on completeness and accuracy.
            """}
        ],
        text_format=VerificationResult
    )

    # Log and return the verification result
    print(f"\nAccuracy verification: {'PASSED' if response.output_parsed.is_accurate else 'FAILED'}")
    print(f"Confidence: {response.output_parsed.confidence}")
    print(f"Explanation: {response.output_parsed.explanation}")

    return response.output_parsed


# Verify the answer using only the cited paragraphs
verification = verify_answer(question, answer, cited_paragraphs)

# Display final result with verification
print("\n==== FINAL VERIFIED ANSWER ====")
print(f"Verification: {'PASSED' if verification.is_accurate else 'FAILED'} | Confidence: {verification.confidence}")
print("\nAnswer:")
print(answer.answer)
print("\nCitations:")
for citation in answer.citations:
    print(f"- {citation}")