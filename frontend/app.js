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
  lastPrediction: null
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
  initSpeechRecognition();
  checkApiHealth();
  setupPatientSearch();
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
    // Remove symptom
    const updated = symptomsList.filter(s => s !== normalizedSymptom);
    textarea.value = updated.join(', ');
    chipElement.classList.remove('selected');
  } else {
    // Add symptom
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
  }
}

// --- Mode Toggle: ASHA Worker vs. Patient Mode ---
function toggleRoleMode() {
  state.currentRole = state.currentRole === 'asha' ? 'patient' : 'asha';
  const roleTitle = document.getElementById('role-title');
  const roleHeadline = document.getElementById('role-headline');
  const roleSubtext = document.getElementById('role-subtext');
  const modeBtnLabel = document.getElementById('mode-btn-label');
  const lookupGroup = document.getElementById('lookup-group');
  const patientIdDisplay = document.getElementById('patient-id-display');

  if (state.currentRole === 'patient') {
    if (roleTitle) roleTitle.innerText = 'Patient Self-Service Mode';
    if (roleHeadline) roleHeadline.innerHTML = '<span>🌱</span> Patient Self-Care & Assessment';
    if (roleSubtext) roleSubtext.innerText = 'Check your health symptoms quickly, get home-care advice, and see affordable medicines.';
    if (modeBtnLabel) modeBtnLabel.innerText = 'Switch to ASHA Worker Mode';
    if (lookupGroup) lookupGroup.style.display = 'none';
    if (patientIdDisplay) patientIdDisplay.style.display = 'none';
  } else {
    if (roleTitle) roleTitle.innerText = 'ASHA Worker & Kiosk Mode';
    if (roleHeadline) roleHeadline.innerHTML = '<span>👩‍⚕️</span> ASHA Worker & Kiosk Mode';
    if (roleSubtext) roleSubtext.innerText = 'Record patient intake, conduct voice symptom triage, detect recurring chronic symptoms, and issue referral slips.';
    if (modeBtnLabel) modeBtnLabel.innerText = 'Switch to Patient Mode';
    if (lookupGroup) lookupGroup.style.display = 'block';
    if (patientIdDisplay) patientIdDisplay.style.display = 'inline-flex';
  }
}

// --- Language Toggle: English <-> Hindi ---
function toggleLanguage() {
  state.currentLang = state.currentLang === 'en' ? 'hi' : 'en';
  const langBtnLabel = document.getElementById('lang-btn-label');
  if (langBtnLabel) {
    langBtnLabel.innerText = state.currentLang === 'hi' ? 'English' : 'हिंदी (Hindi)';
  }

  // Update prominent text labels
  const isHi = state.currentLang === 'hi';
  setText('tagline-text', isHi ? 'ग्रामीण स्वास्थ्य सहायता प्रणाली' : 'Rural Healthcare Decision-Support');
  setText('nav-triage-text', isHi ? 'ट्राइएज स्टूडियो' : 'Triage Studio');
  setText('nav-patients-text', isHi ? 'मरीज सूची' : 'Patient Registry');
  setText('nav-about-text', isHi ? 'प्रणाली के बारे में' : 'About System');
  setText('patient-section-title', isHi ? 'मरीज का विवरण व पहचान' : 'Patient Profile & Identification');
  setText('symptom-section-title', isHi ? 'लक्षण विवरण व आवाज सहायक' : 'Symptom Input & Voice Assistant');
  setText('lbl-name', isHi ? 'मरीज का पूरा नाम *' : 'Full Name *');
  setText('lbl-phone', isHi ? 'मोबाइल नंबर' : 'Mobile Number');
  setText('lbl-village', isHi ? 'गाँव / ग्राम *' : 'Village / Gram *');
  setText('lbl-symptoms', isHi ? 'लक्षणों का विवरण *' : 'Reported Symptoms Description *');
  setText('lbl-quick-chips', isHi ? 'सामान्य ग्रामीण लक्षण (जोड़ने के लिए क्लिक करें):' : 'Common Rural Symptoms (Click to Add):');
  setText('btn-submit-text', isHi ? 'एआई जांच व जोखिम मूल्यांकन करें' : 'Run AI Triage & Risk Assessment');
  
  if (state.recognition) {
    state.recognition.lang = isHi ? 'hi-IN' : 'en-IN';
  }
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.innerText = text;
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
    <div onclick="selectPatient('${p.patient_id}', '${escapeHtml(p.name)}', '${p.phone || ''}', '${escapeHtml(p.village || '')}', ${p.age || 'null'}, '${p.gender || 'Male'}')"
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

function selectPatient(patientId, name, phone, village, age, gender) {
  document.getElementById('patient-name').value = name;
  document.getElementById('patient-phone').value = phone || '';
  document.getElementById('patient-village').value = village || '';
  if (age !== 'null' && age) document.getElementById('patient-age').value = age;
  if (gender) document.getElementById('patient-gender').value = gender;
  
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

  if (!symptoms) {
    alert(state.currentLang === 'hi' 
      ? 'कृपया पहले लक्षणों का विवरण दर्ज करें।' 
      : 'Please enter symptoms description first.');
    document.getElementById('symptoms-input').focus();
    return;
  }

  // Visual Loading State
  setLoadingState(true);

  try {
    const payload = {
      symptoms: symptoms,
      patient_name: name || (state.currentRole === 'asha' ? 'Unknown Patient' : 'Self-Care Visitor'),
      phone: phone || null,
      village: village || null,
      age: age ? parseInt(age) : null,
      gender: gender || null
    };

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

    // Update patient ID badge
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

  const riskLevel = data.risk_level.toUpperCase();
  const acuityBanner = document.getElementById('acuity-banner');
  const acuityIcon = document.getElementById('acuity-icon');
  const acuityTitle = document.getElementById('acuity-title');
  const acuitySummary = document.getElementById('acuity-summary');

  // Reset classes
  acuityBanner.className = 'triage-acuity-banner';

  if (riskLevel === 'HIGH') {
    acuityBanner.classList.add('risk-high');
    acuityIcon.innerText = '🚨';
    acuityTitle.innerText = 'HIGH RISK – IMMEDIATE REFERRAL';
    acuitySummary.innerText = 'Urgent medical attention required. Transfer to PHC / Emergency immediately.';
  } else if (riskLevel === 'MEDIUM') {
    acuityBanner.classList.add('risk-medium');
    acuityIcon.innerText = '⚠️';
    acuityTitle.innerText = 'MEDIUM RISK – CLINICAL CONSULTATION';
    acuitySummary.innerText = 'Schedule doctor consultation / telemedicine visit within 24–48 hours.';
  } else {
    acuityBanner.classList.add('risk-low');
    acuityIcon.innerText = '✅';
    acuityTitle.innerText = 'LOW RISK – MILD / HOME CARE';
    acuitySummary.innerText = 'Home observation and supportive care recommended. Observe precautions.';
  }

  // Longitudinal Alert Check
  const longAlertBox = document.getElementById('longitudinal-alert-box');
  const longAlertMsg = document.getElementById('longitudinal-message');
  if (data.longitudinal_analysis && data.longitudinal_analysis.alert_message) {
    longAlertMsg.innerText = data.longitudinal_analysis.alert_message;
    longAlertBox.style.display = 'block';
    longAlertBox.classList.add('active');
  } else {
    longAlertBox.style.display = 'none';
    longAlertBox.classList.remove('active');
  }

  // Condition & Clinical Advice
  setText('condition-title', data.condition || 'General Symptom Evaluation');
  setText('confidence-label', `Confidence: ${(data.confidence * 100).toFixed(1)}%`);
  setText('condition-desc', data.condition_description || 'Evaluated across rural primary symptom database.');
  setText('action-advice-text', data.action_advice);

  // Precautions List
  const precList = document.getElementById('precautions-list');
  if (precList) {
    precList.innerHTML = (data.precautions && data.precautions.length > 0)
      ? data.precautions.map(p => `<li>${escapeHtml(p)}</li>`).join('')
      : '<li>Maintain hydration, rest in well-ventilated space, and observe for symptom progression.</li>';
  }

  // Affordable Generic Medicines
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
      medsList.innerHTML = '<div style="font-size: 13px; color: var(--text-muted);">No specific generic alternatives required. Home supportive care advised.</div>';
    }
  }

  // Referral Slip
  if (data.referral_guidance) {
    setText('referral-facility', `Facility: ${data.referral_guidance.facility} (${data.referral_guidance.timeframe})`);
    setText('referral-action', `ASHA Action: ${data.referral_guidance.asha_action}`);
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

// --- Print / Export Referral Slip ---
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
  const dateStr = new Date().toLocaleString();

  const printWindow = window.open('', '_blank');
  printWindow.document.write(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>GramCare AI - Clinical Referral Slip</title>
      <style>
        body { font-family: 'Arial', sans-serif; padding: 30px; color: #1e293b; max-width: 650px; margin: 0 auto; line-height: 1.5; }
        .header { border-bottom: 2px solid #0d9488; padding-bottom: 12px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; }
        .title { font-size: 22px; font-weight: bold; color: #0d9488; }
        .badge { background: #fee2e2; color: #dc2626; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 13px; }
        .section { margin-bottom: 14px; }
        .label { font-size: 12px; text-transform: uppercase; color: #64748b; font-weight: bold; }
        .val { font-size: 15px; font-weight: 600; }
        .box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; margin-top: 10px; }
        .footer { margin-top: 30px; border-top: 1px dashed #cbd5e1; padding-top: 12px; font-size: 11px; color: #64748b; }
      </style>
    </head>
    <body>
      <div class="header">
        <div>
          <div class="title">GramCare AI</div>
          <div style="font-size: 12px; color: #64748b;">Rural Healthcare Decision-Support Referral Slip</div>
        </div>
        <div class="badge">${p.risk_level} RISK</div>
      </div>

      <div class="section" style="display: flex; justify-content: space-between;">
        <div>
          <div class="label">Patient Name & ID:</div>
          <div class="val">${escapeHtml(patientName)} (${patientId})</div>
        </div>
        <div>
          <div class="label">Age / Gender:</div>
          <div class="val">${age} / ${p.patient_info.gender || 'N/A'}</div>
        </div>
        <div>
          <div class="label">Village / Gram:</div>
          <div class="val">${escapeHtml(village)}</div>
        </div>
      </div>

      <div class="box">
        <div class="label">Reported Symptoms:</div>
        <div style="font-size: 14px; margin-top: 2px;">${escapeHtml(p.symptoms)}</div>
      </div>

      <div class="box" style="margin-top: 10px;">
        <div class="label">Evaluated Condition & Clinical Acuity:</div>
        <div class="val" style="color: #0f766e;">${escapeHtml(p.condition || 'Clinical Evaluation')} (Confidence: ${(p.confidence * 100).toFixed(0)}%)</div>
        <div style="font-size: 13px; margin-top: 4px;">${escapeHtml(p.action_advice)}</div>
      </div>

      ${p.referral_guidance ? `
        <div class="box" style="margin-top: 10px; background: #fff7ed; border-color: #fed7aa;">
          <div class="label" style="color: #c2410c;">Referral Facility & Action:</div>
          <div style="font-size: 14px; font-weight: bold; color: #9a3412;">${p.referral_guidance.facility} (${p.referral_guidance.timeframe})</div>
          <div style="font-size: 12px; color: #c2410c; margin-top: 2px;">${p.referral_guidance.asha_action}</div>
        </div>
      ` : ''}

      <div class="footer">
        <div>Generated on: ${dateStr} by ASHA Worker / Digital Health Kiosk</div>
        <div style="margin-top: 4px; font-style: italic;">Note: GramCare AI is a triage decision-support tool. Final diagnosis and prescriptions must be performed by a registered medical practitioner.</div>
      </div>
    </body>
    </html>
  `);
  printWindow.document.close();
  printWindow.focus();
  setTimeout(() => printWindow.print(), 350);
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
