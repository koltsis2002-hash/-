/**
 * Στήσιμο του ενιαίου CRM μέσα στη ΛΙΣΤΑ ΤΗΛΕΦΩΝΩΝ.
 *
 * Τρέξε μία φορά τη setupAll(). Δημιουργεί τα βοηθητικά φύλλα, προσθέτει τις
 * στήλες παρακολούθησης στα φύλλα επαφών, βάζει dropdown στις καταστάσεις και
 * εγκαθιστά τον onEdit trigger. Είναι ασφαλές να ξανατρέξει — δεν διπλογράφει
 * τίποτα και δεν πειράζει υπάρχουσες στήλες.
 */

const SHEET_SETTINGS = '_Ρυθμίσεις';
const SHEET_LOG = 'Log_Δραστηριότητας';
const SHEET_DAILY = 'Ημερήσιο';
const SHEET_KPI = 'Δείκτες';
const SHEET_COACH = 'Πίνακας Coach';
const SHEET_PROD = 'Παραγωγή';

const COL_UPDATED = 'Τελ. Ενημέρωση';
const COL_CALLPLUS = 'Κλήση +1';
const COL_APPT_DATE = 'Ημ. Ραντεβού';
const COL_CONTRACT_DATE = 'Ημ. Συμβολαίου';
const COL_AMOUNT = 'Ασφάλιστρο (€)';
const COL_NOTES = 'Σημειώσεις CRM';

const SOURCE_PERSONAL = 'Προσωπικές επαφές';
const SOURCE_ROUTE = 'Διαδρομή επιχειρήσεων';
const SOURCE_GEMI = 'Επιχειρήσεις ΓΕΜΗ';
const SOURCE_LINKEDIN = 'Επαφές LinkedIn';

const LOG_HEADERS = ['Χρονοσήμανση', 'Ημερομηνία', 'Πηγή', 'Κανάλι', 'Κλειδί', 'Όνομα',
  'Παλιά κατάσταση', 'Νέα κατάσταση', 'Ορόσημο', 'Γεγονός', 'Στάδιο', 'Ποσό (€)', 'Σχόλιο'];

const SETTING_START = 'Ημερομηνία έναρξης παρακολούθησης';
const SETTING_BACKFILL_DATE = 'Ημερομηνία αρχικής φόρτωσης';
const SETTING_YEAR_TARGET = 'Ετήσιος στόχος παραγωγής (€)';
const SETTING_MONTH_TARGET = 'Μηνιαίος στόχος παραγωγής (€)';
const SETTING_BACKFILL_DONE = 'Έγινε αρχική φόρτωση';
const SETTING_DASHBOARD_ID = 'ID αρχείου Dashboard (προαιρετικό)';
const SETTING_DASHBOARD_PUSH = 'Αυτόματη αποστολή στο Dashboard';

function ss_() { return SpreadsheetApp.getActive(); }

function sheetByName_(name) { return ss_().getSheetByName(name); }

function ensureSheet_(name) {
  var sheet = sheetByName_(name);
  if (!sheet) sheet = ss_().insertSheet(name);
  return sheet;
}

function setupAll() {
  var settings = ensureSettingsSheet_();
  var sources = detectSources_();
  writeSources_(settings, sources);
  sources.forEach(ensureTrackingColumns_);
  sources.forEach(applyStatusValidation_);
  ensureLogSheet_();
  buildDaily_();
  buildKpis_(sources);
  buildCoachTable_();
  buildProduction_();
  installTrigger_();
  SpreadsheetApp.getActive().toast(
    'Το CRM στήθηκε. Επόμενο βήμα: backfillFromCurrentState()', 'Έτοιμο', 10);
}

/* ------------------------------------------------------------------ */
/* Ρυθμίσεις                                                           */
/* ------------------------------------------------------------------ */

function ensureSettingsSheet_() {
  var sheet = ensureSheet_(SHEET_SETTINGS);
  if (sheet.getRange('A1').getValue()) return sheet;

  var startDate = new Date(2026, 3, 9);
  var backfillDate = new Date(2026, 3, 8);

  sheet.getRange('A1').setValue('ΡΥΘΜΙΣΕΙΣ CRM').setFontWeight('bold').setFontSize(14);
  sheet.getRange('A3:C3').setValues([['Παράμετρος', 'Τιμή', 'Επεξήγηση']]).setFontWeight('bold');
  sheet.getRange('A4:C10').setValues([
    [SETTING_START, startDate, 'Από πότε ξεκινούν οι ημερήσιες γραμμές'],
    [SETTING_BACKFILL_DATE, backfillDate, 'Ημερομηνία που χρεώνεται η αρχική φόρτωση — μία μέρα πριν την έναρξη, ώστε να μην μολύνει τα παράθυρα 7/30 ημερών'],
    [SETTING_YEAR_TARGET, 50000, 'Ετήσιος στόχος παραγωγής'],
    [SETTING_MONTH_TARGET, 4167, 'Μηνιαίος στόχος παραγωγής'],
    [SETTING_BACKFILL_DONE, 'ΟΧΙ', 'Γίνεται ΝΑΙ αυτόματα μετά την αρχική φόρτωση'],
    [SETTING_DASHBOARD_ID, '', 'ID του αρχείου του coach — μόνο αν σου δώσει δικαίωμα επεξεργασίας'],
    [SETTING_DASHBOARD_PUSH, 'ΟΧΙ', 'ΝΑΙ για αυτόματη εγγραφή στο αρχείο του coach']
  ]);
  sheet.getRange('A4:A10').setFontWeight('bold');
  sheet.getRange('B4:B5').setNumberFormat('dd/mm/yyyy');
  sheet.getRange('B6:B7').setNumberFormat('#,##0 €');
  sheet.setColumnWidth(1, 280).setColumnWidth(2, 140).setColumnWidth(3, 460);
  sheet.getRange('C4:C10').setWrap(true);
  return sheet;
}

function settingValue_(label) {
  var sheet = sheetByName_(SHEET_SETTINGS);
  var values = sheet.getRange('A1:B40').getValues();
  var target = normalize_(label);
  for (var i = 0; i < values.length; i++) {
    if (normalize_(values[i][0]) === target) return values[i][1];
  }
  return null;
}

function setSettingValue_(label, value) {
  var sheet = sheetByName_(SHEET_SETTINGS);
  var values = sheet.getRange('A1:A40').getValues();
  var target = normalize_(label);
  for (var i = 0; i < values.length; i++) {
    if (normalize_(values[i][0]) === target) {
      sheet.getRange(i + 1, 2).setValue(value);
      return;
    }
  }
}

/* ------------------------------------------------------------------ */
/* Εντοπισμός πηγών                                                    */
/* ------------------------------------------------------------------ */

const STATUS_HEADERS_PRIMARY = ['ΚΑΤΑΣΤΑΣΗ ΚΛΗΣΗΣ', 'ΣΤΑΔΙΟ ΠΩΛΗΣΗΣ'];
const STATUS_HEADERS_FALLBACK = ['ΚΑΤΑΣΤΑΣΗ'];
/** Το FIRST NAME προηγείται: στις προσωπικές επαφές υπάρχει και DISPLAY NAME, και
 *  το ζευγάρι FIRST + LAST δίνει το όνομα χωρίς να διπλογράφεται το επώνυμο. */
const NAME_HEADERS = ['FIRST NAME', 'ΕΠΩΝΥΜΙΑ', 'ΟΝΟΜΑ', 'DISPLAY NAME'];

function headerRowOf_(sheet) {
  var probe = sheet.getRange(1, 1, Math.min(5, sheet.getLastRow() || 1),
    Math.min(sheet.getLastColumn() || 1, 80)).getValues();
  for (var r = 0; r < probe.length; r++) {
    var row = probe[r].map(normalize_);
    var hasStatus = row.some(function (h) {
      return STATUS_HEADERS_PRIMARY.indexOf(h) >= 0 || STATUS_HEADERS_FALLBACK.indexOf(h) >= 0;
    });
    if (hasStatus) return r + 1;
  }
  return 0;
}

function findColumn_(headers, candidates) {
  for (var i = 0; i < candidates.length; i++) {
    var index = headers.indexOf(candidates[i]);
    if (index >= 0) return index + 1;
  }
  return 0;
}

/**
 * Αναγνωρίζει τα φύλλα επαφών από την υπογραφή των κεφαλίδων τους, όχι από το
 * όνομα του φύλλου — έτσι επιβιώνει σε μετονομασίες καρτελών.
 */
function detectSources_() {
  var sources = [];
  ss_().getSheets().forEach(function (sheet) {
    var name = sheet.getName();
    if (name.charAt(0) === '_' || [SHEET_LOG, SHEET_DAILY, SHEET_KPI, SHEET_COACH, SHEET_PROD]
      .indexOf(name) >= 0) return;

    var headerRow = headerRowOf_(sheet);
    if (!headerRow) return;

    var headers = sheet.getRange(headerRow, 1, 1, sheet.getLastColumn()).getValues()[0].map(normalize_);
    var statusCol = findColumn_(headers, STATUS_HEADERS_PRIMARY) ||
      findColumn_(headers, STATUS_HEADERS_FALLBACK);
    var nameCol = findColumn_(headers, NAME_HEADERS);
    if (!statusCol || !nameCol) return;

    var isLinkedIn = headers.indexOf('ΣΤΑΔΙΟ ΠΩΛΗΣΗΣ') >= 0;
    var label = name;
    if (isLinkedIn) label = SOURCE_LINKEDIN;
    else if (headers.indexOf('FIRST NAME') >= 0) label = SOURCE_PERSONAL;
    else if (headers.indexOf('ΓΡΑΜΜΗ ΣΤΟ ΦΥΛΛΟ') >= 0) label = SOURCE_ROUTE;
    else if (headers.indexOf('ΑΦΜ') >= 0 || headers.indexOf('ΑΡΙΘΜΟΣ ΓΕΜΗ') >= 0) label = SOURCE_GEMI;

    sources.push({
      sheetName: name,
      label: label,
      channel: isLinkedIn ? CHANNELS.MESSAGE : CHANNELS.PHONE,
      headerRow: headerRow,
      nameCol: nameCol,
      nameCol2: headers.indexOf('FIRST NAME') >= 0 ? findColumn_(headers, ['LAST NAME']) : 0,
      statusCol: statusCol
    });
  });
  return sources;
}

function writeSources_(settingsSheet, sources) {
  var startRow = 13;
  settingsSheet.getRange(startRow, 1).setValue('ΠΗΓΕΣ ΕΠΑΦΩΝ').setFontWeight('bold').setFontSize(12);
  var headers = ['Ενεργή', 'Φύλλο', 'Ετικέτα πηγής', 'Κανάλι', 'Γραμμή κεφαλίδων',
    'Στήλη ονόματος', 'Στήλη ονόματος 2', 'Στήλη κατάστασης'];
  settingsSheet.getRange(startRow + 1, 1, 1, headers.length).setValues([headers]).setFontWeight('bold');

  var existing = readSources_();
  var rows = sources.map(function (s) {
    var prior = existing.filter(function (e) { return e.sheetName === s.sheetName; })[0];
    return [
      prior ? prior.active : 'ΝΑΙ',
      s.sheetName,
      prior ? prior.label : s.label,
      prior ? prior.channel : s.channel,
      s.headerRow, s.nameCol, s.nameCol2, s.statusCol
    ];
  });
  if (!rows.length) return;
  settingsSheet.getRange(startRow + 2, 1, settingsSheet.getMaxRows() - startRow - 1, headers.length).clearContent();
  settingsSheet.getRange(startRow + 2, 1, rows.length, headers.length).setValues(rows);
}

/** Οι πηγές όπως είναι καταχωρημένες στις ρυθμίσεις (η επεξεργασία τους εκεί υπερισχύει). */
function readSources_() {
  var sheet = sheetByName_(SHEET_SETTINGS);
  if (!sheet) return [];
  var last = sheet.getLastRow();
  if (last < 15) return [];
  var values = sheet.getRange(15, 1, last - 14, 8).getValues();
  return values.filter(function (r) { return r[1]; }).map(function (r) {
    return {
      active: r[0], sheetName: r[1], label: r[2], channel: r[3],
      headerRow: Number(r[4]), nameCol: Number(r[5]),
      nameCol2: Number(r[6]), statusCol: Number(r[7])
    };
  });
}

function activeSources_() {
  return readSources_().filter(function (s) { return normalize_(s.active) === 'ΝΑΙ'; });
}

/* ------------------------------------------------------------------ */
/* Στήλες παρακολούθησης στα φύλλα επαφών                              */
/* ------------------------------------------------------------------ */

/** Οι στήλες που προστίθενται· η ημερομηνία ραντεβού επαναχρησιμοποιείται αν υπάρχει ήδη. */
const TRACKING_COLUMNS = [COL_UPDATED, COL_CALLPLUS, COL_APPT_DATE, COL_CONTRACT_DATE, COL_AMOUNT, COL_NOTES];

const APPT_DATE_ALIASES = ['ΗΜΕΡΟΜΗΝΙΑ ΡΑΝΤΕΒΟΥ', 'ΗΜ. ΡΑΝΤΕΒΟΥ'];

function headerMap_(source) {
  var sheet = sheetByName_(source.sheetName);
  var headers = sheet.getRange(source.headerRow, 1, 1, sheet.getLastColumn()).getValues()[0];
  var map = {};
  headers.forEach(function (h, i) {
    var key = normalize_(h);
    if (key && map[key] === undefined) map[key] = i + 1;
  });
  return map;
}

/** Στήλη παρακολούθησης -> αριθμός στήλης, με τα συνώνυμα της ημ. ραντεβού. */
function trackingColumn_(source, columnName) {
  var map = headerMap_(source);
  if (columnName === COL_APPT_DATE) {
    for (var i = 0; i < APPT_DATE_ALIASES.length; i++) {
      if (map[APPT_DATE_ALIASES[i]]) return map[APPT_DATE_ALIASES[i]];
    }
  }
  return map[normalize_(columnName)] || 0;
}

function ensureTrackingColumns_(source) {
  var sheet = sheetByName_(source.sheetName);
  TRACKING_COLUMNS.forEach(function (columnName) {
    if (trackingColumn_(source, columnName)) return;
    var col = sheet.getLastColumn() + 1;
    if (col > sheet.getMaxColumns()) sheet.insertColumnsAfter(sheet.getMaxColumns(), 1);
    sheet.getRange(source.headerRow, col).setValue(columnName).setFontWeight('bold');
    var body = sheet.getRange(source.headerRow + 1, col, sheet.getMaxRows() - source.headerRow, 1);
    if (columnName === COL_CALLPLUS) body.insertCheckboxes();
    if (columnName === COL_AMOUNT) body.setNumberFormat('#,##0.00 €');
    if (columnName === COL_UPDATED) body.setNumberFormat('dd/mm/yyyy hh:mm');
    if (columnName === COL_CONTRACT_DATE) body.setNumberFormat('dd/mm/yyyy');
    sheet.setColumnWidth(col, columnName === COL_NOTES ? 260 : 130);
  });
}

function applyStatusValidation_(source) {
  var sheet = sheetByName_(source.sheetName);
  var labels = statusLabelsFor_(source.channel);
  var rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(labels, true)
    .setAllowInvalid(true)
    .setHelpText('Διάλεξε κατάσταση από τη λίστα ώστε να καταγραφεί σωστά στους δείκτες.')
    .build();
  sheet.getRange(source.headerRow + 1, source.statusCol, sheet.getMaxRows() - source.headerRow, 1)
    .setDataValidation(rule);
}

/* ------------------------------------------------------------------ */
/* Ημερολόγιο γεγονότων                                                */
/* ------------------------------------------------------------------ */

function ensureLogSheet_() {
  var sheet = ensureSheet_(SHEET_LOG);
  resizeLogSheet_(sheet);
  if (sheet.getRange('A1').getValue()) return sheet;
  sheet.getRange(1, 1, 1, LOG_HEADERS.length).setValues([LOG_HEADERS]).setFontWeight('bold');
  sheet.setFrozenRows(1);
  sheet.getRange('A:A').setNumberFormat('dd/mm/yyyy hh:mm');
  sheet.getRange('B:B').setNumberFormat('dd/mm/yyyy');
  sheet.getRange('L:L').setNumberFormat('#,##0.00 €');
  sheet.setColumnWidth(5, 200).setColumnWidth(6, 220).setColumnWidth(7, 220).setColumnWidth(8, 220);
  return sheet;
}

/** Οι τύποι δείχνουν μέχρι τη γραμμή LOG_LIMIT — το φύλλο πρέπει να τη φτάνει,
 *  αλλιώς οι αναφορές βγαίνουν εκτός ορίων. */
function resizeLogSheet_(sheet) {
  if (sheet.getMaxColumns() > LOG_HEADERS.length) {
    sheet.deleteColumns(LOG_HEADERS.length + 1, sheet.getMaxColumns() - LOG_HEADERS.length);
  }
  if (sheet.getMaxRows() < LOG_LIMIT) {
    sheet.insertRowsAfter(sheet.getMaxRows(), LOG_LIMIT - sheet.getMaxRows());
  }
}

function installTrigger_() {
  var existing = ScriptApp.getProjectTriggers().filter(function (t) {
    return t.getHandlerFunction() === 'onEditHandler';
  });
  if (existing.length) return;
  ScriptApp.newTrigger('onEditHandler')
    .forSpreadsheet(ss_())
    .onEdit()
    .create();
}

/* ------------------------------------------------------------------ */
/* Πίνακες — όλα τα νούμερα είναι τύποι πάνω στο ημερολόγιο γεγονότων  */
/* ------------------------------------------------------------------ */

const LOG = "'" + SHEET_LOG + "'";

/** Στήλη του ημερολογίου ως εύρος τύπου. Το όριο κρατά τους πίνακες γρήγορους —
 *  20.000 γεγονότα είναι πολλαπλάσια από όσα παράγουν μερικές χιλιάδες επαφές. */
const LOG_LIMIT = 20000;

function logCol_(letter) {
  return LOG + '!$' + letter + '$2:$' + letter + '$' + LOG_LIMIT;
}

/** Κριτήρια COUNTIFS/SUMIFS πάνω στο ημερολόγιο, ως κείμενο τύπου. */
function logCriteria_(opts) {
  var parts = [];
  if (opts.event) parts.push(logCol_('J') + ',"' + opts.event + '"');
  if (opts.channel) parts.push(logCol_('D') + ',"' + opts.channel + '"');
  if (opts.stage) parts.push(logCol_('K') + ',' + opts.stage);
  if (opts.source) parts.push(logCol_('C') + ',' + opts.source);
  if (opts.from) parts.push(logCol_('B') + ',">="&' + opts.from);
  if (opts.to) parts.push(logCol_('B') + ',"<="&' + opts.to);
  if (opts.date) parts.push(logCol_('B') + ',' + opts.date);
  if (opts.extra) parts.push(opts.extra);
  return parts.join(',');
}

function countFormula_(opts) {
  return '=COUNTIFS(' + logCriteria_(opts) + ')';
}

function sumFormula_(opts) {
  return '=SUMIFS(' + logCol_('L') + ',' + logCriteria_(opts) + ')';
}

function buildDaily_() {
  var sheet = ensureSheet_(SHEET_DAILY);
  sheet.clear();
  var headers = ['Ημερομηνία', 'Πηγή', 'Κλήσεις', 'Επαφές', 'Μηνύματα', 'Ραντεβού κλεισμένα',
    'Ραντεβού πραγματοποιημένα', 'Συμβόλαια', 'Παραγωγή (€)', 'Απώλειες'];
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]).setFontWeight('bold');
  sheet.setFrozenRows(1);

  sheet.getRange('A2').setFormula('=IFERROR(QUERY(' + LOG + '!$B$2:$C$' + LOG_LIMIT +
    ',"select B, C where B is not null group by B, C order by B",0),"")');

  var pair = { date: '$A2:$A', source: '$B2:$B' };
  var specs = [
    { event: EVENTS.OUTREACH, channel: CHANNELS.PHONE },
    { event: EVENTS.CONTACT },
    { event: EVENTS.OUTREACH, channel: CHANNELS.MESSAGE },
    { event: EVENTS.APPT_SET },
    { event: EVENTS.APPT_HELD },
    { event: EVENTS.CONTRACT },
    { event: EVENTS.CONTRACT, sum: true },
    { event: EVENTS.LOST }
  ];
  specs.forEach(function (spec, i) {
    var opts = Object.assign({}, spec, pair);
    var inner = spec.sum ? sumFormula_(opts) : countFormula_(opts);
    sheet.getRange(2, i + 3).setFormula(
      '=ARRAYFORMULA(IF($A2:$A="","",' + inner.substring(1) + '))');
  });

  sheet.getRange('A:A').setNumberFormat('dd/mm/yyyy');
  sheet.getRange('I:I').setNumberFormat('#,##0.00 €');
  sheet.setColumnWidth(2, 180);
}

function buildKpis_(sources) {
  var sheet = ensureSheet_(SHEET_KPI);
  sheet.clear();
  var windows = ['7 ημέρες', '30 ημέρες', 'Μήνας μέχρι σήμερα', 'Συνολικά'];
  var starts = ['=TODAY()-6', '=TODAY()-29', '=EOMONTH(TODAY(),-1)+1', '=DATE(2000,1,1)'];

  sheet.getRange('A1').setValue('ΔΕΙΚΤΕΣ ΑΠΟΔΟΤΙΚΟΤΗΤΑΣ').setFontWeight('bold').setFontSize(14);
  sheet.getRange('A2').setValue('Όλα τα νούμερα προκύπτουν αυτόματα από τις αλλαγές κατάστασης στα φύλλα επαφών.')
    .setFontStyle('italic');
  sheet.getRange(4, 2, 1, 4).setValues([windows]).setFontWeight('bold').setHorizontalAlignment('center');
  sheet.getRange(5, 2, 1, 4).setFormulas([starts]);
  sheet.hideRows(5);

  var cols = ['B', 'C', 'D', 'E'];
  var rows = [];
  var addRow = function (label, builder, format) {
    var values = [label];
    cols.forEach(function (col) { values.push(builder(col + '$5')); });
    rows.push({ values: values, format: format });
  };
  var addSection = function (title) { rows.push({ values: [title], section: true }); };
  var rowNumber = function (offset) { return 7 + offset; };

  addSection('ΟΓΚΟΣ ΔΡΑΣΤΗΡΙΟΤΗΤΑΣ');
  var volumeStart = rows.length + 1;
  addRow('Κλήσεις', function (from) {
    return countFormula_({ event: EVENTS.OUTREACH, channel: CHANNELS.PHONE, from: from });
  });
  addRow('Επαφές που μίλησα', function (from) {
    return countFormula_({ event: EVENTS.CONTACT, from: from });
  });
  addRow('Μηνύματα', function (from) {
    return countFormula_({ event: EVENTS.OUTREACH, channel: CHANNELS.MESSAGE, from: from });
  });
  addRow('Ραντεβού που έκλεισα', function (from) {
    return countFormula_({ event: EVENTS.APPT_SET, from: from });
  });
  addRow('Ραντεβού που πραγματοποίησα', function (from) {
    return countFormula_({ event: EVENTS.APPT_HELD, from: from });
  });
  addRow('Συμβόλαια', function (from) {
    return countFormula_({ event: EVENTS.CONTRACT, from: from });
  });
  addRow('Παραγωγή (€)', function (from) {
    return sumFormula_({ event: EVENTS.CONTRACT, from: from });
  }, '#,##0.00 €');
  addRow('Απώλειες', function (from) {
    return countFormula_({ event: EVENTS.LOST, from: from });
  });

  var R = {
    calls: rowNumber(volumeStart - 1),
    contacts: rowNumber(volumeStart),
    messages: rowNumber(volumeStart + 1),
    apptSet: rowNumber(volumeStart + 2),
    apptHeld: rowNumber(volumeStart + 3),
    contracts: rowNumber(volumeStart + 4),
    production: rowNumber(volumeStart + 5)
  };
  var ratio = function (numerator, denominator) {
    return function (col) {
      var c = col.charAt(0);
      return '=IFERROR(' + c + numerator + '/' + c + denominator + ',"—")';
    };
  };

  rows.push({ values: [''] });
  addSection('ΑΝΑΛΟΓΙΕΣ ΜΕΤΑΤΡΟΠΗΣ');
  addRow('Ποσοστό επαφής (επαφές ÷ κλήσεις)', ratio(R.contacts, R.calls), '0.0%');
  addRow('Ποσοστό ραντεβού (ραντεβού ÷ επαφές)', ratio(R.apptSet, R.contacts), '0.0%');
  addRow('Ποσοστό εμφάνισης (έγιναν ÷ κλείστηκαν)', ratio(R.apptHeld, R.apptSet), '0.0%');
  addRow('Ποσοστό κλεισίματος (συμβόλαια ÷ ραντεβού που έγιναν)', ratio(R.contracts, R.apptHeld), '0.0%');
  addRow('Κλήσεις ανά ραντεβού', ratio(R.calls, R.apptSet), '0.0');
  addRow('Κλήσεις ανά συμβόλαιο', ratio(R.calls, R.contracts), '0.0');

  rows.push({ values: [''] });
  addSection('ΟΙΚΟΝΟΜΙΚΟΙ ΔΕΙΚΤΕΣ');
  addRow('Μέσο ασφάλιστρο ανά συμβόλαιο', ratio(R.production, R.contracts), '#,##0.00 €');
  addRow('€ ανά κλήση', ratio(R.production, R.calls), '#,##0.00 €');
  addRow('€ ανά ραντεβού', ratio(R.production, R.apptSet), '#,##0.00 €');
  addRow('€ ανά επαφή', ratio(R.production, R.contacts), '#,##0.00 €');

  var body = rows.map(function (r) {
    var line = r.values.slice();
    while (line.length < 5) line.push('');
    return line;
  });
  sheet.getRange(7, 1, body.length, 5).setValues(body);
  rows.forEach(function (r, i) {
    var range = sheet.getRange(7 + i, 1, 1, 5);
    if (r.section) range.setFontWeight('bold').setBackground('#e8eef7');
    if (r.format) sheet.getRange(7 + i, 2, 1, 4).setNumberFormat(r.format);
  });

  var next = 7 + body.length + 1;
  next = buildTargetBlock_(sheet, next, R);
  next = buildSourceBlock_(sheet, next + 1);
  buildFunnelBlock_(sheet, next + 1, sources);

  sheet.setColumnWidth(1, 340);
  [2, 3, 4, 5].forEach(function (c) { sheet.setColumnWidth(c, 150); });
  sheet.getRange(4, 1, sheet.getMaxRows() - 3, 5).setHorizontalAlignment('center');
  sheet.getRange(1, 1, sheet.getMaxRows(), 1).setHorizontalAlignment('left');
}

function colLetter_(index) {
  var letter = '';
  while (index > 0) {
    var rest = (index - 1) % 26;
    letter = String.fromCharCode(65 + rest) + letter;
    index = (index - rest - 1) / 26;
  }
  return letter;
}

/** Τιμή ρύθμισης μέσα από τύπο — αντέχει σε μετακίνηση γραμμών στις ρυθμίσεις. */
function settingLookup_(label, fallback) {
  return 'IFERROR(VLOOKUP("' + label + '",' + "'" + SHEET_SETTINGS + "'" + '!$A:$B,2,FALSE),' + fallback + ')';
}

function buildTargetBlock_(sheet, startRow, R) {
  var monthStart = 'EOMONTH(TODAY(),-1)+1';
  var yearStart = 'DATE(YEAR(TODAY()),1,1)';
  var rows = [
    ['ΣΤΟΧΟΣ ΠΑΡΑΓΩΓΗΣ', '', ''],
    ['Παραγωγή μήνα (€)', sumFormula_({ event: EVENTS.CONTRACT, from: monthStart }), '#,##0.00 €'],
    ['Μηνιαίος στόχος (€)', '=' + settingLookup_(SETTING_MONTH_TARGET, 4167), '#,##0.00 €'],
    ['Υπόλοιπο μήνα (€)', '=MAX(0,B' + (startRow + 2) + '-B' + (startRow + 1) + ')', '#,##0.00 €'],
    ['Ημέρες που απομένουν στον μήνα', '=MAX(1,EOMONTH(TODAY(),0)-TODAY())', '0'],
    ['Παραγωγή έτους (€)', sumFormula_({ event: EVENTS.CONTRACT, from: yearStart }), '#,##0.00 €'],
    ['Ετήσιος στόχος (€)', '=' + settingLookup_(SETTING_YEAR_TARGET, 50000), '#,##0.00 €'],
    ['Υπόλοιπο για τον ετήσιο στόχο (€)', '=MAX(0,B' + (startRow + 6) + '-B' + (startRow + 5) + ')', '#,##0.00 €'],
    ['Απαιτούμενες κλήσεις/ημέρα για τον μηνιαίο στόχο',
      '=IFERROR(ROUNDUP((B' + (startRow + 3) + '/(E' + R.production + '/E' + R.calls + '))/B' + (startRow + 4) + '),"—")', '0']
  ];
  rows.forEach(function (row, i) {
    var target = sheet.getRange(startRow + i, 1);
    target.setValue(row[0]);
    if (i === 0) {
      sheet.getRange(startRow, 1, 1, 5).setFontWeight('bold').setBackground('#e8eef7');
      return;
    }
    var valueCell = sheet.getRange(startRow + i, 2);
    valueCell.setFormula(row[1]);
    valueCell.setNumberFormat(row[2]);
  });
  sheet.getRange(startRow + 9, 1).setValue(
    'Ο υπολογισμός κλήσεων/ημέρα χρησιμοποιεί το δικό σου ιστορικό € ανά κλήση.').setFontStyle('italic');
  return startRow + 10;
}

function buildSourceBlock_(sheet, startRow) {
  var windows = ['7 ημέρες', '30 ημέρες', 'Μήνας μέχρι σήμερα', 'Συνολικά'];
  sheet.getRange(startRow, 1, 1, 7).setFontWeight('bold').setBackground('#e8eef7');
  sheet.getRange(startRow, 1).setValue('ΑΠΟΔΟΣΗ ΑΝΑ ΠΗΓΗ');
  sheet.getRange(startRow, 2).setValue('Παράθυρο:');
  var picker = sheet.getRange(startRow, 3);
  picker.setValue('Συνολικά').setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(windows, true).build());

  var from = 'J1';
  sheet.getRange(from).setFormula('=IFS(' + picker.getA1Notation() + '="7 ημέρες",TODAY()-6,' +
    picker.getA1Notation() + '="30 ημέρες",TODAY()-29,' +
    picker.getA1Notation() + '="Μήνας μέχρι σήμερα",EOMONTH(TODAY(),-1)+1,TRUE,DATE(2000,1,1))');
  sheet.hideColumns(8, 3);

  var headerRow = startRow + 1;
  sheet.getRange(headerRow, 1, 1, 7).setValues([['Πηγή', 'Κλήσεις', 'Επαφές', 'Ραντεβού κλεισμένα',
    'Ραντεβού που έγιναν', 'Συμβόλαια', 'Παραγωγή (€)']]).setFontWeight('bold');

  var firstRow = headerRow + 1;
  sheet.getRange(firstRow, 1).setFormula('=IFERROR(FILTER(' + "'" + SHEET_SETTINGS + "'" +
    '!$C$15:$C,' + "'" + SHEET_SETTINGS + "'" + '!$B$15:$B<>""),"")');

  var source = '$A' + firstRow + ':$A';
  var specs = [
    { event: EVENTS.OUTREACH, channel: CHANNELS.PHONE },
    { event: EVENTS.CONTACT },
    { event: EVENTS.APPT_SET },
    { event: EVENTS.APPT_HELD },
    { event: EVENTS.CONTRACT },
    { event: EVENTS.CONTRACT, sum: true }
  ];
  specs.forEach(function (spec, i) {
    var opts = Object.assign({}, spec, { source: source, from: '$' + from });
    var inner = spec.sum ? sumFormula_(opts) : countFormula_(opts);
    sheet.getRange(firstRow, i + 2).setFormula(
      '=ARRAYFORMULA(IF(' + source + '="","",' + inner.substring(1) + '))');
  });
  sheet.getRange(firstRow, 7, 20, 1).setNumberFormat('#,##0.00 €');
  sheet.setColumnWidth(6, 130).setColumnWidth(7, 150);
  return firstRow + 20;
}

function buildFunnelBlock_(sheet, startRow, sources) {
  sheet.getRange(startRow, 1).setValue('ΧΩΝΙ ΠΩΛΗΣΕΩΝ — πού βρίσκονται τώρα οι επαφές')
    .setFontWeight('bold');
  sheet.getRange(startRow, 1, 1, 2 + sources.length).setBackground('#e8eef7').setFontWeight('bold');

  var headers = ['Κατάσταση'].concat(sources.map(function (s) { return s.label; })).concat(['Σύνολο']);
  sheet.getRange(startRow + 1, 1, 1, headers.length).setValues([headers]).setFontWeight('bold');

  var labels = [];
  PHONE_STATUSES.concat(MESSAGE_STATUSES).forEach(function (s) {
    if (labels.indexOf(s.label) < 0) labels.push(s.label);
  });
  labels.sort(function (a, b) { return orderOf_(a) - orderOf_(b); });

  var body = labels.map(function (label, rowIndex) {
    var row = [label];
    sources.forEach(function (s) {
      row.push("=COUNTIF('" + s.sheetName + "'!" + colLetter_(s.statusCol) + ':' +
        colLetter_(s.statusCol) + ',$A' + (startRow + 2 + rowIndex) + ')');
    });
    var first = colLetter_(2);
    var last = colLetter_(1 + sources.length);
    row.push('=SUM(' + first + (startRow + 2 + rowIndex) + ':' + last + (startRow + 2 + rowIndex) + ')');
    return row;
  });
  sheet.getRange(startRow + 2, 1, body.length, headers.length).setValues(body);
  return startRow + 2 + body.length;
}

/** Οι στήλες του coach: αυτόματες από το ημερολόγιο, ή χειροκίνητες. */
const COACH_COLUMNS = [
  { title: 'Ημέρες' },
  { title: 'ΤΗΛΕΦΩΝΑ ΑΠΟ ΤΗΝ ΛΙΣΤΑ ΕΠΑΦΩΝ ΜΟΥ', opts: { event: EVENTS.OUTREACH, channel: CHANNELS.PHONE, source: '"' + SOURCE_PERSONAL + '"' } },
  { title: 'Cold Calls', opts: { event: EVENTS.OUTREACH, channel: CHANNELS.PHONE, source: '"<>' + SOURCE_PERSONAL + '"' } },
  { title: 'Μηνύματα σε αγνώστους (cold messages)', opts: { event: EVENTS.OUTREACH, channel: CHANNELS.MESSAGE } },
  { title: 'Αποστολή Ερωτηματολογίων', manual: true },
  { title: 'Μηνύματα σε γνώστους', manual: true },
  { title: 'Μηνύματα συνέχειας (Follow-Ups)', manual: true },
  { title: 'ΕΚΛΕΙΣΑ 1ο ΡΑΝΤΕΒΟΥ', opts: { event: EVENTS.APPT_SET, stage: 1 } },
  { title: '1ο Ραντεβού', opts: { event: EVENTS.APPT_HELD, stage: 1 } },
  { title: '2ο Ραντεβού', opts: { event: EVENTS.APPT_HELD, stage: 2 } },
  { title: '3ο Ραντεβού', opts: { event: EVENTS.APPT_HELD, stage: 3 } },
  { title: 'Ραντέβου που πραγματοποίησα', opts: { event: EVENTS.APPT_HELD } },
  { title: 'Συμβόλαια που έκλεισα', opts: { event: EVENTS.CONTRACT } },
  { title: 'Λεπτά που αφιέρωσα στέλνοντας μηνύματα', manual: true },
  { title: 'Συζητήσεις στον κύκλο μου που άνοιξα', manual: true },
  { title: 'Συζητήσεις που δεν ξεκίνησαν από μένα', manual: true },
  { title: 'Λεπτά που αφιέρωσα γράφοντας περιεχόμενο', manual: true },
  { title: 'Πλήθος δημοσιεύσεων', manual: true },
  { title: 'Συστάσεις που ζήτησα', manual: true },
  { title: 'Λεπτά που αφιέρωσα για εκπλήρωση καθηκόντων για τα συμβόλαια', manual: true },
  { title: 'NVWP', opts: { event: EVENTS.CONTRACT, sum: true }, format: '#,##0.00 €' }
];

const COACH_WINDOWS = [
  { label: '4 Ημέρες', from: '=TODAY()-3' },
  { label: '7 Ημέρες', from: '=TODAY()-6' },
  { label: '30 Ημέρες', from: '=TODAY()-29' },
  { label: 'Μήνας μέχρι σήμερα', from: '=EOMONTH(TODAY(),-1)+1' },
  { label: 'Συνολικά', from: '=DATE(2000,1,1)' }
];

const COACH_FIRST_DAY_ROW = 9;

function buildCoachTable_() {
  var sheet = ensureSheet_(SHEET_COACH);
  sheet.clear();
  sheet.getRange('A1').setValue('ΠΙΝΑΚΑΣ ΓΙΑ ΤΟΝ COACH — γεμίζει μόνος του, αντιγράφεις τη γραμμή της ημέρας')
    .setFontWeight('bold').setFontSize(12);
  sheet.getRange(2, 1, 1, COACH_COLUMNS.length)
    .setValues([COACH_COLUMNS.map(function (c) { return c.title; })])
    .setFontWeight('bold').setWrap(true).setVerticalAlignment('bottom');
  sheet.setFrozenRows(2);
  sheet.setFrozenColumns(1);

  COACH_WINDOWS.forEach(function (w, i) {
    var row = 3 + i;
    sheet.getRange(row, 1).setValue(w.label).setFontWeight('bold');
    sheet.getRange(row, 23).setFormula(w.from);
    COACH_COLUMNS.forEach(function (col, index) {
      if (index === 0) return;
      var letter = colLetter_(index + 1);
      var cell = sheet.getRange(row, index + 1);
      if (col.manual) {
        cell.setFormula('=SUMIFS(' + letter + '$' + COACH_FIRST_DAY_ROW + ':' + letter +
          ',$A$' + COACH_FIRST_DAY_ROW + ':$A,">="&$W' + row + ')');
      } else {
        var opts = Object.assign({}, col.opts, { from: '$W' + row });
        cell.setFormula(col.opts.sum ? sumFormula_(opts) : countFormula_(opts));
      }
      if (col.format) cell.setNumberFormat(col.format);
    });
  });
  sheet.getRange(3, 1, COACH_WINDOWS.length, COACH_COLUMNS.length).setBackground('#e8eef7');

  var start = 'IFERROR(VLOOKUP("' + SETTING_START + '",' + "'" + SHEET_SETTINGS +
    "'" + '!$A:$B,2,FALSE),DATE(2026,4,9))';
  sheet.getRange(COACH_FIRST_DAY_ROW, 1).setFormula(
    '=ARRAYFORMULA(TO_DATE(SEQUENCE(MAX(1,TODAY()-' + start + '+1),1,' + start + ',1)))');

  var dayRange = '$A' + COACH_FIRST_DAY_ROW + ':$A';
  COACH_COLUMNS.forEach(function (col, index) {
    if (index === 0 || col.manual) return;
    var opts = Object.assign({}, col.opts, { date: dayRange });
    var inner = col.opts.sum ? sumFormula_(opts) : countFormula_(opts);
    sheet.getRange(COACH_FIRST_DAY_ROW, index + 1).setFormula(
      '=ARRAYFORMULA(IF(' + dayRange + '="","",' + inner.substring(1) + '))');
    if (col.format) sheet.getRange(COACH_FIRST_DAY_ROW, index + 1, 500, 1).setNumberFormat(col.format);
  });

  sheet.getRange('A:A').setNumberFormat('d-mmm-yyyy');
  sheet.setColumnWidth(1, 150);
  sheet.hideColumns(23);
  sheet.getRange(2, 1, 1, COACH_COLUMNS.length).setFontSize(9);
}

function buildProduction_() {
  var sheet = ensureSheet_(SHEET_PROD);
  sheet.clear();
  sheet.getRange('A1').setValue('ΠΑΡΑΓΩΓΗ').setFontWeight('bold').setFontSize(14);
  sheet.getRange(3, 1, 1, 5).setValues([['Μήνας', 'Στόχος (€)', 'Πραγματικό (€)', 'Διαφορά (€)',
    'Απαιτούμενο ανά μήνα για τον στόχο (€)']]).setFontWeight('bold').setWrap(true);

  var first = 4;
  var months = 14;
  var yearTargetCell = 'B' + (first + months + 1);

  for (var i = 0; i < months; i++) {
    var row = first + i;
    sheet.getRange(row, 1).setFormula(i === 0
      ? '=DATE(YEAR(' + settingLookup_(SETTING_START, 'DATE(2026,4,9)') + '),1,1)'
      : '=EDATE(A' + (row - 1) + ',1)');
    sheet.getRange(row, 2).setFormula('=' + settingLookup_(SETTING_MONTH_TARGET, 4167));
    sheet.getRange(row, 3).setFormula(sumFormula_({
      event: EVENTS.CONTRACT, from: '$A' + row, to: 'EOMONTH($A' + row + ',0)'
    }));
    sheet.getRange(row, 4).setFormula('=B' + row + '-C' + row);
    var priorSum = i === 0 ? '0' : 'SUM($C$' + first + ':C' + (row - 1) + ')';
    sheet.getRange(row, 5).setFormula('=IFERROR(MAX(0,' + yearTargetCell + '-' + priorSum +
      ')/MAX(1,' + (months - i) + '),"")');
  }

  var totalRow = first + months;
  sheet.getRange(totalRow, 1).setValue('Σύνολο').setFontWeight('bold');
  ['B', 'C', 'D'].forEach(function (letter) {
    sheet.getRange(totalRow, letter.charCodeAt(0) - 64)
      .setFormula('=SUM(' + letter + first + ':' + letter + (totalRow - 1) + ')');
  });
  sheet.getRange(totalRow + 1, 1).setValue('Ετήσιος στόχος').setFontWeight('bold');
  sheet.getRange(totalRow + 1, 2).setFormula('=' + settingLookup_(SETTING_YEAR_TARGET, 50000));
  sheet.getRange(totalRow + 2, 1).setValue('Υπόλοιπο για τον στόχο').setFontWeight('bold');
  sheet.getRange(totalRow + 2, 2).setFormula('=MAX(0,' + yearTargetCell + '-C' + totalRow + ')');

  sheet.getRange(first, 1, months, 1).setNumberFormat('mmmm yyyy');
  sheet.getRange(first, 2, months + 3, 4).setNumberFormat('#,##0.00 €');
  sheet.getRange(totalRow, 1, 3, 5).setBackground('#e8eef7');
  sheet.setColumnWidth(1, 160);
  [2, 3, 4, 5].forEach(function (c) { sheet.setColumnWidth(c, 170); });
}
