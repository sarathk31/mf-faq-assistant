/*
 * Source capture and verification helpers, run in a browser DevTools console.
 *
 * Why a browser: the development network blocked hdfcfund.com and sebi.gov.in, so pages were
 * opened in a normal browser and read there. These are the exact steps used on 2026-11-04.
 *
 * 1) Scheme pages (S01-S04): open e.g. https://www.hdfcfund.com/explore/mutual-funds/hdfc-flexi-cap-fund/direct
 *    and run captureSchemePage(). It reads the page's embedded scheme data (__NEXT_DATA__).
 * 2) PDFs (KIM, SID, Fund Facts, factsheet, SEBI circular): open any page on https://www.sebi.gov.in,
 *    run loadPdfJs() once (SEBI hosts pdf.js), then extractPdf(url). HDFC's file server allows cross-origin reads.
 * 3) verifyQuotes(text, quotes) checks every stored excerpt is still present in the live source.
 */

function captureSchemePage() {
  const d = JSON.parse(document.getElementById('__NEXT_DATA__').textContent);
  const ov = d.props.pageProps.singleFundResponse.data.details[0].Overview.data;
  const strip = v => typeof v === 'string' ? v.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim() : v;
  const links = [...document.querySelectorAll('a')].filter(a => /^(SID|KIM|Fund Facts)/.test(a.innerText.trim()))
    .map(a => [a.innerText.trim(), a.href.split('?')[0]]);
  return {
    url: location.href, captured_on: new Date().toISOString().slice(0, 10),
    exit_load: strip(ov.exitLoad), ter_direct: ov.terDirecct, ter_regular: ov.terRegular, min_sip: ov.minimumSip,
    riskometer: (ov.risk || []).map(r => r.name), benchmark: ov.benchmark, lock_in: ov.lockInValue, aum_as_of: ov.aumAsMonth, links,
  };
}

async function loadPdfJs() {
  await new Promise((res, rej) => { const s = document.createElement('script'); s.src = '/build/pdf.js'; s.onload = res; s.onerror = rej; document.head.appendChild(s); });
  window.pdfjsLib.GlobalWorkerOptions.workerSrc = '/build/pdf.worker.js';
}

const normalize = s => s.replace(/[\u2018\u2019]/g, "'").replace(/[\u201C\u201D]/g, '"').replace(/[\u2013\u2014]/g, '-')
  .replace(/₹/g, 'Rs.').replace(/[●•]/g, '-').replace(/\s+-\s+(?=[a-z])/g, '-').replace(/(\w)\s+-\s+(\w)/g, '$1-$2')
  .replace(/[^\x20-\x7E]/g, ' ').replace(/\s+/g, ' ').trim();

async function extractPdf(url, maxPages = 30) {
  const data = new Uint8Array(await (await fetch(url)).arrayBuffer());
  const doc = await window.pdfjsLib.getDocument({ data }).promise;
  const pages = [];
  for (let i = 1; i <= Math.min(doc.numPages, maxPages); i++) {
    const tc = await (await doc.getPage(i)).getTextContent();
    pages.push(tc.items.map(x => x.str).join(' '));
  }
  return { numPages: doc.numPages, text: normalize(pages.join(' ')) };
}

function verifyQuotes(sourceText, quotes) {
  // Spacing-insensitive: PDF extraction sometimes splits words ("level s"), so compare with whitespace removed.
  const squash = s => normalize(s).replace(/\s+/g, '').toLowerCase();
  const hay = squash(sourceText);
  return quotes.map(q => hay.includes(squash(q)) ? 'OK' : 'MISSING: ' + q.slice(0, 60));
}
