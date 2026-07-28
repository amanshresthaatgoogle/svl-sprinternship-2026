import os
from google.adk.agents import Agent
from pypdf import PdfReader


def extract_pdf_text(filename: str) -> str:
    """Extract text from a PDF sitting next to this script, slide by slide."""
    file_path = os.path.join(os.path.dirname(__file__), filename)
    reader = PdfReader(file_path)
    pages_text = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        pages_text.append(f"--- Slide {i} ---\n{text}")
    return "\n\n".join(pages_text)


slides_content = extract_pdf_text("slides.pdf")


def build_instruction(context) -> str:
    """Callable instruction: ADK only template-substitutes `{var}` patterns
    when instruction is a plain string. Using a function instead means any
    literal curly braces inside the extracted slide text (tables, set
    notation, stray PDF artifacts, etc.) get passed through as-is instead
    of being mistaken for session-state placeholders."""
    return f"""You are an agent that answers questions about a slide deck.

The full text extracted from the deck is below, in order, with each slide marked
by a "--- Slide N ---" header.

<slides>
{slides_content}
</slides>

Behavior rules:
1. On your very first turn in any conversation, before anything else, give a
   concise summary (5-8 bullets) of what the deck covers overall. Don't wait
   to be asked for a summary — lead with it.
2. After that, answer the user's questions strictly grounded in the <slides>
   content above.
3. If a question can't be answered from the slides, say so explicitly rather
   than guessing or pulling in outside knowledge.
4. When it's useful, cite which slide(s) an answer comes from (e.g. "See Slide 4").
"""


slides_agent = Agent(
    name="slides_qa_agent",
    model="gemini-2.5-flash",  # swap for whatever model you're using elsewhere
    instruction=build_instruction,
)

root_agent = slides_agent