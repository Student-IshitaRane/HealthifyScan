import os
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

# Load environment variables
load_dotenv()

# Fetch API key from .env
api_key = os.getenv("GEMINI_API_KEY")

# Configure API
genai.configure(api_key=api_key)

def check_ingredient_safety(ingredients, health_context):
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"""
        ACT AS A CLINICAL NUTRITIONIST. Analyze these ingredients for a patient with:

        HEALTH PROFILE:
        {health_context}

        INGREDIENTS:
        {', '.join(ingredients)}

        REQUIREMENTS:
        1. First list ALL definitely safe ingredients
        2. Then list POTENTIALLY UNSAFE ingredients with:
           - Specific medical reason
           - Severity level [Mild/Moderate/Severe]
           - Alternative suggestions when possible
        3. Provide a FINAL VERDICT with:
           - Clear recommendation: [Safe/Moderation/Avoid]
           - Brief explanation (1-2 sentences)
           - Suggested alternatives if needed
        4. Use EXACTLY this format:

        Safe: ingredient1, ingredient2...
        Unsafe:
        - ingredientX (reason) [Severity]
          → Try: alternative1
        - ingredientY (reason) [Severity]

        Verdict:
        - Recommendation: [Safe/Moderation/Avoid]
        - Explanation: Concise explanation based on health context
        - Alternatives: Suggested product alternatives if needed

        EXAMPLES:
        Example 1 (Allergy):
        Safe: sunflower oil, rice flour
        Unsafe:
        - peanuts (severe allergy risk) [Severe]
          → Try: sunflower seeds

        Verdict:
        - Recommendation: Avoid
        - Explanation: Contains peanuts which pose a severe allergy risk.
        - Alternatives: Look for nut-free alternatives.

        Example 2 (Hypertension):
        Safe: tomatoes, olive oil
        Unsafe:
        - salt (may elevate blood pressure) [Moderate]
          → Try: low-sodium version

        Verdict:
        - Recommendation: Moderation
        - Explanation: High salt content makes this unsuitable for regular consumption with hypertension.
        - Alternatives: Choose low-sodium versions or consume small portions occasionally.

        Example 3 (Diabetes):
        Safe: almonds, cinnamon
        Unsafe:
        - high fructose corn syrup (rapidly increases blood sugar) [Severe]

        Verdict:
        - Recommendation: Avoid
        - Explanation: Contains high-glycemic sweeteners that dangerously spike blood sugar.
        - Alternatives: Look for products sweetened with stevia or monk fruit.
        """

        response = model.generate_content(prompt)

        if not response.text:
            return "Error: No response from API"

        if "Safe:" not in response.text or "Unsafe:" not in response.text or "Verdict:" not in response.text:
            return f"Invalid analysis format. Please try again. Raw response: {response.text}"

        return response.text

    except google_exceptions.InvalidArgument as e:
        return f"API Error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"

def analyze_product_safety(product, health_context):
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"""
        ACT AS A CLINICAL NUTRITIONIST. Analyze this product for a user with:
        HEALTH CONTEXT: {health_context if health_context else "General Population"}

        PRODUCT: {product}

        REQUIREMENTS:
        1. Give a 1-line safety verdict with emoji:
           - ❌ Avoid
           - ⚠️ Caution
           - ✅ Safe
        2. State ONE key reason in 5-8 words
        3. List MAX 4 alternatives as bullet points (5-7 words each)
        4. Use THIS EXACT FORMAT:

        Safety Verdict: [emoji] [Avoid/Caution/Safe]
        Reason: [concise 5-8 word reason]
        Better Alternatives:
        - [Alternative 1] (key benefit)
        - [Alternative 2] (key benefit)
        - [Alternative 3] (key benefit)
        - [Alternative 4] (key benefit)

        EXAMPLE 1 (Diabetes):
        Safety Verdict: ❌ Avoid
        Reason: Rapid blood sugar spike
        Better Alternatives:
        - Whole grain crackers (fiber)
        - Roasted chickpeas (protein)
        - Berries (low GI)
        - Almonds (healthy fats)

        EXAMPLE 2 (Hypertension):
        Safety Verdict: ⚠️ Caution
        Reason: High sodium content
        Better Alternatives:
        - Unsalted popcorn (low sodium)
        - Rice cakes (light)
        - Cucumber slices (hydrating)
        - Oatmeal (heart-healthy)

        EXAMPLE 3 (Safe Product):
        Safety Verdict: ✅ Safe
        Reason: No known risks
        Better Alternatives:
        - None needed
        """

        response = model.generate_content(prompt)

        if not response.text:
            return "Error: No response from API"

        return response.text

    except Exception as e:
        return f"Error: {str(e)}"
