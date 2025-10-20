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
    if (isFR) welcomeMsg = `Bienvenue ${username}, j'espère que vous allez bien !`;
    else if (isEN) welcomeMsg = `Welcome ${username}, I hope you're well!`;
    else if (isES) welcomeMsg = `Bienvenido ${username}, ¡espero que esté bien!`;
    else if (isDE) welcomeMsg = `Willkommen ${username}, ich hoffe, es geht Ihnen gut!`;
    else welcomeMsg = `Welcome ${username}!`;

    return welcomeMsg;
  }

  // Code mort supprimé - garder seulement le message de bienvenue
  function buildMessage_OLD(username, prefs, payload){
    const importY = payload.has_imports_yesterday;
    const importYDate = fmtDateISOToLocale(payload.import_date_yesterday, prefs.lang);
    const lastImportDate = fmtDateISOToLocale(payload.last_import_date, prefs.lang);
    const lastImportFilename = payload.last_import_filename || '';
    const lastImportLines = payload.last_import_lines || 0;
    const lastImportPOCount = Number(payload.last_import_po_count || 0);
    const totalPOCount = Number(payload.total_po_count || 0);

    const recY = payload.has_receptions_yesterday;
    const recYList = payload.bons_reception_yesterday || [];
    const lastRecDate = fmtDateISOToLocale(payload.last_receptions_date, prefs.lang);
    const lastRecList = payload.last_bons_reception || [];
    const recYCount = Number(payload.rec_y_count || 0);
    const recYPOCount = Number(payload.rec_y_po_count || 0);
    const recYTotalQuantityDelivered = Number(payload.rec_y_total_quantity_delivered || 0);
    const recYTotalQuantityNotDelivered = Number(payload.rec_y_total_quantity_not_delivered || 0);
    const negCorrectionsY = Number(payload.neg_corrections_y || 0);
    const trend7d = Array.isArray(payload.receptions_trend_7d) ? payload.receptions_trend_7d : [];
    // We keep most active day info, but we won't speak averages
    const mostActiveDay7d = payload.most_active_day_7d || null;

    const msrnY = payload.has_msrn_yesterday;
    const msrnYBc = payload.bon_msrn_yesterday || '';
    const lastMsrnBc = payload.last_msrn_bc || '';
    const lastMsrnDate = fmtDateISOToLocale(payload.last_msrn_date, prefs.lang);
    const msrnCountYesterday = Number(payload.msrn_count_yesterday || 0);
    const msrnCount30d = Number(payload.msrn_count_30d || 0);
    const bcsMissingMsrnY = Array.isArray(payload.bcs_missing_msrn_y) ? payload.bcs_missing_msrn_y : [];
    const avgProgressRateY = Number(payload.avg_progress_rate_y || 0);

    const parts = [];
    // Welcome
    if (isFR) parts.push(`Bienvenue ${username}, j'espère que vous allez bien !`);
    else if (isEN) parts.push(`Welcome ${username}, I hope you’re well!`);
    else if (isES) parts.push(`Bienvenido ${username}, ¡espero que esté bien!`);
    else if (isDE) parts.push(`Willkommen ${username}, ich hoffe, es geht Ihnen gut!`);
    else parts.push(`Welcome ${username}!`);

    // Imports
    if (importY && importYDate){
      if (isFR) parts.push(`Vous avez importé un fichier Excel le ${importYDate}.`);
      else if (isEN) parts.push(`You imported an Excel file on ${importYDate}.`);
      else if (isES) parts.push(`Importó un archivo de Excel el ${importYDate}.`);
      else if (isDE) parts.push(`Sie haben am ${importYDate} eine Excel-Datei importiert.`);
      else parts.push(`You imported an Excel file on ${importYDate}.`);
    } else if (lastImportDate){
      if (isFR) parts.push(`Votre dernier import remonte au ${lastImportDate}.`);
      else if (isEN) parts.push(`Your last import was on ${lastImportDate}.`);
      else if (isES) parts.push(`Su última importación fue el ${lastImportDate}.`);
      else if (isDE) parts.push(`Ihr letzter Import war am ${lastImportDate}.`);
      else parts.push(`Your last import was on ${lastImportDate}.`);
    } else {
      if (isFR) parts.push(`Aucun import récent.`);
      else if (isEN) parts.push(`No recent imports.`);
      else if (isES) parts.push(`No hay importaciones recientes.`);
      else if (isDE) parts.push(`Keine aktuellen Importe.`);
      else parts.push(`No recent imports.`);
    }

    // Import details (filename, lines, and PO counts)
    if (lastImportFilename || lastImportLines){
      if (isFR) parts.push(`Dernier fichier: ${lastImportFilename || '—'}${lastImportLines ? `, ${lastImportLines} lignes.` : '.'}`);
      else if (isEN) parts.push(`Last file: ${lastImportFilename || '—'}${lastImportLines ? `, ${lastImportLines} lines.` : '.'}`);
      else if (isES) parts.push(`Último archivo: ${lastImportFilename || '—'}${lastImportLines ? `, ${lastImportLines} líneas.` : '.'}`);
      else if (isDE) parts.push(`Letzte Datei: ${lastImportFilename || '—'}${lastImportLines ? `, ${lastImportLines} Zeilen.` : '.'}`);
      else parts.push(`Last file: ${lastImportFilename || '—'}${lastImportLines ? `, ${lastImportLines} lines.` : '.'}`);
    }
    if (lastImportPOCount || totalPOCount){
      if (isFR) parts.push(`Bons de commande: ${lastImportPOCount} dans le dernier fichier, ${totalPOCount} au total sur la plateforme.`);
      else if (isEN) parts.push(`Purchase orders: ${lastImportPOCount} in the last file, ${totalPOCount} total on the platform.`);
      else if (isES) parts.push(`Órdenes de compra: ${lastImportPOCount} en el último archivo, ${totalPOCount} en total en la plataforma.`);
      else if (isDE) parts.push(`Bestellungen: ${lastImportPOCount} in der letzten Datei, insgesamt ${totalPOCount} auf der Plattform.`);
      else parts.push(`Purchase orders: ${lastImportPOCount} in the last file, ${totalPOCount} total on the platform.`);
    }

    // Receptions
    function joinBC(arr){
      const list = (arr || []).filter(Boolean);
      const max = 5;
      if (list.length <= max) return list.join(', ');
      const head = list.slice(0, max).join(', ');
      const more = list.length - max;
      if (isFR) return `${head} et ${more} autres`;
      if (isEN) return `${head} and ${more} others`;
      if (isES) return `${head} y ${more} más`;
      if (isDE) return `${head} und ${more} weitere`;
      return `${head} and ${more} others`;
    }

    if (recY && recYList.length){
      const bc = joinBC(recYList);
      if (isFR) parts.push(`Des réceptions ont été enregistrées sur les bons de commande suivants : ${bc}.`);
      else if (isEN) parts.push(`Receptions were recorded on the following purchase orders: ${bc}.`);
      else if (isES) parts.push(`Se registraron recepciones en las siguientes órdenes de compra: ${bc}.`);
      else if (isDE) parts.push(`Wareneingänge wurden für folgende Bestellungen erfasst: ${bc}.`);
      else parts.push(`Receptions were recorded on the following purchase orders: ${bc}.`);
    } else if (lastRecList.length){
      const bc = joinBC(lastRecList);
      if (isFR) parts.push(`Vos dernières réceptions concernent : ${bc}${lastRecDate ? ` (le ${lastRecDate})` : ''}.`);
      else if (isEN) parts.push(`Your last receptions involved: ${bc}${lastRecDate ? ` (on ${lastRecDate})` : ''}.`);
      else if (isES) parts.push(`Sus últimas recepciones correspondieron a: ${bc}${lastRecDate ? ` (el ${lastRecDate})` : ''}.`);
      else if (isDE) parts.push(`Ihre letzten Wareneingänge betrafen: ${bc}${lastRecDate ? ` (am ${lastRecDate})` : ''}.`);
      else parts.push(`Your last receptions involved: ${bc}${lastRecDate ? ` (on ${lastRecDate})` : ''}.`);
    } else {
      if (isFR) parts.push(`Aucune réception récente.`);
      else if (isEN) parts.push(`No recent receptions.`);
      else if (isES) parts.push(`No hay recepciones recientes.`);
      else if (isDE) parts.push(`Keine aktuellen Wareneingänge.`);
      else parts.push(`No recent receptions.`);
    }

    // Receptions details yesterday
    if (recYCount || recYPOCount || recYTotalQuantityDelivered || recYTotalQuantityNotDelivered){
      if (isFR) parts.push(`Hier: ${recYCount} lignes sur ${recYPOCount} bons, total reçu ${recYTotalQuantityDelivered}, restant ${recYTotalQuantityNotDelivered}.`);
      else if (isEN) parts.push(`Yesterday: ${recYCount} lines across ${recYPOCount} POs, total received ${recYTotalQuantityDelivered}, remaining ${recYTotalQuantityNotDelivered}.`);
      else if (isES) parts.push(`Ayer: ${recYCount} líneas en ${recYPOCount} OCs, total recibido ${recYTotalQuantityDelivered}, por recibir ${recYTotalQuantityNotDelivered}.`);
      else if (isDE) parts.push(`Gestern: ${recYCount} Zeilen über ${recYPOCount} Bestellungen, insgesamt erhalten ${recYTotalQuantityDelivered}, verbleibend ${recYTotalQuantityNotDelivered}.`);
      else parts.push(`Yesterday: ${recYCount} lines across ${recYPOCount} POs, total received ${recYTotalQuantityDelivered}, remaining ${recYTotalQuantityNotDelivered}.`);
      if (negCorrectionsY > 0){
        if (isFR) parts.push(`${negCorrectionsY} corrections négatives.`);
        else if (isEN) parts.push(`${negCorrectionsY} negative corrections.`);
        else if (isES) parts.push(`${negCorrectionsY} correcciones negativas.`);
        else if (isDE) parts.push(`${negCorrectionsY} negative Korrekturen.`);
        else parts.push(`${negCorrectionsY} negative corrections.`);
      }
    }

    // 7-day trend (speak peak day only, no averages)
    if (trend7d && trend7d.length){
      const madDate = mostActiveDay7d && mostActiveDay7d.date ? fmtDateISOToLocale(mostActiveDay7d.date, prefs.lang) : '';
      const madCount = mostActiveDay7d && typeof mostActiveDay7d.count === 'number' ? mostActiveDay7d.count : null;
      if (madDate && madCount !== null){
        if (isFR) parts.push(`Sur 7 jours: pic d'activité le ${madDate} (${madCount}).`);
        else if (isEN) parts.push(`Over 7 days: peak activity on ${madDate} (${madCount}).`);
        else if (isES) parts.push(`En 7 días: pico de actividad el ${madDate} (${madCount}).`);
        else if (isDE) parts.push(`Über 7 Tage: Spitzenaktivität am ${madDate} (${madCount}).`);
        else parts.push(`Over 7 days: peak activity on ${madDate} (${madCount}).`);
      }
    }

    // MSRN
    if (msrnY && msrnYBc){
      if (isFR) parts.push(`Un rapport MSRN a été généré pour le bon de commande ${msrnYBc}.`);
      else if (isEN) parts.push(`An MSRN report was generated for PO ${msrnYBc}.`);
      else if (isES) parts.push(`Se generó un informe MSRN para la OC ${msrnYBc}.`);
      else if (isDE) parts.push(`Ein MSRN-Bericht wurde für die Bestellung ${msrnYBc} erstellt.`);
      else parts.push(`An MSRN report was generated for PO ${msrnYBc}.`);
    } else if (lastMsrnBc){
      if (isFR) parts.push(`Dernier rapport MSRN pour le bon de commande ${lastMsrnBc}${lastMsrnDate ? ` (le ${lastMsrnDate})` : ''}.`);
      else if (isEN) parts.push(`Last MSRN report for PO ${lastMsrnBc}${lastMsrnDate ? ` (on ${lastMsrnDate})` : ''}.`);
      else if (isES) parts.push(`Último informe MSRN para la OC ${lastMsrnBc}${lastMsrnDate ? ` (el ${lastMsrnDate})` : ''}.`);
      else if (isDE) parts.push(`Letzter MSRN-Bericht für Bestellung ${lastMsrnBc}${lastMsrnDate ? ` (am ${lastMsrnDate})` : ''}.`);
      else parts.push(`Last MSRN report for PO ${lastMsrnBc}${lastMsrnDate ? ` (on ${lastMsrnDate})` : ''}.`);
    } else {
      if (isFR) parts.push(`Aucun rapport MSRN récent.`);
      else if (isEN) parts.push(`No recent MSRN reports.`);
      else if (isES) parts.push(`No hay informes MSRN recientes.`);
      else if (isDE) parts.push(`Keine aktuellen MSRN-Berichte.`);
      else parts.push(`No recent MSRN reports.`);
    }

    // MSRN counts and missing
    if (msrnCountYesterday || msrnCount30d){
      if (isFR) parts.push(`MSRN: ${msrnCountYesterday} hier, ${msrnCount30d} sur 30 jours.`);
      else if (isEN) parts.push(`MSRN: ${msrnCountYesterday} yesterday, ${msrnCount30d} in the last 30 days.`);
      else if (isES) parts.push(`MSRN: ${msrnCountYesterday} ayer, ${msrnCount30d} en los últimos 30 días.`);
      else if (isDE) parts.push(`MSRN: ${msrnCountYesterday} gestern, ${msrnCount30d} in den letzten 30 Tagen.`);
      else parts.push(`MSRN: ${msrnCountYesterday} yesterday, ${msrnCount30d} in the last 30 days.`);
    }
    if (Array.isArray(bcsMissingMsrnY) && bcsMissingMsrnY.length){
      const bc = joinBC(bcsMissingMsrnY);
      if (isFR) parts.push(`À vérifier: réceptions d'hier sans rapport MSRN pour ${bc}.`);
      else if (isEN) parts.push(`To check: yesterday's receptions without MSRN report for ${bc}.`);
      else if (isES) parts.push(`Para revisar: recepciones de ayer sin informe MSRN para ${bc}.`);
      else if (isDE) parts.push(`Zu prüfen: gestrige Wareneingänge ohne MSRN-Bericht für ${bc}.`);
      else parts.push(`To check: yesterday's receptions without MSRN report for ${bc}.`);
    }

    // Optional progress average if provided
    if (avgProgressRateY){
      if (isFR) parts.push(`Taux d'avancement moyen hier: ${avgProgressRateY.toFixed(1)}%.`);
      else if (isEN) parts.push(`Average progress rate yesterday: ${avgProgressRateY.toFixed(1)}%.`);
      else if (isES) parts.push(`Tasa de avance promedio ayer: ${avgProgressRateY.toFixed(1)}%.`);
      else if (isDE) parts.push(`Durchschnittliche Fortschrittsrate gestern: ${avgProgressRateY.toFixed(1)}%.`);
      else parts.push(`Average progress rate yesterday: ${avgProgressRateY.toFixed(1)}%.`);
    }

    // Redirect hint
    if (isFR) parts.push(`Pour en savoir plus, consultez la page Consultation des logs ou l’Historique MSRN.`);
    else if (isEN) parts.push(`For more details, see the Logs page or MSRN History.`);
    else if (isES) parts.push(`Para más detalles, consulte la página de registros o el historial de MSRN.`);
    else if (isDE) parts.push(`Weitere Details finden Sie auf der Seite Protokolle oder im MSRN-Verlauf.`);
    else parts.push(`For more details, see the Logs page or MSRN History.`);

    return parts.join(' ');
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
