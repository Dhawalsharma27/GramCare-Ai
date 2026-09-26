import os
import json
import urllib.request
import urllib.parse
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from backend.db import get_cached_translation, set_cached_translation

router = APIRouter(prefix="/api", tags=["Translation"])

# --- Supported Language Directory ---
LANGUAGES = [
    {
        "code": "en",
        "name": "English",
        "native_name": "English",
        "script": "Latin",
        "region": "Global & Pan-India",
        "flag": "🇬🇧",
        "speech_code": "en-IN",
        "greeting": "Welcome to GramCare AI"
    },
    {
        "code": "hi",
        "name": "Hindi",
        "native_name": "हिन्दी",
        "script": "Devanagari",
        "region": "Central & Northern India",
        "flag": "🇮🇳",
        "speech_code": "hi-IN",
        "greeting": "नमस्ते! ग्रामकेयर एआई में आपका स्वागत है"
    },
    {
        "code": "cg",
        "name": "Chhattisgarhi",
        "native_name": "छत्तीसगढ़ी",
        "script": "Devanagari",
        "region": "Chhattisgarh & Central Rural Hubs",
        "flag": "🌾",
        "speech_code": "hi-IN",
        "greeting": "जय जोहार! ग्रामकेयर एआई म आपमन के स्वागत हे"
    },
    {
        "code": "bho",
        "name": "Bhojpuri",
        "native_name": "भोजपुरी",
        "script": "Devanagari",
        "region": "Bihar, Eastern UP & Jharkhand",
        "flag": "🌾",
        "speech_code": "hi-IN",
        "greeting": "प्रणाम! ग्रामकेयर एआई में रउआ सब के स्वागत बा"
    },
    {
        "code": "bn",
        "name": "Bengali",
        "native_name": "বাংলা",
        "script": "Bengali",
        "region": "West Bengal, Tripura & Assam",
        "flag": "🇮🇳",
        "speech_code": "bn-IN",
        "greeting": "নমস্কার! গ্রামকেয়ার এআই-তে আপনাকে স্বাগতম"
    },
    {
        "code": "mr",
        "name": "Marathi",
        "native_name": "मराठी",
        "script": "Devanagari",
        "region": "Maharashtra & Western India",
        "flag": "🇮🇳",
        "speech_code": "mr-IN",
        "greeting": "नमस्कार! ग्रामकेअर एआय मध्ये आपले स्वागत आहे"
    },
    {
        "code": "te",
        "name": "Telugu",
        "native_name": "తెలుగు",
        "script": "Telugu",
        "region": "Andhra Pradesh & Telangana",
        "flag": "🇮🇳",
        "speech_code": "te-IN",
        "greeting": "నమస్కారం! గ్రామ్‌కేర్ AI కి స్వాగతం"
    },
    {
        "code": "ta",
        "name": "Tamil",
        "native_name": "தமிழ்",
        "script": "Tamil",
        "region": "Tamil Nadu & Puducherry",
        "flag": "🇮🇳",
        "speech_code": "ta-IN",
        "greeting": "வணக்கம்! கிராம்கேர் AI-க்கு உங்களை வரவேற்கிறோம்"
    },
    {
        "code": "gu",
        "name": "Gujarati",
        "native_name": "ગુજરાતી",
        "script": "Gujarati",
        "region": "Gujarat & Western Coast",
        "flag": "🇮🇳",
        "speech_code": "gu-IN",
        "greeting": "નમસ્તે! ગ્રામકેર એઆઈ માં આપનું સ્વાગત છે"
    },
    {
        "code": "or",
        "name": "Odia",
        "native_name": "ଓଡ଼ିଆ",
        "script": "Odia",
        "region": "Odisha & Eastern Rural Belts",
        "flag": "🇮🇳",
        "speech_code": "or-IN",
        "greeting": "ନମସ୍କାର! ଗ୍ରାମକେୟାର ଏଆଇ କୁ ସ୍ୱାଗତ"
    },
    {
        "code": "pa",
        "name": "Punjabi",
        "native_name": "ਪੰਜਾਬੀ",
        "script": "Gurmukhi",
        "region": "Punjab & Northern Belts",
        "flag": "🇮🇳",
        "speech_code": "pa-IN",
        "greeting": "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ! ਗ੍ਰਾਮਕੇਅਰ ਏਆਈ ਵਿੱਚ ਤੁਹਾਡਾ ਸਵਾਗਤ ਹੈ"
    },
    {
        "code": "kn",
        "name": "Kannada",
        "native_name": "ಕನ್ನಡ",
        "script": "Kannada",
        "region": "Karnataka & Deccan Region",
        "flag": "🇮🇳",
        "speech_code": "kn-IN",
        "greeting": "ನಮಸ್ಕಾರ! ಗ್ರಾಮ್‌ಕೇರ್ AI ಗೆ ಸುಸ್ವಾಗತ"
    },
    {
        "code": "ml",
        "name": "Malayalam",
        "native_name": "മലയാളം",
        "script": "Malayalam",
        "region": "Kerala & Lakshadweep",
        "flag": "🇮🇳",
        "speech_code": "ml-IN",
        "greeting": "നമസ്കാരം! ഗ്രാംകെയർ AI-ലേക്ക് സ്വാഗതം"
    },
    {
        "code": "ur",
        "name": "Urdu",
        "native_name": "اردو",
        "script": "Perso-Arabic",
        "region": "Pan-India & Northern Regions",
        "flag": "🇮🇳",
        "speech_code": "ur-IN",
        "greeting": "خوش آمدید! گرام کیئر اے آئی میں آپ کا خیر مقدم ہے"
    }
]

LANG_MAP = {lang["code"]: lang for lang in LANGUAGES}

# Chhattisgarhi rural dialect phrase transformations
CHHATTISGARHI_DIALECT_RULES = [
    (r"नमस्ते|प्रणाम", "जय जोहार"),
    (r"आपका स्वागत है", "आपमन के स्वागत हे"),
    (r"कैसे हैं|कैसी हैं", "कइसन हव"),
    (r"दर्द|पीड़ा", "पीरा"),
    (r"खांसी|खाँसी", "खोंखी"),
    (r"बुखार", "तपन / बुखार"),
    (r"पेट दर्द", "पेट पीरा"),
    (r"सिर दर्द", "माथा पीरा"),
    (r"कमजोरी", "सुस्त लगना"),
    (r"उल्टी", "उलटी / छेंक"),
    (r"दस्त", "झड़ाव / दस्त"),
    (r"दवाएं|दवाइयां|दवा", "दवाई"),
    (r"कीजिए|करें", "करव"),
    (r"लीजिए|लें", "लेवव"),
    (r"जाएं|जाइए", "जावव"),
    (r"खाइए|खाएं", "खवव"),
    (r"रखें", "रखव"),
    (r"रहें", "रहव"),
    (r"आशा कार्यकर्ता", "मितानिन (आशा कार्यकर्ता)"),
    (r"अस्पताल", "अस्पताल / अस्पताल"),
    (r"तुरंत", "तुरते"),
    (r"पानी", "पानी"),
    (r"पीजिए", "पीवव"),
    (r"हैं|है", "हे"),
    (r"नहीं", "नइ"),
    (r"बहुत", "जबर / बहुत"),
]

# Bhojpuri rural dialect phrase transformations
BHOJPURI_DIALECT_RULES = [
    (r"नमस्ते", "प्रणाम"),
    (r"स्वागत है", "स्वागत बा"),
    (r"दर्द|पीड़ा", "दरद"),
    (r"खांसी", "खोंखी"),
    (r"दवाएं|दवा", "दवाई"),
    (r"कीजिए|करें", "करीं"),
    (r"लीजिए|लें", "लीं"),
    (r"जाएं|जाइए", "जाईं"),
    (r"खाइए|खाएं", "खाईं"),
    (r"है", "बा"),
    (r"हैं", "बाड़ीं"),
    (r"नहीं", "नाहीं"),
    (r"तुरंत", "झटपट / तुरंते"),
]

def apply_dialect_rules(text: str, dialect: str) -> str:
    import re
    if dialect == "cg":
        for pattern, repl in CHHATTISGARHI_DIALECT_RULES:
            text = re.sub(pattern, repl, text)
    elif dialect == "bho":
        for pattern, repl in BHOJPURI_DIALECT_RULES:
            text = re.sub(pattern, repl, text)
    return text


# --- Built-in Localized Dictionaries for Instant Zero-Latency UI Rendering ---
UI_DICTIONARIES: Dict[str, Dict[str, str]] = {
    "en": {
        "app_title": "GramCare AI",
        "tagline": "Rural Healthcare Decision-Support",
        "nav_triage": "Triage Studio",
        "nav_patients": "Patient Registry",
        "nav_analytics": "Outbreak Analytics",
        "nav_about": "About System",
        "status_ml_active": "ML Active",
        "role_asha_title": "ASHA Worker & Kiosk Mode",
        "role_asha_subtext": "Record patient intake, conduct voice symptom triage, detect recurring chronic symptoms, and issue referral slips.",
        "role_patient_title": "Patient Self-Service Mode",
        "role_patient_subtext": "Check symptoms at home, view family health records, and connect directly to teleconsultation doctors.",
        "btn_switch_patient": "Switch to Patient Mode",
        "btn_switch_asha": "Switch to ASHA Mode",
        "patient_card_title": "Patient Profile & Identification",
        "lbl_search": "Search Existing Patient (Name / Phone / Village)",
        "lbl_name": "Full Name *",
        "lbl_phone": "Mobile Number",
        "lbl_village": "Village / Gram *",
        "lbl_age": "Age",
        "lbl_gender": "Gender",
        "gender_male": "Male",
        "gender_female": "Female",
        "gender_other": "Other",
        "clinical_safety": "Clinical Safety Screening:",
        "chk_pregnant": "Pregnant / Maternal Care",
        "chk_diabetic": "Diabetic",
        "chk_hypertension": "Hypertension / BP",
        "chk_asthma": "Asthma",
        "lbl_allergies": "Known Drug Allergies (Omit Incompatible Generic Medicines):",
        "symptom_card_title": "Symptom Input & Voice Assistant",
        "voice_tap_to_speak": "Tap Microphone and Speak Symptoms",
        "voice_listening": "Listening... Speak symptoms clearly",
        "voice_subtext": "Supports Chhattisgarhi, Hindi, English, and regional Indian dialects",
        "lbl_symptoms": "Reported Symptoms Description *",
        "lbl_quick_chips": "Common Rural Symptoms (Click to Add):",
        "btn_submit": "Run AI Triage & Risk Assessment",
        "empty_heading": "Ready for Triage Analysis",
        "empty_subtext": "Enter symptoms by voice or text and click 'Run AI Triage' to generate clinical risk level, matched condition, precautions, and generic medicine alternatives.",
        "loading_heading": "Analyzing Symptoms with Machine Learning...",
        "loading_subtext": "Vectorizing features & evaluating longitudinal history...",
        "emergency_title": "EMERGENCY MEDICAL OVERRIDE ACTIVATED",
        "emergency_body": "Critical life-threatening symptom detected! Bypassing non-urgent triage. Arrange immediate 108 Emergency Ambulance transport to Primary Health Centre (PHC) or District Hospital without delay.",
        "risk_high": "HIGH RISK",
        "risk_medium": "MEDIUM RISK",
        "risk_low": "LOW RISK",
        "risk_high_sub": "Immediate Medical Attention Required",
        "risk_medium_sub": "Clinical Evaluation Required (Doctor Teleconsultation Standby)",
        "risk_low_sub": "Primary Care / Monitored Home Care",
        "telemed_online_doctor": "ONLINE DOCTOR ON STANDBY",
        "telemed_connect_btn": "Connect to Doctor Online (Live Video Call)",
        "telemed_copy_link": "Copy Call Link",
        "explain_title": "Clinical Risk Rationale (Why this Risk was Assigned):",
        "differential_title": "Top Differential Diagnoses",
        "action_advice_title": "Action Advice:",
        "precautions_title": "Clinical Precautions:",
        "generic_meds_title": "Affordable Generic Alternatives",
        "jan_aushadhi_badge": "Jan Aushadhi Scheme",
        "referral_title": "Referral Guidance Slip",
        "btn_print_slip": "Print / Save Consultation Report",
        "btn_view_timeline": "View Health Timeline",
        "lang_selector_title": "Language & Regional Dialect",
        "lang_search_placeholder": "Search languages (e.g. Chhattisgarhi, Hindi, বাংলা)...",
        "translate_report_btn": "Translate Clinical Report"
    },
    "hi": {
        "app_title": "ग्रामकेयर एआई",
        "tagline": "ग्रामीण स्वास्थ्य सहायता प्रणाली",
        "nav_triage": "ट्राइएज स्टूडियो",
        "nav_patients": "मरीज सूची",
        "nav_analytics": "प्रकोप निगरानी",
        "nav_about": "प्रणाली के बारे में",
        "status_ml_active": "मशीन लर्निंग सक्रिय",
        "role_asha_title": "आशा कार्यकर्ता व कियोस्क मोड",
        "role_asha_subtext": "मरीज का विवरण दर्ज करें, आवाज द्वारा लक्षण जांचें, बार-बार होने वाले लक्षणों की पहचान करें और रेफरल पर्ची जारी करें।",
        "role_patient_title": "मरीज स्व-सेवा मोड",
        "role_patient_subtext": "घर पर लक्षण जांचें, पारिवारिक स्वास्थ्य इतिहास देखें और ऑनलाइन डॉक्टरों से सीधे परामर्श लें।",
        "btn_switch_patient": "मरीज मोड में बदलें",
        "btn_switch_asha": "आशा मोड में बदलें",
        "patient_card_title": "मरीज का विवरण व पहचान",
        "lbl_search": "पुराने मरीज को खोजें (नाम / मोबाइल / गाँव)",
        "lbl_name": "मरीज का पूरा नाम *",
        "lbl_phone": "मोबाइल नंबर",
        "lbl_village": "गाँव / ग्राम *",
        "lbl_age": "उम्र",
        "lbl_gender": "लिंग",
        "gender_male": "पुरुष",
        "gender_female": "महिला",
        "gender_other": "अन्य",
        "clinical_safety": "चिकित्सीय सुरक्षा जांच:",
        "chk_pregnant": "गर्भवती / मातृ देखभाल",
        "chk_diabetic": "मधुमेह (शुगर)",
        "chk_hypertension": "उच्च रक्तचाप (बीपी)",
        "chk_asthma": "दमा / अस्थमा",
        "lbl_allergies": "ज्ञात दवा एलर्जी (असंगत जेनेरिक दवाएं न दें):",
        "symptom_card_title": "लक्षण विवरण व आवाज सहायक",
        "voice_tap_to_speak": "माइक दबाकर लक्षण बोलें",
        "voice_listening": "सुन रहे हैं... लक्षण स्पष्ट बोलें",
        "voice_subtext": "छत्तीसगढ़ी, हिन्दी, अंग्रेजी और क्षेत्रीय बोलियों में उपलब्ध",
        "lbl_symptoms": "लक्षणों का विवरण *",
        "lbl_quick_chips": "सामान्य ग्रामीण लक्षण (जोड़ने के लिए क्लिक करें):",
        "btn_submit": "एआई जांच व जोखिम मूल्यांकन करें",
        "empty_heading": "लक्षण जांच के लिए तैयार",
        "empty_subtext": "आवाज या लिखकर लक्षण दर्ज करें और 'एआई जांच करें' दबाएं। तुरंत जोखिम स्तर, बीमारी, सावधानियां और सस्ती जेनेरिक दवाएं प्राप्त करें।",
        "loading_heading": "मशीन लर्निंग द्वारा लक्षणों का विश्लेषण जारी है...",
        "loading_subtext": "लक्षणों का मिलान व पूर्व इतिहास की जांच हो रही है...",
        "emergency_title": "आपातकालीन चिकित्सा चेतावनी सक्रिय",
        "emergency_body": "गंभीर जानलेवा लक्षण पाया गया! सामान्य प्रक्रिया को रोककर तत्काल 108 एम्बुलेंस से मरीज को प्राथमिक स्वास्थ्य केंद्र या जिला अस्पताल भेजें।",
        "risk_high": "उच्च जोखिम (High Risk)",
        "risk_medium": "मध्यम जोखिम (Medium Risk)",
        "risk_low": "कम जोखिम (Low Risk)",
        "risk_high_sub": "तत्काल डॉक्टरी देखभाल आवश्यक",
        "risk_medium_sub": "डॉक्टरी जांच आवश्यक (ऑनलाइन डॉक्टर तैयार)",
        "risk_low_sub": "प्राथमिक देखभाल / घरेलू निगरानी",
        "telemed_online_doctor": "ऑनलाइन डॉक्टर तैयार हैं",
        "telemed_connect_btn": "डॉक्टर से लाइव वीडियो परामर्श शुरू करें",
        "telemed_copy_link": "परामर्श लिंक कॉपी करें",
        "explain_title": "जोखिम निर्धारण का कारण (एआई स्पष्टीकरण):",
        "differential_title": "संभावित मुख्य बीमारियां",
        "action_advice_title": "चिकित्सीय सलाह:",
        "precautions_title": "आवश्यक सावधानियां:",
        "generic_meds_title": "किफायती जेनेरिक दवाएं",
        "jan_aushadhi_badge": "जन औषधि योजना",
        "referral_title": "रेफरल व परामर्श पर्ची",
        "btn_print_slip": "परामर्श पर्ची प्रिंट / सुरक्षित करें",
        "btn_view_timeline": "स्वास्थ्य इतिहास देखें",
        "lang_selector_title": "भाषा व क्षेत्रीय बोली",
        "lang_search_placeholder": "भाषा खोजें (जैसे छत्तीसगढ़ी, हिन्दी, বাংলা)...",
        "translate_report_btn": "रिपोर्ट का अनुवाद करें"
    },
    "cg": {
        "app_title": "ग्रामकेयर एआई",
        "tagline": "गाँव-गंवाई स्वास्थ्य सहायता प्रणाली",
        "nav_triage": "ट्राइएज स्टूडियो",
        "nav_patients": "मरीज रजिस्टर",
        "nav_analytics": "बीमारी निगरानी",
        "nav_about": "प्रणाली के बारे म",
        "status_ml_active": "एआई सक्रिय हे",
        "role_asha_title": "मितानिन (आशा) व कियोस्क मोड",
        "role_asha_subtext": "मरीज के नाम-गाँव लिखव, गोठिया के लक्षण जांचव, पुरना बीमारी देखव अउ अस्पताल बर रेफरल पर्ची बनावव।",
        "role_patient_title": "मरीज स्व-सेवा मोड",
        "role_patient_subtext": "घर बइठे लक्षण जांचव, परिवार के स्वास्थ्य इतिहास देखव अउ फोन/वीडियो म डाक्टर ले गोठियावव।",
        "btn_switch_patient": "मरीज मोड म जावव",
        "btn_switch_asha": "मितानिन मोड म जावव",
        "patient_card_title": "मरीज के विवरण अउ पहचान",
        "lbl_search": "पुरना मरीज खोजव (नाम / मोबाइल / गाँव)",
        "lbl_name": "मरीज के पूरा नाम *",
        "lbl_phone": "मोबाइल नंबर",
        "lbl_village": "गाँव / पारा / ग्राम *",
        "lbl_age": "उमर (साल)",
        "lbl_gender": "लिंग",
        "gender_male": "पुरुस",
        "gender_female": "माईलोग (महिला)",
        "gender_other": "अउ दूसर",
        "clinical_safety": "स्वास्थ्य सुरक्षा जांच:",
        "chk_pregnant": "दाई-माई गर्भवती हे (जचकी)",
        "chk_diabetic": "सुगर बीमारी (मधुमेह)",
        "chk_hypertension": "बीपी (ब्लड प्रेसर)",
        "chk_asthma": "दमा / सांस फूले",
        "lbl_allergies": "कोनो दवाई ले एलर्जी (जेनेरिक दवाई छांटे बर):",
        "symptom_card_title": "लक्षण बताओ अउ आवाज सहायक",
        "voice_tap_to_speak": "माइक दबा के लक्षण बोलव",
        "voice_listening": "सुनत हन... साफ-साफ लक्षण बोलव",
        "voice_subtext": "छत्तीसगढ़ी, हिन्दी अउ अंग्रेजी म गोठिया सकत हव",
        "lbl_symptoms": "का-का तकलीफ हे, विस्तार ले बतावव *",
        "lbl_quick_chips": "गाँव-घर के आम लक्षण (जोड़े बर दबाएं):",
        "btn_submit": "एआई जांच अउ जोखिम मूल्यांकन करव",
        "empty_heading": "लक्षण जांचे बर तइयार हे",
        "empty_subtext": "बोल के या लिख के लक्षण दर्ज करव अउ 'एआई जांच करव' दबाएं। तुरंत बीमारी, परहेज़ अउ जन औषधि के सस्ती दवाई मिलही।",
        "loading_heading": "एआई ले लक्षण के जांच चलत हे...",
        "loading_subtext": "लक्षण मिलावत हन अउ पुरना बीमारी के जांच करत हन...",
        "emergency_title": "🚨 भारी आपातकालीन चेतावनी - तुरते अस्पताल ले जावव!",
        "emergency_body": "मरीज के जान जोखिम म हे! तुरते 108 एम्बुलेंस बुला के अस्पताल या पीएससी (PHC) ले जावव। एक घड़ी के घलो देरी झन करव।",
        "risk_high": "जबर जोखिम (High Risk)",
        "risk_medium": "मंझोला जोखिम (Medium Risk)",
        "risk_low": "कम जोखिम (Low Risk)",
        "risk_high_sub": "तुरते डाक्टर ले जांच कराना जरूरी हे",
        "risk_medium_sub": "डाक्टर के सलाह जरूरी हे (वीडियो कॉल म डाक्टर उपलब्ध हे)",
        "risk_low_sub": "साधारण देखभाल / घर म आराम करव",
        "telemed_online_doctor": "ऑनलाइन डाक्टर तइयार हें",
        "telemed_connect_btn": "डाक्टर ले लाइव वीडियो गोठ-बात करव",
        "telemed_copy_link": "वीडियो कॉल लिंक कापी करव",
        "explain_title": "जोखिम के कारन (एआई स्पष्टीकरण):",
        "differential_title": "संभावित बीमारी के नाम",
        "action_advice_title": "सलाह अउ उपाय:",
        "precautions_title": "का-का परहेज़ करना हे:",
        "generic_meds_title": "सस्ती जन औषधि जेनेरिक दवाई",
        "jan_aushadhi_badge": "प्रधानमंत्री जन औषधि केंद्र",
        "referral_title": "अस्पताल बर रेफरल पर्ची",
        "btn_print_slip": "पर्ची प्रिंट / सुरक्षित करव",
        "btn_view_timeline": "स्वास्थ्य इतिहास देखव",
        "lang_selector_title": "भाखा अउ बोली चुनो",
        "lang_search_placeholder": "भाखा खोजव (जैसे छत्तीसगढ़ी, हिन्दी, বাংলা)...",
        "translate_report_btn": "पर्ची के अनुवाद करव"
    },
    "bn": {
        "app_title": "গ্রামকেয়ার এআই",
        "tagline": "গ্রামীণ স্বাস্থ্যসেবা সহায়তা ব্যবস্থা",
        "nav_triage": "ট্রায়াজ স্টুডিও",
        "nav_patients": "রোগীর তালিকা",
        "nav_analytics": "প্রাদুর্ভাব নজরদারি",
        "nav_about": "সিস্টেম সম্পর্কে",
        "status_ml_active": "এমএল সক্রিয়",
        "role_asha_title": "আশা কর্মী ও কিয়স্ক মোড",
        "role_asha_subtext": "রোগীর তথ্য নথিভুক্ত করুন, ভয়েস উপসর্গ ট্রায়াজ করুন এবং রেফারেল স্লিপ তৈরি করুন।",
        "role_patient_title": "রোগী স্ব-পরিষেবা মোড",
        "role_patient_subtext": "বাড়িতে উপসর্গ পরীক্ষা করুন, পারিবারিক স্বাস্থ্য রেকর্ড দেখুন এবং চিকিৎসকদের সাথে পরামর্শ করুন।",
        "btn_switch_patient": "রোগী মোডে যান",
        "btn_switch_asha": "আশা মোডে যান",
        "patient_card_title": "রোগীর প্রোফাইল ও পরিচয়",
        "lbl_search": "বিদ্যমান রোগী খুঁজুন (নাম / ফোন / গ্রাম)",
        "lbl_name": "রোগীর পুরো নাম *",
        "lbl_phone": "মোবাইল নম্বর",
        "lbl_village": "গ্রাম *",
        "lbl_age": "বয়স",
        "lbl_gender": "লিঙ্গ",
        "gender_male": "পুরুষ",
        "gender_female": "মহিলা",
        "gender_other": "অন্যান্য",
        "clinical_safety": "ক্লিনিকাল সুরক্ষা পরীক্ষা:",
        "chk_pregnant": "গর্ভবতী / মাতৃত্বকালীন যত্ন",
        "chk_diabetic": "ডায়াবেটিস (সুগার)",
        "chk_hypertension": "উচ্চ রক্তচাপ (বিপি)",
        "chk_asthma": "হাঁপানি / অ্যাজমা",
        "lbl_allergies": "ওষুধে পরিচিত অ্যালার্জি:",
        "symptom_card_title": "উপসর্গ ইনপুট ও ভয়েস সহকারী",
        "voice_tap_to_speak": "মাইক চেপে উপসর্গ বলুন",
        "voice_listening": "শুনছি... স্পষ্টভাবে উপসর্গ বলুন",
        "voice_subtext": "বাংলা, হিন্দি, ইংরেজি এবং আঞ্চলিক ভাষায় সমর্থিত",
        "lbl_symptoms": "উপসর্গের বিবরণ *",
        "lbl_quick_chips": "সাধারণ গ্রামীণ উপসর্গ (যুক্ত করতে ক্লিক করুন):",
        "btn_submit": "এআই ট্রায়াজ ও ঝুঁকি মূল্যায়ন চালান",
        "empty_heading": "ট্রায়াজ বিশ্লেষণের জন্য প্রস্তুত",
        "empty_subtext": "ভয়েস বা টেক্সটে উপসর্গ লিখে 'এআই ট্রায়াজ চালান' বাটনে ক্লিক করুন।",
        "loading_heading": "মেশিন লার্নিং দ্বারা উপসর্গ বিশ্লেষণ চলছে...",
        "loading_subtext": "বৈশিষ্ট্য বিশ্লেষণ ও ইতিহাস যাচাই করা হচ্ছে...",
        "emergency_title": "🚨 জরুরি মেডিকেল ওভাররাইড সক্রিয়",
        "emergency_body": "মারাত্মক উপসর্গ সনাক্ত হয়েছে! অবিলম্বে ১০৮ অ্যাম্বুলেন্সে প্রাথমিক স্বাস্থ্য কেন্দ্র বা জেলা হাসপাতালে নিয়ে যান।",
        "risk_high": "উচ্চ ঝুঁকি (HIGH RISK)",
        "risk_medium": "মাঝারি ঝুঁকি (MEDIUM RISK)",
        "risk_low": "কম ঝুঁকি (LOW RISK)",
        "risk_high_sub": "অবিলম্বে চিকিৎসকের পরামর্শ প্রয়োজন",
        "risk_medium_sub": "ক্লিনিকাল মূল্যায়ন প্রয়োজন (অনলাইন ডাক্তার প্রস্তুত)",
        "risk_low_sub": "প্রাথমিক যত্ন / গৃহ পর্যবেক্ষণ",
        "telemed_online_doctor": "অনলাইন ডাক্তার প্রস্তুত আছেন",
        "telemed_connect_btn": "অনলাইন ডাক্তারের সাথে ভিডিও কল শুরু করুন",
        "telemed_copy_link": "ভিডিও কল লিঙ্ক কপি করুন",
        "explain_title": "ঝুঁকি মূল্যায়নের কারণ:",
        "differential_title": "সম্ভাব্য রোগসমূহ",
        "action_advice_title": "চিকিৎসা সংক্রান্ত পরামর্শ:",
        "precautions_title": "প্রয়োজনীয় সতর্কতা:",
        "generic_meds_title": "সাশ্রয়ী জেনেরিক ওষুধ",
        "jan_aushadhi_badge": "জন ঔষধি যোজনা",
        "referral_title": "রেফারেল নির্দেশিকা স্লিপ",
        "btn_print_slip": "প্রতিবেদন প্রিন্ট / সেভ করুন",
        "btn_view_timeline": "স্বাস্থ্য ইতিহাস দেখুন",
        "lang_selector_title": "ভাষা ও উপভাষা নির্বাচন",
        "lang_search_placeholder": "ভাষা খুঁজুন...",
        "translate_report_btn": "রিপোর্ট অনুবাদ করুন"
    },
    "mr": {
        "app_title": "ग्रामकेअर एआय",
        "tagline": "ग्रामीण आरोग्य निर्णय-सहाय्य प्रणाली",
        "nav_triage": "ट्रायज स्टुडिओ",
        "nav_patients": "रुग्ण नोंदणी",
        "nav_analytics": "साथीचे विश्लेषण",
        "nav_about": "प्रणालीबद्दल माहिती",
        "status_ml_active": "एमएल सक्रिय",
        "role_asha_title": "आशा सेविका व किओस्क मोड",
        "role_asha_subtext": "रुग्णाची नोंदणी करा, आवाजाद्वारे लक्षणे तपासा, जुनी लक्षणे ओळखा आणि रेफरल स्लिप जारी करा.",
        "role_patient_title": "रुग्ण स्व-सेवा मोड",
        "role_patient_subtext": "घरी बसून लक्षणे तपासा, कौटुंबिक आरोग्य नोंदी पहा आणि डॉक्टरांशी संपर्क साधा.",
        "btn_switch_patient": "रुग्ण मोड निवडा",
        "btn_switch_asha": "आशा मोड निवडा",
        "patient_card_title": "रुग्ण तपशील व ओळख",
        "lbl_search": "मागील रुग्ण शोधा (नाव / फोन / गाव)",
        "lbl_name": "रुग्णाचे पूर्ण नाव *",
        "lbl_phone": "मोबाईल नंबर",
        "lbl_village": "गाव / ग्राम *",
        "lbl_age": "वय",
        "lbl_gender": "लिंग",
        "gender_male": "पुरुष",
        "gender_female": "महिला",
        "gender_other": "इतर",
        "clinical_safety": "वैद्यकीय सुरक्षा तपासणी:",
        "chk_pregnant": "गर्भवती / मातृत्व काळजी",
        "chk_diabetic": "मधुमेह (डायबेटिस)",
        "chk_hypertension": "उच्च रक्तदाब (बीपी)",
        "chk_asthma": "दमा / अस्थमा",
        "lbl_allergies": "ज्ञात औषध ऍलर्जी:",
        "symptom_card_title": "लक्षण नोंद व व्हॉईस सहाय्यक",
        "voice_tap_to_speak": "माइक दाबून लक्षणे सांगा",
        "voice_listening": "ऐकत आहोत... लक्षणे स्पष्ट सांगा",
        "voice_subtext": "मराठी, हिंदी, इंग्रजी आणि स्थानिक भाषांमध्ये उपलब्ध",
        "lbl_symptoms": "लक्षणे सांगा *",
        "lbl_quick_chips": "सामान्य ग्रामीण लक्षणे:",
        "btn_submit": "एआय ट्रायज व जोखीम मूल्यांकन करा",
        "empty_heading": "ट्रायज विश्लेषणासाठी सज्ज",
        "empty_subtext": "आवाजाने किंवा लिहून लक्षणे प्रविष्ट करा आणि 'एआय ट्रायज करा' वर क्लिक करा.",
        "loading_heading": "लक्षण विश्लेषित होत आहेत...",
        "loading_subtext": "वैद्यकीय इतिहास तपासला जात आहे...",
        "emergency_title": "🚨 तातडीची वैद्यकीय आणीबाणी सक्रिय",
        "emergency_body": "गंभीर लक्षण आढळले! त्वरित १०८ रुग्णवाहिकेद्वारे रुग्णालयात हलवा.",
        "risk_high": "उच्च जोखीम (HIGH RISK)",
        "risk_medium": "मध्यम जोखीम (MEDIUM RISK)",
        "risk_low": "कमी जोखीम (LOW RISK)",
        "risk_high_sub": "तातडीने डॉक्टरांचा सल्ला आवश्यक",
        "risk_medium_sub": "वैद्यकीय तपासणी आवश्यक (डॉक्टर ऑनलाइन उपलब्ध)",
        "risk_low_sub": "प्राथमिक काळजी / घरी विश्रांती",
        "telemed_online_doctor": "ऑनलाइन डॉक्टर सज्ज आहेत",
        "telemed_connect_btn": "डॉक्टरांशी व्हिडिओ कॉल सुरू करा",
        "telemed_copy_link": "कॉल लिंक कॉपी करा",
        "explain_title": "जोखीम निश्चित करण्याचे कारण:",
        "differential_title": "संभाव्य आजार",
        "action_advice_title": "वैद्यकीय सल्ला:",
        "precautions_title": "आवश्यक खबरदारी:",
        "generic_meds_title": "किफायतशीर जेनेरिक औषधे",
        "jan_aushadhi_badge": "जन औषधी योजना",
        "referral_title": "रेफरल स्लिप",
        "btn_print_slip": "अहवाल मुद्रित करा / सेव्ह करा",
        "btn_view_timeline": "आरोग्य इतिहास पहा",
        "lang_selector_title": "भाषा व बोली निवडा",
        "lang_search_placeholder": "भाषा शोधा...",
        "translate_report_btn": "अहवालाचे भाषांतर करा"
    },
    "te": {
        "app_title": "గ్రామ్‌కేర్ AI",
        "tagline": "గ్రామీణ ఆరోగ్య సంరక్షణ నిర్ణయ మద్దతు",
        "nav_triage": "ట్రయాజ్ స్టూడియో",
        "nav_patients": "రోగుల రిజిస్ట్రీ",
        "nav_analytics": "వ్యాధి వ్యాప్తి విశ్లేషణ",
        "nav_about": "సిస్టమ్ గురించి",
        "status_ml_active": "ML సక్రియం",
        "role_asha_title": "ఆశా వర్కర్ & కియోస్క్ మోడ్",
        "role_asha_subtext": "రోగి వివరాలను నమోదు చేయండి, వాయిస్ ద్వారా లక్షణాలను తనిఖీ చేయండి మరియు రిఫరల్ స్లిప్‌ను జారీ చేయండి.",
        "role_patient_title": "రోగి స్వీయ సేవా మోడ్",
        "role_patient_subtext": "ఇంట్లోనే లక్షణాలను తనిఖీ చేసుకోండి, కుటుంబ ఆరోగ్య రికార్డులను వీక్షించండి మరియు డాక్టర్లను సంప్రదించండి.",
        "btn_switch_patient": "పేషెంట్ మోడ్‌కి మారండి",
        "btn_switch_asha": "ఆశా మోడ్‌కి మారండి",
        "patient_card_title": "రోగి ప్రొఫైల్ & గుర్తింపు",
        "lbl_search": "రోగిని శోధించండి (పేరు / ఫోన్ / గ్రామం)",
        "lbl_name": "రోగి పూర్తి పేరు *",
        "lbl_phone": "మొబైల్ నంబర్",
        "lbl_village": "గ్రామం *",
        "lbl_age": "వయస్సు",
        "lbl_gender": "లింగం",
        "gender_male": "పురుషుడు",
        "gender_female": "మహిళ",
        "gender_other": "ఇతర",
        "clinical_safety": "క్లినికల్ భద్రతా పరీక్ష:",
        "chk_pregnant": "గర్భిణీ / మాతా శిశు సంరక్షణ",
        "chk_diabetic": "డయాబెటిస్ (షుగర్)",
        "chk_hypertension": "రక్తపోటు (బీపీ)",
        "chk_asthma": "ఉబ్బసం / ఆస్తమా",
        "lbl_allergies": "ఔషధ అలెర్జీలు:",
        "symptom_card_title": "లక్షణాల నమోదు & వాయిస్ అసిస్టెంట్",
        "voice_tap_to_speak": "మైక్ నొక్కి లక్షణాలను మాట్లాడండి",
        "voice_listening": "వింటున్నాము... స్పష్టంగా మాట్లాడండి",
        "voice_subtext": "తెలుగు, హిందీ, ఇంగ్లీష్ భాషలలో లభ్యం",
        "lbl_symptoms": "లక్షణాల వివరణ *",
        "lbl_quick_chips": "సాధారణ గ్రామీణ లక్షణాలు:",
        "btn_submit": "AI ట్రయాజ్ & ప్రమాద అంచనా వేయండి",
        "empty_heading": "ట్రయాజ్ విశ్లేషణకు సిద్ధంగా ఉంది",
        "empty_subtext": "లక్షణాలను నమోదు చేసి 'AI ట్రయాజ్ వేయండి' క్లిక్ చేయండి.",
        "loading_heading": "లక్షణాలను విశ్లేషిస్తున్నాము...",
        "loading_subtext": "చరిత్ర మరియు లక్షణాలను సరిపోలుస్తున్నాము...",
        "emergency_title": "🚨 అత్యవసర వైద్య హెచ్చరిక",
        "emergency_body": "తీవ్రమైన ప్రాణాంతక లక్షణం కనుగొనబడింది! వెంటనే 108 అంబులెన్స్ ద్వారా ఆసుపత్రికి తరలించండి.",
        "risk_high": "అధిక ప్రమాదం (HIGH RISK)",
        "risk_medium": "మధ్యస్థ ప్రమాదం (MEDIUM RISK)",
        "risk_low": "తక్కువ ప్రమాదం (LOW RISK)",
        "risk_high_sub": "వెంటనే డాక్టర్ సంరక్షణ అవసరం",
        "risk_medium_sub": "వైద్య పరీక్ష అవసరం (ఆన్‌లైన్ డాక్టర్ సిద్ధం)",
        "risk_low_sub": "ప్రాథమిక సంరక్షణ / ఇంట్లో విశ్రాంతి",
        "telemed_online_doctor": "ఆన్‌లైన్ డాక్టర్ సిద్ధంగా ఉన్నారు",
        "telemed_connect_btn": "డాక్టర్‌తో లైవ్ వీడియో సంప్రదింపు ప్రారంభించండి",
        "telemed_copy_link": "కాల్ లింక్ కాపీ చేయండి",
        "explain_title": "ప్రమాద నిర్ణయానికి కారణం:",
        "differential_title": "సంభావ్య వ్యాధులు",
        "action_advice_title": "వైద్య సలహా:",
        "precautions_title": "తీసుకోవలసిన జాగ్రత్తలు:",
        "generic_meds_title": "చవకైన జెనరిక్ మందులు",
        "jan_aushadhi_badge": "జన్ ఔషధి పథకం",
        "referral_title": "రిఫరల్ స్లిప్",
        "btn_print_slip": "నివేదికను ముద్రించండి / సేవ్ చేయండి",
        "btn_view_timeline": "ఆరోగ్య చరిత్రను చూడండి",
        "lang_selector_title": "భాషను ఎంచుకోండి",
        "lang_search_placeholder": "భాషను శోధించండి...",
        "translate_report_btn": "నివేదికను అనువదించండి"
    }
}

# Duplicate helper for other languages falling back gracefully
for lcode in ["gu", "or", "pa", "kn", "ml", "bho", "ur"]:
    if lcode not in UI_DICTIONARIES:
        # Create dialect-aware baseline from Hindi/English
        base = dict(UI_DICTIONARIES["hi"])
        if lcode == "bho":
            for k, v in base.items():
                base[k] = apply_dialect_rules(v, "bho")
        UI_DICTIONARIES[lcode] = base


# --- Translation Provider Implementations ---

def translate_with_gemini(text: str, target_lang: str, source_lang: str = "auto") -> Optional[str]:
    """Call Google Gemini API if GEMINI_API_KEY is available."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None

    target_info = LANG_MAP.get(target_lang, {"name": target_lang, "native_name": target_lang})
    prompt = (
        f"You are a compassionate, accurate medical healthcare translator specializing in rural Indian healthcare and vernacular languages. "
        f"Translate the following medical/UI text into {target_info['name']} ({target_info['native_name']}). "
        f"Ensure medical accuracy and natural phrasing for rural community members and ASHA workers. "
        f"Return ONLY the translated text, no quotes or explanations.\n\n"
        f"Text to translate:\n{text}"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024}
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
    except Exception as e:
        print(f"[Gemini Translate] Error: {e}")
    return None

def translate_with_deepl(text: str, target_lang: str) -> Optional[str]:
    """Call DeepL API if DEEPL_API_KEY is available."""
    api_key = os.environ.get("DEEPL_API_KEY")
    if not api_key:
        return None

    endpoint = "https://api-free.deepl.com/v2/translate" if api_key.endswith(":fx") else "https://api.deepl.com/v2/translate"
    # DeepL target lang mapping (uppercase)
    target_code = target_lang.upper()
    if target_code == "EN":
        target_code = "EN-US"

    try:
        data = urllib.parse.urlencode({
            "text": text,
            "target_lang": target_code
        }).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={
                "Authorization": f"DeepL-Auth-Key {api_key}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            translations = res.get("translations", [])
            if translations:
                return translations[0].get("text", "").strip()
    except Exception as e:
        print(f"[DeepL Translate] Error: {e}")
    return None

def translate_with_openai(text: str, target_lang: str) -> Optional[str]:
    """Call OpenAI API if OPENAI_API_KEY is available."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    target_info = LANG_MAP.get(target_lang, {"name": target_lang})
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": f"You are a medical healthcare translator. Translate the text into {target_info['name']}. Return only translated text without quotes."
            },
            {"role": "user", "content": text}
        ],
        "temperature": 0.2
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        print(f"[OpenAI Translate] Error: {e}")
    return None

def translate_with_google_free(text: str, target_lang: str, source_lang: str = "auto") -> Optional[str]:
    """
    Translate text using the reliable Google Translate API endpoint.
    Handles dialect mapping (cg -> hi with dialect post-processing, bho -> hi with bho post-processing).
    """
    # Map dialect codes that Google Translate doesn't directly support to base language
    effective_target = target_lang
    if target_lang in ["cg", "bho"]:
        effective_target = "hi"

    encoded = urllib.parse.quote(text)
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source_lang}&tl={effective_target}&dt=t&q={encoded}"

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            # Response is array of sentences: [[["translated", "source", ...], ...], ...]
            translated_pieces = []
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                for piece in data[0]:
                    if isinstance(piece, list) and len(piece) > 0 and piece[0]:
                        translated_pieces.append(piece[0])
            if translated_pieces:
                result = "".join(translated_pieces).strip()
                # If target is Chhattisgarhi or Bhojpuri, apply regional vocabulary transforms
                if target_lang in ["cg", "bho"]:
                    result = apply_dialect_rules(result, target_lang)
                return result
    except Exception as e:
        print(f"[Google Free Translate] Error: {e}")
    return None

def perform_translation(
    text: str,
    target_lang: str,
    source_lang: str = "auto",
    preferred_provider: str = "auto"
) -> Dict[str, Any]:
    """
    Translate a single text string using the best available provider with caching.
    """
    clean_text = text.strip()
    if not clean_text:
        return {"translated_text": "", "provider": "noop", "cached": True}

    if target_lang == source_lang or (source_lang == "en" and target_lang == "en"):
        return {"translated_text": clean_text, "provider": "noop", "cached": True}

    # 1. Check SQLite Translation Cache
    cached = get_cached_translation(clean_text, source_lang, target_lang)
    if cached:
        return {"translated_text": cached, "provider": "cache", "cached": True}

    # 2. Check Static Dictionary if available
    dict_for_target = UI_DICTIONARIES.get(target_lang, {})
    # Match text with dictionary values or keys
    for k, v in dict_for_target.items():
        en_val = UI_DICTIONARIES.get("en", {}).get(k, "")
        if clean_text.lower() == en_val.lower():
            set_cached_translation(clean_text, source_lang, target_lang, v, provider="static_dictionary")
            return {"translated_text": v, "provider": "static_dictionary", "cached": False}

    # 3. Provider Dispatch
    result = None
    provider_used = "static"

    if preferred_provider == "gemini" or (preferred_provider == "auto" and os.environ.get("GEMINI_API_KEY")):
        result = translate_with_gemini(clean_text, target_lang, source_lang)
        if result:
            provider_used = "gemini"

    if not result and (preferred_provider == "openai" or (preferred_provider == "auto" and os.environ.get("OPENAI_API_KEY"))):
        result = translate_with_openai(clean_text, target_lang)
        if result:
            provider_used = "openai"

    if not result and (preferred_provider == "deepl" or (preferred_provider == "auto" and os.environ.get("DEEPL_API_KEY"))):
        result = translate_with_deepl(clean_text, target_lang)
        if result:
            provider_used = "deepl"

    if not result and preferred_provider in ["auto", "google", "free"]:
        result = translate_with_google_free(clean_text, target_lang, source_lang)
        if result:
            provider_used = "google_translate"

    # 4. Fallback: If Chhattisgarhi/Bhojpuri, use Hindi with dialect adaptation
    if not result and target_lang in ["cg", "bho"]:
        hi_trans = perform_translation(clean_text, "hi", source_lang, preferred_provider)
        if hi_trans.get("translated_text"):
            result = apply_dialect_rules(hi_trans["translated_text"], target_lang)
            provider_used = f"dialect_adapter_{target_lang}"

    # Final fallback: return original text
    if not result:
        result = clean_text
        provider_used = "fallback_original"

    # Save to Cache
    set_cached_translation(clean_text, source_lang, target_lang, result, provider=provider_used)

    return {
        "translated_text": result,
        "provider": provider_used,
        "cached": False
    }


# --- Request & Response Models ---

class TranslateRequest(BaseModel):
    text: Optional[str] = Field(None, example="High fever and severe cough")
    texts: Optional[List[str]] = Field(None, example=["High fever", "Severe cough"])
    target_lang: str = Field(..., example="cg")
    source_lang: str = Field("auto", example="en")
    provider: str = Field("auto", example="auto")

class TranslateResponse(BaseModel):
    translated_text: Optional[str] = None
    translated_texts: Optional[List[str]] = None
    source_lang: str
    target_lang: str
    provider: str
    cached: bool

class TranslateTriageRequest(BaseModel):
    target_lang: str = Field(..., example="cg")
    source_lang: str = Field("en", example="en")
    condition: Optional[str] = None
    condition_description: Optional[str] = None
    action_advice: Optional[str] = None
    precautions: Optional[List[str]] = None
    risk_reasons: Optional[List[str]] = None
    referral_facility: Optional[str] = None
    referral_action: Optional[str] = None
    generic_medicines: Optional[List[Dict[str, Any]]] = None


# --- API Routes ---

@router.get("/languages")
def get_languages():
    """Return all supported regional languages, native names, regions, and translation engine statuses."""
    active_providers = []
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        active_providers.append("Gemini LLM (Active)")
    if os.environ.get("DEEPL_API_KEY"):
        active_providers.append("DeepL API (Active)")
    if os.environ.get("OPENAI_API_KEY"):
        active_providers.append("OpenAI (Active)")
    active_providers.append("Google Cloud / Translate (Active)")
    active_providers.append("Offline Rural Dialect & Medical Dictionary (Active)")

    return {
        "count": len(LANGUAGES),
        "languages": LANGUAGES,
        "active_providers": active_providers,
        "default_language": "en",
        "supported_dialects": ["cg (Chhattisgarhi)", "bho (Bhojpuri)"]
    }

@router.get("/translations/{lang}")
def get_ui_translations(lang: str):
    """Retrieve full UI static dictionary for instant zero-latency client switching."""
    clean_lang = lang.lower().strip()
    if clean_lang not in UI_DICTIONARIES:
        # Fallback to English
        clean_lang = "en"
    return {
        "lang": clean_lang,
        "dictionary": UI_DICTIONARIES[clean_lang]
    }

@router.post("/translate", response_model=TranslateResponse)
def translate_endpoint(req: TranslateRequest):
    """Translate single text or a batch of text strings into target language/dialect."""
    if not req.text and not req.texts:
        raise HTTPException(status_code=400, detail="Either 'text' or 'texts' must be provided.")

    target = req.target_lang.lower().strip()
    source = req.source_lang.lower().strip()

    if req.texts:
        translated_list = []
        providers = []
        is_all_cached = True
        for t in req.texts:
            res = perform_translation(t, target, source, req.provider)
            translated_list.append(res["translated_text"])
            providers.append(res["provider"])
            if not res["cached"]:
                is_all_cached = False
        return TranslateResponse(
            translated_texts=translated_list,
            source_lang=source,
            target_lang=target,
            provider=",".join(set(providers)) or "auto",
            cached=is_all_cached
        )
    else:
        res = perform_translation(req.text or "", target, source, req.provider)
        return TranslateResponse(
            translated_text=res["translated_text"],
            source_lang=source,
            target_lang=target,
            provider=res["provider"],
            cached=res["cached"]
        )

@router.post("/translate/triage-result")
def translate_triage_result(req: TranslateTriageRequest):
    """
    Dynamically translates clinical triage output (condition name, description,
    action advice, precautions, referral guidance, and generic medicine advice)
    into Chhattisgarhi, Hindi, or any target Indian language.
    """
    target = req.target_lang.lower().strip()
    source = req.source_lang.lower().strip()

    translated: Dict[str, Any] = {
        "target_lang": target,
        "source_lang": source,
    }

    if req.condition:
        translated["condition"] = perform_translation(req.condition, target, source)["translated_text"]

    if req.condition_description:
        translated["condition_description"] = perform_translation(req.condition_description, target, source)["translated_text"]

    if req.action_advice:
        translated["action_advice"] = perform_translation(req.action_advice, target, source)["translated_text"]

    if req.precautions:
        translated["precautions"] = [
            perform_translation(p, target, source)["translated_text"] for p in req.precautions
        ]

    if req.risk_reasons:
        translated["risk_reasons"] = [
            perform_translation(r, target, source)["translated_text"] for r in req.risk_reasons
        ]

    if req.referral_facility:
        translated["referral_facility"] = perform_translation(req.referral_facility, target, source)["translated_text"]

    if req.referral_action:
        translated["referral_action"] = perform_translation(req.referral_action, target, source)["translated_text"]

    if req.generic_medicines:
        meds_translated = []
        for m in req.generic_medicines:
            med_copy = dict(m)
            if "purpose" in med_copy and med_copy["purpose"]:
                med_copy["purpose"] = perform_translation(med_copy["purpose"], target, source)["translated_text"]
            meds_translated.append(med_copy)
        translated["generic_medicines"] = meds_translated

    return translated
