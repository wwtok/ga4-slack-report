const page = await openTab('https://searchadvisor.naver.com/console/site/report/expose?site={{SITE_ENC}}');
try {
  const title = await page.title();
  if (title.includes('오류')) {
    console.log(JSON.stringify({ error: 'not_logged_in' }));
  } else {
    const url = '/api-console/report/expose/{{SITE_HASH}}?site={{SITE_ENC}}&period={{WINDOW}}&device=d&topN={{TOP_N}}';
    const json = await page.evaluate(async (u) => {
      const res = await fetch(u, { credentials: 'include' });
      return await res.json();
    }, url);
    console.log(JSON.stringify(json));
  }
} catch (e) {
  console.log(JSON.stringify({ error: String(e) }));
} finally {
  await closeTab(page);
}
