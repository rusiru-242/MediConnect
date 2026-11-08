"""Verified Healthy Food, Nutrition, Exercise & Wellness Assistant (Phase 40).

Provides culturally-relevant evidence-based guidance for:
- Healthy Sri Lankan meals (breakfast, lunch, dinner)
- Sugar reduction & balanced nutrition
- Budget-friendly protein options
- Beginner exercise routines (walking, strength, mobility)
- Sleep hygiene & stress reduction
Strictly adheres to safety rules:
- Avoids extreme diets or unsupported medical claims.
- Never prescribes restrictive medical diets without clinical oversight.
- Screens for concerning symptoms and avoids recommending strenuous exercise.
"""

from typing import Any, Dict, List, Optional
import re


class WellnessKnowledge:
    """Evidence-based nutrition, exercise and daily habits guidance engine."""

    # -------------------------------------------------------------------------
    # 1. Healthy Food & Nutrition
    # -------------------------------------------------------------------------
    @classmethod
    def get_healthy_food_guidance(cls, query: str) -> Dict[str, Any]:
        """Provide balanced nutrition and Sri Lankan food guidance."""
        clean_q = query.lower()

        # Check sub-intent
        if any(w in clean_q for w in ["breakfast", "morning", "උදේ", "උදෑසන"]):
            title = "Healthy Sri Lankan Breakfast Suggestions"
            summary = "Nutritious, high-fiber, low-glycemic breakfast options native to Sri Lanka:"
            tips = [
                "Prioritize whole grains and complex carbohydrates for sustained morning energy.",
                "Incorporate leafy greens and herbs for natural vitamins and micronutrients.",
                "Control portion sizes of sweetened milk tea; switch to plain tea or herbal infusions.",
            ]
            options = [
                "Kola Kenda (herbal congee) prepared with Gotu Kola, Hathawariya, or Karapincha and red raw rice with a small piece of jaggery.",
                "Red Rice or Kurakkan String Hoppers (Indi Appa) with mild Dhal curry (parippu) and fresh Pol Sambol / Katta Sambol in moderation.",
                "Boiled Chickpeas (Kadalai) or Mung Beans (Mun Eta) tempered with mustard seeds, curry leaves, onions, and lightly sprinkled fresh coconut.",
                "Wholemeal or Kurakkan Pittu served with fresh vegetable soup or steamed fish curry.",
            ]
        elif any(w in clean_q for w in ["sugar", "sweet", "sweetener", "සීනි"]):
            title = "Practical Strategies to Reduce Added Sugar"
            summary = "Evidence-based, gradual habits to reduce dietary added sugar without deprivation:"
            tips = [
                "Identify hidden sugars: commercial cordials, sweetened carbonated sodas, malt drinks, and bottled fruit juices.",
                "Transition your tea: If drinking 2-3 cups of sweetened milk tea daily, gradually reduce sugar from 2 teaspoons to 1, then half, before enjoying unsweetened tea or ginger tea.",
                "Choose whole fresh local fruits (papaya, guava, banana, woodapple) instead of fruit syrups or canned desserts.",
                "Read nutrition labels on biscuits and bakery items to check total sugars per 100g.",
            ]
            options = [
                "Unsweetened Ceylon black tea infused with fresh ginger, cardamom, or cinnamon.",
                "Natural King Coconut water (Thambili) without added syrup for natural electrolytes.",
                "Plain curd (Mee Kiri) paired with fresh cut papaya or guava rather than treacle.",
            ]
        elif any(w in clean_q for w in ["protein", "budget", "affordable", "ලාභ"]):
            title = "Affordable & Accessible Protein Sources in Sri Lanka"
            summary = "Cost-effective, highly nutritious protein options for daily meals:"
            tips = [
                "Combine plant-based legumes (dhal, chickpeas, green gram) with red rice to achieve complete amino acid profiles.",
                "Include small dried or fresh fish several times a week for calcium and omega-3 fatty acids.",
                "Eggs are an exceptionally bioavailable and economical complete protein source.",
            ]
            options = [
                "Eggs: Hard-boiled, poached, or lightly scrambled with onions, green chilies, and tomatoes.",
                "Dhal (Mysoor Parippu): Rich in soluble fiber, potassium, and plant protein.",
                "Small local fish: Sprats (Halmassa), Salaya, Hurulla, and Linna offer affordable high-density protein and calcium.",
                "Legumes: Chickpeas (Kadalai), Green Gram (Mun Eta), and Black Gram (Ulundu).",
                "Soya meat (texturized vegetable protein) prepared with roasted curry powder, paired with abundant green vegetables.",
            ]
        else:
            # General balanced meal plate
            title = "The MediConnect Balanced Healthy Plate"
            summary = "A simple, sustainable framework for healthy daily eating:"
            tips = [
                "Half your plate: Non-starchy vegetables and greens (Gotu kola, Mukunuwenna, Kankun, beans, cabbage, brinjal).",
                "Quarter of your plate: High-fiber complex carbohydrates (Red raw rice, kurakkan, boiled sweet potato).",
                "Quarter of your plate: Lean protein (Fresh fish, egg, chicken breast, dhal, or tofu).",
                "Hydration: Aim for 2 to 2.5 liters of clean water daily, adjusting for heat and activity.",
            ]
            options = [
                "Red rice, tempered Dhal, steamed Kankun or Gotu Kola Sambol, and grilled/curried fresh fish.",
                "Kurakkan roti with mixed vegetable curry and boiled egg.",
                "Warm vegetable and lentil soup with a slice of wholemeal bread.",
            ]

        card = {
            "category": "food",
            "title": title,
            "summary": summary,
            "tips": tips,
            "sriLankanOptions": options,
            "safetyNote": (
                "General nutritional guidance only. If you have chronic conditions such as diabetes, "
                "chronic kidney disease, or cardiovascular disease, consult a registered clinical dietitian for customized meal plans."
            ),
        }

        bullet_tips = "\n".join([f"• {t}" for t in tips])
        bullet_opts = "\n".join([f"• {o}" for o in options])

        text = (
            f"### 🥗 {title}\n\n"
            f"{summary}\n\n"
            f"**Healthy Guidelines:**\n{bullet_tips}\n\n"
            f"**Recommended Options:**\n{bullet_opts}\n\n"
            f"*{card['safetyNote']}*"
        )

        return {
            "intent": "HEALTHY_FOOD",
            "text": text,
            "card": card,
        }

    # -------------------------------------------------------------------------
    # 2. Exercise & Mobility Guidance
    # -------------------------------------------------------------------------
    @classmethod
    def get_exercise_guidance(cls, query: str) -> Dict[str, Any]:
        """Provide safe beginner physical activity guidance."""
        clean_q = query.lower()

        # Check for concerning symptoms mentioned in exercise queries
        if any(w in clean_q for w in ["chest pain", "dizzy", "faint", "short of breath", "heart racing"]):
            return {
                "intent": "EMERGENCY_GUIDANCE",
                "text": (
                    "⚠️ **Exercise Safety Warning:** You mentioned symptoms such as chest discomfort, dizziness, or shortness of breath. "
                    "Do NOT start or continue any exercise program right now. Please rest, and if symptoms are acute or severe, "
                    "seek immediate medical evaluation or call the 1990 Emergency Hotline."
                ),
                "card": None,
            }

        title = "Beginner-Friendly Exercise & Daily Movement Routine"
        summary = "Safe, adaptable physical activity guidelines recommended for beginners:"
        tips = [
            "Start gradually: Consistency is vastly more effective than intensity. Aim for 20 to 30 minutes of moderate activity 4-5 days a week.",
            "Always include a 5-minute gentle warm-up before and cool-down after exercise.",
            "Stay well hydrated, particularly in warm and humid tropical climates.",
            "Listen to your body: Mild muscle soreness is normal, but sharp, radiating, or joint pain is a signal to stop.",
        ]
        options = [
            "Brisk Walking: The safest, most functional cardiovascular exercise. Start with 15 minutes and build up to 30 minutes daily.",
            "Chair Squats: Stand in front of a sturdy chair, lower your hips until lightly touching the seat, and push through your heels to stand (10-12 repetitions).",
            "Wall Push-Ups: Stand an arm's length from a wall, place palms flat at shoulder height, lower your chest slowly, and press back (8-10 repetitions).",
            "Gentle Stretching: Hamstring stretch, shoulder rolls, neck mobility, and gentle seated torso twists to maintain spinal flexibility.",
            "Postural Breaks: If working at a desk, stand up every 45 minutes, walk around for 2 minutes, and stretch your hip flexors.",
        ]

        card = {
            "category": "exercise",
            "title": title,
            "summary": summary,
            "tips": tips,
            "sriLankanOptions": options,
            "safetyNote": (
                "Educational fitness suggestions only. If you have pre-existing cardiovascular conditions, arthritis, hypertension, "
                "or recent surgeries, obtain clearance from your physician or physiotherapist before beginning a new physical routine."
            ),
        }

        bullet_tips = "\n".join([f"• {t}" for t in tips])
        bullet_opts = "\n".join([f"• {o}" for o in options])

        text = (
            f"### 🏃 {title}\n\n"
            f"{summary}\n\n"
            f"**Key Principles:**\n{bullet_tips}\n\n"
            f"**Recommended Starter Routine:**\n{bullet_opts}\n\n"
            f"*{card['safetyNote']}*"
        )

        return {
            "intent": "EXERCISE_GUIDANCE",
            "text": text,
            "card": card,
        }

    # -------------------------------------------------------------------------
    # 3. General Wellness, Sleep & Stress Management
    # -------------------------------------------------------------------------
    @classmethod
    def get_wellness_guidance(cls, query: str) -> Dict[str, Any]:
        """Provide evidence-based guidance for sleep hygiene, stress, and lifestyle wellness."""
        clean_q = query.lower()

        if any(w in clean_q for w in ["sleep", "insomnia", "නින්ද", "tired", "fatigue"]):
            title = "Sleep Hygiene & Restful Sleep Practices"
            summary = "Proven behavioral habits to improve sleep quality and circadian rhythm:"
            tips = [
                "Maintain a consistent sleep-wake schedule, even on weekends, to stabilize your body clock.",
                "Avoid screens (smartphones, laptops, TV) for at least 30 to 45 minutes before bedtime, as blue light inhibits melatonin secretion.",
                "Keep your sleeping environment cool, quiet, and adequately ventilated.",
                "Avoid heavy, spicy dinners and caffeinated beverages within 4-6 hours of your planned bedtime.",
            ]
            options = [
                "Establish a wind-down routine: A warm bath, reading a book, or listening to calm music.",
                "Enjoy a warm cup of caffeine-free herbal tea such as Chamomile or Belimal before sleep.",
                "If unable to fall asleep after 20 minutes, get out of bed and do a quiet, non-stimulating activity in dim light until drowsy.",
            ]
        elif any(w in clean_q for w in ["stress", "anxiety", "mind", "calm", "relax", "පීඩනය"]):
            title = "Evidence-Based Stress Reduction & Mindfulness"
            summary = "Daily practices to soothe the nervous system and manage stress:"
            tips = [
                "Practice the 4-7-8 Breathing Technique: Inhale through nose for 4 seconds, hold breath for 7 seconds, exhale slowly through mouth for 8 seconds. Repeat 4 cycles.",
                "Take mindful outdoor walking breaks: Spending 15 minutes in natural green surroundings lowers cortisol levels.",
                "Set clear boundaries with digital notifications and work communication outside working hours.",
            ]
            options = [
                "Daily 10-minute mindfulness breathing meditation upon waking.",
                "Journaling thoughts and priorities before bed to clear cognitive clutter.",
                "Engaging in a creative hobby or spending quality time connecting with family and friends.",
            ]
        else:
            title = "Daily Health & Preventive Wellness Routine"
            summary = "Foundational daily habits for vitality, immunity, and longevity:"
            tips = [
                "Drink 2-3 liters of clean water daily, keeping urine a pale straw color.",
                "Get 15-20 minutes of early morning sunlight exposure for natural Vitamin D synthesis.",
                "Schedule routine annual preventive health screenings (blood pressure, fasting blood glucose, lipid panel).",
            ]
            options = [
                "Start morning with a glass of warm water.",
                "Incorporate a 15-minute brisk walk after your main meal.",
                "Aim for 7 to 8 hours of restorative sleep nightly.",
            ]

        card = {
            "category": "lifestyle",
            "title": title,
            "summary": summary,
            "tips": tips,
            "sriLankanOptions": options,
            "safetyNote": (
                "Educational wellness suggestions only. If you experience persistent chronic insomnia, severe anxiety, "
                "or depressive symptoms, please consult a qualified mental health professional or primary care physician."
            ),
        }

        bullet_tips = "\n".join([f"• {t}" for t in tips])
        bullet_opts = "\n".join([f"• {o}" for o in options])

        text = (
            f"### 🧘 {title}\n\n"
            f"{summary}\n\n"
            f"**Wellness Guidelines:**\n{bullet_tips}\n\n"
            f"**Recommended Routine:**\n{bullet_opts}\n\n"
            f"*{card['safetyNote']}*"
        )

        return {
            "intent": "GENERAL_WELLNESS",
            "text": text,
            "card": card,
        }

