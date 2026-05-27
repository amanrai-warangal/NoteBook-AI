import os
from openai import AsyncOpenAI

# Point to your local Ollama container's OpenAI-compatible endpoint route
# By appending /v1, we tell the OpenAI client to send payloads to our local Docker instance
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT","http://localhost:11434/v1")

# Initialize the official client layout. Ollama is free and doesn't validate keys,
# but the OpenAI SDK strictly requires the api_key parameter to be filled with string characters.

ai_client = AsyncOpenAI(
    base_url = LLM_ENDPOINT,
    api_key = "ollama_local_sandbox"
)

async def generate_text_embedding(text : str) -> list[float]:
    """
    Connects to the local Ollama instance using the standardized OpenAI API footprint.
    Converts raw text context into a 768-dimensional mathematical float vector.
    """
    try:
        # Standard OpenAI SDK call for generating text vectors
        response = await ai_client.embeddings.create(
            model="nomic-embed-text",
            input=text
        )
        # Dig into the standard OpenAI response tree structure
        return response.data[0].embedding
    except Exception as e:
        # Fallback safeguard: If the container is sleeping, return an empty array 
        # so the application doesn't crash and the text note still saves to MongoDB.
        print(f"⚠️ OpenAI-Style Embedding Generation Failure: {e}")
        return []

async def generate_llm_response(system_prompt: str, user_prompt : str) -> str:
    """
    Connects to the local Ollama Docker instance using OpenAI-style routing.
    Passes the context-augmented prompts to the phi3 model for generation.
    """
    try:
        response = await ai_client.chat.completions.create(
            model = "qwen2.5:0.5b",
            messages = [
                {"role" : "system", "content" : system_prompt},
                {"role" : "user", "content" : user_prompt}
            ],
            temperature = 0.2 #low temp keeps the model strict, factual, and focused on your notes
        )

        return response.choices[0].message.content
    
    except Exception as e:
        print(f"⚠️ OpenAI-Style Chat Generation Failure: {e}")
        return "Sorry, I encountered an issue communicating with my local AI generation core."