from typing import List, Dict, Any
from pydantic import BaseModel, field_validator

from rag.Router import client, question, navigation_result


class LegalAnswer(BaseModel):
    """Structured response format for legal questions"""
    answer: str
    citations: List[str]

    @field_validator('citations')
    def validate_citations(cls, citations, info):
        # Access valid_citations from the model_config
        valid_citations = info.data.get('_valid_citations', [])
        if valid_citations:
            for citation in citations:
                if citation not in valid_citations:
                    raise ValueError(f"Invalid citation: {citation}. Must be one of: {valid_citations}")
        return citations


def generate_answer(question: str, paragraphs: List[Dict[str, Any]],
                    scratchpad: str) -> LegalAnswer:
    """Generate an answer from the retrieved paragraphs."""
    print("\n==== GENERATING ANSWER ====")

    # Extract valid citation IDs
    valid_citations = [str(p.get("display_id", str(p["id"]))) for p in paragraphs]

    if not paragraphs:
        return LegalAnswer(
            answer="I couldn't find relevant information to answer this question in the document.",
            citations=[],
            _valid_citations=[]
        )

    # Prepare context for the model
    context = ""
    for paragraph in paragraphs:
        display_id = paragraph.get("display_id", str(paragraph["id"]))
        context += f"PARAGRAPH {display_id}:\n{paragraph['text']}\n\n"

    system_prompt = """You are a legal research assistant answering questions about the 
Trademark Trial and Appeal Board Manual of Procedure (TBMP).

Answer questions based ONLY on the provided paragraphs. Do not rely on any foundation knowledge or external information or extrapolate from the paragraphs.
Cite phrases of the paragraphs that are relevant to the answer. This will help you be more specific and accurate.
Include citations to paragraph IDs for every statement in your answer. Valid citation IDs are: {valid_citations_str}
Keep your answer clear, precise, and professional.
"""
    valid_citations_str = ", ".join(valid_citations)

    # Call the model using structured output
    response = client.responses.parse(
        model="gpt-4.1",
        input=[
            {"role": "system", "content": system_prompt.format(valid_citations_str=valid_citations_str)},
            {"role": "user",
             "content": f"QUESTION: {question}\n\nSCRATCHPAD (Navigation reasoning):\n{scratchpad}\n\nPARAGRAPHS:\n{context}"}
        ],
        text_format=LegalAnswer,
        temperature=0.3
    )

    # Add validation information after parsing
    response.output_parsed._valid_citations = valid_citations

    print(f"\nAnswer: {response.output_parsed.answer}")
    print(f"Citations: {response.output_parsed.citations}")

    return response.output_parsed


# Generate an answer
answer = generate_answer(question, navigation_result["paragraphs"],
                         navigation_result["scratchpad"])

cited_paragraphs = []
for paragraph in navigation_result["paragraphs"]:
    para_id = str(paragraph.get("display_id", str(paragraph["id"])))
    if para_id in answer.citations:
        cited_paragraphs.append(paragraph)

# Display the cited paragraphs for the audience
print("\n==== CITED PARAGRAPHS ====")
for i, paragraph in enumerate(cited_paragraphs):
    display_id = paragraph.get("display_id", str(paragraph["id"]))
    print(f"\nPARAGRAPH {i + 1} (ID: {display_id}):")
    print("-" * 40)
    print(paragraph["text"])
    print("-" * 40)