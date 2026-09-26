/* ==========================================================================
   GramCare AI - Modern Frontend Application Controller
   ========================================================================== */

// Application State
const state = {
  currentRole: 'asha', // 'asha' or 'patient'
  currentLang: 'en',   // 'en' or 'hi'
  activeTab: 'triage',
  isRecording: false,
  recognition: null,
  activePatientId: null,
  lastPrediction: null,
  currentUser: {
    user_id: 'ASHA-782',
    username: 'asha@gramcare.gov.in',
    full_name: 'Sunita Devi (ASHA Worker #782)',
    role: 'asha',
    village: 'Rampur'
  },
  sessionToken: 'DEMO-ASHA-TOKEN',
  activeTokenId: 'TK-RAM-84920',
  familyMembers: [],
  activeFamilyMember: null,
  ashaTokens: [],
  tempModalLang: 'en',
  preferredEngine: 'auto',
  languagesList: [],
  translationsCache: {}
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
  initLanguages();
  initSpeechRecognition();
  checkApiHealth();
  setupPatientSearch();
  setupOfflineSync();
  updateAuthBadge();
  loadAshaTokens();
});

// --- Speech Recognition (Web Speech API with Fallback) ---
function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    const badge = document.getElementById('voice-engine-badge');
    if (badge) badge.innerText = 'Text Input (Web Speech Not Supported)';
    return;
  }

  try {
    state.recognition = new SpeechRecognition();
    state.recognition.continuous = false;
    state.recognition.interimResults = true;
    state.recognition.lang = state.currentLang === 'hi' ? 'hi-IN' : 'en-IN';

    state.recognition.onstart = () => {
      state.isRecording = true;
      const micBtn = document.getElementById('mic-btn');
      const voiceStatus = document.getElementById('voice-status');
      if (micBtn) micBtn.classList.add('recording');
      if (voiceStatus) {
        voiceStatus.innerText = state.currentLang === 'hi' ? 'सुन रहे हैं... लक्षण बोलें' : 'Listening... Speak symptoms clearly';
      }
    };

    state.recognition.onresult = (event) => {
      let transcript = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }
      const symptomsInput = document.getElementById('symptoms-input');
      if (symptomsInput && transcript.trim()) {
        const existing = symptomsInput.value.trim();
        symptomsInput.value = existing ? `${existing}, ${transcript}` : transcript;
      }
    };

    state.recognition.onerror = (event) => {
      console.warn('Speech recognition error:', event.error);
      stopRecordingUI();
      const voiceStatus = document.getElementById('voice-status');
      if (voiceStatus) {
        voiceStatus.innerText = `Mic alert (${event.error}). Please type symptoms directly.`;
      }
    };

    state.recognition.onend = () => {
      stopRecordingUI();
    };
  } catch (err) {
    console.error('Failed to init SpeechRecognition:', err);
  }
}

function toggleVoiceRecording() {
  if (!state.recognition) {
    alert(state.currentLang === 'hi' 
      ? 'आपका ब्राउज़र वॉइस इनपुट का समर्थन नहीं करता है। कृपया लक्षण सीधे टाइप करें।'
      : 'Your browser does not support Web Speech. Please type symptoms directly.');
    return;
  }

  if (state.isRecording) {
    state.recognition.stop();
    stopRecordingUI();
  } else {
    try {
      state.recognition.lang = state.currentLang === 'hi' ? 'hi-IN' : 'en-IN';
      state.recognition.start();
    } catch (e) {
      console.warn('Recognition start error:', e);
      state.recognition.stop();
      stopRecordingUI();
    }
  }
}

function stopRecordingUI() {
  state.isRecording = false;
  const micBtn = document.getElementById('mic-btn');
  const voiceStatus = document.getElementById('voice-status');
  if (micBtn) micBtn.classList.remove('recording');
  if (voiceStatus) {
    voiceStatus.innerText = state.currentLang === 'hi'
      ? 'माइक दबाकर लक्षण बोलें'
      : 'Tap Microphone and Speak Symptoms';
  }
}

// --- Quick Symptom Chips ---
function toggleSymptomChip(symptom, chipElement) {
  const textarea = document.getElementById('symptoms-input');
  if (!textarea) return;

  let current = textarea.value.trim();
  const symptomsList = current ? current.split(',').map(s => s.trim().toLowerCase()) : [];
  const normalizedSymptom = symptom.trim().toLowerCase();

  if (symptomsList.includes(normalizedSymptom)) {
    const updated = symptomsList.filter(s => s !== normalizedSymptom);
    textarea.value = updated.join(', ');
    chipElement.classList.remove('selected');
  } else {
    textarea.value = current ? `${current}, ${symptom}` : symptom;
    chipElement.classList.add('selected');
  }
}

// --- Tab Switching ---
function switchMainTab(tabName) {
  state.activeTab = tabName;
  document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
  document.querySelectorAll('.nav-pill-btn').forEach(btn => btn.classList.remove('active'));

  const activeContent = document.getElementById(`tab-${tabName}`);
  const activeBtn = document.getElementById(`tab-btn-${tabName}`);
  if (activeContent) activeContent.classList.add('active');
  if (activeBtn) activeBtn.classList.add('active');

  if (tabName === 'directory') {
    loadPatientRegistry();
  } else if (tabName === 'analytics') {
    loadAnalyticsDashboard();
  }
}

// --- Mode Toggle: ASHA Worker vs. Patient Mode ---
function toggleRoleMode(targetRole) {
  if (targetRole) {
    state.currentRole = targetRole;
  } else {
    state.currentRole = state.currentRole === 'asha' ? 'patient' : 'asha';
  }

  const roleTitle = document.getElementById('role-title');
  const roleHeadline = document.getElementById('role-headline');
  const roleSubtext = document.getElementById('role-subtext');
  const modeBtnLabel = document.getElementById('mode-btn-label');
  const lookupGroup = document.getElementById('lookup-group');
  const patientIdDisplay = document.getElementById('patient-id-display');
  const vulnBox = document.getElementById('vulnerability-screening-box');
  const ashaTokenBox = document.getElementById('asha-token-box');
  const familyVaultBox = document.getElementById('family-vault-box');

  if (state.currentRole === 'patient') {
    if (roleTitle) roleTitle.innerText = 'Patient Self-Service Mode';
    if (roleHeadline) roleHeadline.innerHTML = '<span>🌱</span> Patient Self-Care & Assessment';
    if (roleSubtext) roleSubtext.innerText = 'Check health symptoms for Self and Family Members with isolated private records and generic medicine guidance.';
    if (modeBtnLabel) modeBtnLabel.innerText = 'Switch to ASHA Worker Mode';
    if (lookupGroup) lookupGroup.style.display = 'none';
    if (patientIdDisplay) patientIdDisplay.style.display = 'none';
    if (vulnBox) vulnBox.style.display = 'block';
    if (ashaTokenBox) ashaTokenBox.style.display = 'none';
    if (familyVaultBox) familyVaultBox.style.display = 'block';
    
    // Auto-load family members if patient logged in
    const userId = state.currentUser ? state.currentUser.user_id : 'USR-1082';
    loadFamilyMembers(userId);
  } else {
    if (roleTitle) roleTitle.innerText = 'ASHA Worker & Kiosk Mode';
    if (roleHeadline) roleHeadline.innerHTML = '<span>👩‍⚕️</span> ASHA Worker & Kiosk Mode';
    if (roleSubtext) roleSubtext.innerText = 'Record patient intake, issue Patient Token IDs, conduct voice triage, and track rural referral care-loops.';
    if (modeBtnLabel) modeBtnLabel.innerText = 'Switch to Patient Mode';
    if (lookupGroup) lookupGroup.style.display = 'block';
    if (patientIdDisplay) patientIdDisplay.style.display = 'inline-flex';
    if (vulnBox) vulnBox.style.display = 'block';
    if (ashaTokenBox) ashaTokenBox.style.display = 'block';
    if (familyVaultBox) familyVaultBox.style.display = 'none';
    loadAshaTokens();
  }
}

// --- Comprehensive Multilingual & Dialect Controller ---

const SUPPORTED_LANGUAGES = [
  { code: 'en', name: 'English', native_name: 'English', script: 'Latin', region: 'Global & Pan-India', category: 'global', flag: '🇬🇧', speech_code: 'en-IN', greeting: 'Welcome to GramCare AI' },
  { code: 'hi', name: 'Hindi', native_name: 'हिन्दी', script: 'Devanagari', region: 'Central & Northern India', category: 'rural', flag: '🇮🇳', speech_code: 'hi-IN', greeting: 'नमस्ते! ग्रामकेयर एआई में आपका स्वागत है' },
  { code: 'cg', name: 'Chhattisgarhi', native_name: 'छत्तीसगढ़ी', script: 'Devanagari', region: 'Chhattisgarh & Central Hubs', category: 'rural', flag: '🌾', speech_code: 'hi-IN', greeting: 'जय जोहार! ग्रामकेयर एआई म आपमन के स्वागत हे' },
  { code: 'bho', name: 'Bhojpuri', native_name: 'भोजपुरी', script: 'Devanagari', region: 'Bihar, Eastern UP & Jharkhand', category: 'rural', flag: '🌾', speech_code: 'hi-IN', greeting: 'प्रणाम! ग्रामकेयर एआई में रउआ सब के स्वागत बा' },
  { code: 'bn', name: 'Bengali', native_name: 'বাংলা', script: 'Bengali', region: 'West Bengal & Eastern India', category: 'east', flag: '🇮🇳', speech_code: 'bn-IN', greeting: 'নমস্কার! গ্রামকেয়ার এআই-তে স্বাগতম' },
  { code: 'mr', name: 'Marathi', native_name: 'मराठी', script: 'Devanagari', region: 'Maharashtra & Western India', category: 'west', flag: '🇮🇳', speech_code: 'mr-IN', greeting: 'नमस्कार! ग्रामकेअर एआय मध्ये स्वागत आहे' },
  { code: 'te', name: 'Telugu', native_name: 'తెలుగు', script: 'Telugu', region: 'Andhra Pradesh & Telangana', category: 'south', flag: '🇮🇳', speech_code: 'te-IN', greeting: 'నమస్కారం! గ్రామ్‌కేర్ AI కి స్వాగతం' },
  { code: 'ta', name: 'Tamil', native_name: 'தமிழ்', script: 'Tamil', region: 'Tamil Nadu & Southern India', category: 'south', flag: '🇮🇳', speech_code: 'ta-IN', greeting: 'வணக்கம்! கிராம்கேர் AI-க்கு நல்வரவு' },
  { code: 'gu', name: 'Gujarati', native_name: 'ગુજરાતી', script: 'Gujarati', region: 'Gujarat & Western Coast', category: 'west', flag: '🇮🇳', speech_code: 'gu-IN', greeting: 'નમસ્તે! ગ્રામકેર એઆઈ માં સ્વાગત છે' },
  { code: 'or', name: 'Odia', native_name: 'ଓଡ଼ିଆ', script: 'Odia', region: 'Odisha & Eastern Rural Belts', category: 'east', flag: '🇮🇳', speech_code: 'or-IN', greeting: 'ନମସ୍କାର! ଗ୍ରାମକେୟାର ଏଆଇ କୁ ସ୍ୱାଗତ' },
  { code: 'pa', name: 'Punjabi', native_name: 'ਪੰਜਾਬੀ', script: 'Gurmukhi', region: 'Punjab & Northern Belts', category: 'north', flag: '🇮🇳', speech_code: 'pa-IN', greeting: 'ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ! ਗ੍ਰਾਮਕੇਅਰ ਏਆਈ ਵਿੱਚ ਸਵਾਗਤ ਹੈ' },
  { code: 'kn', name: 'Kannada', native_name: 'ಕನ್ನಡ', script: 'Kannada', region: 'Karnataka & Deccan', category: 'south', flag: '🇮🇳', speech_code: 'kn-IN', greeting: 'ನಮಸ್ಕಾರ! ಗ್ರಾಮ್‌ಕೇರ್ AI ಗೆ ಸುಸ್ವಾಗತ' },
  { code: 'ml', name: 'Malayalam', native_name: 'മലയാളം', script: 'Malayalam', region: 'Kerala & Southern Coast', category: 'south', flag: '🇮🇳', speech_code: 'ml-IN', greeting: 'നമസ്കാരം! ഗ്രാംകെയർ AI-ലേക്ക് സ്വാഗതം' },
  { code: 'ur', name: 'Urdu', native_name: 'اردو', script: 'Perso-Arabic', region: 'Pan-India & Northern Belts', category: 'north', flag: '🇮🇳', speech_code: 'ur-IN', greeting: 'خوش آمدید! گرام کیئر اے آئی میں خیر مقدم ہے' }
];

const UI_LOCALIZATIONS = {
  en: {
    app_title: "GramCare AI",
    tagline: "Rural Healthcare Decision-Support",
    nav_triage: "Triage Studio",
    nav_patients: "Patient Registry",
    nav_analytics: "Outbreak Analytics",
    nav_about: "About System",
    role_asha_title: "ASHA Worker & Kiosk Mode",
    role_asha_subtext: "Record patient intake, conduct voice symptom triage, detect recurring chronic symptoms, and issue referral slips.",
    role_patient_title: "Patient Self-Service Mode",
    role_patient_subtext: "Check symptoms at home, view family health records, and connect directly to teleconsultation doctors.",
    btn_switch_patient: "Switch to Patient Mode",
    btn_switch_asha: "Switch to ASHA Mode",
    patient_section_title: "Patient Profile & Identification",
    lbl_search: "Search Existing Patient (Name / Phone / Village)",
    lbl_name: "Full Name *",
    lbl_phone: "Mobile Number",
    lbl_village: "Village / Gram *",
    lbl_age: "Age",
    lbl_gender: "Gender",
    symptom_section_title: "Symptom Input & Voice Assistant",
    voice_status: "Tap Microphone and Speak Symptoms",
    voice_subtext: "Supports Chhattisgarhi, Hindi, English, and regional accents",
    voice_hint: "Voice Input Dialect:",
    lbl_symptoms: "Reported Symptoms Description *",
    symptoms_placeholder: "Describe symptoms (e.g., persistent dry cough for 3 days, mild fever, body ache, breathlessness)...",
    lbl_quick_chips: "Common Rural Symptoms (Click to Add):",
    btn_submit_text: "Run AI Triage & Risk Assessment",
    empty_heading: "Ready for Triage Analysis",
    empty_subtext: "Enter symptoms by voice or text and click 'Run AI Triage' to generate clinical risk level, matched condition, precautions, and generic medicine alternatives.",
    loading_heading: "Analyzing Symptoms with Machine Learning...",
    loading_subtext: "Vectorizing features & evaluating longitudinal history...",
    trans_bar_title: "Translate Clinical Guidance:",
    btn_translate_text: "Translate",
    action_advice_header: "📋 Action Advice:",
    precautions_header: "🛡️ Clinical Precautions:",
    generic_meds_title: "💊 Affordable Generic Alternatives",
    jan_badge: "Jan Aushadhi Scheme",
    referral_header: "🏥 Referral Guidance Slip",
    btn_print_slip: "🖨️ Print / Save Consultation Report",
    btn_view_timeline: "📜 View Health Timeline"
  },
  hi: {
    app_title: "ग्रामकेयर एआई",
    tagline: "ग्रामीण स्वास्थ्य सहायता प्रणाली",
    nav_triage: "ट्राइएज स्टूडियो",
    nav_patients: "मरीज सूची",
    nav_analytics: "प्रकोप निगरानी",
    nav_about: "प्रणाली के बारे में",
    role_asha_title: "आशा कार्यकर्ता व कियोस्क मोड",
    role_asha_subtext: "मरीज का विवरण दर्ज करें, आवाज द्वारा लक्षण जांचें, पुराने लक्षणों की पहचान करें और रेफरल पर्ची जारी करें।",
    role_patient_title: "मरीज स्व-सेवा मोड",
    role_patient_subtext: "घर पर लक्षण जांचें, पारिवारिक स्वास्थ्य इतिहास देखें और ऑनलाइन डॉक्टरों से परामर्श लें।",
    btn_switch_patient: "मरीज मोड में बदलें",
    btn_switch_asha: "आशा मोड में बदलें",
    patient_section_title: "मरीज का विवरण व पहचान",
    lbl_search: "पुराने मरीज को खोजें (नाम / मोबाइल / गाँव)",
    lbl_name: "मरीज का पूरा नाम *",
    lbl_phone: "मोबाइल नंबर",
    lbl_village: "गाँव / ग्राम *",
    lbl_age: "उम्र",
    lbl_gender: "लिंग",
    symptom_section_title: "लक्षण विवरण व आवाज सहायक",
    voice_status: "माइक दबाकर लक्षण बोलें",
    voice_subtext: "छत्तीसगढ़ी, हिन्दी, अंग्रेजी और क्षेत्रीय बोलियों में उपलब्ध",
    voice_hint: "आवाज इनपुट बोली:",
    lbl_symptoms: "लक्षणों का विवरण *",
    symptoms_placeholder: "लक्षण बताएं (जैसे 3 दिन से तेज बुखार, सूखी खांसी, सांस फूलना, बदन दर्द)...",
    lbl_quick_chips: "सामान्य ग्रामीण लक्षण (जोड़ने के लिए क्लिक करें):",
    btn_submit_text: "एआई जांच व जोखिम मूल्यांकन करें",
    empty_heading: "लक्षण जांच के लिए तैयार",
    empty_subtext: "आवाज या लिखकर लक्षण दर्ज करें और 'एआई जांच करें' दबाएं। तुरंत जोखिम स्तर, बीमारी, सावधानियां और सस्ती जेनेरिक दवाएं प्राप्त करें।",
    loading_heading: "मशीन लर्निंग द्वारा लक्षणों का विश्लेषण जारी है...",
    loading_subtext: "लक्षणों का मिलान व पूर्व इतिहास की जांच हो रही है...",
    trans_bar_title: "पर्चे का भाषा अनुवाद करें:",
    btn_translate_text: "अनुवाद करें",
    action_advice_header: "📋 चिकित्सकीय सलाह:",
    precautions_header: "🛡️ आवश्यक सावधानियां:",
    generic_meds_title: "💊 किफायती जेनेरिक दवाएं",
    jan_badge: "जन औषधि योजना",
    referral_header: "🏥 रेफरल व परामर्श पर्ची",
    btn_print_slip: "🖨️ पर्ची प्रिंट / सुरक्षित करें",
    btn_view_timeline: "📜 स्वास्थ्य इतिहास देखें"
  },
  cg: {
    app_title: "ग्रामकेयर एआई",
    tagline: "गाँव-गंवाई स्वास्थ्य सहायता प्रणाली",
    nav_triage: "ट्राइएज स्टूडियो",
    nav_patients: "मरीज रजिस्टर",
    nav_analytics: "बीमारी निगरानी",
    nav_about: "प्रणाली के बारे म",
    role_asha_title: "मितानिन (आशा) व कियोस्क मोड",
    role_asha_subtext: "मरीज के नाम-गाँव लिखव, गोठिया के लक्षण जांचव, पुरना बीमारी देखव अउ अस्पताल बर रेफरल पर्ची बनावव।",
    role_patient_title: "मरीज स्व-सेवा मोड",
    role_patient_subtext: "घर बइठे लक्षण जांचव, परिवार के स्वास्थ्य इतिहास देखव अउ डाक्टर ले गोठियावव।",
    btn_switch_patient: "मरीज मोड म जावव",
    btn_switch_asha: "मितानिन मोड म जावव",
    patient_section_title: "मरीज के विवरण अउ पहचान",
    lbl_search: "पुरना मरीज खोजव (नाम / मोबाइल / गाँव)",
    lbl_name: "मरीज के पूरा नाम *",
    lbl_phone: "मोबाइल नंबर",
    lbl_village: "गाँव / पारा / ग्राम *",
    lbl_age: "उमर (साल)",
    lbl_gender: "लिंग",
    symptom_section_title: "लक्षण बताओ अउ आवाज सहायक",
    voice_status: "माइक दबा के लक्षण बोलव",
    voice_subtext: "छत्तीसगढ़ी, हिन्दी अउ अंग्रेजी म गोठिया सकत हव",
    voice_hint: "गोठियाए के बोली:",
    lbl_symptoms: "का-का तकलीफ हे, विस्तार ले बतावव *",
    symptoms_placeholder: "तकलीफ बतावव (जैसे 3 दिन ले जबर तपन / बुखार, खोंखी, छाती पीरा, माथा पीरा, सांस फूले)...",
    lbl_quick_chips: "गाँव-घर के आम लक्षण (जोड़े बर दबाएं):",
    btn_submit_text: "एआई जांच अउ जोखिम मूल्यांकन करव",
    empty_heading: "लक्षण जांचे बर तइयार हे",
    empty_subtext: "बोल के या लिख के लक्षण दर्ज करव अउ 'एआई जांच करव' दबाएं। तुरंत बीमारी, परहेज़ अउ जन औषधि के सस्ती दवाई मिलही।",
    loading_heading: "एआई ले लक्षण के जांच चलत हे...",
    loading_subtext: "लक्षण मिलावत हन अउ पुरना बीमारी के जांच करत हन...",
    trans_bar_title: "पर्ची के भाखा बदलव (अनुवाद):",
    btn_translate_text: "अनुवाद करव",
    action_advice_header: "📋 सलाह अउ उपाय:",
    precautions_header: "🛡️ का-का परहेज़ करना हे:",
    generic_meds_title: "💊 सस्ती जन औषधि जेनेरिक दवाई",
    jan_badge: "प्रधानमंत्री जन औषधि केंद्र",
    referral_header: "🏥 अस्पताल बर रेफरल पर्ची",
    btn_print_slip: "🖨️ पर्ची प्रिंट / सुरक्षित करव",
    btn_view_timeline: "📜 स्वास्थ्य इतिहास देखव"
  },
  bn: {
    app_title: "গ্রামকেয়ার এআই",
    tagline: "গ্রামীণ স্বাস্থ্যসেবা সহায়তা ব্যবস্থা",
    nav_triage: "ট্রায়াজ স্টুডিও",
    nav_patients: "রোগীর তালিকা",
    nav_analytics: "প্রাদুর্ভাব নজরদারি",
    nav_about: "সিস্টেম সম্পর্কে",
    role_asha_title: "আশা কর্মী ও কিয়স্ক মোড",
    role_asha_subtext: "রোগীর তথ্য নথিভুক্ত করুন, ভয়েস উপসর্গ ট্রায়াজ করুন এবং রেফারেল স্লিপ তৈরি করুন।",
    role_patient_title: "রোগী স্ব-পরিষেবা মোড",
    role_patient_subtext: "বাড়িতে উপসর্গ পরীক্ষা করুন, পারিবারিক স্বাস্থ্য রেকর্ড দেখুন এবং চিকিৎসকদের সাথে পরামর্শ করুন।",
    btn_switch_patient: "রোগী মোডে যান",
    btn_switch_asha: "আশা মোডে যান",
    patient_section_title: "রোগীর প্রোফাইল ও পরিচয়",
    lbl_search: "বিদ্যমান রোগী খুঁজুন (নাম / ফোন / গ্রাম)",
    lbl_name: "রোগীর পুরো নাম *",
    lbl_phone: "মোবাইল নম্বর",
    lbl_village: "গ্রাম *",
    lbl_age: "বয়স",
    lbl_gender: "লিঙ্গ",
    symptom_section_title: "উপসর্গ ইনপুট ও ভয়েস সহকারী",
    voice_status: "মাইক চেপে উপসর্গ বলুন",
    voice_subtext: "বাংলা, হিন্দি, ইংরেজি এবং আঞ্চলিক ভাষায় সমর্থিত",
    voice_hint: "ভয়েস ভাষা:",
    lbl_symptoms: "উপসর্গের বিবরণ *",
    symptoms_placeholder: "উপসর্গের বিবরণ দিন...",
    lbl_quick_chips: "সাধারণ গ্রামীণ উপসর্গ:",
    btn_submit_text: "এআই ট্রায়াজ ও ঝুঁকি মূল্যায়ন চালান",
    empty_heading: "ট্রায়াজ বিশ্লেষণের জন্য প্রস্তুত",
    empty_subtext: "ভয়েস বা টেক্সটে উপসর্গ লিখে 'এআই ট্রায়াজ চালান' বাটনে ক্লিক করুন।",
    loading_heading: "মেশিন লার্নিং দ্বারা উপসর্গ বিশ্লেষণ চলছে...",
    loading_subtext: "ইতিহাস যাচাই করা হচ্ছে...",
    trans_bar_title: "প্রতিবেদন অনুবাদ করুন:",
    btn_translate_text: "অনুবাদ করুন",
    action_advice_header: "📋 চিকিৎসা পরামর্শ:",
    precautions_header: "🛡️ প্রয়োজনীয় সতর্কতা:",
    generic_meds_title: "💊 সাশ্রয়ী জেনেরিক ওষুধ",
    jan_badge: "জন ঔষধি যোজনা",
    referral_header: "🏥 রেফারেল স্লিপ",
    btn_print_slip: "🖨️ প্রিন্ট করুন",
    btn_view_timeline: "📜 ইতিহাস দেখুন"
  },
  mr: {
    app_title: "ग्रामकेअर एआय",
    tagline: "ग्रामीण आरोग्य निर्णय-सहाय्य प्रणाली",
    nav_triage: "ट्रायज स्टुडिओ",
    nav_patients: "रुग्ण नोंदणी",
    nav_analytics: "साथीचे विश्लेषण",
    nav_about: "प्रणालीबद्दल माहिती",
    role_asha_title: "आशा सेविका व किओस्क मोड",
    role_asha_subtext: "रुग्णाची नोंदणी करा, आवाजाद्वारे लक्षणे तपासा आणि रेफरल स्लिप जारी करा.",
    role_patient_title: "रुग्ण स्व-सेवा मोड",
    role_patient_subtext: "घरी बसून लक्षणे तपासा आणि डॉक्टरांशी संपर्क साधा.",
    btn_switch_patient: "रुग्ण मोड निवडा",
    btn_switch_asha: "आशा मोड निवडा",
    patient_section_title: "रुग्ण तपशील व ओळख",
    lbl_search: "मागील रुग्ण शोधा (नाव / फोन / गाव)",
    lbl_name: "रुग्णाचे पूर्ण नाव *",
    lbl_phone: "मोबाईल नंबर",
    lbl_village: "गाव / ग्राम *",
    lbl_age: "वय",
    lbl_gender: "लिंग",
    symptom_section_title: "लक्षण नोंद व व्हॉईस सहाय्यक",
    voice_status: "माइक दाबून लक्षणे सांगा",
    voice_subtext: "मराठी, हिंदी, इंग्रजी आणि स्थानिक भाषांमध्ये उपलब्ध",
    voice_hint: "आवाज इनपुट भाषा:",
    lbl_symptoms: "लक्षणे सांगा *",
    symptoms_placeholder: "लक्षणे सांगा...",
    lbl_quick_chips: "सामान्य ग्रामीण लक्षणे:",
    btn_submit_text: "एआय ट्रायज व जोखीम मूल्यांकन करा",
    empty_heading: "ट्रायज विश्लेषणासाठी सज्ज",
    empty_subtext: "लक्षणे प्रविष्ट करा आणि 'एआय ट्रायज करा' वर क्लिक करा.",
    loading_heading: "लक्षण विश्लेषित होत आहेत...",
    loading_subtext: "इतिहास तपासला जात आहे...",
    trans_bar_title: "अहवाल भाषांतर करा:",
    btn_translate_text: "भाषांतर करा",
    action_advice_header: "📋 वैद्यकीय सल्ला:",
    precautions_header: "🛡️ आवश्यक खबरदारी:",
    generic_meds_title: "💊 किफायतशीर जेनेरिक औषधे",
    jan_badge: "जन औषधी योजना",
    referral_header: "🏥 रेफरल स्लिप",
    btn_print_slip: "🖨️ मुद्रित करा",
    btn_view_timeline: "📜 इतिहास पहा"
  },
  te: {
    app_title: "గ్రామ్‌కేర్ AI",
    tagline: "గ్రామీణ ఆరోగ్య సంరక్షణ నిర్ణయ మద్దతు",
    nav_triage: "ట్రయాజ్ స్టూడియో",
    nav_patients: "రోగుల రిజిస్ట్రీ",
    nav_analytics: "వ్యాధి వ్యాప్తి విశ్లేషణ",
    nav_about: "సిస్టమ్ గురించి",
    role_asha_title: "ఆశా వర్కర్ & కియోస్క్ మోడ్",
    role_asha_subtext: "రోగి వివరాలను నమోదు చేయండి, వాయిస్ ద్వారా లక్షణాలను తనిఖీ చేయండి.",
    role_patient_title: "రోగి స్వీయ సేవా మోడ్",
    role_patient_subtext: "ఇంట్లోనే లక్షణాలను తనిఖీ చేసుకోండి, డాక్టర్లను సంప్రదించండి.",
    btn_switch_patient: "పేషెంట్ మోడ్‌కి మారండి",
    btn_switch_asha: "ఆశా మోడ్‌కి మారండి",
    patient_section_title: "రోగి ప్రొఫైల్ & గుర్తింపు",
    lbl_search: "రోగిని శోధించండి (పేరు / ఫోన్ / గ్రామం)",
    lbl_name: "రోగి పూర్తి పేరు *",
    lbl_phone: "మొబైల్ నంబర్",
    lbl_village: "గ్రామం *",
    lbl_age: "వయస్సు",
    lbl_gender: "లింగం",
    symptom_section_title: "లక్షణాల నమోదు & వాయిస్ అసిస్టెంట్",
    voice_status: "మైక్ నొక్కి లక్షణాలను మాట్లాడండి",
    voice_subtext: "తెలుగు, హిందీ, ఇంగ్లీష్ భాషలలో లభ్యం",
    voice_hint: "వాయిస్ భాష:",
    lbl_symptoms: "లక్షణాల వివరణ *",
    symptoms_placeholder: "లక్షణాలను వివరించండి...",
    lbl_quick_chips: "సాధారణ గ్రామీణ లక్షణాలు:",
    btn_submit_text: "AI ట్రయాజ్ & ప్రమాద అంచనా వేయండి",
    empty_heading: "ట్రయాజ్ విశ్లేషణకు సిద్ధంగా ఉంది",
    empty_subtext: "లక్షణాలను నమోదు చేసి 'AI ట్రయాజ్ వేయండి' క్లిక్ చేయండి.",
    loading_heading: "లక్షణాలను విశ్లేషిస్తున్నాము...",
    loading_subtext: "చరిత్రను సరిపోలుస్తున్నాము...",
    trans_bar_title: "నివేదికను అనువదించండి:",
    btn_translate_text: "అనువదించు",
    action_advice_header: "📋 వైద్య సలహా:",
    precautions_header: "🛡️ జాగ్రత్తలు:",
    generic_meds_title: "💊 చవకైన జెనరిక్ మందులు",
    jan_badge: "జన్ ఔషధి పథకం",
    referral_header: "🏥 రిఫరల్ స్లిప్",
    btn_print_slip: "🖨️ ముద్రించండి",
    btn_view_timeline: "📜 చరిత్రను చూడండి"
  }
};

const QUICK_CHIPS_I18N = {
  en: [
    { label: "🌡️ High Fever", val: "Fever" },
    { label: "🤒 Mild Fever", val: "Mild Fever" },
    { label: "🗣️ Cough", val: "Cough" },
    { label: "💔 Chest Pain", val: "Chest Pain" },
    { label: "🫁 Breathlessness", val: "Breathlessness" },
    { label: "🤕 Headache", val: "Headache" },
    { label: "🤢 Stomach Pain", val: "Stomach Ache" },
    { label: "🤮 Vomiting", val: "Vomiting" },
    { label: "💧 Loose Motions", val: "Diarrhea" },
    { label: "🔴 Skin Rash", val: "Skin Rash" },
    { label: "🦴 Joint Pain", val: "Joint Pain" },
    { label: "🥱 Weakness", val: "Fatigue" }
  ],
  hi: [
    { label: "🌡️ तेज बुखार", val: "High Fever" },
    { label: "🤒 हल्का बुखार", val: "Mild Fever" },
    { label: "🗣️ खांसी", val: "Cough" },
    { label: "💔 सीने में दर्द", val: "Chest Pain" },
    { label: "🫁 सांस फूलना", val: "Breathlessness" },
    { label: "🤕 सिरदर्द", val: "Headache" },
    { label: "🤢 पेट दर्द", val: "Stomach Ache" },
    { label: "🤮 उल्टी", val: "Vomiting" },
    { label: "💧 दस्त", val: "Diarrhea" },
    { label: "🔴 त्वचा पर चकत्ते / खुजली", val: "Skin Rash" },
    { label: "🦴 जोड़ों में दर्द", val: "Joint Pain" },
    { label: "🥱 थकान / कमजोरी", val: "Fatigue" }
  ],
  cg: [
    { label: "🌡️ जबर तपन / तेज बुखार", val: "High Fever" },
    { label: "🤒 हल्का बुखार", val: "Mild Fever" },
    { label: "🗣️ खोंखी", val: "Cough" },
    { label: "💔 छाती पीरा", val: "Chest Pain" },
    { label: "🫁 सांस फूले", val: "Breathlessness" },
    { label: "🤕 माथा पीरा", val: "Headache" },
    { label: "🤢 पेट पीरा", val: "Stomach Ache" },
    { label: "🤮 उलटी / छेंक", val: "Vomiting" },
    { label: "💧 झड़ाव / दस्त", val: "Diarrhea" },
    { label: "🔴 चमड़ी खुजली / चकत्ता", val: "Skin Rash" },
    { label: "🦴 गांठ-जोड़ पीरा", val: "Joint Pain" },
    { label: "🥱 सुस्त / कमजोरी", val: "Fatigue" }
  ],
  bn: [
    { label: "🌡️ উচ্চ জ্বর", val: "High Fever" },
    { label: "🤒 মৃদু জ্বর", val: "Mild Fever" },
    { label: "🗣️ কাশি", val: "Cough" },
    { label: "💔 বুকে ব্যথা", val: "Chest Pain" },
    { label: "🫁 শ্বাসকষ্ট", val: "Breathlessness" },
    { label: "🤕 মাথাব্যথা", val: "Headache" },
    { label: "🤢 পেটে ব্যথা", val: "Stomach Ache" },
    { label: "🤮 বমি", val: "Vomiting" },
    { label: "💧 পাতলা পায়খানা", val: "Diarrhea" },
    { label: "🔴 ত্বকে ফুসকুড়ি", val: "Skin Rash" },
    { label: "🦴 গাঁটে ব্যথা", val: "Joint Pain" },
    { label: "🥱 দুর্বলতা", val: "Fatigue" }
  ],
  mr: [
    { label: "🌡️ तीव्र ताप", val: "High Fever" },
    { label: "🤒 सौम्य ताप", val: "Mild Fever" },
    { label: "🗣️ खोकला", val: "Cough" },
    { label: "💔 छातीत दुखणे", val: "Chest Pain" },
    { label: "🫁 धाप लागणे", val: "Breathlessness" },
    { label: "🤕 डोकेदुखी", val: "Headache" },
    { label: "🤢 पोटदुखी", val: "Stomach Ache" },
    { label: "🤮 उलट्या", val: "Vomiting" },
    { label: "💧 जुलाब", val: "Diarrhea" },
    { label: "🔴 खाज / पुरळ", val: "Skin Rash" },
    { label: "🦴 सांधेदुखी", val: "Joint Pain" },
    { label: "🥱 अशक्तपणा", val: "Fatigue" }
  ],
  te: [
    { label: "🌡️ తీవ్ర జ్వరం", val: "High Fever" },
    { label: "🤒 స్వల్ప జ్వరం", val: "Mild Fever" },
    { label: "🗣️ దగ్గు", val: "Cough" },
    { label: "💔 ఛాతీ నొప్పి", val: "Chest Pain" },
    { label: "🫁 శ్వాస తీసుకోవడంలో ఇబ్బంది", val: "Breathlessness" },
    { label: "🤕 తలనొప్పి", val: "Headache" },
    { label: "🤢 కడుపు నొప్పి", val: "Stomach Ache" },
    { label: "🤮 వాంతులు", val: "Vomiting" },
    { label: "💧 విరేచనాలు", val: "Diarrhea" },
    { label: "🔴 చర్మంపై దద్దుర్లు", val: "Skin Rash" },
    { label: "🦴 కీళ్ల నొప్పులు", val: "Joint Pain" },
    { label: "🥱 అలసట", val: "Fatigue" }
  ]
};

// --- Multilingual Controller Core Functions ---

async function initLanguages() {
  const savedLang = localStorage.getItem('gramcare_lang') || 'en';
  const savedEngine = localStorage.getItem('gramcare_engine') || 'auto';
  state.currentLang = savedLang;
  state.preferredEngine = savedEngine;
  state.tempModalLang = savedLang;

  // Try fetching backend languages directory
  try {
    const res = await fetch('/api/languages');
    if (res.ok) {
      const data = await res.json();
      if (data.languages && data.languages.length > 0) {
        state.languagesList = data.languages;
      }
    }
  } catch (err) {
    console.warn('Backend languages list offline, using local registry.', err);
    state.languagesList = SUPPORTED_LANGUAGES;
  }
  if (!state.languagesList || state.languagesList.length === 0) {
    state.languagesList = SUPPORTED_LANGUAGES;
  }

  populateLanguageControls();
  changeLanguage(state.currentLang, false);

  // Setup outside click listener for navbar dropdown and floating menu
  document.addEventListener('click', (e) => {
    const navDropdown = document.getElementById('nav-lang-dropdown-wrapper');
    const navMenu = document.getElementById('nav-lang-menu');
    if (navDropdown && !navDropdown.contains(e.target) && navMenu) {
      navMenu.style.display = 'none';
    }

    const fabContainer = document.getElementById('floating-lang-fab');
    const fabMenu = document.getElementById('floating-lang-menu');
    if (fabContainer && !fabContainer.contains(e.target) && fabMenu) {
      fabMenu.style.display = 'none';
    }
  });
}

function populateLanguageControls() {
  const langs = state.languagesList && state.languagesList.length > 0 ? state.languagesList : SUPPORTED_LANGUAGES;

  // 1. Header Navigation Dropdown Items
  const navItemsContainer = document.getElementById('nav-lang-items');
  if (navItemsContainer) {
    navItemsContainer.innerHTML = langs.map(l => `
      <div class="lang-menu-item ${l.code === state.currentLang ? 'active' : ''}" onclick="changeLanguage('${l.code}', true); toggleNavLangDropdown(event);">
        <span>${l.flag || '🌐'} ${escapeHtml(l.native_name)}</span>
        <span style="font-size: 11px; color: var(--text-muted);">${escapeHtml(l.name)}</span>
      </div>
    `).join('');
  }

  // 2. Results Toolbar Language Select
  const resultsSelect = document.getElementById('results-lang-select');
  if (resultsSelect) {
    resultsSelect.innerHTML = langs.map(l => `
      <option value="${l.code}" ${l.code === state.currentLang ? 'selected' : ''}>
        ${l.flag || '🌐'} ${escapeHtml(l.native_name)} (${escapeHtml(l.name)})
      </option>
    `).join('');
  }

  // 3. Floating FAB Menu Items
  const fabItemsContainer = document.getElementById('floating-lang-items');
  if (fabItemsContainer) {
    fabItemsContainer.innerHTML = langs.slice(0, 7).map(l => `
      <div class="floating-menu-item ${l.code === state.currentLang ? 'active' : ''}" onclick="changeLanguage('${l.code}', true); toggleFloatingLangMenu();">
        <span>${l.flag || '🌐'} ${escapeHtml(l.native_name)}</span>
        <span style="font-size: 11px; opacity: 0.7;">${escapeHtml(l.name)}</span>
      </div>
    `).join('');
  }

  // 4. Modal Cards Grid
  renderLanguageModalCards(langs);
}

function renderLanguageModalCards(langsToRender) {
  const modalGrid = document.getElementById('lang-cards-grid');
  if (!modalGrid) return;

  modalGrid.innerHTML = langsToRender.map(l => `
    <div class="lang-card ${l.code === state.tempModalLang ? 'selected' : ''}" id="lang-card-${l.code}" onclick="selectModalLanguage('${l.code}')">
      <div>
        <div class="lang-card-top">
          <span class="lang-card-flag">${l.flag || '🌐'}</span>
          <span class="lang-card-check">✓</span>
        </div>
        <div class="lang-card-native">${escapeHtml(l.native_name)}</div>
        <div class="lang-card-en">${escapeHtml(l.name)} (${l.code})</div>
        <div class="lang-card-region">${escapeHtml(l.region || 'India')}</div>
      </div>
      <div class="lang-card-preview">"${escapeHtml(l.greeting || 'GramCare AI')}"</div>
    </div>
  `).join('');

  const modalSelectedLabel = document.getElementById('modal-selected-lang-label');
  if (modalSelectedLabel) {
    const cur = (state.languagesList || SUPPORTED_LANGUAGES).find(l => l.code === state.tempModalLang);
    modalSelectedLabel.innerText = cur ? `${cur.flag} ${cur.native_name} (${cur.name})` : state.tempModalLang;
  }
}

function changeLanguage(langCode, savePreference = true) {
  const langs = state.languagesList && state.languagesList.length > 0 ? state.languagesList : SUPPORTED_LANGUAGES;
  const langObj = langs.find(l => l.code === langCode) || langs[0];
  state.currentLang = langObj.code;
  state.tempModalLang = langObj.code;

  if (savePreference) {
    localStorage.setItem('gramcare_lang', state.currentLang);
  }

  // Update Speech Recognition language code
  if (state.recognition) {
    state.recognition.lang = langObj.speech_code || 'en-IN';
  }

  // Update Nav Badge (Option 1)
  const navFlag = document.getElementById('nav-lang-flag');
  const navLabel = document.getElementById('nav-lang-label');
  if (navFlag) navFlag.innerText = langObj.flag || '🌐';
  if (navLabel) navLabel.innerText = langObj.native_name || langObj.name;

  // Update Role Banner Button (Option 2)
  const langBtnLabel = document.getElementById('lang-btn-label');
  if (langBtnLabel) {
    langBtnLabel.innerText = `Language: ${langObj.flag} ${langObj.native_name} (Change)`;
  }

  // Update Voice Dialect Button (Option 5)
  const voiceFlag = document.getElementById('voice-dialect-flag');
  const voiceLabel = document.getElementById('voice-dialect-label');
  if (voiceFlag) voiceFlag.innerText = langObj.flag || '🎙️';
  if (voiceLabel) voiceLabel.innerText = `${langObj.native_name} (${langObj.speech_code || 'en-IN'})`;

  // Update Floating FAB (Option 4)
  const fabFlag = document.getElementById('fab-flag-icon');
  const fabCode = document.getElementById('fab-lang-code');
  if (fabFlag) fabFlag.innerText = langObj.flag || '🌐';
  if (fabCode) fabCode.innerText = langObj.code.toUpperCase();

  // Update Results Select
  const resultsSelect = document.getElementById('results-lang-select');
  if (resultsSelect) resultsSelect.value = state.currentLang;

  // Retrieve translation dictionary
  const dict = UI_LOCALIZATIONS[state.currentLang] || UI_LOCALIZATIONS['en'];

  // Update UI Elements with Localized Strings
  setText('tagline-text', dict.tagline || 'Rural Healthcare Decision-Support');
  setText('nav-triage-text', dict.nav_triage || 'Triage Studio');
  setText('nav-patients-text', dict.nav_patients || 'Patient Registry');
  setText('nav-analytics-text', dict.nav_analytics || 'Outbreak Analytics');
  setText('nav-about-text', dict.nav_about || 'About System');
  
  if (state.currentRole === 'asha') {
    setText('role-title', dict.role_asha_title || 'ASHA Worker & Kiosk Mode');
    setText('role-subtext', dict.role_asha_subtext || 'Record patient intake, conduct voice symptom triage, detect recurring chronic symptoms, and issue referral slips.');
    setText('mode-btn-label', dict.btn_switch_patient || 'Switch to Patient Mode');
  } else {
    setText('role-title', dict.role_patient_title || 'Patient Self-Service Mode');
    setText('role-subtext', dict.role_patient_subtext || 'Check symptoms at home, view family health records, and connect directly to teleconsultation doctors.');
    setText('mode-btn-label', dict.btn_switch_asha || 'Switch to ASHA Mode');
  }

  setText('patient-section-title', dict.patient_section_title || 'Patient Profile & Identification');
  setText('lbl-search', dict.lbl_search || 'Search Existing Patient (Name / Phone / Village)');
  setText('lbl-name', dict.lbl_name || 'Full Name *');
  setText('lbl-phone', dict.lbl_phone || 'Mobile Number');
  setText('lbl-village', dict.lbl_village || 'Village / Gram *');
  setText('lbl-age', dict.lbl_age || 'Age');
  setText('lbl-gender', dict.lbl_gender || 'Gender');
  setText('symptom-section-title', dict.symptom_section_title || 'Symptom Input & Voice Assistant');
  setText('voice-status', dict.voice_status || 'Tap Microphone and Speak Symptoms');
  setText('voice-subtext', dict.voice_subtext || 'Supports Chhattisgarhi, Hindi, English, and regional accents');
  setText('voice-dialect-hint', dict.voice_hint || 'Voice Input Dialect:');
  setText('lbl-symptoms', dict.lbl_symptoms || 'Reported Symptoms Description *');
  setText('lbl-quick-chips', dict.lbl_quick_chips || 'Common Rural Symptoms (Click to Add):');
  setText('btn-submit-text', dict.btn_submit_text || 'Run AI Triage & Risk Assessment');
  setText('empty-heading', dict.empty_heading || 'Ready for Triage Analysis');
  setText('empty-subtext', dict.empty_subtext || 'Enter symptoms by voice or text and click "Run AI Triage" to generate clinical risk level, matched condition, precautions, and generic medicine alternatives.');
  setText('trans-bar-title', dict.trans_bar_title || 'Translate Clinical Guidance:');
  setText('btn-retranslate-text', dict.btn_translate_text || 'Translate');

  const symInput = document.getElementById('symptoms-input');
  if (symInput && dict.symptoms_placeholder) {
    symInput.placeholder = dict.symptoms_placeholder;
  }

  // Re-render Quick Symptom Chips
  renderQuickChips(state.currentLang);

  // Update active state in nav dropdown & modal cards
  document.querySelectorAll('.lang-menu-item').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.floating-menu-item').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.lang-card').forEach(el => el.classList.remove('selected'));
  const activeCard = document.getElementById(`lang-card-${state.currentLang}`);
  if (activeCard) activeCard.classList.add('selected');

  // If there's an active prediction result on screen, translate it dynamically
  if (state.lastPrediction && state.currentLang !== 'en') {
    translateActiveTriageResults(state.currentLang);
  }
}

function renderQuickChips(langCode) {
  const container = document.getElementById('quick-chips-container');
  if (!container) return;

  const chips = QUICK_CHIPS_I18N[langCode] || QUICK_CHIPS_I18N['en'];
  container.innerHTML = chips.map(c => `
    <span class="symptom-chip" onclick="toggleSymptomChip('${escapeHtml(c.val)}', this)">${escapeHtml(c.label)}</span>
  `).join('');
}

// Quick toggle cycle: English -> Hindi -> Chhattisgarhi
function toggleLanguage() {
  if (state.currentLang === 'en') {
    changeLanguage('hi', true);
  } else if (state.currentLang === 'hi') {
    changeLanguage('cg', true);
  } else {
    changeLanguage('en', true);
  }
}

function toggleNavLangDropdown(event) {
  if (event) event.stopPropagation();
  const menu = document.getElementById('nav-lang-menu');
  if (!menu) return;
  menu.style.display = menu.style.display === 'block' ? 'none' : 'block';
}

function toggleFloatingLangMenu() {
  const menu = document.getElementById('floating-lang-menu');
  if (!menu) return;
  menu.style.display = menu.style.display === 'block' ? 'none' : 'block';
}

function openLanguageModal() {
  const modal = document.getElementById('language-modal');
  if (!modal) return;
  state.tempModalLang = state.currentLang;
  
  // Set engine select value
  const engineSel = document.getElementById('lang-engine-select');
  if (engineSel) engineSel.value = state.preferredEngine || 'auto';

  // Clear search input
  const searchInput = document.getElementById('lang-modal-search');
  if (searchInput) searchInput.value = '';

  renderLanguageModalCards(state.languagesList || SUPPORTED_LANGUAGES);
  modal.style.display = 'flex';
}

function closeLanguageModal() {
  const modal = document.getElementById('language-modal');
  if (modal) modal.style.display = 'none';
}

function filterLanguagesModal(query) {
  const q = (query || '').toLowerCase().trim();
  const all = state.languagesList && state.languagesList.length > 0 ? state.languagesList : SUPPORTED_LANGUAGES;
  if (!q) {
    renderLanguageModalCards(all);
    return;
  }
  const filtered = all.filter(l => 
    l.name.toLowerCase().includes(q) || 
    l.native_name.toLowerCase().includes(q) || 
    l.code.toLowerCase().includes(q) ||
    (l.region && l.region.toLowerCase().includes(q))
  );
  renderLanguageModalCards(filtered);
}

function filterLanguagesByRegion(region, btnElement) {
  document.querySelectorAll('.region-pill').forEach(p => p.classList.remove('active'));
  if (btnElement) btnElement.classList.add('active');

  const all = state.languagesList && state.languagesList.length > 0 ? state.languagesList : SUPPORTED_LANGUAGES;
  if (region === 'all') {
    renderLanguageModalCards(all);
    return;
  }
  const filtered = all.filter(l => l.category === region);
  renderLanguageModalCards(filtered);
}

function selectModalLanguage(langCode) {
  state.tempModalLang = langCode;
  document.querySelectorAll('.lang-card').forEach(el => el.classList.remove('selected'));
  const card = document.getElementById(`lang-card-${langCode}`);
  if (card) card.classList.add('selected');

  const modalSelectedLabel = document.getElementById('modal-selected-lang-label');
  if (modalSelectedLabel) {
    const cur = (state.languagesList || SUPPORTED_LANGUAGES).find(l => l.code === langCode);
    modalSelectedLabel.innerText = cur ? `${cur.flag} ${cur.native_name} (${cur.name})` : langCode;
  }
}

function applyModalLanguageSelection() {
  if (state.tempModalLang) {
    changeLanguage(state.tempModalLang, true);
  }
  closeLanguageModal();
}

function handleEngineChange(engine) {
  state.preferredEngine = engine;
  localStorage.setItem('gramcare_engine', engine);
}

// Dynamic Translation of Triage Results via API
async function translateActiveTriageResults(targetLang) {
  const lang = targetLang || state.currentLang;
  if (!state.lastPrediction) return;

  const btnRetranslate = document.getElementById('btn-retranslate');
  const btnText = document.getElementById('btn-retranslate-text');
  if (btnRetranslate && btnText) {
    btnRetranslate.disabled = true;
    btnText.innerText = 'Translating...';
  }

  const payload = {
    target_lang: lang,
    source_lang: 'en',
    condition: state.lastPrediction.condition,
    condition_description: state.lastPrediction.condition_description,
    action_advice: state.lastPrediction.action_advice,
    precautions: state.lastPrediction.precautions || [],
    risk_reasons: state.lastPrediction.risk_reasons || [],
    referral_facility: state.lastPrediction.referral_guidance ? state.lastPrediction.referral_guidance.facility : null,
    referral_action: state.lastPrediction.referral_guidance ? state.lastPrediction.referral_guidance.asha_action : null,
    generic_medicines: state.lastPrediction.generic_medicines || []
  };

  try {
    const response = await fetch('/api/translate/triage-result', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (response.ok) {
      const trans = await response.json();

      if (trans.condition) setText('condition-title', trans.condition);
      if (trans.condition_description) setText('condition-desc', trans.condition_description);
      if (trans.action_advice) setText('action-advice-text', trans.action_advice);

      if (trans.precautions && trans.precautions.length > 0) {
        const precList = document.getElementById('precautions-list');
        if (precList) {
          precList.innerHTML = trans.precautions.map(p => `<li>${escapeHtml(p)}</li>`).join('');
        }
      }

      if (trans.risk_reasons && trans.risk_reasons.length > 0) {
        const explainList = document.getElementById('explain-reasons-list');
        if (explainList) {
          explainList.innerHTML = trans.risk_reasons.map(r => `<li>${escapeHtml(r)}</li>`).join('');
        }
      }

      if (trans.referral_facility) {
        const timeframe = state.lastPrediction.referral_guidance ? state.lastPrediction.referral_guidance.timeframe : '';
        setText('referral-facility', `Facility: ${trans.referral_facility} (${timeframe})`);
      }
      if (trans.referral_action) {
        setText('referral-action', `ASHA Action: ${trans.referral_action}`);
      }

      if (trans.generic_medicines && trans.generic_medicines.length > 0) {
        const medsList = document.getElementById('generic-meds-list');
        if (medsList) {
          medsList.innerHTML = trans.generic_medicines.map(m => `
            <div class="med-item">
              <div>
                <div class="med-name">${escapeHtml(m.name)} <span style="font-weight: 500; font-size: 12px; color: var(--text-muted);">(${escapeHtml(m.type)})</span></div>
                <div class="med-purpose">${escapeHtml(m.purpose)}</div>
              </div>
              <div class="med-savings">${escapeHtml(m.savings)}</div>
            </div>
          `).join('');
        }
      }
    }
  } catch (err) {
    console.error('Failed to dynamically translate triage results:', err);
  } finally {
    if (btnRetranslate && btnText) {
      btnRetranslate.disabled = false;
      btnText.innerText = 'Translate';
    }
  }
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el && text !== undefined && text !== null) {
    el.innerText = text;
  }
}


// --- Patient Fast Search & Auto-fill ---
function setupPatientSearch() {
  const searchInput = document.getElementById('patient-search-input');
  if (!searchInput) return;

  searchInput.addEventListener('input', (e) => {
    const val = e.target.value.trim();
    if (val.length < 2) {
      hideSearchResults();
      return;
    }
    fetchPatientSuggestions(val);
  });
}

function handlePatientSearch(event) {
  if (event.key === 'Enter') {
    executePatientSearch();
  }
}

async function fetchPatientSuggestions(term) {
  try {
    const res = await fetch(`/api/patients?search=${encodeURIComponent(term)}&limit=5`);
    if (!res.ok) return;
    const patients = await res.json();
    renderSearchDropdown(patients);
  } catch (err) {
    console.error('Failed to search patients:', err);
  }
}

function executePatientSearch() {
  const term = document.getElementById('patient-search-input').value.trim();
  if (term) fetchPatientSuggestions(term);
}

function renderSearchDropdown(patients) {
  const container = document.getElementById('search-results-dropdown');
  if (!container) return;

  if (!patients || patients.length === 0) {
    container.innerHTML = '<div style="padding: 10px; font-size: 13px; color: var(--text-muted);">No matching patients found. Fill details below for new registration.</div>';
    container.style.display = 'block';
    return;
  }

  container.innerHTML = patients.map(p => `
    <div onclick="selectPatient('${p.patient_id}', '${escapeHtml(p.name)}', '${p.phone || ''}', '${escapeHtml(p.village || '')}', ${p.age || 'null'}, '${p.gender || 'Male'}', ${p.is_pregnant ? 'true' : 'false'}, '${escapeHtml((p.allergies || []).join(', '))}')"
         style="padding: 10px 14px; border-bottom: 1px solid var(--border); cursor: pointer; display: flex; justify-content: space-between; align-items: center; transition: background 0.15s;"
         onmouseover="this.style.background='#f1f5f9'" onmouseout="this.style.background='white'">
      <div>
        <strong style="color: var(--text-main); font-size: 13.5px;">${escapeHtml(p.name)}</strong>
        <span style="font-size: 12px; color: var(--text-muted); margin-left: 8px;">(${escapeHtml(p.village || 'Village N/A')})</span>
      </div>
      <div>
        <span class="patient-id-tag">${p.patient_id}</span>
        <span style="font-size: 11px; color: var(--text-muted); margin-left: 6px;">${p.visit_count || 0} visits</span>
      </div>
    </div>
  `).join('');
  container.style.display = 'block';
}

function hideSearchResults() {
  const container = document.getElementById('search-results-dropdown');
  if (container) container.style.display = 'none';
}

function selectPatient(patientId, name, phone, village, age, gender, isPregnant, allergies) {
  document.getElementById('patient-name').value = name;
  document.getElementById('patient-phone').value = phone || '';
  document.getElementById('patient-village').value = village || '';
  if (age !== 'null' && age) document.getElementById('patient-age').value = age;
  if (gender) document.getElementById('patient-gender').value = gender;
  
  const chkPregnant = document.getElementById('chk-pregnant');
  if (chkPregnant) chkPregnant.checked = isPregnant;

  const allergyInput = document.getElementById('patient-allergies');
  if (allergyInput) allergyInput.value = allergies || '';

  state.activePatientId = patientId;
  const idDisplay = document.getElementById('patient-id-display');
  if (idDisplay) idDisplay.innerText = `ID: ${patientId}`;
  
  hideSearchResults();
}

// --- Submit Triage & Evaluate Risk ---
async function submitTriage() {
  const symptoms = document.getElementById('symptoms-input').value.trim();
  const name = document.getElementById('patient-name').value.trim();
  const phone = document.getElementById('patient-phone').value.trim();
  const village = document.getElementById('patient-village').value.trim();
  const age = document.getElementById('patient-age').value;
  const gender = document.getElementById('patient-gender').value;

  const isPregnant = document.getElementById('chk-pregnant') ? document.getElementById('chk-pregnant').checked : false;
  
  const comorbidities = [];
  if (document.getElementById('chk-diabetic')?.checked) comorbidities.push('Diabetes');
  if (document.getElementById('chk-hypertension')?.checked) comorbidities.push('Hypertension');
  if (document.getElementById('chk-asthma')?.checked) comorbidities.push('Asthma');

  const allergyText = document.getElementById('patient-allergies')?.value.trim();
  const allergies = allergyText ? allergyText.split(',').map(a => a.trim()).filter(Boolean) : [];

  if (!symptoms) {
    alert(state.currentLang === 'hi' 
      ? 'कृपया पहले लक्षणों का विवरण दर्ज करें।' 
      : 'Please enter symptoms description first.');
    document.getElementById('symptoms-input').focus();
    return;
  }

  setLoadingState(true);

  const payload = {
    symptoms: symptoms,
    patient_name: name || (state.currentRole === 'asha' ? 'Unknown Patient' : (state.activeFamilyMember ? state.activeFamilyMember.name : 'Self-Care Visitor')),
    phone: phone || null,
    village: village || null,
    age: age ? parseInt(age) : null,
    gender: gender || null,
    is_pregnant: isPregnant,
    comorbidities: comorbidities,
    allergies: allergies,
    user_id: state.currentUser ? state.currentUser.user_id : null,
    token_id: (state.currentRole === 'asha') ? state.activeTokenId : null,
    family_member_id: (state.currentRole === 'patient' && state.activeFamilyMember) ? state.activeFamilyMember.member_id : null,
    family_member_name: (state.currentRole === 'patient' && state.activeFamilyMember) ? state.activeFamilyMember.name : null
  };

  // Offline Check
  if (!navigator.onLine) {
    saveToOfflineQueue(payload);
    setLoadingState(false);
    alert('You appear to be offline. Consultation saved to local queue and will sync when internet reconnects.');
    return;
  }

  try {
    const response = await fetch('/api/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'Prediction failed');
    }

    const data = await response.json();
    state.lastPrediction = data;
    state.activePatientId = data.patient_id;

    if (data.patient_id) {
      const idDisplay = document.getElementById('patient-id-display');
      if (idDisplay) idDisplay.innerText = `ID: ${data.patient_id}`;
    }

    renderTriageResults(data);

  } catch (err) {
    alert(`Triage Error: ${err.message}`);
    console.error('Triage submission failed:', err);
  } finally {
    setLoadingState(false);
  }
}

function setLoadingState(isLoading) {
  const submitBtn = document.getElementById('btn-submit-triage');
  const emptyCard = document.getElementById('empty-state-card');
  const loadingCard = document.getElementById('loading-card');
  const resultsCard = document.getElementById('results-card');

  if (submitBtn) submitBtn.disabled = isLoading;

  if (isLoading) {
    if (emptyCard) emptyCard.style.display = 'none';
    if (resultsCard) resultsCard.style.display = 'none';
    if (loadingCard) loadingCard.style.display = 'block';
  } else {
    if (loadingCard) loadingCard.style.display = 'none';
  }
}

// --- Render Triage Results ---
function renderTriageResults(data) {
  const resultsCard = document.getElementById('results-card');
  const emptyCard = document.getElementById('empty-state-card');
  if (emptyCard) emptyCard.style.display = 'none';
  if (resultsCard) {
    resultsCard.style.display = 'block';
    resultsCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // 1. Emergency Override Banner
  const emergencyBanner = document.getElementById('emergency-banner');
  if (emergencyBanner) {
    if (data.emergency_override) {
      emergencyBanner.style.display = 'block';
      emergencyBanner.classList.add('active');
    } else {
      emergencyBanner.style.display = 'none';
      emergencyBanner.classList.remove('active');
    }
  }

  // 2. Acuity Banner
  const riskLevel = data.risk_level.toUpperCase();
  const acuityBanner = document.getElementById('acuity-banner');
  const acuityIcon = document.getElementById('acuity-icon');
  const acuityTitle = document.getElementById('acuity-title');
  const acuitySummary = document.getElementById('acuity-summary');

  acuityBanner.className = 'triage-acuity-banner';

  if (riskLevel === 'HIGH') {
    acuityBanner.classList.add('risk-high');
    acuityIcon.innerText = '🚨';
    acuityTitle.innerText = data.emergency_override ? 'CRITICAL EMERGENCY – OVERRIDE ACTIVATED' : 'HIGH RISK – IMMEDIATE REFERRAL';
    acuitySummary.innerText = 'Urgent medical attention required. Transfer to Primary Health Centre / Emergency immediately.';
  } else if (riskLevel === 'MEDIUM') {
    acuityBanner.classList.add('risk-medium');
    acuityIcon.innerText = '📹';
    acuityTitle.innerText = 'MEDIUM RISK – ONLINE DOCTOR VIDEO CONSULTATION REQUIRED';
    acuitySummary.innerText = 'Self-cure is NOT recommended for this condition. Direct online doctor video consultation is required immediately.';
  } else {
    acuityBanner.classList.add('risk-low');
    acuityIcon.innerText = '✅';
    acuityTitle.innerText = 'LOW RISK – MILD / HOME CARE';
    acuitySummary.innerText = 'Home observation and supportive care recommended. Observe precautions.';
  }

  // 2b. Telemedicine Online Doctor Video Call Card (Mandatory for Medium Risk)
  const telemedCard = document.getElementById('telemedicine-card');
  if (telemedCard) {
    if (riskLevel === 'MEDIUM' || (data.telemedicine && data.telemedicine.available)) {
      telemedCard.style.display = 'block';
      state.activeTelemedicine = data.telemedicine;
      if (data.telemedicine) {
        setText('telemed-doctor-name', data.telemedicine.doctor_name || 'Dr. Anjali Verma, MBBS');
        setText('telemed-doctor-role', `${data.telemedicine.doctor_role || 'Medical Officer'} • ${data.telemedicine.organization || 'e-Sanjeevani Network'}`);
      }
    } else {
      telemedCard.style.display = 'none';
      state.activeTelemedicine = null;
    }
  }

  // 3. Follow-up Badge
  const followupBadge = document.getElementById('followup-badge-display');
  const followupText = document.getElementById('followup-text');
  if (followupBadge && followupText && data.followup_date) {
    followupText.innerText = `Next Scheduled Follow-up: ${data.followup_date}`;
    followupBadge.style.display = 'inline-flex';
  }

  // 4. Longitudinal Alert
  const longAlertBox = document.getElementById('longitudinal-alert-box');
  const longAlertMsg = document.getElementById('longitudinal-message');
  if (data.longitudinal_alert || (data.longitudinal_analysis && data.longitudinal_analysis.alert_message)) {
    const msg = data.longitudinal_alert || data.longitudinal_analysis.alert_message;
    longAlertMsg.innerText = msg;
    longAlertBox.style.display = 'block';
    longAlertBox.classList.add('active');
  } else {
    longAlertBox.style.display = 'none';
    longAlertBox.classList.remove('active');
  }

  // 5. Explainability Reasons Checklist
  const explainList = document.getElementById('explain-reasons-list');
  if (explainList && data.risk_reasons && data.risk_reasons.length > 0) {
    explainList.innerHTML = data.risk_reasons.map(r => `<li>${escapeHtml(r)}</li>`).join('');
  }

  // 6. Top-3 Differential Diagnoses Ranking
  const diffList = document.getElementById('differential-items-list');
  if (diffList && data.top_conditions && data.top_conditions.length > 0) {
    diffList.innerHTML = data.top_conditions.map((item, idx) => `
      <div class="differential-item">
        <div class="differential-meta">
          <span>${idx + 1}. ${escapeHtml(item.disease)}</span>
          <span style="color: var(--primary); font-weight: 700;">${item.confidence_pct}%</span>
        </div>
        <div class="diff-bar-bg">
          <div class="diff-bar-fill" style="width: ${Math.min(100, Math.max(10, item.confidence_pct))}%;"></div>
        </div>
      </div>
    `).join('');
  }

  // 7. Condition & Advice
  setText('condition-title', data.condition || 'Clinical Evaluation');
  setText('confidence-label', `Confidence: ${(data.confidence * 100).toFixed(1)}%`);
  setText('condition-desc', data.condition_description || 'Evaluated across rural primary symptom database.');
  setText('action-advice-text', data.action_advice);

  // 8. Precautions List
  const precList = document.getElementById('precautions-list');
  if (precList) {
    precList.innerHTML = (data.precautions && data.precautions.length > 0)
      ? data.precautions.map(p => `<li>${escapeHtml(p)}</li>`).join('')
      : '<li>Maintain hydration, rest in well-ventilated space, and observe for symptom progression.</li>';
  }

  // 9. Generic Medicines (Allergy Filtered)
  const medsList = document.getElementById('generic-meds-list');
  if (medsList) {
    if (data.generic_medicines && data.generic_medicines.length > 0) {
      medsList.innerHTML = data.generic_medicines.map(m => `
        <div class="med-item">
          <div>
            <div class="med-name">${escapeHtml(m.name)} <span style="font-weight: 500; font-size: 12px; color: var(--text-muted);">(${escapeHtml(m.type)})</span></div>
            <div class="med-purpose">${escapeHtml(m.purpose)}</div>
          </div>
          <div class="med-savings">${escapeHtml(m.savings)}</div>
        </div>
      `).join('');
    } else {
      medsList.innerHTML = '<div style="font-size: 13px; color: var(--text-muted);">No specific generic alternatives required or omitted due to reported drug allergy.</div>';
    }
  }

  // 10. Referral Slip Details & Care-loop Status
  if (data.referral_guidance) {
    setText('referral-facility', `Facility: ${data.referral_guidance.facility} (${data.referral_guidance.timeframe})`);
    setText('referral-action', `ASHA Action: ${data.referral_guidance.asha_action}`);
  }

  const referralSelect = document.getElementById('referral-status-select');
  if (referralSelect && data.referral_status) {
    referralSelect.value = data.referral_status;
  }

  // 11. Automatic dynamic translation if active language is not English
  if (state.currentLang && state.currentLang !== 'en') {
    translateActiveTriageResults(state.currentLang);
  }
}

// --- Care-Loop Referral Status Updater ---
async function updateActiveReferralStatus() {
  if (!state.lastPrediction || !state.lastPrediction.record_id) {
    alert('No active triage record selected.');
    return;
  }

  const select = document.getElementById('referral-status-select');
  const status = select ? select.value : 'Referral Generated';

  try {
    const res = await fetch(`/api/history/${state.lastPrediction.record_id}/referral-status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        referral_status: status,
        doctor_notes: `Status updated to '${status}' by ASHA worker.`
      })
    });

    if (!res.ok) throw new Error('Status update failed');
    alert(`Care-loop referral status saved: '${status}'`);
    state.lastPrediction.referral_status = status;
  } catch (err) {
    alert(`Could not save referral status: ${err.message}`);
  }
}

// --- Health Analytics & Outbreak Surveillance ---
async function loadAnalyticsDashboard() {
  try {
    const res = await fetch('/api/analytics');
    if (!res.ok) throw new Error('Analytics failed to load');
    const data = await res.json();

    setText('metric-total-consults', data.total_consultations);
    setText('metric-total-patients', data.total_patients);
    setText('metric-high-risk', data.risk_breakdown['High'] || 0);
    setText('metric-emergency-overrides', data.emergency_overrides || 0);

    // Render Village Outbreak Heatmap
    const tbody = document.getElementById('outbreak-table-body');
    if (tbody) {
      if (!data.village_stats || data.village_stats.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 16px;">No village records yet.</td></tr>';
      } else {
        tbody.innerHTML = data.village_stats.map(v => {
          const highBadge = v.high_risk_count > 0 
            ? `<span style="background: #fee2e2; color: #dc2626; padding: 2px 6px; border-radius: 4px; font-weight: bold;">${v.high_risk_count} Urgent</span>`
            : '<span style="color: var(--text-muted); font-size: 12px;">0</span>';

          return `
            <tr>
              <td><strong>${escapeHtml(v.village)}</strong></td>
              <td><span style="font-weight: 700;">${v.count}</span></td>
              <td>${highBadge}</td>
              <td><span style="font-size: 12px; color: var(--primary);">${escapeHtml(v.primary_condition || 'Various')}</span></td>
            </tr>
          `;
        }).join('');
      }
    }

    // Render Follow-ups Due
    const fBody = document.getElementById('followups-list-body');
    const fCount = document.getElementById('followups-due-count');
    if (fCount) fCount.innerText = `${data.followups_due_count} Due`;

    if (fBody) {
      if (!data.followups_due || data.followups_due.length === 0) {
        fBody.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 20px;">No pending follow-ups due today.</div>';
      } else {
        fBody.innerHTML = data.followups_due.map(f => `
          <div style="background: var(--surface-alt); padding: 10px 12px; border-radius: 6px; margin-bottom: 8px; border: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
            <div>
              <strong style="font-size: 13px;">${escapeHtml(f.patient_name || 'Patient')}</strong> 
              <span style="font-size: 11px; color: var(--text-muted);">(${escapeHtml(f.village || 'N/A')})</span>
              <div style="font-size: 11.5px; color: var(--text-muted);">${escapeHtml(f.condition || 'Triage')} • Due: ${f.followup_date}</div>
            </div>
            <span style="font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 4px; background: #e0f2fe; color: #0369a1;">
              ${escapeHtml(f.referral_status)}
            </span>
          </div>
        `).join('');
      }
    }

  } catch (err) {
    console.error('Analytics load error:', err);
  }
}

// --- Patient Registry ---
async function loadPatientRegistry() {
  const tbody = document.getElementById('patient-table-body');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 24px;">Loading patient registry...</td></tr>';

  try {
    const res = await fetch('/api/patients?limit=50');
    if (!res.ok) throw new Error('Failed to load patient records');
    const patients = await res.json();

    if (!patients || patients.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 24px;">No registered patients found. Conduct triage to add records.</td></tr>';
      return;
    }

    tbody.innerHTML = patients.map(p => {
      const riskClass = (p.latest_risk || '').toLowerCase();
      const riskBadgeStyle = riskClass === 'high' 
        ? 'background: var(--risk-high-bg); color: var(--risk-high); border: 1px solid var(--risk-high-border);'
        : riskClass === 'medium'
        ? 'background: var(--risk-medium-bg); color: var(--risk-medium); border: 1px solid var(--risk-medium-border);'
        : 'background: var(--risk-low-bg); color: var(--risk-low); border: 1px solid var(--risk-low-border);';

      return `
        <tr>
          <td><strong style="color: var(--primary);">${p.patient_id}</strong></td>
          <td><strong>${escapeHtml(p.name)}</strong></td>
          <td>${escapeHtml(p.village || 'N/A')}</td>
          <td>${p.age || '-'} / ${p.gender || '-'}</td>
          <td><span style="font-weight: 700; background: var(--surface-alt); padding: 2px 8px; border-radius: 10px;">${p.visit_count || 1}</span></td>
          <td>
            <span style="font-size: 11px; font-weight: 800; padding: 3px 8px; border-radius: var(--radius-sm); ${riskBadgeStyle}">
              ${p.latest_risk || 'N/A'}
            </span>
          </td>
          <td>${escapeHtml(p.latest_condition || 'N/A')}</td>
          <td>
            <button class="btn-secondary" style="padding: 4px 10px; font-size: 12px;" onclick="openPatientTimeline('${p.patient_id}', '${escapeHtml(p.name)}')">
              📜 Timeline
            </button>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--risk-high); padding: 24px;">Error: ${err.message}</td></tr>`;
  }
}

function filterPatientTable(query) {
  const q = query.toLowerCase().trim();
  const rows = document.querySelectorAll('#patient-table-body tr');
  rows.forEach(row => {
    const text = row.innerText.toLowerCase();
    row.style.display = text.includes(q) ? '' : 'none';
  });
}

// --- Longitudinal Timeline Modal ---
async function openPatientTimeline(patientId, patientName) {
  const modal = document.getElementById('timeline-modal');
  const modalTitle = document.getElementById('timeline-modal-title');
  const modalBody = document.getElementById('timeline-modal-body');

  if (modalTitle) modalTitle.innerText = `Longitudinal Health Timeline: ${patientName} (${patientId})`;
  if (modalBody) modalBody.innerHTML = '<div style="text-align: center; padding: 24px; color: var(--text-muted);">Fetching consultation history...</div>';
  if (modal) modal.classList.add('active');

  try {
    const res = await fetch(`/api/patients/${patientId}/timeline`);
    if (!res.ok) throw new Error('Could not retrieve timeline');
    const data = await res.json();

    if (!data.timeline || data.timeline.length === 0) {
      modalBody.innerHTML = '<div style="text-align: center; padding: 24px; color: var(--text-muted);">No past consultations recorded for this patient.</div>';
      return;
    }

    modalBody.innerHTML = `
      <div style="margin-bottom: 16px; background: var(--surface-alt); padding: 12px 16px; border-radius: var(--radius-md); font-size: 13px;">
        <strong>Total Recorded Visits:</strong> ${data.total_consultations} | 
        <strong>Village:</strong> ${escapeHtml(data.patient.village || 'N/A')} | 
        <strong>Mobile:</strong> ${data.patient.phone || 'N/A'}
      </div>
      <div class="timeline">
        ${data.timeline.map((item, idx) => {
          const riskLower = (item.risk_level || 'low').toLowerCase();
          const dotClass = riskLower === 'high' ? 'high' : riskLower === 'medium' ? 'medium' : 'low';
          const visitDate = item.created_at ? item.created_at.replace('T', ' ').substring(0, 16) : 'Unknown Date';

          return `
            <div class="timeline-item">
              <div class="timeline-dot ${dotClass}"></div>
              <div class="timeline-card">
                <div class="timeline-date">Visit #${data.total_consultations - idx} • ${visitDate}</div>
                <div class="timeline-condition">
                  <span>${escapeHtml(item.condition || 'General Triage')}</span>
                  <span style="font-size: 11px; font-weight: 800; padding: 2px 8px; border-radius: 4px; background: white;">
                    ${item.risk_level} (${(item.confidence * 100).toFixed(0)}%)
                  </span>
                </div>
                <div class="timeline-symptoms"><strong>Symptoms:</strong> ${escapeHtml(item.symptoms)}</div>
                ${item.longitudinal_alert ? `<div style="margin-top: 6px; font-size: 12px; color: #c2410c; background: #fff7ed; padding: 6px; border-radius: 4px;">⚠️ ${escapeHtml(item.longitudinal_alert)}</div>` : ''}
              </div>
            </div>
          `;
        }).join('')}
      </div>
    `;

  } catch (err) {
    modalBody.innerHTML = `<div style="color: var(--risk-high); padding: 24px;">Failed to load timeline: ${err.message}</div>`;
  }
}

function viewPatientTimeline() {
  if (!state.activePatientId) {
    alert('No active patient selected.');
    return;
  }
  const name = document.getElementById('patient-name').value.trim() || 'Patient';
  openPatientTimeline(state.activePatientId, name);
}

function closeTimelineModal() {
  const modal = document.getElementById('timeline-modal');
  if (modal) modal.classList.remove('active');
}

// --- Print / Export Comprehensive Consultation Report ---
function printReferralSlip() {
  if (!state.lastPrediction) {
    alert('Please run triage assessment first.');
    return;
  }

  const p = state.lastPrediction;
  const patientName = p.patient_info.patient_name || 'Patient';
  const age = p.patient_info.age || 'N/A';
  const village = p.patient_info.village || 'N/A';
  const patientId = p.patient_id || 'N/A';
  const phone = p.patient_info.phone || 'N/A';
  const dateStr = new Date().toLocaleString();

  const printWindow = window.open('', '_blank');
  printWindow.document.write(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>GramCare AI - Clinical Consultation & Referral Report</title>
      <style>
        body { font-family: 'Arial', sans-serif; padding: 30px; color: #1e293b; max-width: 720px; margin: 0 auto; line-height: 1.5; font-size: 13px; }
        .header { border-bottom: 2.5px solid #0d9488; padding-bottom: 12px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; }
        .title { font-size: 24px; font-weight: bold; color: #0d9488; }
        .badge { padding: 6px 14px; border-radius: 4px; font-weight: bold; font-size: 14px; text-transform: uppercase; }
        .badge.high { background: #fee2e2; color: #dc2626; border: 1.5px solid #fca5a5; }
        .badge.medium { background: #fef3c7; color: #d97706; border: 1.5px solid #fcd34d; }
        .badge.low { background: #d1fae5; color: #059669; border: 1.5px solid #6ee7b7; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
        .label { font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: bold; }
        .val { font-size: 14px; font-weight: 600; }
        .box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; margin-bottom: 12px; }
        .table { width: 100%; border-collapse: collapse; margin-top: 6px; }
        .table th, .table td { padding: 6px 8px; border-bottom: 1px solid #e2e8f0; font-size: 12.5px; text-align: left; }
        .footer { margin-top: 24px; border-top: 1px dashed #cbd5e1; padding-top: 14px; display: flex; justify-content: space-between; font-size: 11px; color: #64748b; }
      </style>
    </head>
    <body>
      <div class="header">
        <div>
          <div class="title">GramCare AI</div>
          <div style="font-size: 12px; color: #64748b;">Clinical Decision-Support & Rural Referral Document</div>
        </div>
        <div class="badge ${p.risk_level.toLowerCase()}">${p.risk_level} RISK</div>
      </div>

      <div class="grid-2">
        <div>
          <div class="label">Patient Name & ID:</div>
          <div class="val">${escapeHtml(patientName)} (${patientId})</div>
        </div>
        <div>
          <div class="label">Village & Mobile:</div>
          <div class="val">${escapeHtml(village)} | ${phone}</div>
        </div>
      </div>

      <div class="box">
        <div class="label">Reported Symptoms:</div>
        <div style="font-size: 13.5px; margin-top: 4px;">${escapeHtml(p.symptoms)}</div>
      </div>

      ${p.emergency_override ? `
        <div class="box" style="background: #fef2f2; border-color: #f87171;">
          <div class="label" style="color: #b91c1c;">🚨 EMERGENCY OVERRIDE ACTIVATED:</div>
          <div style="font-weight: bold; color: #dc2626; margin-top: 2px;">Critical life-safety symptoms detected. Immediate emergency medical transport required.</div>
        </div>
      ` : ''}

      <div class="box">
        <div class="label">Primary Condition & Clinical Diagnosis:</div>
        <div class="val" style="color: #0f766e; font-size: 16px;">${escapeHtml(p.condition || 'General Evaluation')} (Confidence: ${(p.confidence * 100).toFixed(0)}%)</div>
        <div style="margin-top: 4px; color: #475569;">${escapeHtml(p.condition_description || '')}</div>
        
        ${p.top_conditions && p.top_conditions.length > 1 ? `
          <div style="margin-top: 8px; font-size: 12px;">
            <strong>Differential Diagnoses:</strong> ${p.top_conditions.map(c => `${escapeHtml(c.disease)} (${c.confidence_pct}%)`).join(', ')}
          </div>
        ` : ''}
      </div>

      ${p.risk_reasons && p.risk_reasons.length > 0 ? `
        <div class="box" style="background: #f0fdfa; border-color: #99f6e4;">
          <div class="label" style="color: #0f766e;">Clinical Risk Rationale:</div>
          <ul style="margin: 4px 0 0 16px; font-size: 12.5px;">
            ${p.risk_reasons.map(r => `<li>${escapeHtml(r)}</li>`).join('')}
          </ul>
        </div>
      ` : ''}

      <div class="box">
        <div class="label">Affordable Generic Medicines (Jan Aushadhi Scheme):</div>
        ${p.generic_medicines && p.generic_medicines.length > 0 ? `
          <table class="table">
            <thead><tr><th>Generic Medicine</th><th>Purpose</th><th>Estimated Savings</th></tr></thead>
            <tbody>
              ${p.generic_medicines.map(m => `
                <tr>
                  <td><strong>${escapeHtml(m.name)}</strong> (${escapeHtml(m.type)})</td>
                  <td>${escapeHtml(m.purpose)}</td>
                  <td>${escapeHtml(m.savings)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        ` : '<div>Home supportive hydration and rest advised.</div>'}
      </div>

      <div class="grid-2">
        <div class="box" style="background: #fff7ed; border-color: #fed7aa;">
          <div class="label" style="color: #c2410c;">Referral Facility:</div>
          <div style="font-weight: bold; color: #9a3412;">${p.referral_guidance ? p.referral_guidance.facility : 'Primary Health Centre'}</div>
          <div style="font-size: 11.5px; color: #9a3412; margin-top: 2px;">${p.referral_guidance ? p.referral_guidance.asha_action : ''}</div>
        </div>
        <div class="box" style="background: #eff6ff; border-color: #bfdbfe;">
          <div class="label" style="color: #1d4ed8;">Scheduled Follow-Up:</div>
          <div style="font-weight: bold; color: #1e40af; font-size: 15px;">${p.followup_date || 'Within 7 Days'}</div>
          <div style="font-size: 11.5px; color: #1e40af; margin-top: 2px;">Status: ${p.referral_status || 'Referral Generated'}</div>
        </div>
      </div>

      <div class="footer">
        <div>
          <div>Generated on: ${dateStr}</div>
          <div style="margin-top: 2px;">Report ID: GC-REP-${p.record_id || '01'} | Valid for PHC Consultation</div>
        </div>
        <div style="text-align: right;">
          <div style="border-top: 1px solid #94a3b8; width: 140px; margin-top: 16px; margin-left: auto;"></div>
          <div>ASHA Worker / Officer Signature</div>
        </div>
      </div>
    </body>
    </html>
  `);
  printWindow.document.close();
  printWindow.focus();
  setTimeout(() => printWindow.print(), 350);
}

// --- Offline Synchronization Queue ---
function setupOfflineSync() {
  window.addEventListener('online', () => {
    syncOfflineQueue();
  });
}

function saveToOfflineQueue(payload) {
  try {
    const queue = JSON.parse(localStorage.getItem('gramcare_offline_queue') || '[]');
    queue.push({ payload, queued_at: new Date().toISOString() });
    localStorage.setItem('gramcare_offline_queue', JSON.stringify(queue));
  } catch (e) {
    console.error('LocalStorage write error:', e);
  }
}

async function syncOfflineQueue() {
  try {
    const raw = localStorage.getItem('gramcare_offline_queue');
    if (!raw) return;
    const queue = JSON.parse(raw);
    if (!queue.length) return;

    for (const item of queue) {
      await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(item.payload)
      });
    }
    localStorage.removeItem('gramcare_offline_queue');
    alert(`Online sync complete! ${queue.length} offline consultation(s) synced to database.`);
  } catch (err) {
    console.warn('Sync failed:', err);
  }
}

// --- Health Check ---
async function checkApiHealth() {
  try {
    const res = await fetch('/api/health');
    const data = await res.json();
    const indicator = document.getElementById('status-label');
    if (indicator && data.status === 'ok') {
      indicator.innerText = 'ML Active (Triage Ready)';
    }
  } catch (e) {
    const indicator = document.getElementById('status-label');
    if (indicator) indicator.innerText = 'Offline Mode';
  }
}

// --- Utility Helpers ---
function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ==========================================================================
// Telemedicine Live Video Consultation Modal & WebRTC Controller
// ==========================================================================
let callTimerInterval = null;
let callSeconds = 0;
let isMicMuted = false;
let isCamOff = false;

function openVideoConsultation() {
  const modal = document.getElementById('video-call-modal');
  const iframe = document.getElementById('video-frame');
  const placeholder = document.getElementById('video-placeholder');
  const timerBadge = document.getElementById('call-timer-display');

  if (!modal) return;

  // Retrieve current active record and telemedicine info
  const prediction = state.lastPrediction || {};
  const telemed = state.activeTelemedicine || prediction.telemedicine || {};

  // Populate Clinical Patient Summary in modal sidebar
  const patientInfo = prediction.patient_info || {};
  setText('telemed-patient-name', patientInfo.patient_name || 'Anonymous Patient');
  setText('telemed-patient-meta', `${patientInfo.age ? patientInfo.age + ' yrs' : '--'} / ${patientInfo.gender || '--'}`);
  setText('telemed-patient-village', patientInfo.village || 'Primary Health Sub-centre');
  setText('telemed-patient-condition', prediction.condition || 'General Clinical Review');
  setText('telemed-patient-symptoms', prediction.symptoms || '--');

  // Room URL
  const roomUrl = telemed.room_url || `https://meet.jit.si/GramCare-Consult-${prediction.record_id || Date.now()}#config.prejoinPageEnabled=false`;

  // Display modal
  modal.style.display = 'flex';
  if (placeholder) placeholder.style.display = 'flex';

  if (iframe) {
    iframe.src = roomUrl;
    iframe.onload = () => {
      if (placeholder) placeholder.style.display = 'none';
    };
  }

  // Start Call Timer
  callSeconds = 0;
  if (timerBadge) timerBadge.innerText = '00:00';
  clearInterval(callTimerInterval);
  callTimerInterval = setInterval(() => {
    callSeconds++;
    const mins = String(Math.floor(callSeconds / 60)).padStart(2, '0');
    const secs = String(callSeconds % 60).padStart(2, '0');
    if (timerBadge) timerBadge.innerText = `${mins}:${secs}`;
  }, 1000);
}

function closeVideoConsultation() {
  const modal = document.getElementById('video-call-modal');
  const iframe = document.getElementById('video-frame');
  const placeholder = document.getElementById('video-placeholder');

  if (modal) modal.style.display = 'none';
  if (iframe) iframe.src = 'about:blank';
  if (placeholder) placeholder.style.display = 'flex';

  clearInterval(callTimerInterval);
  callTimerInterval = null;
  callSeconds = 0;
}

function copyVideoLink() {
  const telemed = state.activeTelemedicine || (state.lastPrediction && state.lastPrediction.telemedicine);
  const link = telemed ? telemed.room_url : window.location.href;

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(link).then(() => {
      alert(`Telemedicine Video Consultation Link copied to clipboard:\n${link}\n\nShare with patient or visiting specialist.`);
    }).catch(() => {
      prompt('Copy video consultation link:', link);
    });
  } else {
    prompt('Copy video consultation link:', link);
  }
}

function toggleCallMic() {
  isMicMuted = !isMicMuted;
  const btn = document.getElementById('btn-toggle-mic');
  if (btn) {
    if (isMicMuted) {
      btn.innerText = '🔇 Mic Muted';
      btn.classList.add('active-off');
    } else {
      btn.innerText = '🎤 Mic On';
      btn.classList.remove('active-off');
    }
  }
}

function toggleCallCam() {
  isCamOff = !isCamOff;
  const btn = document.getElementById('btn-toggle-cam');
  if (btn) {
    if (isCamOff) {
      btn.innerText = '🚫 Cam Off';
      btn.classList.add('active-off');
    } else {
      btn.innerText = '📷 Cam On';
      btn.classList.remove('active-off');
    }
  }
}

async function completeConsultationDialog() {
  const prediction = state.lastPrediction || {};
  const telemed = state.activeTelemedicine || prediction.telemedicine || {};

  const notes = prompt('Enter Medical Officer Consultation & Rx Notes (optional):', 'Patient evaluated via video consultation. Prescription issued. Advised 3-day recovery follow-up.');
  if (notes === null) return; // User cancelled

  if (telemed.session_id) {
    try {
      await fetch(`/api/telemedicine/session/${telemed.session_id}/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          doctor_notes: notes,
          rx_medicines: [],
          followup_advice: 'Follow prescription and report if symptoms persist'
        })
      });
    } catch (e) {
      console.warn('Could not post session completion:', e);
    }
  }

  // Update referral status in database to 'Doctor Consulted'
  if (prediction.record_id) {
    try {
      await fetch(`/api/history/${prediction.record_id}/referral-status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          referral_status: 'Doctor Consulted',
          doctor_notes: notes
        })
      });
      const select = document.getElementById('referral-status-select');
      if (select) select.value = 'Doctor Consulted';
      if (state.lastPrediction) state.lastPrediction.referral_status = 'Doctor Consulted';
    } catch (e) {
      console.warn('Status update failed:', e);
    }
  }

  alert('✅ Video consultation recorded successfully! Status updated to "Doctor Consulted".');
  closeVideoConsultation();
}

// ==========================================================================
// Authentication & Role Management Controller
// ==========================================================================
let currentAuthTab = 'asha';

function openAuthModal() {
  const modal = document.getElementById('auth-modal');
  if (modal) modal.style.display = 'flex';
}

function closeAuthModal() {
  const modal = document.getElementById('auth-modal');
  if (modal) modal.style.display = 'none';
}

function switchAuthTab(tab) {
  currentAuthTab = tab;
  document.querySelectorAll('.auth-tab-btn').forEach(btn => btn.classList.remove('active'));
  const activeBtn = document.getElementById(`tab-login-${tab}`);
  if (activeBtn) activeBtn.classList.add('active');

  const nameGroup = document.getElementById('auth-fullname-group');
  const vilGroup = document.getElementById('auth-village-group');
  const userLabel = document.getElementById('lbl-auth-username');
  const userInput = document.getElementById('auth-username');
  const submitBtn = document.getElementById('btn-auth-submit');

  if (tab === 'register') {
    if (nameGroup) nameGroup.style.display = 'block';
    if (vilGroup) vilGroup.style.display = 'block';
    if (userLabel) userLabel.innerText = 'Mobile Number or Username *';
    if (userInput) userInput.placeholder = 'e.g. 9812345678 or ramesh';
    if (submitBtn) submitBtn.innerText = 'Create Secure Account';
  } else if (tab === 'asha') {
    if (nameGroup) nameGroup.style.display = 'none';
    if (vilGroup) vilGroup.style.display = 'none';
    if (userLabel) userLabel.innerText = 'ASHA Worker ID / Phone / Email *';
    if (userInput) userInput.placeholder = 'e.g. asha@gramcare.gov.in';
    if (submitBtn) submitBtn.innerText = 'Sign In as ASHA Worker';
  } else {
    if (nameGroup) nameGroup.style.display = 'none';
    if (vilGroup) vilGroup.style.display = 'none';
    if (userLabel) userLabel.innerText = 'Patient Mobile / Email *';
    if (userInput) userInput.placeholder = 'e.g. patient@gramcare.in or 9812345678';
    if (submitBtn) submitBtn.innerText = 'Sign In to Patient Vault';
  }
}

async function demoLoginAsha() {
  const usernameInput = document.getElementById('auth-username');
  const passwordInput = document.getElementById('auth-password');
  if (usernameInput) usernameInput.value = 'asha@gramcare.gov.in';
  if (passwordInput) passwordInput.value = 'asha123';
  await executeLogin('asha@gramcare.gov.in', 'asha123');
}

async function demoLoginPatient() {
  const usernameInput = document.getElementById('auth-username');
  const passwordInput = document.getElementById('auth-password');
  if (usernameInput) usernameInput.value = 'patient@gramcare.in';
  if (passwordInput) passwordInput.value = 'patient123';
  await executeLogin('patient@gramcare.in', 'patient123');
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  const username = document.getElementById('auth-username').value.trim();
  const password = document.getElementById('auth-password').value;

  if (currentAuthTab === 'register') {
    const fullName = document.getElementById('auth-fullname').value.trim();
    const village = document.getElementById('auth-village').value.trim();
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: username,
          password: password,
          full_name: fullName || 'Patient User',
          role: 'patient',
          village: village || 'Village'
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Registration failed');
      onUserAuthenticated(data.user, data.session_token);
      alert(`Account registered successfully! Welcome to GramCare, ${data.user.full_name}.`);
    } catch (err) {
      alert(`Registration Error: ${err.message}`);
    }
  } else {
    await executeLogin(username, password);
  }
}

async function executeLogin(username, password) {
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Login failed');
    onUserAuthenticated(data.user, data.session_token);
    closeAuthModal();
  } catch (err) {
    alert(`Authentication Error: ${err.message}`);
  }
}

async function triggerGoogleLogin() {
  const defaultEmail = 'dhawal.gramcare@gmail.com';
  const defaultName = 'Dhawal Sharma';

  const emailInput = prompt('Google Sign-In\n\nEnter your Google account email to sign in or auto-register:', defaultEmail);
  if (!emailInput) return;

  const email = emailInput.trim();
  const name = email === defaultEmail 
    ? defaultName 
    : email.split('@')[0].replace(/[._]/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

  try {
    const res = await fetch('/api/auth/google', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: email,
        name: name,
        google_id: 'goog_' + btoa(encodeURIComponent(email)).replace(/=/g, '').slice(0, 16),
        village: 'Rural Health Sub-centre'
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Google sign-in failed');
    onUserAuthenticated(data.user, data.session_token);
    closeAuthModal();
    alert(`✅ Successfully signed in with Google as ${data.user.full_name}!\nFamily & Health Vault is now accessible.`);
  } catch (err) {
    alert(`Google Sign-In Error: ${err.message}`);
  }
}

function onUserAuthenticated(user, sessionToken) {
  state.currentUser = user;
  state.sessionToken = sessionToken;
  updateAuthBadge();

  if (user.role === 'asha') {
    toggleRoleMode('asha');
  } else {
    toggleRoleMode('patient');
    loadFamilyMembers(user.user_id);
  }
}

function handleLogout() {
  if (confirm('Are you sure you want to sign out? Data privacy protection will remain active.')) {
    state.currentUser = null;
    state.sessionToken = null;
    state.activeFamilyMember = null;
    state.familyMembers = [];
    updateAuthBadge();
    toggleRoleMode('asha');
    alert('You have logged out.');
  }
}

function updateAuthBadge() {
  const badgeName = document.getElementById('user-badge-name');
  const badgeIcon = document.getElementById('user-badge-icon');
  const logoutBtn = document.getElementById('btn-logout');

  if (state.currentUser) {
    if (badgeName) badgeName.innerText = state.currentUser.full_name;
    if (badgeIcon) badgeIcon.innerText = state.currentUser.role === 'asha' ? '👩‍⚕️' : '👤';
    if (logoutBtn) logoutBtn.style.display = 'inline-flex';
  } else {
    if (badgeName) badgeName.innerText = 'Login / Sign In';
    if (badgeIcon) badgeIcon.innerText = '🔐';
    if (logoutBtn) logoutBtn.style.display = 'none';
  }
}

// ==========================================================================
// ASHA Worker Patient Intake Token Controller
// ==========================================================================

async function generateAshaTokenForActivePatient() {
  const ashaId = state.currentUser && state.currentUser.role === 'asha' ? state.currentUser.user_id : 'ASHA-782';
  const name = document.getElementById('patient-name')?.value.trim() || 'Village Patient';
  const phone = document.getElementById('patient-phone')?.value.trim() || null;
  const village = document.getElementById('patient-village')?.value.trim() || 'Rampur';
  const age = document.getElementById('patient-age')?.value ? parseInt(document.getElementById('patient-age').value) : null;
  const gender = document.getElementById('patient-gender')?.value || 'Female';

  try {
    const res = await fetch('/api/auth/asha/generate-token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        asha_worker_id: ashaId,
        patient_name: name,
        phone: phone,
        village: village,
        age: age,
        gender: gender
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Token generation failed');

    state.activeTokenId = data.token.token_id;
    setText('current-token-code', data.token.token_id);
    alert(`🎟️ New Patient Intake Token Issued!\n\nToken ID: ${data.token.token_id}\nPatient: ${data.token.patient_name} (${data.token.village})\n\nThis token will tag this consultation separately for community records.`);
    loadAshaTokens();
  } catch (err) {
    alert(`Could not generate token: ${err.message}`);
  }
}

async function loadAshaTokens() {
  const ashaId = state.currentUser && state.currentUser.role === 'asha' ? state.currentUser.user_id : 'ASHA-782';
  try {
    const res = await fetch(`/api/auth/asha/tokens?asha_worker_id=${encodeURIComponent(ashaId)}`);
    if (!res.ok) return;
    const data = await res.json();
    state.ashaTokens = data.tokens || [];
    setText('asha-token-count', state.ashaTokens.length);

    if (state.ashaTokens.length > 0 && !state.activeTokenId) {
      state.activeTokenId = state.ashaTokens[0].token_id;
      setText('current-token-code', state.activeTokenId);
    }
  } catch (e) {
    console.warn('Could not load ASHA tokens:', e);
  }
}

function openAshaTokenListModal() {
  const modal = document.getElementById('asha-tokens-modal');
  const container = document.getElementById('asha-tokens-table-container');
  if (!modal || !container) return;

  if (!state.ashaTokens || state.ashaTokens.length === 0) {
    container.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 24px;">No patient tokens issued yet. Click "Generate Token ID" to issue a community token.</div>';
  } else {
    container.innerHTML = `
      <table class="tokens-table">
        <thead>
          <tr>
            <th>Token ID</th>
            <th>Patient Name</th>
            <th>Village</th>
            <th>Issued Time</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          ${state.ashaTokens.map(t => `
            <tr>
              <td><span class="token-code-badge">${escapeHtml(t.token_id)}</span></td>
              <td><strong>${escapeHtml(t.patient_name)}</strong></td>
              <td>${escapeHtml(t.village || '--')}</td>
              <td>${t.created_at ? t.created_at.slice(0, 16).replace('T', ' ') : '--'}</td>
              <td>
                <button type="button" class="btn-secondary" style="padding: 3px 8px; font-size: 11.5px;" onclick="selectAshaToken('${t.token_id}')">
                  Select for Triage
                </button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  }

  modal.style.display = 'flex';
}

function closeAshaTokensModal() {
  const modal = document.getElementById('asha-tokens-modal');
  if (modal) modal.style.display = 'none';
}

function selectAshaToken(tokenId) {
  const token = state.ashaTokens.find(t => t.token_id === tokenId);
  if (!token) return;

  state.activeTokenId = token.token_id;
  setText('current-token-code', token.token_id);

  // Pre-fill patient intake fields with token data
  const nameInput = document.getElementById('patient-name');
  const phoneInput = document.getElementById('patient-phone');
  const villageInput = document.getElementById('patient-village');
  const ageInput = document.getElementById('patient-age');
  const genderInput = document.getElementById('patient-gender');

  if (nameInput) nameInput.value = token.patient_name || '';
  if (phoneInput) phoneInput.value = token.phone || '';
  if (villageInput) villageInput.value = token.village || '';
  if (ageInput && token.age) ageInput.value = token.age;
  if (genderInput && token.gender) genderInput.value = token.gender;

  closeAshaTokensModal();
}

// ==========================================================================
// Self Patient "My Health & Family Vault" Controller
// ==========================================================================

async function loadFamilyMembers(userId) {
  const uid = userId || (state.currentUser ? state.currentUser.user_id : 'USR-1082');
  try {
    const res = await fetch(`/api/auth/family?user_id=${encodeURIComponent(uid)}`);
    if (!res.ok) return;
    const data = await res.json();
    state.familyMembers = data.family_members || [];

    // Default select primary 'Self' member if none selected
    if (!state.activeFamilyMember && state.familyMembers.length > 0) {
      state.activeFamilyMember = state.familyMembers.find(m => m.relation === 'Self') || state.familyMembers[0];
    }
    renderFamilyPills();
  } catch (e) {
    console.warn('Could not load family vault:', e);
  }
}

function renderFamilyPills() {
  const container = document.getElementById('family-pills-list');
  if (!container) return;

  if (!state.familyMembers || state.familyMembers.length === 0) {
    container.innerHTML = '<div style="font-size: 12.5px; color: var(--text-muted);">No members registered. Click "+ Add Family Member" to add spouse, child, or parent.</div>';
    return;
  }

  container.innerHTML = state.familyMembers.map(m => {
    const isSelected = state.activeFamilyMember && state.activeFamilyMember.member_id === m.member_id;
    let icon = '👤';
    if (m.relation === 'Child') icon = '👧';
    else if (m.relation === 'Parent') icon = '👵';
    else if (m.relation === 'Spouse') icon = '❤️';

    const meta = m.age ? ` (${m.age} yrs)` : '';
    return `
      <div class="family-pill ${isSelected ? 'active' : ''}" onclick="selectFamilyMember('${m.member_id}')">
        <span>${icon}</span>
        <span>${escapeHtml(m.name)}</span>
        <span class="pill-meta">${escapeHtml(m.relation)}${meta}</span>
      </div>
    `;
  }).join('');
}

function selectFamilyMember(memberId) {
  const member = state.familyMembers.find(m => m.member_id === memberId);
  if (!member) return;

  state.activeFamilyMember = member;
  renderFamilyPills();

  // Populate patient form fields with family member details
  const nameInput = document.getElementById('patient-name');
  const ageInput = document.getElementById('patient-age');
  const genderInput = document.getElementById('patient-gender');
  const pregChk = document.getElementById('chk-pregnant');
  const diabChk = document.getElementById('chk-diabetic');
  const hyperChk = document.getElementById('chk-hypertension');
  const asthmaChk = document.getElementById('chk-asthma');
  const allergyInput = document.getElementById('patient-allergies');

  if (nameInput) nameInput.value = member.name;
  if (ageInput && member.age) ageInput.value = member.age;
  if (genderInput && member.gender) genderInput.value = member.gender;
  if (pregChk) pregChk.checked = Boolean(member.is_pregnant);

  // Set comorbidities
  const comorbs = (member.comorbidities || []).map(c => c.toLowerCase());
  if (diabChk) diabChk.checked = comorbs.some(c => c.includes('diabet'));
  if (hyperChk) hyperChk.checked = comorbs.some(c => c.includes('hypertens') || c.includes('bp'));
  if (asthmaChk) asthmaChk.checked = comorbs.some(c => c.includes('asthma'));

  // Set allergies
  if (allergyInput) {
    allergyInput.value = (member.allergies || []).join(', ');
  }
}

function openAddFamilyModal() {
  const modal = document.getElementById('family-modal');
  if (modal) modal.style.display = 'flex';
}

function closeAddFamilyModal() {
  const modal = document.getElementById('family-modal');
  if (modal) modal.style.display = 'none';
}

async function handleAddFamilySubmit(event) {
  event.preventDefault();
  const userId = state.currentUser ? state.currentUser.user_id : 'USR-1082';
  const name = document.getElementById('fam-name').value.trim();
  const relation = document.getElementById('fam-relation').value;
  const age = document.getElementById('fam-age').value;
  const gender = document.getElementById('fam-gender').value;
  const comorbText = document.getElementById('fam-comorbidities').value.trim();
  const allergyText = document.getElementById('fam-allergies').value.trim();

  const comorbidities = comorbText ? comorbText.split(',').map(s => s.trim()).filter(Boolean) : [];
  const allergies = allergyText ? allergyText.split(',').map(s => s.trim()).filter(Boolean) : [];

  try {
    const res = await fetch('/api/auth/family', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        name: name,
        relation: relation,
        age: age ? parseInt(age) : null,
        gender: gender,
        is_pregnant: false,
        comorbidities: comorbidities,
        allergies: allergies
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Could not add family member');

    alert(`✅ Successfully added ${data.member.name} (${data.member.relation}) to your Health Vault!`);
    closeAddFamilyModal();
    await loadFamilyMembers(userId);
    selectFamilyMember(data.member.member_id);
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}


