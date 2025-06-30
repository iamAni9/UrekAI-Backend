from google import generativeai as genai
from dotenv import load_dotenv
from app.config.logger import get_logger
from app.config.settings import settings

load_dotenv()
logger = get_logger("API Logger")

API_KEY = settings.GOOGLE_API_KEY

if not API_KEY:
    raise ValueError("GOOGLE_API_KEY is not set in the environment")

genai.configure(api_key=API_KEY)

# model = genai.GenerativeModel(model_name="gemini-2.5-flash")

async def query_ai(user_query: str, system_prompt: str, response_format: str = "json") -> str:
    try:
        system_instruction = (
            system_prompt +
            "\nIMPORTANT: Respond ONLY with valid JSON. Do not include markdown, code blocks, or extra text. The response must be parseable JSON."
        )
        
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_instruction
        )

        chat = model.start_chat()
        response = chat.send_message(user_query)
        # response = chat.send_message([
        #     {"role": "system", "parts": [system_instruction]},
        #     {"role": "user", "parts": [user_query]}
        # ])

        return response.text

    except Exception as e:
        logger.error("❌ Error querying AI", exc_info=True)
        raise
