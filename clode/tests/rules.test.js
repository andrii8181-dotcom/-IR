// Тести правил доступу хмари S.A.D. Запуск: cd cloud && npm install && npm test
// (потрібні Node.js і Java 21; firebase-tools сам запускає локальний емулятор Firestore)
import { readFileSync } from 'node:fs';
import { describe, it, before, after, beforeEach } from 'node:test';
import {
  initializeTestEnvironment, assertSucceeds, assertFails,
} from '@firebase/rules-unit-testing';
import {
  doc, getDoc, setDoc, updateDoc, deleteDoc, addDoc, getDocs, collection,
  query, where, serverTimestamp, Timestamp,
} from 'firebase/firestore';

const PROJECT = 'demo-sad';
let env;

// Учасники: керівник, запрошений виконавець, сторонній, виконавець без підтвердженої адреси
const OWNER = { uid: 'owner1', email: 'Kerivnyk@Example.com' };
const WORKER = { uid: 'worker1', email: 'vykonavets@example.com' };
const STRANGER = { uid: 'stranger1', email: 'chuzhyi@example.com' };
const UNVERIFIED = { uid: 'worker2', email: 'neperevireny@example.com' };

const db = (u, verified = true) =>
  env.authenticatedContext(u.uid, { email: u.email, email_verified: verified }).firestore();
const anon = () => env.unauthenticatedContext().firestore();

const EXP = 'exp1';
const expDoc = (over = {}) => ({
  ownerUid: OWNER.uid,
  ownerEmail: OWNER.email.toLowerCase(),
  code: 'E1',
  name: 'Регуляція росту яблуні',
  mode: 'open',
  status: 'active',
  memberEmails: [WORKER.email, UNVERIFIED.email],
  closedYears: [2025],
  ...over,
});
const value = (u, over = {}) => ({
  plot: 3,
  row: 1,
  pos: 3,
  indicator: 'Висота, см',
  year: 2026,
  value: 154.5,
  authorUid: u.uid,
  authorEmail: u.email,
  serverTime: serverTimestamp(),
  clientTime: Timestamp.fromDate(new Date('2026-06-15T10:00:00Z')),
  device: 'test',
  ...over,
});

async function seed() {
  await env.withSecurityRulesDisabled(async (ctx) => {
    const f = ctx.firestore();
    await setDoc(doc(f, 'experiments', EXP), expDoc());
    await setDoc(doc(f, 'experiments', EXP, 'schemes', 'SIG1'), { sig: 'SIG1', plots: [] });
    await setDoc(doc(f, 'experiments', EXP, 'indicators', 'h'), { name: 'Висота, см', type: 'number', year: 2026 });
    await setDoc(doc(f, 'experiments', EXP, 'values', 'v0'), {
      ...value(WORKER), serverTime: Timestamp.now(),
    });
    await setDoc(doc(f, 'experiments', 'exp2'), expDoc({ ownerUid: 'other', memberEmails: [] }));
  });
}

before(async () => {
  env = await initializeTestEnvironment({
    projectId: PROJECT,
    firestore: { rules: readFileSync(new URL('../firestore.rules', import.meta.url), 'utf8') },
  });
});
after(async () => { await env?.cleanup(); });
beforeEach(async () => { await env.clearFirestore(); await seed(); });

describe('профіль користувача', () => {
  it('свій профіль – можна читати й писати', async () => {
    await assertSucceeds(setDoc(doc(db(WORKER), 'users', WORKER.uid), { name: 'В' }));
    await assertSucceeds(getDoc(doc(db(WORKER), 'users', WORKER.uid)));
  });
  it('чужий профіль – не можна', async () => {
    await assertFails(getDoc(doc(db(STRANGER), 'users', WORKER.uid)));
    await assertFails(setDoc(doc(db(STRANGER), 'users', WORKER.uid), { name: 'x' }));
  });
  it('без входу – нічого', async () => {
    await assertFails(getDoc(doc(anon(), 'users', WORKER.uid)));
  });
});

describe('дослід', () => {
  it('власник і запрошений бачать дослід', async () => {
    await assertSucceeds(getDoc(doc(db(OWNER), 'experiments', EXP)));
    await assertSucceeds(getDoc(doc(db(WORKER), 'experiments', EXP)));
  });
  it('регістр адреси не має значення', async () => {
    const w = { uid: 'w3', email: 'VYKONAVETS@EXAMPLE.COM' };
    await assertSucceeds(getDoc(doc(db(w), 'experiments', EXP)));
  });
  it('сторонній, без входу й без підтвердженої адреси – не бачать', async () => {
    await assertFails(getDoc(doc(db(STRANGER), 'experiments', EXP)));
    await assertFails(getDoc(doc(anon(), 'experiments', EXP)));
    await assertFails(getDoc(doc(db(UNVERIFIED, false), 'experiments', EXP)));
  });
  it('перевірити неіснуючий дослід можна (нічого не розкриває), без входу – ні', async () => {
    const snap = await assertSucceeds(getDoc(doc(db(STRANGER), 'experiments', 'nema')));
    if (snap.exists()) throw new Error('документа не мало бути');
    await assertFails(getDoc(doc(anon(), 'experiments', 'nema')));
  });
  it('список «мої досліди» для виконавця – лише ті, куди запрошено', async () => {
    const q = query(collection(db(WORKER), 'experiments'), where('memberEmails', 'array-contains', WORKER.email));
    const snap = await assertSucceeds(getDocs(q));
    if (snap.size !== 1) throw new Error(`очікувався 1 дослід, отримано ${snap.size}`);
  });
  it('список «мої досліди» для власника', async () => {
    const q = query(collection(db(OWNER), 'experiments'), where('ownerUid', '==', OWNER.uid));
    await assertSucceeds(getDocs(q));
  });
  it('список усіх дослідів без фільтра – заборонено', async () => {
    await assertFails(getDocs(collection(db(WORKER), 'experiments')));
  });
  it('створити дослід може лише сам за себе', async () => {
    await assertSucceeds(setDoc(doc(db(STRANGER), 'experiments', 'n1'),
      expDoc({ ownerUid: STRANGER.uid, memberEmails: [] })));
    await assertFails(setDoc(doc(db(STRANGER), 'experiments', 'n2'),
      expDoc({ ownerUid: OWNER.uid })));
  });
  it('без підтвердженої адреси дослід не створити', async () => {
    await assertFails(setDoc(doc(db(UNVERIFIED, false), 'experiments', 'n3'),
      expDoc({ ownerUid: UNVERIFIED.uid })));
  });
  it('неправильний дослід відхиляється', async () => {
    const f = db(STRANGER);
    await assertFails(setDoc(doc(f, 'experiments', 'b1'), expDoc({ ownerUid: STRANGER.uid, mode: 'x' })));
    await assertFails(setDoc(doc(f, 'experiments', 'b2'), expDoc({ ownerUid: STRANGER.uid, code: '' })));
    await assertFails(setDoc(doc(f, 'experiments', 'b3'), expDoc({ ownerUid: STRANGER.uid, extra: 1 })));
  });
  it('сліпий дослід не може мати назви', async () => {
    const f = db(STRANGER);
    await assertFails(setDoc(doc(f, 'experiments', 's1'), expDoc({ ownerUid: STRANGER.uid, mode: 'blind' })));
    await assertSucceeds(setDoc(doc(f, 'experiments', 's2'), expDoc({ ownerUid: STRANGER.uid, mode: 'blind', name: '' })));
  });
  it('змінювати й видаляти – лише власник', async () => {
    await assertSucceeds(updateDoc(doc(db(OWNER), 'experiments', EXP), { status: 'archive' }));
    await assertFails(updateDoc(doc(db(WORKER), 'experiments', EXP), { status: 'archive' }));
    await assertFails(updateDoc(doc(db(WORKER), 'experiments', EXP), { memberEmails: [WORKER.email, STRANGER.email] }));
    await assertFails(deleteDoc(doc(db(WORKER), 'experiments', EXP)));
  });
  it('власника змінити не можна', async () => {
    await assertFails(updateDoc(doc(db(OWNER), 'experiments', EXP), { ownerUid: STRANGER.uid }));
  });
  it('відкликаний виконавець більше не бачить дослід', async () => {
    await updateDoc(doc(db(OWNER), 'experiments', EXP), { memberEmails: [] });
    await assertFails(getDoc(doc(db(WORKER), 'experiments', EXP)));
  });
});

describe('схема й показники', () => {
  it('читають власник і виконавець', async () => {
    await assertSucceeds(getDoc(doc(db(WORKER), 'experiments', EXP, 'schemes', 'SIG1')));
    await assertSucceeds(getDoc(doc(db(WORKER), 'experiments', EXP, 'indicators', 'h')));
  });
  it('сторонній не читає', async () => {
    await assertFails(getDoc(doc(db(STRANGER), 'experiments', EXP, 'schemes', 'SIG1')));
  });
  it('пише лише власник', async () => {
    await assertSucceeds(setDoc(doc(db(OWNER), 'experiments', EXP, 'schemes', 'SIG2'), { sig: 'SIG2' }));
    await assertFails(setDoc(doc(db(WORKER), 'experiments', EXP, 'schemes', 'SIG3'), { sig: 'SIG3' }));
    await assertFails(setDoc(doc(db(WORKER), 'experiments', EXP, 'indicators', 'x'), { name: 'x' }));
  });
});

describe('значення обліку', () => {
  const vals = (u) => collection(db(u), 'experiments', EXP, 'values');

  it('виконавець і власник вносять значення', async () => {
    await assertSucceeds(addDoc(vals(WORKER), value(WORKER)));
    await assertSucceeds(addDoc(vals(OWNER), value(OWNER)));
  });
  it('дата фенофази й ділянка з рослиною', async () => {
    await assertSucceeds(addDoc(vals(WORKER), value(WORKER, { indicator: 'Цвітіння', value: '2026-05-02' })));
    await assertSucceeds(addDoc(vals(WORKER), value(WORKER, { plot: 2, row: 2, pos: 4 })));
  });
  it('виправлення – новий запис із посиланням на попередній', async () => {
    await assertSucceeds(addDoc(vals(WORKER), value(WORKER, { value: 150, supersedes: 'v0' })));
    await assertSucceeds(addDoc(vals(WORKER), value(WORKER, { value: null, deleted: true, supersedes: 'v0' })));
  });
  it('змінити наявне значення не може ніхто', async () => {
    await assertFails(updateDoc(doc(db(WORKER), 'experiments', EXP, 'values', 'v0'), { value: 1 }));
    await assertFails(updateDoc(doc(db(OWNER), 'experiments', EXP, 'values', 'v0'), { value: 1 }));
  });
  it('видалити може лише власник', async () => {
    await assertFails(deleteDoc(doc(db(WORKER), 'experiments', EXP, 'values', 'v0')));
    await assertSucceeds(deleteDoc(doc(db(OWNER), 'experiments', EXP, 'values', 'v0')));
  });
  it('від чужого імені внести не можна', async () => {
    await assertFails(addDoc(vals(WORKER), value(WORKER, { authorUid: OWNER.uid })));
  });
  it('час сервера підробити не можна', async () => {
    await assertFails(addDoc(vals(WORKER), value(WORKER, { serverTime: Timestamp.fromDate(new Date('2020-01-01')) })));
  });
  it('у закритий рік внести не можна', async () => {
    await assertFails(addDoc(vals(WORKER), value(WORKER, { year: 2025 })));
    await assertFails(addDoc(vals(OWNER), value(OWNER, { year: 2025 })));
  });
  it('сторонній і виконавець без підтвердженої адреси не вносять і не читають', async () => {
    await assertFails(addDoc(vals(STRANGER), value(STRANGER)));
    await assertFails(addDoc(collection(db(UNVERIFIED, false), 'experiments', EXP, 'values'), value(UNVERIFIED)));
    await assertFails(getDoc(doc(db(STRANGER), 'experiments', EXP, 'values', 'v0')));
  });
  it('виконавець читає значення досліду', async () => {
    await assertSucceeds(getDocs(vals(WORKER)));
  });
  it('неправильні значення відхиляються', async () => {
    const bad = [
      { plot: 0 }, { plot: 'a' }, { row: 0 }, { pos: 1.5 }, { plant: 1 }, { indicator: '' }, { year: 1800 },
      { value: 'багато' }, { value: '2026-5-2' }, { value: null }, { deleted: 'так' },
      { extra: 1 }, { clientTime: 'вчора' },
    ];
    for (const b of bad) {
      await assertFails(addDoc(vals(WORKER), value(WORKER, b)));
    }
  });
  it('відсутнє обов\'язкове поле відхиляється', async () => {
    for (const k of ['indicator', 'row', 'pos']) {
      const v = value(WORKER); delete v[k];
      await assertFails(addDoc(vals(WORKER), v));
    }
  });
  it('значення в неіснуючий дослід внести не можна', async () => {
    await assertFails(addDoc(collection(db(WORKER), 'experiments', 'nema', 'values'), value(WORKER)));
  });
});
