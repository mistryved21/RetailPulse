"""Unified LLM wrapper supporting OpenAI, Gemini, and Ollama."""
import logging
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from utils.config import settings

logger = logging.getLogger(__name__)

def get_llm(temperature: float = 0.1) -> BaseChatModel:
    """Get LLM instance based on configured provider.
    
    Supports: openai, gemini, ollama
    Configure via LLM_PROVIDER in .env
    """
    provider = settings.LLM_PROVIDER.lower()
    
    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in .env")
        logger.info(f"Using OpenAI model: {settings.OPENAI_MODEL}")
        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=temperature,
        )
    elif provider == "gemini":
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not set in .env")
            
        model_name = settings.GEMINI_MODEL
        if getattr(settings, 'MODEL_MODE', 'base') == 'tuned' and getattr(settings, 'TUNED_GEMINI_MODEL', ''):
            model_name = settings.TUNED_GEMINI_MODEL
            logger.info(f"Using TUNED Gemini model: {model_name}")
        else:
            logger.info(f"Using base Gemini model: {model_name}")
            
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=temperature,
            convert_system_message_to_human=True,
        )
    elif provider == "ollama":
        try:
            from langchain_community.chat_models import ChatOllama
        except ImportError:
            from langchain_ollama import ChatOllama
        logger.info(f"Using Ollama model: {settings.OLLAMA_MODEL}")
        return ChatOllama(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=temperature,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}. Use openai/gemini/ollama")

def invoke_llm(prompt: str, system_prompt: str = "", temperature: float = 0.1) -> str:
    """Convenience function to invoke LLM and get string response."""
    from langchain_core.messages import HumanMessage, SystemMessage
    llm = get_llm(temperature=temperature)
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))
    try:
        response = llm.invoke(messages)
        return response.content
    except Exception as e:
        logger.error(f"LLM invocation failed: {e}")
        raise
