"""Verified Healthy Food, Nutrition, Exercise & Wellness Assistant (Phase 40 & 41).

Provides culturally-relevant evidence-based guidance in English and Sinhala for:
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
    """Evidence-based nutrition, exercise and daily habits guidance engine in English and Sinhala."""

    # -------------------------------------------------------------------------
    # 1. Healthy Food & Nutrition
    # -------------------------------------------------------------------------
    @classmethod
    def get_healthy_food_guidance(cls, query: str, lang: str = "en") -> Dict[str, Any]:
        """Provide balanced nutrition and Sri Lankan food guidance in English or Sinhala."""
        clean_q = query.lower()
        is_si = lang == "si" or bool(re.search(r"[\u0D80-\u0DFF]", query)) or any(
            w in clean_q.split() for w in ["kanna", "kama", "keema", "udeta", "ude", "sinhalen", "sinhala", "seeni", "poshana"]
        )

        if any(w in clean_q for w in ["breakfast", "morning", "උදේ", "උදෑසන", "udeta", "ude"]):
            if is_si:
                lead_in = "🥗 ඔබට ගැළපෙන සෞඛ්‍ය සම්පන්න ශ්‍රී ලාංකික උදෑසන ආහාර යෝජනා මෙන්න:"
                title = "සෞඛ්‍ය සම්පන්න ශ්‍රී ලාංකික උදෑසන ආහාර යෝජනා"
                summary = "ශ්‍රී ලංකාවට ආවේණික, පෝෂ්‍යදායී, කෙඳි බහුල සහ අඩු ග්ලයිසමික් උදෑසන ආහාර විකල්ප:"
                tips = [
                    "උදෑසන ක්‍රියාශීලී බව පවත්වා ගැනීමට පෝෂ්‍යදායී ධාන්‍ය හා සංකීර්ණ කාබෝහයිඩ්‍රේට සඳහා මුල්තැන දෙන්න.",
                    "ස්වභාවික විටමින් හා ක්ෂුද්‍ර පෝෂක ලබා ගැනීමට කොළ කැඳ හා නැවුම් එළවළු එක් කරගන්න.",
                    "අධික සීනි සහිත කිරි තේ වෙනුවට සරල තේ හෝ ඖෂධීය පාන වර්ග තෝරාගන්න.",
                ]
                options = [
                    "කොළ කැඳ (ගොටුකොළ, හාතාවාරිය හෝ කරපිංචා කැඳ) රතු කැකුළු බත් හා හකුරු කැබැල්ලක් සමඟ.",
                    "රතු සහල් හෝ කුරක්කන් ඉඳිආප්ප, පරිප්පු හොදි හා පොල් සම්බෝල ස්වල්පයක් සමඟ.",
                    "තැම්බූ කඩල හෝ මුංඇට, අබ, කරපිංචා සහ ලූනු දමා තෙම්පරාදු කර පොල් ස්වල්පයක් සමඟ.",
                    "කුරක්කන් හෝ ආටා පිටි පිට්ටු, නැවුම් එළවළු සුප් හෝ මාළු හොදි සමඟ.",
                ]
                safety_note = (
                    "සාමාන්‍ය පෝෂණ මාර්ගෝපදේශ පමණි. දියවැඩියාව, අධි රුධිර පීඩනය හෝ වෙනත් නිදන්ගත රෝග ඇත්නම් සුදුසුකම්ලත් පෝෂණවේදියෙකුගෙන් උපදෙස් ලබාගන්න."
                )
            else:
                lead_in = "🥗 Here are healthy Sri Lankan breakfast suggestions for balanced nutrition:"
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
                safety_note = (
                    "General nutritional guidance only. If you have chronic conditions such as diabetes, "
                    "chronic kidney disease, or cardiovascular disease, consult a registered clinical dietitian for customized meal plans."
                )
        elif any(w in clean_q for w in ["sugar", "sweet", "sweetener", "සීනි", "seeni"]):
            if is_si:
                lead_in = "🥗 දෛනික ආහාරයේ සීනි ප්‍රමාණය අඩු කරගැනීම සඳහා සෞඛ්‍ය උපදෙස් මෙන්න:"
                title = "දෛනික ආහාරයේ සීනි අඩු කරගැනීමේ ප්‍රායෝගික පුරුදු"
                summary = "ශරීරයට අමතර කැලරි එකතු නොවී ක්‍රමයෙන් සීනි පාලනය කරගැනීමට සරල පියවර:"
                tips = [
                    "පැණි බීම, කෘත්‍රිම පළතුරු බීම සහ ශක්තිජනක පාන වෙනුවට ස්වභාවික පාන තෝරාගන්න.",
                    "තේ සඳහා යොදන සීනි ප්‍රමාණය ක්‍රමයෙන් අඩු කර ගන්න (හැඳි 2 සිට 1 දක්වා, පසුව සීනි රහිතව).",
                    "පැණි රස අතුරුපස වෙනුවට පැපොල්, පේර, කෙසෙල් වැනි නැවුම් දේශීය පළතුරු භාවිතා කරන්න.",
                    "බිස්කට් සහ බේකරි නිෂ්පාදන මිලදී ගැනීමේදී එහි අඩංගු සීනි ප්‍රමාණය ලේබලයෙන් පරීක්ෂා කරන්න.",
                ]
                options = [
                    "ඉඟුරු හෝ එනසාල් දැමූ සීනි රහිත කළු තේ හෝ කොළ තේ.",
                    "ස්වභාවික තැඹිලි වතුර (කිසිදු පැණිරසක් එකතු නොකර).",
                    "පැණි රහිත මී කිරි සමඟ නැවුම් පළතුරු පෙති.",
                ]
                safety_note = "දියවැඩියා රෝගීන් තම රුධිර සීනි මට්ටමට අදාළව පෝෂණ සැලසුම් සකස් කරගත යුතුය."
            else:
                lead_in = "🥗 Here are practical, evidence-based habits to reduce added dietary sugar:"
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
                safety_note = "Diabetic patients should tailor dietary plans with clinical oversight."
        elif any(w in clean_q for w in ["protein", "budget", "affordable", "ලාභ", "labha"]):
            if is_si:
                lead_in = "🥗 ශ්‍රී ලංකාවේ පහසුවෙන් ලබාගත හැකි පෝෂ්‍යදායී ප්‍රෝටීන් ආහාර මෙන්න:"
                title = "අඩු වියදමකින් ලබාගත හැකි ප්‍රෝටීන් බහුල ආහාර"
                summary = "දෛනිකව ශරීරයට අවශ්‍ය ප්‍රෝටීන් පහසුවෙන් හා ලාභදායීව සපුරාගත හැකි ක්‍රම:"
                tips = [
                    "රතු සහල් සමඟ පරිප්පු, කඩල හෝ මුංඇට වැනි ධාන්‍ය වර්ග එක් කර ගැනීමෙන් සම්පූර්ණ ප්‍රෝටීන් ලබාගත හැක.",
                    "කැල්සියම් හා ඔමේගා-3 ලබා ගැනීමට කුඩා මාළු සතියකට කිහිප වතාවක් ආහාරයට එක් කරගන්න.",
                    "බිත්තර යනු ඉතා ලාභදායී හා උසස් තත්ත්වයේ ප්‍රෝටීන් ප්‍රභවයකි.",
                ]
                options = [
                    "තම්බාගත් හෝ ඔම්ලට් ආකාරයෙන් සැකසූ බිත්තර.",
                    "මයිසූර් පරිප්පු හෝ කඩල පරිප්පු හොදි.",
                    "හාල්මැස්සන්, සාලයන්, හුරුල්ලන් හෝ ලින්නන් වැනි කුඩා මාළු.",
                    "කඩල, මුංඇට හා උඳු ඇට.",
                    "සෝයා මීට් නැවුම් එළවළු සමඟ පිළියෙල කර.",
                ]
                safety_note = "වකුගඩු ආබාධ සහිත රෝගීන් ප්‍රෝටීන් භාවිතයේදී වෛද්‍ය උපදෙස් ලබාගත යුතුය."
            else:
                lead_in = "🥗 Here are affordable and accessible protein sources in Sri Lanka:"
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
                safety_note = "General dietary guidance only; kidney patients should monitor protein intake with a doctor."
        else:
            if is_si:
                lead_in = "🥗 නිරෝගී දිවියකට සමබල ආහාර වේලක් පිළියෙල කරගන්නා ආකාරය මෙන්න:"
                title = "මෙඩිකනෙක්ට් සමබල සෞඛ්‍ය සම්පන්න ආහාර පිඟාන"
                summary = "දිනපතා ආහාර වේල සමබලව සකස් කරගැනීමට සරල ක්‍රමවේදය:"
                tips = [
                    "පිඟානෙන් අඩක්: පිෂ්ඨය අඩු නැවුම් එළවළු සහ පලා වර්ග (ගොටුකොළ, මුකුණුවැන්න, කංකුන්, බෝංචි).",
                    "පිඟානෙන් හතරෙන් පංගුවක්: සංකීර්ණ කාබෝහයිඩ්‍රේට (රතු කැකුළු බත්, කුරක්කන්, බතල).",
                    "පිඟානෙන් හතරෙන් පංගුවක්: කෙට්ටු ප්‍රෝටීන් (නැවුම් මාළු, බිත්තර, කුකුළු මස්, පරිප්පු).",
                    "ප්‍රමාණවත් ජලය: දිනකට පිරිසිදු ජලය ලීටර් 2-2.5ක් පානය කරන්න.",
                ]
                options = [
                    "රතු බත්, තෙම්පරාදු පරිප්පු, ගොටුකොළ සම්බෝල හා මාළු මිරිසට.",
                    "කුරක්කන් රොටී, එළවළු ව්‍යංජනයක් සහ තම්බපු බිත්තරයක්.",
                    "නැවුම් එළවළු සුප් සහ ධාන්‍ය පාන්.",
                ]
                safety_note = "සාමාන්‍ය පෝෂණ මාර්ගෝපදේශ පමණි. වැඩිදුර විස්තර සඳහා පෝෂණවේදියෙකු හමුවන්න."
            else:
                lead_in = "🥗 Here are evidence-based recommendations for a balanced daily plate:"
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
                safety_note = (
                    "General nutritional guidance only. If you have chronic conditions such as diabetes, "
                    "chronic kidney disease, or cardiovascular disease, consult a registered clinical dietitian for customized meal plans."
                )

        card = {
            "category": "food",
            "title": title,
            "summary": summary,
            "tips": tips,
            "sriLankanOptions": options,
            "safetyNote": safety_note,
        }

        return {
            "intent": "HEALTHY_FOOD",
            "text": lead_in,
            "card": card,
        }

    # -------------------------------------------------------------------------
    # 2. Exercise & Mobility Guidance
    # -------------------------------------------------------------------------
    @classmethod
    def get_exercise_guidance(cls, query: str, lang: str = "en") -> Dict[str, Any]:
        """Provide safe beginner physical activity guidance in English or Sinhala."""
        clean_q = query.lower()
        is_si = lang == "si" or bool(re.search(r"[\u0D80-\u0DFF]", query)) or any(
            w in clean_q.split() for w in ["kettu", "bara", "adu", "viyama", "karanna", "karannada", "sinhalen", "sinhala"]
        )

        # Check for concerning symptoms mentioned in exercise queries
        if any(w in clean_q for w in ["chest pain", "dizzy", "faint", "short of breath", "heart racing", "පපුවේ"]):
            warning_text = (
                "⚠️ **ව්‍යායාම ආරක්ෂණ අනතුරු ඇඟවීම:** පපුවේ වේදනාව, කරකැවිල්ල හෝ හුස්ම ගැනීමේ අපහසුවක් ඇති නම් කිසිදු ව්‍යායාමයක් ආරම්භ නොකරන්න. "
                "වහාම විවේක ගෙන, අවශ්‍ය නම් ළඟම ඇති හදිසි ප්‍රතිකාර ඒකකයට යොමු වන්න හෝ 1990 අමතන්න."
                if is_si
                else "⚠️ **Exercise Safety Warning:** You mentioned symptoms such as chest discomfort, dizziness, or shortness of breath. "
                "Do NOT start or continue any exercise program right now. Please rest, and if symptoms are acute or severe, "
                "seek immediate medical evaluation or call the 1990 Emergency Hotline."
            )
            return {
                "intent": "EMERGENCY_GUIDANCE",
                "text": warning_text,
                "card": None,
            }

        if is_si:
            lead_in = "🏃 ආරම්භකයින් සඳහා වඩාත් ආරක්ෂිත, සරල ව්‍යායාම මාර්ගෝපදේශ මෙන්න:"
            title = "ආරම්භකයින් සඳහා සරල ව්‍යායාම හා දෛනික චලන රටා"
            summary = "දිනපතා නිරෝගීව හා ක්‍රියාශීලීව සිටීමට ආරම්භකයින්ට සුදුසු ආරක්ෂිත ව්‍යායාම:"
            tips = [
                "ක්‍රමයෙන් ආරම්භ කරන්න: සතියකට දින 4-5ක් විනාඩි 20-30ක් මධ්‍යස්ථ ලෙස ව්‍යායාම කරන්න.",
                "ව්‍යායාම කිරීමට පෙර විනාඩි 5ක මූලික උණුසුම් වීමක් (warm-up) සහ අවසානයේ සිසිල් වීමක් (cool-down) සිදු කරන්න.",
                "ව්‍යායාම අතරතුර හා පසුව ප්‍රමාණවත් ලෙස ජලය පානය කරන්න.",
                "ශරීරයට දැඩි අපහසුවක් හෝ වේදනාවක් දැනේ නම් වහාම ව්‍යායාම නතර කරන්න.",
            ]
            options = [
                "වේගයෙන් ඇවිදීම (Brisk Walking): දිනකට විනාඩි 15 සිට 30 දක්වා ක්‍රමයෙන් වැඩි කරන්න.",
                "පුටු ස්කොට්ස් (Chair Squats): ශක්තිමත් පුටුවක් ඉදිරියේ සිට හිඳගෙන නැගී සිටීම (වට 10-12).",
                "බිත්ති පුෂ්-අප්ස් (Wall Push-Ups): බිත්තියකට දෑත් තබා සෙමින් පහත් වී නැවත එසවීම (වට 8-10).",
                "සරල ඇදීම් ව්‍යායාම (Gentle Stretching): කොන්ද, කර සහ පාද සඳහා සරල ඇදීම්.",
                "වැඩ කරන අතරතුර විවේක: පරිගණකයේ වැඩ කරන විට සෑම විනාඩි 45කට වරක් නැගිට ඇවිදින්න.",
            ]
            safety_note = (
                "සාමාන්‍ය සුවතා යෝජනා පමණි. අධි රුධිර පීඩනය, හෘද රෝග හෝ ආතරයිටිස් වැනි තත්ත්වයන් ඇත්නම් නව ව්‍යායාම ආරම්භ කිරීමට පෙර වෛද්‍ය උපදෙස් ලබාගන්න."
            )
        else:
            lead_in = "🏃 Here are safe, beginner-friendly exercise and movement guidelines:"
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
            safety_note = (
                "Educational fitness suggestions only. If you have pre-existing cardiovascular conditions, arthritis, hypertension, "
                "or recent surgeries, obtain clearance from your physician or physiotherapist before beginning a new physical routine."
            )

        card = {
            "category": "exercise",
            "title": title,
            "summary": summary,
            "tips": tips,
            "sriLankanOptions": options,
            "safetyNote": safety_note,
        }

        return {
            "intent": "EXERCISE_GUIDANCE",
            "text": lead_in,
            "card": card,
        }

    # -------------------------------------------------------------------------
    # 3. General Wellness, Sleep & Stress Management
    # -------------------------------------------------------------------------
    @classmethod
    def get_wellness_guidance(cls, query: str, lang: str = "en") -> Dict[str, Any]:
        """Provide evidence-based guidance for sleep hygiene, stress, and lifestyle wellness."""
        clean_q = query.lower()
        is_si = lang == "si" or bool(re.search(r"[\u0D80-\u0DFF]", query)) or any(
            w in clean_q.split() for w in ["ninda", "nidaganna", "peedanaya", "manasika", "sinhalen", "sinhala"]
        )

        if any(w in clean_q for w in ["sleep", "insomnia", "නින්ද", "tired", "fatigue", "ninda"]):
            if is_si:
                lead_in = "🧘 සුවබර නින්දක් ලබාගැනීම සඳහා වැදගත් උපදෙස් මෙන්න:"
                title = "සුවබර නින්දක් සඳහා සෞඛ්‍ය පුරුදු (Sleep Hygiene)"
                summary = "නින්දේ ගුණාත්මකභාවය වැඩි දියුණු කරගැනීමට ඔප්පු කරන ලද ප්‍රායෝගික පුරුදු:"
                tips = [
                    "සති අන්තයේ පවා එකම වේලාවකට නින්දට යාම සහ අවදි වීම පුරුද්දක් කරගන්න.",
                    "නින්දට යාමට පෙර අවම වශයෙන් විනාඩි 30-45ක් ස්මාර්ට්ෆෝන්, රූපවාහිනී භාවිතයෙන් වළකින්න.",
                    "නිදන කාමරය සිසිල්ව, අඳුරුව සහ නිහඬව තබාගන්න.",
                    "රාත්‍රියේ නිදා ගැනීමට පෙර අධික තෙල්/මිරිස් සහිත ආහාර හා කැෆේන් අඩංගු පානවලින් වළකින්න.",
                ]
                options = [
                    "නින්දට පෙර මනස සන්සුන් කරන ක්‍රියාකාරකමක් (පොතක් කියවීම, සන්සුන් සංගීතයකට සවන්දීම).",
                    "නින්දට පෙර කැෆේන් රහිත බෙලිමල් හෝ රණවරා වැනි උණුසුම් ඖෂධීය පානයක් ලබාගැනීම.",
                    "විනාඩි 20කින් නින්ද නොයන්නේ නම් ඇඳෙන් නැගිට මඳ ආලෝකයක නිස්කලංක දෙයක යෙදෙන්න.",
                ]
                safety_note = "කල්පවතින නින්ද නොයාමේ ගැටළු ඇත්නම් වෛද්‍යවරයෙකු හමුවන්න."
            else:
                lead_in = "🧘 Here are proven behavioral practices for restful sleep:"
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
                safety_note = (
                    "Educational wellness suggestions only. If you experience persistent chronic insomnia, consult a physician."
                )
        elif any(w in clean_q for w in ["stress", "anxiety", "mind", "calm", "relax", "පීඩනය", "peedanaya"]):
            if is_si:
                lead_in = "🧘 මානසික ආතතිය අවම කර ගැනීම සඳහා ප්‍රායෝගික උපදෙස් මෙන්න:"
                title = "මානසික ආතතිය පාලනය හා සුවතාවය"
                summary = "ස්නායු පද්ධතිය සන්සුන් කර ආතතිය කළමනාකරණය සඳහා දෛනික පුරුදු:"
                tips = [
                    "4-7-8 හුස්ම ගැනීමේ ක්‍රමය: තත්පර 4ක් නාසයෙන් හුස්ම ගෙන, තත්පර 7ක් රඳවාගෙන, තත්පර 8ක් මුඛයෙන් සෙමින් පිටකරන්න (වට 4ක්).",
                    "ස්වභාවික පරිසරයක විනාඩි 15ක් ඇවිදීමෙන් මානසික ආතති හෝමෝන මට්ටම පහත වැටේ.",
                    "වැඩ කරන වේලාවෙන් පසු ඩිජිටල් තිර හා දැනුම්දීම්වලින් බැහැරව විවේක ගන්න.",
                ]
                options = [
                    "උදෑසන විනාඩි 10ක භාවනාවක හෝ මනා සිහියෙන් යුත් හුස්ම ගැනීමේ යෙදීම.",
                    "නින්දට පෙර සිතේ ඇති කරුණු දිනපොතක සටහන් කර සිත සැහැල්ලු කර ගැනීම.",
                    "පවුලේ අය හා මිතුරන් සමඟ සුහදව කාලය ගත කිරීම.",
                ]
                safety_note = "දැඩි මානසික අවපීඩනයක් හෝ ආතතියක් පවතී නම් මනෝ වෛද්‍ය උපදෙස් ලබාගන්න."
            else:
                lead_in = "🧘 Here are evidence-based practices for stress reduction and mindfulness:"
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
                safety_note = "If you experience severe anxiety or depressive symptoms, please consult a qualified mental health professional."
        else:
            if is_si:
                lead_in = "🧘 දෛනික සුවතාවය සහ නිරෝගී ජීවන රටාවක් සඳහා උපදෙස් මෙන්න:"
                title = "දෛනික සුවතාවය සහ රෝග නිවාරණ පුරුදු"
                summary = "ප්‍රබෝධමත් බව සහ ප්‍රතිශක්තිය පවත්වා ගැනීමට අත්‍යවශ්‍ය දෛනික පුරුදු:"
                tips = [
                    "දිනකට පිරිසිදු පානීය ජලය ලීටර් 2-3ක් පානය කරන්න.",
                    "ස්වභාවික විටමින් D ලබාගැනීමට උදෑසන විනාඩි 15-20ක් හිරු එළියට නිරාවරණය වන්න.",
                    "වසරකට වරක් රුධිර පීඩනය, සීනි මට්ටම වැනි මූලික පරීක්ෂණ සිදුකරගන්න.",
                ]
                options = [
                    "උදෑසන ඇල්මැරුණු වතුර වීදුරුවකින් දවස ආරම්භ කරන්න.",
                    "ප්‍රධාන ආහාර වේලකට පසු විනාඩි 15ක සරල ඇවිදීමක් එක්කරගන්න.",
                    "දිනකට පැය 7 සිට 8 දක්වා සුවදායක නින්දක් ලබාගන්න.",
                ]
                safety_note = "සාමාන්‍ය සුවතා යෝජනා පමණි. නිදන්ගත රෝග සඳහා වෛද්‍ය උපදෙස් ලබාගන්න."
            else:
                lead_in = "🧘 Here are foundational daily habits for vitality and preventive wellness:"
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
                safety_note = "Educational wellness suggestions only; consult a physician for individual health questions."

        card = {
            "category": "lifestyle",
            "title": title,
            "summary": summary,
            "tips": tips,
            "sriLankanOptions": options,
            "safetyNote": safety_note,
        }

        return {
            "intent": "GENERAL_WELLNESS",
            "text": lead_in,
            "card": card,
        }
