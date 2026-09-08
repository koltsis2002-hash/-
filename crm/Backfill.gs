/**
 * Αρχική φόρτωση και προαιρετική αποστολή στο αρχείο του coach.
 */

/**
 * Διαβάζει τις τρέχουσες καταστάσεις όλων των πηγών και γράφει τα γεγονότα που
 * τις δικαιολογούν, ώστε οι δείκτες να ξεκινούν από την πραγματικότητα και όχι
 * από το μηδέν. Χρεώνεται στην «Ημερομηνία αρχικής φόρτωσης» των ρυθμίσεων, μία
 * μέρα πριν την έναρξη, ώστε να μην μολύνει τα παράθυρα 7 και 30 ημερών.
 * Τρέχει μία φορά — προστατεύεται από τη σημαία στις ρυθμίσεις.
 */
function backfillFromCurrentState() {
  if (normalize_(settingValue_(SETTING_BACKFILL_DONE)) === 'ΝΑΙ') {
    SpreadsheetApp.getUi().alert('Η αρχική φόρτωση έχει ήδη γίνει. Για να ξανατρέξει, γύρισε τη ρύθμιση «' +
      SETTING_BACKFILL_DONE + '» σε ΟΧΙ.');
    return;
  }

  var backfillDate = dateOnly_(new Date(settingValue_(SETTING_BACKFILL_DATE)));
  var now = new Date();
  var known = {};
  logValues_().forEach(function (r) { known[r[4]] = true; });

  var rows = [];
  activeSources_().forEach(function (source) {
    var sheet = sheetByName_(source.sheetName);
    if (!sheet) return;
    var lastRow = sheet.getLastRow();
    if (lastRow <= source.headerRow) return;

    var width = sheet.getLastColumn();
    var values = sheet.getRange(source.headerRow + 1, 1, lastRow - source.headerRow, width).getValues();
    var amountCol = trackingColumn_(source, COL_AMOUNT);

    values.forEach(function (values_row, index) {
      var row = source.headerRow + 1 + index;
      var key = keyFor_(source, row);
      if (known[key]) return;

      var status = values_row[source.statusCol - 1];
      if (!isKnownStatus_(status)) return;

      var name = [values_row[source.nameCol - 1],
        source.nameCol2 ? values_row[source.nameCol2 - 1] : ''].filter(String).join(' ').trim();
      var amount = amountCol ? values_row[amountCol - 1] : '';

      pendingEvents_(status, {}).forEach(function (m) {
        rows.push(buildLogRow_({
          timestamp: now, date: backfillDate, source: source, key: key, name: name,
          oldStatus: '', newStatus: status, milestone: m.milestone, event: m.event, stage: m.stage,
          amount: m.event === EVENTS.CONTRACT ? (amount || '') : '',
          note: 'Αρχική φόρτωση'
        }));
      });
    });
  });

  if (rows.length) appendLogRows_(rows);
  setSettingValue_(SETTING_BACKFILL_DONE, 'ΝΑΙ');
  SpreadsheetApp.getActive().toast('Καταγράφηκαν ' + rows.length + ' γεγονότα από τις τρέχουσες καταστάσεις.',
    'Αρχική φόρτωση', 10);
}

/**
 * Γράφει τη σημερινή γραμμή του «Πίνακα Coach» στο αρχείο του coach.
 * Είναι απενεργοποιημένη: χρειάζεται δικαίωμα επεξεργασίας στο αρχείο του και
 * τη ρύθμιση «Αυτόματη αποστολή στο Dashboard» σε ΝΑΙ.
 */
function pushToCoachDashboard() {
  var ui = SpreadsheetApp.getUi();
  if (normalize_(settingValue_(SETTING_DASHBOARD_PUSH)) !== 'ΝΑΙ') {
    ui.alert('Η αυτόματη αποστολή είναι κλειστή. Άνοιξέ την στις ρυθμίσεις («' +
      SETTING_DASHBOARD_PUSH + '» = ΝΑΙ) αφού αποκτήσεις δικαίωμα επεξεργασίας στο αρχείο.');
    return;
  }
  var fileId = settingValue_(SETTING_DASHBOARD_ID);
  if (!fileId) {
    ui.alert('Λείπει το «' + SETTING_DASHBOARD_ID + '» από τις ρυθμίσεις.');
    return;
  }

  var local = sheetByName_(SHEET_COACH);
  var dates = local.getRange(COACH_FIRST_DAY_ROW, 1, local.getLastRow() - COACH_FIRST_DAY_ROW + 1, 1).getValues();
  var today = dateOnly_(new Date()).getTime();
  var offset = -1;
  dates.forEach(function (r, i) {
    if (r[0] instanceof Date && dateOnly_(r[0]).getTime() === today) offset = i;
  });
  if (offset < 0) {
    ui.alert('Δεν βρέθηκε σημερινή γραμμή στον Πίνακα Coach.');
    return;
  }

  var values = local.getRange(COACH_FIRST_DAY_ROW + offset, 2, 1, COACH_COLUMNS.length - 1).getValues();
  var remote = SpreadsheetApp.openById(fileId).getSheets()[0];
  var remoteDates = remote.getRange(1, 1, remote.getLastRow(), 1).getValues();
  for (var i = 0; i < remoteDates.length; i++) {
    if (remoteDates[i][0] instanceof Date && dateOnly_(remoteDates[i][0]).getTime() === today) {
      remote.getRange(i + 1, 2, 1, values[0].length).setValues(values);
      ui.alert('Η σημερινή γραμμή στάλθηκε στο Dashboard.');
      return;
    }
  }
  ui.alert('Δεν βρέθηκε η σημερινή ημερομηνία στο αρχείο του coach.');
}
