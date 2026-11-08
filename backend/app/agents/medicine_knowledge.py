"""Verified Medicine Knowledge Base & Educational Information Service (Phase 40).

Provides evidence-based general pharmacology educational information for common medications in Sri Lanka.
Strictly complies with medical safety standards:
- NEVER prescribes medications or personalized dosages.
- NEVER instructs patients to start, stop, or change prescribed medications.
- Directs patients to a registered pharmacist or doctor for personal health questions,
  pregnancy, allergies, drug interactions, or pre-existing conditions.
"""

from typing import Any, Dict, List, Optional
import re

# Curated reference database of common medications in Sri Lanka / South Asia
MEDICINE_DATABASE: Dict[str, Dict[str, Any]] = {
    "paracetamol": {
        "genericName": "Paracetamol",
        "brandNames": ["Panadol", "Calpol", "Paramol", "Tylenol", "Disprol"],
        "activeIngredient": "Acetaminophen (Paracetamol) 500mg / 120mg/5ml",
        "drugClass": "Analgesic & Antipyretic (Pain reliever & fever reducer)",
        "commonUses": [
            "Temporary relief of mild to moderate pain (headache, muscle ache, toothache, backache)",
            "Reduction of fever associated with common cold, viral infections, or influenza",
            "Relief of pain associated with mild arthritis",
        ],
        "precautions": [
            "Never exceed the maximum recommended adult daily dose of 4,000 mg (4 grams / 8 standard 500mg tablets in 24 hours).",
            "Check other cold, flu, or pain medications to ensure they do not also contain paracetamol, avoiding accidental overdose.",
            "Exercise caution if you have underlying liver disease or chronic alcohol use.",
            "Consult a pediatrician for weight-based liquid dosage in infants and young children.",
        ],
        "sideEffects": [
            "Generally well-tolerated at recommended therapeutic doses.",
            "Rare: Mild nausea, skin rash, or allergic reactions.",
            "Critical warning: Excessive doses can cause severe, potentially irreversible liver damage (hepatotoxicity).",
        ],
        "warnings": [
            "Severe liver injury can occur if you take more than recommended in 24 hours or consume 3+ alcoholic drinks daily while using.",
            "Seek immediate medical attention if you notice yellowing of eyes/skin (jaundice), dark urine, or severe nausea.",
        ],
        "consultPharmacistWhen": "Pain persists for more than 5 days, fever persists over 3 days, or if you are pregnant/breastfeeding.",
        "isPrescriptionRequired": False,
    },
    "amoxicillin": {
        "genericName": "Amoxicillin",
        "brandNames": ["Amoxil", "Augmentin (Amoxicillin + Clavulanic acid)", "Moxatag", "Novamox"],
        "activeIngredient": "Amoxicillin trihydrate",
        "drugClass": "Beta-lactam Antibiotic (Penicillin group)",
        "commonUses": [
            "Treatment of confirmed bacterial infections (middle ear infections, bacterial sinusitis, streptococcal pharyngitis)",
            "Lower respiratory tract infections (bacterial bronchitis, community-acquired pneumonia)",
            "Uncomplicated urinary tract infections and dental abscesses",
        ],
        "precautions": [
            "DO NOT use for viral infections such as common cold, influenza, COVID-19, or uncomplicated sore throats.",
            "Complete the entire course prescribed by your physician, even if you feel better after a couple of days, to prevent bacterial resistance.",
            "Strictly inform your doctor if you have a known allergy to penicillin or cephalosporin antibiotics.",
        ],
        "sideEffects": [
            "Common: Mild diarrhea, nausea, vomiting, or stomach discomfort.",
            "Allergic skin rashes (hives, itching) require immediate cessation and doctor review.",
            "Disruption of normal gut flora; consider taking with meals.",
        ],
        "warnings": [
            "Severe allergic reactions (anaphylaxis: facial swelling, difficulty breathing) are medical emergencies (call 1990).",
            "Persistent watery or bloody diarrhea may indicate Clostridioides difficile infection and requires urgent medical review.",
        ],
        "consultPharmacistWhen": "You have a history of antibiotic allergies, develop any skin rash, or experience persistent severe diarrhea.",
        "isPrescriptionRequired": True,
    },
    "metformin": {
        "genericName": "Metformin",
        "brandNames": ["Glucophage", "Diaformin", "Glycomet", "Formet"],
        "activeIngredient": "Metformin Hydrochloride",
        "drugClass": "Biguanide Antidiabetic Agent",
        "commonUses": [
            "First-line oral medication for managing blood glucose in Type 2 Diabetes Mellitus",
            "Management of Polycystic Ovary Syndrome (PCOS) under specialist supervision",
            "Improves insulin sensitivity and reduces hepatic glucose production",
        ],
        "precautions": [
            "Take with or immediately after meals to significantly reduce gastrointestinal side effects.",
            "Requires routine periodic monitoring of kidney function (eGFR / Serum Creatinine) and HbA1c.",
            "Must be temporarily paused prior to diagnostic procedures using iodinated contrast dye or major surgery.",
        ],
        "sideEffects": [
            "Common: Nausea, diarrhea, abdominal bloating, metallic taste, loss of appetite (typically subsides after 1-2 weeks).",
            "Long-term use may reduce Vitamin B12 absorption; periodic B12 checks are recommended.",
        ],
        "warnings": [
            "Rare but serious risk: Lactic Acidosis, especially in patients with severe kidney impairment, sepsis, or heavy alcohol intake.",
            "Seek urgent medical evaluation if experiencing extreme fatigue, muscle aches, breathing distress, or severe stomach discomfort.",
        ],
        "consultPharmacistWhen": "You experience persistent severe diarrhea, missed doses, or are undergoing planned surgical or radiological procedures.",
        "isPrescriptionRequired": True,
    },
    "omeprazole": {
        "genericName": "Omeprazole",
        "brandNames": ["Prilosec", "Omez", "Losec", "Omep"],
        "activeIngredient": "Omeprazole 20mg / 40mg",
        "drugClass": "Proton Pump Inhibitor (PPI)",
        "commonUses": [
            "Gastroesophageal Reflux Disease (GERD) and frequent acid reflux / heartburn",
            "Treatment and prevention of gastric and duodenal peptic ulcers",
            "Gastric mucosal protection during prolonged NSAID (painkiller) therapy",
            "Part of H. pylori eradication therapy in combination with antibiotics",
        ],
        "precautions": [
            "Best taken 30 to 60 minutes before breakfast on an empty stomach with a glass of water.",
            "Capsules should be swallowed whole without chewing or crushing the internal pellets.",
            "Prolonged unmonitored use (over 1 year) may decrease absorption of magnesium, calcium, and Vitamin B12.",
        ],
        "sideEffects": [
            "Generally well tolerated. Mild headache, abdominal pain, constipation, flatulence, or diarrhea can occasionally occur.",
        ],
        "warnings": [
            "Do NOT confuse heart attack symptoms (crushing chest tightness radiating to arm or jaw) with simple acid indigestion.",
            "Alarm symptoms like unexplained weight loss, difficulty swallowing (dysphagia), or black tarry stools require immediate endoscopic medical evaluation.",
        ],
        "consultPharmacistWhen": "Acid reflux symptoms persist after 14 days of consecutive use or worsen over time.",
        "isPrescriptionRequired": False,
    },
    "atorvastatin": {
        "genericName": "Atorvastatin",
        "brandNames": ["Lipitor", "Atorva", "Storvas", "Lipicure"],
        "activeIngredient": "Atorvastatin Calcium",
        "drugClass": "HMG-CoA Reductase Inhibitor (Statin)",
        "commonUses": [
            "Reduction of elevated low-density lipoprotein cholesterol (LDL-C) and triglycerides",
            "Prevention of cardiovascular events (heart attacks, strokes) in high-risk patients",
            "Stabilization of atherosclerotic plaque in coronary artery disease",
        ],
        "precautions": [
            "Can be taken once daily at any time of day, with or without food (taking it at night is often recommended).",
            "Avoid excessive consumption of grapefruit or grapefruit juice, as it inhibits CYP3A4 metabolism and increases drug levels.",
            "Strictly contraindicated in active liver disease and during pregnancy or breastfeeding.",
        ],
        "sideEffects": [
            "Common: Mild joint pain, digestive discomfort, headache.",
            "Uncommon: Unexplained muscle pain, tenderness, or weakness (myopathy).",
        ],
        "warnings": [
            "Report severe, unexplained muscle pain, tenderness, or dark brown urine promptly (rare rhabdomyolysis risk).",
            "Regular liver function tests (ALT/AST) and lipid panels are advised as requested by your doctor.",
        ],
        "consultPharmacistWhen": "You develop unexplained muscle soreness or weakness, or if starting any new prescription medication.",
        "isPrescriptionRequired": True,
    },
    "cetirizine": {
        "genericName": "Cetirizine",
        "brandNames": ["Zyrtec", "Cetzine", "Alerid", "Zyncet"],
        "activeIngredient": "Cetirizine Hydrochloride 10mg",
        "drugClass": "Second-Generation Antihistamine",
        "commonUses": [
            "Relief of allergic rhinitis (sneezing, runny nose, itchy watery eyes, nasal congestion)",
            "Relief of symptoms associated with chronic urticaria (hives, itchy allergic skin rashes)",
            "Allergic conjunctivitis and insect bite reactions",
        ],
        "precautions": [
            "Although less sedating than first-generation antihistamines (like Piriton), it can still cause mild drowsiness in some individuals.",
            "Avoid alcohol or sedative medications while taking cetirizine.",
            "Exercise care if driving or operating heavy machinery until you know how it affects you.",
        ],
        "sideEffects": [
            "Mild drowsiness, dry mouth, headache, fatigue.",
        ],
        "warnings": [
            "Does not treat acute severe allergic anaphylaxis alone (which requires epinephrine / emergency medical care).",
        ],
        "consultPharmacistWhen": "Allergy symptoms do not improve after 7 days, or if you have severe kidney impairment requiring dosage adjustment.",
        "isPrescriptionRequired": False,
    },
    "ibuprofen": {
        "genericName": "Ibuprofen",
        "brandNames": ["Brufen", "Advil", "Nurofen", "Motrin"],
        "activeIngredient": "Ibuprofen 200mg / 400mg",
        "drugClass": "Non-Steroidal Anti-Inflammatory Drug (NSAID)",
        "commonUses": [
            "Relief of inflammatory pain, headache, dental pain, menstrual cramps (dysmenorrhea)",
            "Symptomatic management of arthritis, sprains, sports injuries, and swelling",
            "Fever reduction when paracetamol alone is insufficient (under medical guidance)",
        ],
        "precautions": [
            "ALWAYS take with or immediately after food or milk to protect the stomach lining.",
            "Use the lowest effective dose for the shortest possible duration.",
            "Avoid taking if you have active peptic ulcer disease, severe heart failure, or kidney disease.",
            "Do NOT take during suspected Dengue fever in Sri Lanka, as NSAIDs can increase bleeding risk.",
        ],
        "sideEffects": [
            "Common: Indigestion, heartburn, stomach ache, nausea.",
            "Rare: Gastric bleeding, fluid retention, raised blood pressure.",
        ],
        "warnings": [
            "Contraindicated in third-trimester pregnancy and patients with aspirin-exacerbated respiratory disease (asthma).",
            "Black tarry stools, vomiting blood, or sharp abdominal pain require immediate emergency evaluation.",
        ],
        "consultPharmacistWhen": "You have a history of stomach ulcers, asthma, high blood pressure, or kidney disease.",
        "isPrescriptionRequired": False,
    },
    "salbutamol": {
        "genericName": "Salbutamol (Albuterol)",
        "brandNames": ["Ventolin", "Asthalin", "Aerolin"],
        "activeIngredient": "Salbutamol sulphate (Inhaler 100mcg/puff / Syrup / Nebulizer)",
        "drugClass": "Short-Acting Beta-2 Adrenergic Agonist (Bronchodilator)",
        "commonUses": [
            "Quick relief ('rescue inhaler') of acute bronchospasm in bronchial asthma and COPD",
            "Prevention of exercise-induced bronchospasm",
        ],
        "precautions": [
            "This is a quick-relief rescue bronchodilator; it does not replace daily anti-inflammatory preventer inhalers (corticosteroids).",
            "Using more than 2-3 times per week indicates sub-optimally controlled asthma and warrants doctor review.",
            "Always rinse mouth with water after inhaler use, and use a spacer device if advised for optimal lung delivery.",
        ],
        "sideEffects": [
            "Mild hand tremors (shakiness), rapid heartbeat (palpitations), nervous tension, headache.",
        ],
        "warnings": [
            "If your rescue inhaler does not relieve breathing difficulty or if symptoms worsen rapidly, call 1990 immediately.",
        ],
        "consultPharmacistWhen": "Your inhaler canister is running low or you find yourself needing it more frequently than usual.",
        "isPrescriptionRequired": True,
    },
    "losartan": {
        "genericName": "Losartan",
        "brandNames": ["Cozaar", "Losar", "Tozaar", "Covance"],
        "activeIngredient": "Losartan Potassium 25mg / 50mg / 100mg",
        "drugClass": "Angiotensin II Receptor Blocker (ARB)",
        "commonUses": [
            "Management of essential hypertension (high blood pressure)",
            "Kidney protection in patients with Type 2 diabetes and nephropathy / proteinuria",
            "Reduction of stroke risk in patients with hypertension and left ventricular hypertrophy",
        ],
        "precautions": [
            "Take at the same time each day, with or without food.",
            "Stand up slowly from sitting or lying down to avoid dizziness or orthostatic hypotension.",
            "Regular monitoring of blood pressure, serum potassium, and kidney function is required.",
            "Strictly contraindicated in pregnancy due to risk of fetal injury.",
        ],
        "sideEffects": [
            "Dizziness, lightheadedness, nasal congestion, fatigue.",
            "Hyperkalemia (elevated blood potassium level).",
        ],
        "warnings": [
            "Never stop blood pressure medication abruptly without physician consultation.",
            "Facial, lip, or tongue swelling (angioedema) is rare but requires immediate emergency medical care.",
        ],
        "consultPharmacistWhen": "You experience persistent lightheadedness, miss doses, or are taking potassium supplements or salt substitutes.",
        "isPrescriptionRequired": True,
    },
}


class MedicineKnowledge:
    """Pharmacological educational retriever and safety analyzer."""

    @classmethod
    def find_medicine(cls, query: str) -> Optional[Dict[str, Any]]:
        """Identify a known medicine in the query by generic or brand name."""
        clean_q = query.lower()

        # Direct generic match
        for generic_key, med_data in MEDICINE_DATABASE.items():
            if generic_key in clean_q:
                return med_data

            # Check brand names
            for b in med_data.get("brandNames", []):
                # Clean brand name of extra parenthetical descriptions
                brand_clean = re.sub(r"\(.*?\)", "", b).strip().lower()
                if brand_clean and re.search(r"\b" + re.escape(brand_clean) + r"\b", clean_q):
                    return med_data

        return None

    @classmethod
    def generate_educational_response(cls, query: str) -> Dict[str, Any]:
        """Generate safe, evidence-based educational text for a medicine inquiry."""
        med = cls.find_medicine(query)

        if not med:
            return {
                "found": False,
                "medicineName": None,
                "text": (
                    "I could not locate verified pharmacological information for that specific medication name in our database. "
                    "For your safety, I never guess or invent medicine details. Please verify the exact generic or brand spelling "
                    "on your prescription or packaging, or speak directly with a registered pharmacist or qualified physician before "
                    "taking any medication."
                ),
                "card": None,
                "disclaimer": "This information is for general educational purposes only and is not a prescription or clinical diagnosis.",
            }

        name = med["genericName"]
        brands = ", ".join(med["brandNames"])
        uses = "\n".join([f"• {u}" for u in med["commonUses"]])
        precautions = "\n".join([f"• {p}" for p in med["precautions"]])
        side_effects = "\n".join([f"• {s}" for s in med["sideEffects"]])
        warnings = "\n".join([f"• {w}" for w in med["warnings"]])

        rx_status = "Prescription medication (requires a valid doctor's prescription)" if med["isPrescriptionRequired"] else "Available over-the-counter (OTC) under pharmacy guidance"

        formatted_text = (
            f"**{name}** ({med['drugClass']})\n\n"
            f"**Common Brand Names:** {brands}\n"
            f"**Classification:** {rx_status}\n"
            f"**Active Ingredient:** {med['activeIngredient']}\n\n"
            f"**Common Medical Uses:**\n{uses}\n\n"
            f"**Important Precautions:**\n{precautions}\n\n"
            f"**Potential Side Effects:**\n{side_effects}\n\n"
            f"**Safety Warnings:**\n{warnings}\n\n"
            f"**When to Consult a Professional:** {med['consultPharmacistWhen']}\n\n"
            f"*Disclaimer: This information is strictly educational. MediConnect does not prescribe personalized dosages or recommend changes to your prescribed treatment. "
            f"Always consult your doctor or pharmacist regarding personal medical conditions, pregnancy, or potential drug interactions.*"
        )

        return {
            "found": True,
            "medicineName": name,
            "text": formatted_text,
            "card": {
                "medicineName": name,
                "activeIngredient": med["activeIngredient"],
                "commonUses": med["commonUses"],
                "precautions": med["precautions"],
                "sideEffects": med["sideEffects"],
                "warnings": med["warnings"],
                "consultPharmacistWhen": med["consultPharmacistWhen"],
                "isPrescriptionRequired": med["isPrescriptionRequired"],
            },
            "disclaimer": "This information is for general educational purposes only and is not a prescription or clinical diagnosis.",
        }

