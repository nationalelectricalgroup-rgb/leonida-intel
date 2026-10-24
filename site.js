(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const text = (value, fallback='') => typeof value === 'string' && value.trim() ? value.trim() : fallback;
  const number = value => { const n = Number(value); return Number.isFinite(n) ? n : 0; };
  function setActiveNav(){
    const page = location.pathname.split('/').pop() || 'index.html';
    const key = page === 'missions.html' ? 'missions' : page === 'newsletter.html' ? 'newsletter' : 'home';
    document.querySelectorAll('[data-nav]').forEach(a => { if(a.dataset.nav === key) a.setAttribute('aria-current','page'); });
  }
  function setupMenu(){
    const button = document.querySelector('.menu-toggle'); const nav = $('site-nav');
    if(!button || !nav) return;
    button.addEventListener('click', () => { const open = button.getAttribute('aria-expanded') !== 'true'; button.setAttribute('aria-expanded', String(open)); nav.classList.toggle('is-open', open); });
    nav.addEventListener('click', event => { if(event.target.closest('a')) { button.setAttribute('aria-expanded','false'); nav.classList.remove('is-open'); } });
  }
  function labelFor(topic){
    const raw = text(topic.evidence_status || topic.content_label || topic.status).toLowerCase().replace(/[_-]/g,' ');
    if(/official|confirmed/.test(raw)) return ['Official / confirmed','status-official'];
    if(/report/.test(raw)) return ['Reported · unverified','status-reported'];
    if(/rumou|theor|speculat|unverified|community/.test(raw)) return ['Theory / unverified','status-theory'];
    return ['Community discussion','status-reported'];
  }
  function getTopics(data){
    if(Array.isArray(data)) return data;
    if(data && Array.isArray(data.topics)) return data.topics;
    if(data && Array.isArray(data.trends)) return data.trends;
    return [];
  }
  function relevantTopic(t){
    const title = text(t.name || t.title || t.topic).toLowerCase();
    const sampleTitles = Array.isArray(t.samples) ? t.samples.map(s=>text(s.title)).join(' ').toLowerCase() : '';
    const summary = text(t.summary || t.description).toLowerCase();
    const hay = `${title} ${sampleTitles} ${summary}`;
    // Keep the homepage specifically about GTA VI; avoid unrelated trend items (e.g. other games).
    if(/shrek|crypto|bitcoin|politics|weather/.test(hay)) return false;
    return /gta\s*6|gta\s*vi|grand theft auto|leonida|vice city|rockstar games/.test(hay);
  }
  function topicCard(topic, index){
    const title = text(topic.name || topic.title || topic.topic, 'GTA VI update');
    const [label, cls] = labelFor(topic);
    const score = number(topic.trend_score ?? topic.score);
    const sample = Array.isArray(topic.samples) ? topic.samples.find(s => s && typeof s.url === 'string' && /^https?:\/\//i.test(s.url)) : null;
    const sourceUrl = sample ? sample.url : 'https://www.rockstargames.com/VI';
    const description = text(topic.summary || topic.description || (sample && sample.title), 'Open the source to review the original context.');
    return `<article class="trend-card"><span class="status-pill ${cls}">${escapeHTML(label)}</span><h3>${escapeHTML(title)}</h3><p>${escapeHTML(description)}</p><div class="card-bottom"><span class="rank">${score > 0 ? `${Math.round(score)} trend points` : 'Latest topic'}</span><a href="${escapeHTML(sourceUrl)}" target="_blank" rel="noopener noreferrer">Read source ↗</a></div></article>`;
  }
  async function loadHomeTrends(){
    const grid = $('home-trends'); if(!grid) return;
    const status = $('trend-status');
    try {
      const response = await fetch('./data/trends.json', {cache:'no-store'});
      if(!response.ok) throw new Error(`Data request failed (${response.status})`);
      const data = await response.json();
      const topics = getTopics(data).filter(relevantTopic);
      topics.sort((a,b)=>number(b.trend_score ?? b.score)-number(a.trend_score ?? a.score));
      const selected = topics.slice(0,3);
      if(!selected.length){ grid.innerHTML = '<article class="trend-card"><span class="status-pill status-prep">NO VERIFIED MATCHES</span><h3>We’re checking for useful updates</h3><p>No clearly relevant GTA VI topics are available in the latest saved run. We would rather show fewer items than fill the page with unrelated stories.</p><div class="card-bottom"><span class="rank">Data refreshes automatically</span><a href="https://www.rockstargames.com/VI" target="_blank" rel="noopener noreferrer">Official GTA VI page ↗</a></div></article>'; }
      else grid.innerHTML = selected.map(topicCard).join('');
      if(status) status.textContent = `Showing ${selected.length} relevant topic${selected.length===1?'':'s'} from the latest saved data. Labels are automated and should be checked against the linked source.`;
    } catch(error) {
      grid.innerHTML = '<article class="trend-card"><span class="status-pill status-prep">TEMPORARILY UNAVAILABLE</span><h3>Latest topics could not load</h3><p>The saved trend file is not available right now. You can still explore the player hub and official GTA VI source.</p><div class="card-bottom"><span class="rank">Data unavailable</span><a href="https://www.rockstargames.com/VI" target="_blank" rel="noopener noreferrer">Official source ↗</a></div></article>';
      if(status) status.textContent = 'Trend data could not be loaded. The rest of the website remains available.';
      console.error('Leonida Intel trend data:', error);
    }
  }
  document.addEventListener('DOMContentLoaded', () => { setActiveNav(); setupMenu(); loadHomeTrends(); });
})();
