/**
 * Λεξιλόγιο καταστάσεων και χαρτογράφηση σε γεγονότα.
 *
 * Μοντέλο οροσήμων: κάθε κατάσταση δηλώνει ποια ορόσημα *προϋποθέτει*. Όταν μια
 * επαφή αλλάζει κατάσταση, καταγράφονται μόνο τα ορόσημα που δεν έχουν ήδη
 * καταγραφεί γι' αυτήν. Έτσι το άλμα «ΔΕΝ ΕΧΩ ΚΑΛΕΣΕΙ -> ΕΚΛΕΙΣΑ 1ο ΡΑΝΤΕΒΟΥ»
 * μετράει κλήση, επαφή και ραντεβού, μια διόρθωση προς τα πίσω δεν ξαναμετράει
 * τίποτα, και ένα συμβόλαιο μετά από ένα μόνο ραντεβού δεν εφευρίσκει 2ο και 3ο.
 */

const EVENTS = {
  OUTREACH: 'ΠΡΟΣΕΓΓΙΣΗ',
  CONTACT: 'ΕΠΑΦΗ',
  APPT_SET: 'ΡΑΝΤΕΒΟΥ_ΚΛΕΙΣΤΟ',
  APPT_HELD: 'ΡΑΝΤΕΒΟΥ_ΕΓΙΝΕ',
  CONTRACT: 'ΣΥΜΒΟΛΑΙΟ',
  LOST: 'ΑΠΩΛΕΙΑ',
  CANCELLED: 'ΑΚΥΡΩΣΗ'
};

const CHANNELS = { PHONE: 'Τηλέφωνο', MESSAGE: 'Μήνυμα' };

/** Τα ορόσημα της πώλησης. Το id καταγράφεται στο ημερολόγιο και εγγυάται ότι
 *  κανένα ορόσημο δεν μετριέται δύο φορές για την ίδια επαφή. */
const MILESTONES = {
  OUTREACH: { event: EVENTS.OUTREACH, stage: '' },
  CONTACT: { event: EVENTS.CONTACT, stage: '' },
  APPT_SET_1: { event: EVENTS.APPT_SET, stage: 1 },
  APPT_HELD_1: { event: EVENTS.APPT_HELD, stage: 1 },
  APPT_SET_2: { event: EVENTS.APPT_SET, stage: 2 },
  APPT_HELD_2: { event: EVENTS.APPT_HELD, stage: 2 },
  APPT_SET_3: { event: EVENTS.APPT_SET, stage: 3 },
  APPT_HELD_3: { event: EVENTS.APPT_HELD, stage: 3 },
  CONTRACT: { event: EVENTS.CONTRACT, stage: '' }
};

const REACHED = ['OUTREACH'];
const TALKED = REACHED.concat(['CONTACT']);
const SET_1 = TALKED.concat(['APPT_SET_1']);
const HELD_1 = SET_1.concat(['APPT_HELD_1']);
const SET_2 = HELD_1.concat(['APPT_SET_2']);
const HELD_2 = SET_2.concat(['APPT_HELD_2']);
const SET_3 = HELD_2.concat(['APPT_SET_3']);
const HELD_3 = SET_3.concat(['APPT_HELD_3']);
/** Το συμβόλαιο προϋποθέτει ένα ραντεβού που έγινε — όχι και τα τρία. */
const SIGNED = HELD_1.concat(['CONTRACT']);

/**
 * Καταστάσεις τηλεφωνικών πηγών. Οι πέντε πρώτες υπάρχουν ήδη στα φύλλα σου με
 * ακριβώς αυτά τα ονόματα και δεν αλλάζουν· οι υπόλοιπες είναι νέες.
 */
const PHONE_STATUSES = [
  { label: 'ΔΕΝ ΕΧΩ ΚΑΛΕΣΕΙ', implies: [] },
  { label: 'ΕΧΩ ΚΑΛΕΣΕΙ, ΔΕΝ ΤΟ ΣΗΚΩΣΕ', implies: REACHED },
  { label: 'ΕΧΩ ΚΑΛΕΣΕΙ, ΔΕΝ ΜΠΟΡΕΙ ΤΩΡΑ ΛΟΓΩ ΔΟΥΛΕΙΑΣ ΝΑ ΚΑΝΕΙ ΡΑΝΤΕΒΟΥ, ΘΑ ΞΑΝΑ ΚΑΛΕΣΩ', implies: TALKED },
  { label: 'ΔΕΝ ΕΝΔΙΑΦΕΡΕΤΑΙ', implies: TALKED, extra: [EVENTS.LOST] },
  { label: 'ΕΚΛΕΙΣΑ 1ο ΡΑΝΤΕΒΟΥ', implies: SET_1 },
  { label: 'ΠΡΑΓΜΑΤΟΠΟΙΗΘΗΚΕ 1ο ΡΑΝΤΕΒΟΥ', implies: HELD_1 },
  { label: 'ΕΚΛΕΙΣΑ 2ο ΡΑΝΤΕΒΟΥ', implies: SET_2 },
  { label: 'ΠΡΑΓΜΑΤΟΠΟΙΗΘΗΚΕ 2ο ΡΑΝΤΕΒΟΥ', implies: HELD_2 },
  { label: 'ΕΚΛΕΙΣΑ 3ο ΡΑΝΤΕΒΟΥ', implies: SET_3 },
  { label: 'ΠΡΑΓΜΑΤΟΠΟΙΗΘΗΚΕ 3ο ΡΑΝΤΕΒΟΥ', implies: HELD_3 },
  { label: 'ΑΚΥΡΩΣΕ ΡΑΝΤΕΒΟΥ', implies: TALKED, extra: [EVENTS.CANCELLED] },
  { label: 'ΕΚΑΝΕ ΣΥΜΒΟΛΑΙΟ', implies: SIGNED }
];

/** Καταστάσεις για πηγές μηνυμάτων (LinkedIn) — ίδια ορόσημα, δικό τους λεξιλόγιο στην αρχή. */
const MESSAGE_STATUSES = [
  { label: 'Καμία επαφή', implies: [] },
  { label: 'Πρώτη επαφή', implies: REACHED },
  { label: '2η+ επαφή', implies: TALKED }
].concat(PHONE_STATUSES.filter(function (s) { return s.implies.length >= 2 && s.label !== 'ΕΧΩ ΚΑΛΕΣΕΙ, ΔΕΝ ΜΠΟΡΕΙ ΤΩΡΑ ΛΟΓΩ ΔΟΥΛΕΙΑΣ ΝΑ ΚΑΝΕΙ ΡΑΝΤΕΒΟΥ, ΘΑ ΞΑΝΑ ΚΑΛΕΣΩ'; }));

/** Κείμενο σε συγκρίσιμη μορφή: κεφαλαία, χωρίς τόνους, χωρίς διπλά κενά. */
function normalize_(value) {
  if (value === null || value === undefined) return '';
  return String(value)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toUpperCase();
}

var STATUS_INDEX = null;

function statusIndex_() {
  if (STATUS_INDEX) return STATUS_INDEX;
  STATUS_INDEX = {};
  PHONE_STATUSES.concat(MESSAGE_STATUSES).forEach(function (s) {
    STATUS_INDEX[normalize_(s.label)] = s;
  });
  return STATUS_INDEX;
}

function statusDef_(status) {
  return statusIndex_()[normalize_(status)] || null;
}

/** true όταν το κείμενο της κατάστασης αναγνωρίζεται από το λεξιλόγιο. */
function isKnownStatus_(status) {
  return !!statusDef_(status);
}

/** Σειρά της κατάστασης στη διαδρομή της πώλησης — για ταξινόμηση στο χωνί. */
function orderOf_(status) {
  var def = statusDef_(status);
  return def ? def.implies.length : -1;
}

/**
 * Τα γεγονότα που πρέπει να καταγραφούν όταν μια επαφή περνά στη νέα κατάσταση,
 * δεδομένων των οροσήμων που έχουν ήδη καταγραφεί γι' αυτήν.
 * Επιστρέφει πίνακα από {milestone, event, stage}.
 */
function pendingEvents_(newStatus, recorded) {
  var def = statusDef_(newStatus);
  if (!def) return [];

  var events = def.implies
    .filter(function (id) { return !recorded[id]; })
    .map(function (id) {
      return { milestone: id, event: MILESTONES[id].event, stage: MILESTONES[id].stage };
    });

  (def.extra || []).forEach(function (event) {
    var id = event + '@' + normalize_(newStatus);
    if (!recorded[id]) events.push({ milestone: id, event: event, stage: '' });
  });
  return events;
}

/** Οι ετικέτες που μπαίνουν ως dropdown στη στήλη κατάστασης μιας πηγής. */
function statusLabelsFor_(channel) {
  var set = channel === CHANNELS.MESSAGE ? MESSAGE_STATUSES : PHONE_STATUSES;
  return set.map(function (s) { return s.label; });
}
