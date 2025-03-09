from pydantic import BaseModel
from typing import List

class qwq_answer(BaseModel):
    """
    Answer_Q represents a detailed answer response structure.
    
    It includes:
        - thought: your reasoning process,
        - topic: the subject matter being addressed,
        - final_answer: the final main response content, use MarkDown to answer
        - suggestion_topics_for_user: a list of subsequent topic/question for further clarification.
    """
    thought: str
    topic: str
    final_answer: str
    suggestion_topics_for_user: List[str]
