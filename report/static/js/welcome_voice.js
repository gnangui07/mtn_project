(function (global) {
  'use strict';

  function PREFS_KEY(u){ return `welcome_prefs_${u || 'anonymous'}`; }
  function getPrefs(username){
    try {
      const raw = localStorage.getItem(PREFS_KEY(username));
      const parsed = raw ? JSON.parse(raw) : null;
      return Object.assign({ enabled: true, lang: 'fr-FR', voiceName: '' }, parsed || {});
    } catch { return { enabled: true, lang: 'fr-FR', voiceName: '' }; }
  }

  function fmtDateISOToLocale(iso, locale){
    if (!iso) return '';
    try {
      const d = new Date(iso + 'T00:00:00');
      return new Intl.DateTimeFormat(locale || 'fr-FR', { day: 'numeric', month: 'long' }).format(d);
    } catch { return iso; }
  }

  function buildMessage(username, prefs, payload){
    const lang = (prefs.lang || 'fr-FR').toLowerCase();
    const isFR = lang.startsWith('fr');
    const isEN = lang.startsWith('en');
    const isES = lang.startsWith('es');
    const isDE = lang.startsWith('de');

    // Message de bienvenue simple
    let welcomeMsg = '';
    if (isFR) welcomeMsg = `Yello ${username}, j'espère que vous allez bien ! Alors on fait quoi aujourd'hui ?`;
    else if (isEN) welcomeMsg = `Yello ${username}, I hope you're well! So what are we doing today?`;
    else if (isES) welcomeMsg = `Yello ${username}, ¡espero que esté bien! ¿Entonces qué hacemos hoy?`;
    else if (isDE) welcomeMsg = `Yello ${username}, ich hoffe, es geht Ihnen gut! Also was machen wir heute?`;
    else welcomeMsg = `Yello ${username}! So what are we doing today?`;

    return welcomeMsg;
  }

  function getPlayKey(username){ return `welcomePlayed_${username || 'anonymous'}`; }
  function getResumeKey(username){ return `welcomeResume_${username || 'anonymous'}`; }
  function getStopKey(username){ return `welcomeStop_${username || 'anonymous'}`; }

  function speak(text, prefs, startIndex){
    return new Promise((resolve) => {
      if (!('speechSynthesis' in window)) return resolve();
      const u = new SpeechSynthesisUtterance();
      const fullText = String(text || '');
      const start = Math.max(0, Number(startIndex || 0));
      u.text = start > 0 ? fullText.slice(start) : fullText;
      u.lang = prefs.lang || 'fr-FR';
      u.volume = 1; u.rate = 1; u.pitch = 1;
      const chooseVoice = () => {
        const vs = window.speechSynthesis.getVoices();
        if (!vs || !vs.length) return null;
        if (prefs.voiceName) return vs.find(v => v.name === prefs.voiceName) || null;
        return vs.find(v => v.lang && v.lang.toLowerCase().includes((prefs.lang || '').toLowerCase())) || null;
      };
      const v = chooseVoice();
      if (v) u.voice = v;
      // Persist progress to resume across navigation
      try { sessionStorage.setItem(getResumeKey(global.__WELCOME_USER__), JSON.stringify({ text: fullText, pos: start })); } catch {}
      u.onboundary = (e) => {
        try {
          const currentPos = start + (e.charIndex || 0);
          sessionStorage.setItem(getResumeKey(global.__WELCOME_USER__), JSON.stringify({ text: fullText, pos: currentPos }));
        } catch {}
      };
      u.onend = () => {
        try { sessionStorage.removeItem(getResumeKey(global.__WELCOME_USER__)); } catch {}
        resolve();
      };
      u.onerror = () => {
        try { sessionStorage.removeItem(getResumeKey(global.__WELCOME_USER__)); } catch {}
        resolve();
      };
      window.speechSynthesis.speak(u);
    });
  }

  async function play(username){
    // Ne pas jouer si l'utilisateur n'est pas authentifié (username vide)
    if (!username || username.trim() === '') return;
    if (global.__WELCOME_TTS_SPOKEN__) return;
    const prefs = getPrefs(username);
    // If user has pressed stop in this session, do not start
    try { if (sessionStorage.getItem(getStopKey(username))) return; } catch {}
    
    // Message de bienvenue simple (plus besoin d'appeler l'API)
    const text = buildMessage(username, prefs, {});
    
    // Re-check stop just before speaking
    try { if (sessionStorage.getItem(getStopKey(username))) return; } catch {}
    global.__WELCOME_TTS_SPOKEN__ = true;
    global.__WELCOME_USER__ = username;
    try { sessionStorage.setItem(getPlayKey(username), 'true'); } catch {}
    await speak(text, prefs, 0);
  }

  // Resume if a previous speech was interrupted by navigation
  function resumeIfNeeded(username){
    // Ne pas reprendre si l'utilisateur n'est pas authentifié
    if (!username || username.trim() === '') return;
    try {
      // Do not resume if user explicitly stopped in this tab/session
      if (sessionStorage.getItem(getStopKey(username))) {
        try { sessionStorage.removeItem(getResumeKey(username)); } catch {}
        return;
      }
      const raw = sessionStorage.getItem(getResumeKey(username));
      if (!raw) return;
      const data = JSON.parse(raw);
      if (!data || !data.text) return;
      const prefs = getPrefs(username);
      global.__WELCOME_TTS_SPOKEN__ = true; // prevent duplicate building
      global.__WELCOME_USER__ = username;
      speak(data.text, prefs, Number(data.pos || 0));
    } catch {}
  }

  function stop(username){
    // Set stop flag first to prevent any upcoming play/resume
    try { sessionStorage.setItem(getStopKey(username || global.__WELCOME_USER__), 'true'); } catch {}
    try {
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
        // Double-cancel to handle some engines where a pending utterance persists briefly
        setTimeout(() => { try { window.speechSynthesis.cancel(); } catch {} }, 50);
      }
    } catch {}
    try { sessionStorage.removeItem(getResumeKey(username || global.__WELCOME_USER__)); } catch {}
    try { delete global.__WELCOME_TTS_SPOKEN__; } catch {}
  }

  global.WelcomeVoice = { play, resumeIfNeeded, stop };

})(window);
