/**
 * Καταγραφή γεγονότων. Ο handler γράφει ΜΟΝΟ στο Log_Δραστηριότητας —
 * όλοι οι πίνακες από πάνω είναι τύποι, οπότε δεν υπάρχει τίποτα να συγχρονιστεί.
 */

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('CRM')
    .addItem('Στήσιμο / ενημέρωση πινάκων', 'setupAll')
    .addItem('Αρχική φόρτωση από τις τρέχουσες καταστάσεις', 'backfillFromCurrentState')
    .addSeparator()
    .addItem('Αποστολή σημερινής γραμμής στο Dashboard', 'pushToCoachDashboard')
    .addToUi();
}

function onEditHandler(e) {
  if (!e || !e.range) return;
  var sheet = e.range.getSheet();
  var source = sourceForSheet_(sheet.getName());
  if (!source) return;

  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(15000)) return;
  try {
    var col = e.range.getColumn();
    var width = e.range.getNumColumns();
    var firstRow = Math.max(e.range.getRow(), source.headerRow + 1);
    var lastRow = e.range.getRow() + e.range.getNumRows() - 1;
    if (lastRow < firstRow) return;

    var statusCol = source.statusCol;
    var callPlusCol = trackingColumn_(source, COL_CALLPLUS);
    var amountCol = trackingColumn_(source, COL_AMOUNT);
    var touches = function (target) { return target && col <= target && target < col + width; };

    var pending = [];
    for (var row = firstRow; row <= lastRow; row++) {
      if (touches(statusCol)) pending = pending.concat(statusChangeEvents_(source, sheet, row));
      if (touches(callPlusCol)) pending = pending.concat(callPlusEvents_(source, sheet, row, callPlusCol));
      if (touches(amountCol)) syncAmount_(source, sheet, row, amountCol);
    }
    if (pending.length) appendLogRows_(pending);
    if (touches(statusCol) || touches(callPlusCol)) stampUpdated_(source, sheet, firstRow, lastRow);
  } finally {
    lock.releaseLock();
  }
}

function sourceForSheet_(name) {
  var matches = activeSources_().filter(function (s) { return s.sheetName === name; });
  return matches.length ? matches[0] : null;
}

function keyFor_(source, row) { return source.sheetName + '#' + row; }

function nameFor_(source, sheet, row) {
  var parts = [sheet.getRange(row, source.nameCol).getValue()];
  if (source.nameCol2) parts.push(sheet.getRange(row, source.nameCol2).getValue());
  return parts.filter(String).join(' ').trim();
}

/* ------------------------------------------------------------------ */
/* Ανάγνωση ημερολογίου                                                */
/* ------------------------------------------------------------------ */

var LOG_CACHE = null;

function logValues_() {
  if (LOG_CACHE) return LOG_CACHE;
  var sheet = sheetByName_(SHEET_LOG);
  var last = sheet.getLastRow();
  LOG_CACHE = last < 2 ? [] : sheet.getRange(2, 1, last - 1, LOG_HEADERS.length).getValues();
  return LOG_CACHE;
}

/** Τα ορόσημα που έχουν ήδη καταγραφεί για μια επαφή — η μνήμη του συστήματος. */
function recordedMilestones_(key) {
  var recorded = {};
  logValues_().forEach(function (r) {
    if (r[4] === key && r[8]) recorded[r[8]] = true;
  });
  return recorded;
}

function lastStatusFor_(key) {
  var values = logValues_();
  for (var i = values.length - 1; i >= 0; i--) {
    if (values[i][4] === key) return values[i][7];
  }
  return '';
}

/* ------------------------------------------------------------------ */
/* Παραγωγή γεγονότων                                                  */
/* ------------------------------------------------------------------ */

function statusChangeEvents_(source, sheet, row) {
  var newStatus = sheet.getRange(row, source.statusCol).getValue();
  if (!isKnownStatus_(newStatus)) return [];

  var key = keyFor_(source, row);
  var events = pendingEvents_(newStatus, recordedMilestones_(key));
  if (!events.length) return [];

  var name = nameFor_(source, sheet, row);
  var oldStatus = lastStatusFor_(key);
  var amountCol = trackingColumn_(source, COL_AMOUNT);
  var amount = amountCol ? sheet.getRange(row, amountCol).getValue() : '';
  var now = new Date();
  var today = dateOnly_(now);

  var rows = events.map(function (m) {
    return buildLogRow_({
      timestamp: now, date: today, source: source, key: key, name: name,
      oldStatus: oldStatus, newStatus: newStatus, milestone: m.milestone,
      event: m.event, stage: m.stage,
      amount: m.event === EVENTS.CONTRACT ? (amount || '') : '',
      note: ''
    });
  });

  var hasContract = events.some(function (m) { return m.event === EVENTS.CONTRACT; });
  if (hasContract) stampDateIfEmpty_(source, sheet, row, COL_CONTRACT_DATE, today);
  return rows;
}

function callPlusEvents_(source, sheet, row, callPlusCol) {
  var cell = sheet.getRange(row, callPlusCol);
  if (cell.getValue() !== true) return [];
  cell.setValue(false);

  var key = keyFor_(source, row);
  var now = new Date();
  return [buildLogRow_({
    timestamp: now, date: dateOnly_(now), source: source, key: key,
    name: nameFor_(source, sheet, row),
    oldStatus: '', newStatus: sheet.getRange(row, source.statusCol).getValue(),
    milestone: '', event: EVENTS.OUTREACH, stage: '', amount: '',
    note: 'Επαναληπτική προσέγγιση'
  })];
}

/** Ποσό που μπήκε μετά την αλλαγή κατάστασης — ενημερώνει την εγγραφή του συμβολαίου. */
function syncAmount_(source, sheet, row, amountCol) {
  var amount = sheet.getRange(row, amountCol).getValue();
  if (amount === '' || amount === null) return;

  var key = keyFor_(source, row);
  var logSheet = sheetByName_(SHEET_LOG);
  var values = logValues_();
  for (var i = values.length - 1; i >= 0; i--) {
    if (values[i][4] === key && values[i][9] === EVENTS.CONTRACT) {
      logSheet.getRange(i + 2, 12).setValue(amount);
      values[i][11] = amount;
      return;
    }
  }
}

function buildLogRow_(o) {
  return [o.timestamp, o.date, o.source.label, o.source.channel, o.key, o.name,
    o.oldStatus, o.newStatus, o.milestone, o.event, o.stage, o.amount, o.note];
}

function appendLogRows_(rows) {
  var sheet = sheetByName_(SHEET_LOG);
  var start = Math.max(sheet.getLastRow() + 1, 2);
  if (start + rows.length > LOG_LIMIT) {
    SpreadsheetApp.getActive().toast(
      'Το ημερολόγιο γέμισε. Αύξησε το LOG_LIMIT στο Setup.gs και ξανατρέξε το στήσιμο.',
      'Προσοχή', 30);
  }
  sheet.getRange(start, 1, rows.length, LOG_HEADERS.length).setValues(rows);
  if (LOG_CACHE) LOG_CACHE = LOG_CACHE.concat(rows);
}

function dateOnly_(value) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

function stampUpdated_(source, sheet, firstRow, lastRow) {
  var col = trackingColumn_(source, COL_UPDATED);
  if (!col) return;
  var now = new Date();
  var stamps = [];
  for (var row = firstRow; row <= lastRow; row++) stamps.push([now]);
  sheet.getRange(firstRow, col, stamps.length, 1).setValues(stamps);
}

function stampDateIfEmpty_(source, sheet, row, columnName, value) {
  var col = trackingColumn_(source, columnName);
  if (!col) return;
  var cell = sheet.getRange(row, col);
  if (!cell.getValue()) cell.setValue(value);
}
