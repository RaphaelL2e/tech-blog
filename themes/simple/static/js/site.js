(function () {
  'use strict';

  const menuButton = document.querySelector('.menu-toggle');
  const mobileNav = document.getElementById('mobile-nav');
  if (menuButton && mobileNav) {
    menuButton.addEventListener('click', () => {
      const open = menuButton.getAttribute('aria-expanded') === 'true';
      menuButton.setAttribute('aria-expanded', String(!open));
      menuButton.setAttribute('aria-label', open ? '打开导航' : '关闭导航');
      mobileNav.hidden = open;
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !mobileNav.hidden) {
        mobileNav.hidden = true;
        menuButton.setAttribute('aria-expanded', 'false');
        menuButton.focus();
      }
    });
  }

  const article = document.querySelector('[data-article-content]');
  if (article) {
    const progressBars = document.querySelectorAll('.reading-progress span, .toc-progress > span');
    const progressText = document.querySelector('.toc-progress b');
    const updateProgress = () => {
      const start = article.getBoundingClientRect().top + window.scrollY;
      const distance = Math.max(article.offsetHeight - window.innerHeight * .55, 1);
      const value = Math.min(100, Math.max(0, ((window.scrollY - start + 100) / distance) * 100));
      progressBars.forEach((bar) => { bar.style.width = value.toFixed(1) + '%'; });
      if (progressText) progressText.textContent = Math.round(value) + '%';
    };
    updateProgress();
    window.addEventListener('scroll', updateProgress, { passive: true });
    window.addEventListener('resize', updateProgress);

    article.querySelectorAll('h2[id], h3[id]').forEach((heading) => {
      const anchor = document.createElement('a');
      anchor.className = 'heading-anchor';
      anchor.href = '#' + encodeURIComponent(heading.id);
      anchor.setAttribute('aria-label', '复制这一节的链接');
      anchor.textContent = '#';
      anchor.addEventListener('click', () => {
        const url = window.location.origin + window.location.pathname + '#' + encodeURIComponent(heading.id);
        if (navigator.clipboard) navigator.clipboard.writeText(url).catch(() => {});
      });
      heading.appendChild(anchor);
    });

    article.querySelectorAll('pre').forEach((block) => {
      const code = block.querySelector('code');
      if (!code) return;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'copy-code';
      button.textContent = '复制';
      button.setAttribute('aria-label', '复制代码');
      button.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(code.innerText);
          button.textContent = '已复制';
          document.getElementById('live-region').textContent = '代码已复制';
          window.setTimeout(() => { button.textContent = '复制'; }, 1600);
        } catch (_) { button.textContent = '复制失败'; }
      });
      block.appendChild(button);
    });

    const tocLinks = Array.from(document.querySelectorAll('.article-toc a'));
    if (tocLinks.length && 'IntersectionObserver' in window) {
      const headingMap = new Map(tocLinks.map((link) => [decodeURIComponent(link.hash.slice(1)), link]));
      const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            tocLinks.forEach((link) => link.classList.remove('active'));
            const link = headingMap.get(entry.target.id);
            if (link) link.classList.add('active');
          }
        });
      }, { rootMargin: '-18% 0px -72% 0px' });
      article.querySelectorAll('h2[id], h3[id]').forEach((heading) => observer.observe(heading));
    }
  }

  const searchRoot = document.querySelector('[data-search-root]');
  if (searchRoot) {
    const topicLabels = {
      'java-spring': 'Java 与 Spring',
      'distributed-systems': '分布式与微服务',
      'database-middleware': '数据库与中间件',
      'system-engineering': '系统设计与工程效能',
      'ai-engineering': 'AI 工程化',
      'computer-science': '计算机基础',
      archive: '历史归档'
    };
    const input = searchRoot.querySelector('input[type="search"]');
    const topicButtons = Array.from(searchRoot.querySelectorAll('[data-topic]'));
    const seriesSelect = searchRoot.querySelector('select[name="series"]');
    const resultRoot = document.getElementById('search-results');
    const empty = document.getElementById('search-empty');
    const summary = document.getElementById('search-summary') || document.querySelector('.result-summary');
    const defaultLibrary = document.querySelector('[data-default-library]');
    const defaultResults = document.getElementById('default-results');
    const pagination = defaultLibrary ? defaultLibrary.querySelector('.pagination') : null;
    let index = null;
    let activeTopic = '';
    let debounce;

    const escapeHTML = (value) => value.replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[char]);
    const highlight = (value, query) => {
      const safe = escapeHTML(value || '');
      if (!query) return safe;
      const words = query.trim().split(/\s+/).filter(Boolean).map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
      if (!words.length) return safe;
      return safe.replace(new RegExp('(' + words.join('|') + ')', 'ig'), '<mark>$1</mark>');
    };
    const snippet = (item, query) => {
      const source = item.description || item.content || '';
      if (!query) return source.slice(0, 150);
      const lower = source.toLowerCase();
      const pos = lower.indexOf(query.toLowerCase());
      const start = Math.max(0, pos > -1 ? pos - 35 : 0);
      return (start ? '…' : '') + source.slice(start, start + 155) + (source.length > start + 155 ? '…' : '');
    };
    const render = (items, query) => {
      resultRoot.innerHTML = items.slice(0, 60).map((item) => `
        <article class="post-card search-card">
          <a class="card-link" href="${escapeHTML(item.url)}" aria-label="阅读：${escapeHTML(item.title)}"></a>
          <div class="card-topline"><span class="topic-badge">${escapeHTML(topicLabels[item.topic] || item.topic)}</span>${item.seriesOrder ? `<span class="series-position">#${item.seriesOrder}</span>` : ''}</div>
          <h2>${highlight(item.title, query)}</h2>
          <p>${highlight(snippet(item, query), query)}</p>
          <div class="card-meta"><time>${item.date}</time><span>${item.readingTime} 分钟</span></div>
        </article>`).join('');
      empty.hidden = items.length > 0;
      resultRoot.hidden = items.length === 0;
      if (summary) summary.innerHTML = `<strong>${items.length}</strong> 篇匹配文章`;
    };
    const ensureIndex = async () => {
      if (index) return index;
      const response = await fetch(searchRoot.dataset.indexUrl, { credentials: 'same-origin' });
      if (!response.ok) throw new Error('search index unavailable');
      index = await response.json();
      return index;
    };
    const search = async () => {
      const query = input.value.trim();
      const series = seriesSelect ? seriesSelect.value : '';
      const active = query || activeTopic || series;
      if (defaultLibrary) {
        defaultResults.hidden = Boolean(active);
        if (pagination) pagination.hidden = Boolean(active);
        resultRoot.hidden = !active;
        if (!active) {
          empty.hidden = true;
          if (summary) summary.innerHTML = `<strong>${defaultLibrary.querySelectorAll('#default-results .post-card').length}</strong> 篇当页文章 <span>·</span> 按最近更新排序`;
          return;
        }
      }
      if (!active && document.querySelector('[data-search-page]')) {
        resultRoot.innerHTML = '';
        empty.hidden = true;
        if (summary) summary.textContent = '输入关键词开始搜索';
        return;
      }
      try {
        const data = await ensureIndex();
        const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
        const matches = data.filter((item) => {
          if (activeTopic && item.topic !== activeTopic) return false;
          if (series && item.series !== series) return false;
          if (!terms.length) return true;
          const haystack = `${item.title} ${item.description} ${item.content}`.toLowerCase();
          return terms.every((term) => haystack.includes(term));
        });
        render(matches, query);
        const params = new URLSearchParams();
        if (query) params.set('q', query);
        if (activeTopic) params.set('topic', activeTopic);
        if (series) params.set('series', series);
        history.replaceState(null, '', window.location.pathname + (params.toString() ? '?' + params : ''));
      } catch (_) {
        empty.hidden = false;
        empty.querySelector('strong').textContent = '搜索索引暂时不可用';
      }
    };

    input.addEventListener('input', () => { clearTimeout(debounce); debounce = setTimeout(search, 120); });
    topicButtons.forEach((button) => button.addEventListener('click', () => {
      topicButtons.forEach((item) => item.classList.remove('active'));
      button.classList.add('active');
      activeTopic = button.dataset.topic;
      search();
    }));
    if (seriesSelect) seriesSelect.addEventListener('change', search);

    const params = new URLSearchParams(window.location.search);
    input.value = params.get('q') || '';
    activeTopic = params.get('topic') || '';
    topicButtons.forEach((button) => button.classList.toggle('active', button.dataset.topic === activeTopic));
    if (!topicButtons.some((button) => button.classList.contains('active'))) topicButtons[0].classList.add('active');
    if (seriesSelect) seriesSelect.value = params.get('series') || '';
    search();
  }

  document.addEventListener('keydown', (event) => {
    const target = event.target;
    const typing = target && (/^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName) || target.isContentEditable);
    if ((event.key === '/' && !typing) || ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k')) {
      event.preventDefault();
      const localInput = document.querySelector('[data-search-root] input[type="search"]');
      if (localInput) localInput.focus(); else window.location.href = document.querySelector('.search-trigger').href;
    }
  });
})();
