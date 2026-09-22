'use strict';

/* ============ PARTICULES (canvas) ============ */
const canvas = document.getElementById('particles');
const ctx = canvas.getContext('2d');
let particles = [];
const COLORS = ['#8b5cf6', '#22d3ee', '#ec4899'];

function resizeCanvas() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
}

function createParticles() {
  const count = Math.min(90, Math.floor(window.innerWidth / 14));
  particles = Array.from({ length: count }, () => ({
    x: Math.random() * canvas.width,
    y: Math.random() * canvas.height,
    r: Math.random() * 2 + 0.5,
    vx: (Math.random() - 0.5) * 0.35,
    vy: (Math.random() - 0.5) * 0.35,
    color: COLORS[Math.floor(Math.random() * COLORS.length)],
    alpha: Math.random() * 0.5 + 0.2
  }));
}

function drawParticles() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  particles.forEach((p, i) => {
    p.x += p.vx;
    p.y += p.vy;
    if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
    if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    ctx.fillStyle = p.color;
    ctx.globalAlpha = p.alpha;
    ctx.fill();

    for (let j = i + 1; j < particles.length; j++) {
      const q = particles[j];
      const dx = p.x - q.x;
      const dy = p.y - q.y;
      const dist = Math.hypot(dx, dy);
      if (dist < 120) {
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(q.x, q.y);
        ctx.strokeStyle = p.color;
        ctx.globalAlpha = (1 - dist / 120) * 0.15;
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    }
  });
  ctx.globalAlpha = 1;
  requestAnimationFrame(drawParticles);
}

resizeCanvas();
createParticles();
drawParticles();
window.addEventListener('resize', () => {
  resizeCanvas();
  createParticles();
});

/* ============ NAVIGATION : scrolled + mobile ============ */
const nav = document.querySelector('.nav');
const burger = document.getElementById('burger');
const navLinks = document.getElementById('nav-links');

window.addEventListener('scroll', () => {
  nav.classList.toggle('scrolled', window.scrollY > 40);
});

burger.addEventListener('click', () => {
  burger.classList.toggle('open');
  navLinks.classList.toggle('open');
});

navLinks.querySelectorAll('.nav-link').forEach((link) => {
  link.addEventListener('click', () => {
    burger.classList.remove('open');
    navLinks.classList.remove('open');
  });
});

/* ============ LIEN ACTIF AU SCROLL ============ */
const sections = document.querySelectorAll('section[id]');
const linkMap = new Map(
  [...navLinks.querySelectorAll('.nav-link')].map((l) => [l.getAttribute('href').slice(1), l])
);

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        navLinks.querySelectorAll('.nav-link').forEach((l) => l.classList.remove('active'));
        linkMap.get(entry.target.id)?.classList.add('active');
      }
    });
  },
  { rootMargin: '-45% 0px -45% 0px' }
);
sections.forEach((s) => observer.observe(s));

/* ============ BARRE DE PROGRESSION ============ */
const progressBar = document.getElementById('scroll-progress');
window.addEventListener('scroll', () => {
  const max = document.documentElement.scrollHeight - window.innerHeight;
  progressBar.style.width = `${(window.scrollY / max) * 100}%`;
});

/* ============ TEXTE TAPÉ (effet machine à écrire) ============ */
const typedEl = document.querySelector('.typed');
const roles = [
  'Ingénieur DevSecOps',
  'Architecte Microservices',
  'Spécialiste Cybersécurité',
  'Ingénieur Réseaux & Télécoms',
  'Docker · Kubernetes · Python'
];
let roleIndex = 0;
let charIndex = 0;
let deleting = false;

function typeLoop() {
  const current = roles[roleIndex];
  if (deleting) {
    charIndex--;
  } else {
    charIndex++;
  }
  typedEl.textContent = current.slice(0, charIndex);
  let delay = deleting ? 40 : 80;
  if (!deleting && charIndex === current.length) {
    delay = 1800;
    deleting = true;
  } else if (deleting && charIndex === 0) {
    deleting = false;
    roleIndex = (roleIndex + 1) % roles.length;
    delay = 400;
  }
  setTimeout(typeLoop, delay);
}
typeLoop();

/* ============ COMPTEURS (stats) ============ */
const statObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      const el = entry.target;
      const target = Number(el.dataset.count);
      let current = 0;
      const step = Math.max(1, Math.ceil(target / 50));
      const tick = () => {
        current += step;
        if (current >= target) {
          el.textContent = target;
          return;
        }
        el.textContent = current;
        setTimeout(tick, 28);
      };
      tick();
      statObserver.unobserve(el);
    });
  },
  { threshold: 0.5 }
);
document.querySelectorAll('.stat-num').forEach((el) => statObserver.observe(el));

/* ============ RÉVÉLATION AU SCROLL ============ */
const revealObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        revealObserver.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.12 }
);
document.querySelectorAll('.reveal').forEach((el) => revealObserver.observe(el));

/* ============ BARRES DE COMPÉTENCES ============ */
const skillObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.querySelectorAll('.skill-fill').forEach((fill, index) => {
          setTimeout(() => {
            fill.style.width = fill.dataset.width;
          }, index * 150);
        });
        skillObserver.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.3 }
);
document.querySelectorAll('.skill-card').forEach((card) => skillObserver.observe(card));

/* ============ FORMULAIRE CONTACT ============ */
const form = document.getElementById('contact-form');
const statusEl = document.getElementById('form-status');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const nom = form.nom.value.trim();
  const email = form.email.value.trim();
  const message = form.message.value.trim();

  if (!nom || !email || !message) {
    statusEl.textContent = 'Merci de remplir tous les champs.';
    statusEl.className = 'form-status err';
    return;
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    statusEl.textContent = 'Adresse email invalide.';
    statusEl.className = 'form-status err';
    return;
  }

  statusEl.textContent = 'Envoi en cours...';
  statusEl.className = 'form-status';

  try {
    const res = await fetch('/api/contact', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nom, email, message })
    });
    const data = await res.json();
    if (data.success) {
      statusEl.textContent = 'Merci ' + nom + ' ! Votre message a bien été envoyé.';
      statusEl.className = 'form-status ok';
      form.reset();
    } else {
      statusEl.textContent = data.error || 'Erreur lors de l\'envoi.';
      statusEl.className = 'form-status err';
    }
  } catch {
    statusEl.textContent = 'Erreur réseau. Réessayez plus tard.';
    statusEl.className = 'form-status err';
  }
});

/* ============ ANNÉE DU FOOTER ============ */
document.getElementById('year').textContent = new Date().getFullYear();

/* ============ CV MODAL (instantané, données injectées par le serveur) ============ */
const cvModal = new bootstrap.Modal(document.getElementById('cvModal'));
const viewCVBtn = document.getElementById('view-cv-btn');
viewCVBtn.addEventListener('click', () => {
  cvModal.show();
  loadCV();
});

const cvIframe = document.getElementById('cv-iframe');
const cvImage = document.getElementById('cv-image');
const cvImageWrap = document.getElementById('cv-image-wrap');
const cvEmpty = document.getElementById('cv-empty');

function loadCV() {
  const url = viewCVBtn.dataset.cvUrl;
  let name = (viewCVBtn.dataset.cvName || '').toLowerCase();

  cvIframe.style.display = 'none';
  cvImageWrap.style.display = 'none';

  if (!url) {
    cvEmpty.style.display = 'flex';
    return;
  }

  if (name.endsWith('.pdf')) {
    cvIframe.src = url + '#toolbar=0&navpanes=0&scrollbar=0';
    cvIframe.style.display = 'block';
  } else if (/\.(jpe?g|png|gif|webp|svg)$/.test(name)) {
    cvEmpty.style.display = 'none';
    cvImage.src = url;
    cvImageWrap.style.display = 'block';
    return;
  } else {
    cvEmpty.style.display = 'flex';
  }
}

/* ============ CERTIFICATIONS GRID (instantané, données injectées par le serveur) ============ */
const certsGrid = document.getElementById('certs-grid');
const certModal = new bootstrap.Modal(document.getElementById('certModal'));
const certIframe = document.getElementById('cert-iframe');
const certImage = document.getElementById('cert-image');
const certImageWrap = document.getElementById('cert-image-wrap');
const certEmpty = document.getElementById('cert-empty');
const certModalTitle = document.getElementById('certModalTitle');

async function fetchCertifications() {
  const res = await fetch('/api/certifications', { cache: 'no-store' });
  return res.json();
}

async function loadCertsGrid(certifications, silent) {
  certsGrid.innerHTML = '';
  if (!certifications) {
    certifications = await fetchCertifications();
  }

  const obtained = certifications.filter(c => c.status === 'obtenue');

  if (obtained.length === 0) {
    certsGrid.innerHTML = '<div class="col-12 text-center text-muted py-4"><p>Aucune certification uploadée pour le moment.</p></div>';
    return;
  }

  let index = 0;

  obtained.forEach((cert) => {
    const hasFile = !!(cert.file_url);
    const isPdf = hasFile ? cert.file_url.toLowerCase().endsWith('.pdf') : false;
    const urlStamp = hasFile ? (cert.file_url_v || cert.file_url) : '';
    const cardClass = silent ? 'cert-dynamic-card reveal visible' : 'cert-dynamic-card reveal';

    const col = document.createElement('div');
    col.className = 'col-md-6 col-lg-4';
    col.innerHTML = `
      <article class="${cardClass}" style="animation-delay: ${index * 0.1}s" data-file-url="${hasFile ? escapeHtml(urlStamp) : ''}" data-file-title="${escapeHtml(cert.title)}">
        <div class="cert-visual">
          ${hasFile
            ? isPdf
              ? '<div class="cert-preview-placeholder"><span class="cert-preview-icon">📄</span><span class="cert-preview-label">PDF</span></div>'
              : `<img src="${urlStamp}" alt="${escapeHtml(cert.title)}" />`
            : '<div class="cert-preview-placeholder"><span class="cert-preview-icon">🏆</span><span class="cert-preview-label">Obtenue</span></div>'
          }
          ${hasFile ? '<div class="cert-overlay"><span class="btn btn-primary btn-small cert-view-btn">Voir le certificat</span></div>' : ''}
        </div>
        <div class="cert-info-bar">
          <h4>${escapeHtml(cert.title)}</h4>
          <span class="cert-type-badge">${hasFile ? (isPdf ? 'PDF' : 'Image') : 'Obtenue'}</span>
        </div>
      </article>
    `;

    certsGrid.appendChild(col);
    index++;
  });

  if (!silent) {
    document.querySelectorAll('.cert-dynamic-card.reveal').forEach(el => revealObserver.observe(el));
  }
}

/* ============ CERTIFICATIONS EN COURS (dynamique) ============ */
const certsProgressGrid = document.getElementById('certs-progress-grid');

async function loadCertsProgress(certifications, silent) {
  if (!certifications) {
    certifications = await fetchCertifications();
  }
  certsProgressGrid.innerHTML = '';

  const inProgress = certifications.filter(c => c.status === 'en_cours');

  if (inProgress.length === 0) {
    certsProgressGrid.innerHTML = '<div class="col-12 text-center text-muted py-3"><p>Aucune certification en cours pour le moment.</p></div>';
    return;
  }

  inProgress.forEach((cert, index) => {
    const cardClass = silent ? 'cert-progress-card reveal visible' : 'cert-progress-card reveal';
    const col = document.createElement('div');
    col.className = 'col-md-6 col-lg-4';
    col.innerHTML = `
      <article class="${cardClass}" style="animation-delay: ${index * 0.1}s">
        <div class="cert-progress-icon">⏳</div>
        <div class="cert-progress-body">
          <h4>${escapeHtml(cert.title)}</h4>
          <p>${escapeHtml(cert.description)}</p>
          <span class="cert-progress-status">En cours</span>
        </div>
      </article>
    `;
    certsProgressGrid.appendChild(col);
  });

  if (!silent) {
    document.querySelectorAll('.cert-progress-card.reveal').forEach(el => revealObserver.observe(el));
  }
}

function openCertModal(file, displayName) {
  const name = (file.filename || '').toLowerCase();
  const isPdf = name.endsWith('.pdf');
  const isImage = /\.(jpe?g|png|gif|webp|svg)$/.test(name);
  certModalTitle.textContent = displayName;

  certIframe.style.display = 'none';
  certImageWrap.style.display = 'none';
  certEmpty.style.display = 'none';

  if (isPdf) {
    certIframe.src = file.url + '#toolbar=0&navpanes=0&scrollbar=0';
    certIframe.style.display = 'block';
  } else if (isImage) {
    certImage.src = file.url;
    certImageWrap.style.display = 'block';
  } else {
    certEmpty.style.display = 'flex';
  }

  certModal.show();
}

/* Clics sur les cartes (les cartes servies par le serveur portent déjà les données) */
certsGrid.addEventListener('click', (e) => {
  const card = e.target.closest('.cert-dynamic-card');
  if (!card || !card.dataset.fileUrl) return;
  const title = card.dataset.fileTitle || 'Certification';
  const filename = card.dataset.fileUrl.split('?')[0].split('/').pop();
  openCertModal({ filename, url: card.dataset.fileUrl, original_name: title }, title);
});

const certsDataEl = document.getElementById('certs-data');
let certsCacheKey = '';
if (certsDataEl && certsDataEl.textContent.trim()) {
  try {
    certsCacheKey = JSON.stringify(JSON.parse(certsDataEl.textContent));
  } catch (e) {}
}

async function autoRefreshCerts() {
  try {
    const data = await fetchCertifications();
    const key = JSON.stringify(data);
    if (key === certsCacheKey) return;
    certsCacheKey = key;
    await Promise.all([loadCertsGrid(data, true), loadCertsProgress(data, true)]);
  } catch (e) {}
}

setInterval(autoRefreshCerts, 25000);
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) autoRefreshCerts();
});
window.addEventListener('focus', autoRefreshCerts);

/* ============ REALISATIONS (dynamique) ============ */
const realisationsGrid = document.getElementById('realisations-grid');

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str == null ? '' : String(str);
  return div.innerHTML;
}

async function loadRealisations() {
  const res = await fetch('/api/realisations');
  const items = await res.json();
  realisationsGrid.innerHTML = '';

  if (items.length === 0) {
    realisationsGrid.innerHTML = '<div class="col-12 text-center text-muted py-4"><p>Aucune réalisation pour le moment.</p></div>';
    return;
  }

  items.forEach((rel, index) => {
    const tags = (rel.tags || '').split(',').map((t) => t.trim()).filter(Boolean);
    const tagsHtml = tags.length
      ? `<div class="project-tags">${tags.map((t) => `<span>${escapeHtml(t)}</span>`).join('')}</div>`
      : '';
    const overlayLinks =
      (rel.code_url || rel.demo_url) && (rel.code_url || rel.demo_url).trim()
        ? `
          <div class="project-overlay">
            ${rel.code_url ? `<a href="${escapeHtml(rel.code_url)}" target="_blank" rel="noopener" class="btn btn-ghost btn-small">Code source ↗</a>` : ''}
            ${rel.demo_url ? `<a href="${escapeHtml(rel.demo_url)}" target="_blank" rel="noopener" class="btn btn-primary btn-small">Démo live ↗</a>` : ''}
          </div>`
        : '';
    const imgHtml = rel.image
      ? `<img src="${escapeHtml(rel.image)}?t=${Date.now()}" alt="${escapeHtml(rel.title)}" />`
      : '<div class="project-visual" style="display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,rgba(139,92,246,.15),rgba(34,211,238,.1));"><span style="font-size:2.5rem;">🚀</span></div>';

    const col = document.createElement('div');
    col.className = 'col-lg-4 col-md-6';
    col.innerHTML = `
      <article class="project-card reveal" style="animation-delay: ${index * 0.1}s">
        <div class="project-visual">
          ${imgHtml}
          ${overlayLinks}
        </div>
        <div class="project-info">
          <h3>${escapeHtml(rel.title)}</h3>
          <p>${escapeHtml(rel.description)}</p>
          ${tagsHtml}
        </div>
      </article>
    `;
    realisationsGrid.appendChild(col);
  });

  document.querySelectorAll('#realisations-grid .reveal').forEach((el) => revealObserver.observe(el));
}

/* ============ FORMATIONS (dynamique) ============ */
const formationsGrid = document.getElementById('formations-grid');

async function loadFormations() {
  if (formationsGrid.children.length > 0) return;
  const res = await fetch('/api/formations');
  const items = await res.json();
  formationsGrid.innerHTML = '';

  if (items.length === 0) {
    formationsGrid.innerHTML = '<div class="col-12 text-center text-muted py-3"><p>Aucune formation pour le moment.</p></div>';
    return;
  }

  items.forEach((form, index) => {
    const isEnCours = form.status === 'en_cours';
    const tagText = isEnCours ? '🎓 En cours' : '✅ Terminée';
    const institution = (form.institution || '').trim();
    const col = document.createElement('div');
    col.className = 'col-md-6';
    col.innerHTML = `
      <div class="formation-card reveal" style="animation-delay: ${index * 0.1}s">
        <span class="formation-tag">${tagText}</span>
        <h3>${escapeHtml(form.title)}</h3>
        <p>${institution ? `<strong>${escapeHtml(institution)}</strong><br>` : ''}${escapeHtml(form.description)}</p>
      </div>
    `;
    formationsGrid.appendChild(col);
  });

  document.querySelectorAll('#formations-grid .reveal').forEach((el) => revealObserver.observe(el));
}

loadRealisations();
loadFormations();

/* ============ PRÉCHARGEMENT CV + CERTIFICATS (affichage instantané) ============ */
function preloadFile(url) {
  if (!url) return;
  if (/\.(jpe?g|png|gif|webp|svg)$/i.test(url.split('?')[0])) {
    const img = new Image();
    img.src = url;
    return;
  }
  fetch(url, { cache: 'default', priority: 'low', mode: 'same-origin' }).catch(() => {});
}

function preloadDocs() {
  preloadFile(viewCVBtn.dataset.cvUrl || '');

  document.querySelectorAll('.cert-dynamic-card[data-file-url]').forEach((card) => {
    preloadFile(card.dataset.fileUrl);
  });
}

if (document.readyState === 'complete') {
  preloadDocs();
} else {
  window.addEventListener('load', preloadDocs);
}