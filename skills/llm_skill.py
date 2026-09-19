# pyrefly: ignore [missing-import]
import ollama
from logger import logger
from memory.memory import get_user_facts

def handle_general_query(query: str) -> str:
    """
    Sends a query to the local Ollama instance running phi4-mini.
    Injects persistent user memory into the system prompt.
    """
    try:
        facts = get_user_facts()
        memory_str = "\n".join([f"- {fact}" for fact in facts])
        
        system_prompt = (
            "You are Deeks, a highly intelligent, natural, and helpful personal voice assistant for Mark. "
            "Keep your responses concise, direct, and conversational, suitable for text-to-speech. "
            "Do not use markdown formatting like asterisks, bullet points, or bold text, as it will be spoken out loud. "
            "Never mention internal mechanics, tools, skills, databases, switching to an LLM, or that you are an AI/language model. "
            "Speak naturally and directly as Mark's personal assistant."
        )
        
        if memory_str:
            system_prompt += f"\n\nHere are some things you know about Mark:\n{memory_str}"
            
        logger.info("Sending query to local assistant intelligence...")
        
        response = ollama.chat(model='phi4-mini', messages=[
            {
                'role': 'system',
                'content': system_prompt
            },
            {
                'role': 'user',
                'content': query
            }
        ])
        
        reply = response['message']['content'].strip()
        logger.info(f"Assistant response: {reply}")
        return reply
        
    except Exception as e:
        logger.exception(f"Error communicating with local LLM backend: {e}")
        return "I'm having trouble processing that right now."
