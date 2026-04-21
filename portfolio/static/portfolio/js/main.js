// Navbar scroll effect
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
    navbar.classList.toggle('scrolled', window.scrollY > 8);
});

// Active nav link tracking
const sections = document.querySelectorAll('.section, section');
const allNavLinks = document.querySelectorAll('.nav-links .nav-link, .nav-links .nav-dropdown-item');

function updateActiveLink() {
    let current = '';
    sections.forEach(section => {
        const top = section.offsetTop - 100;
        if (window.scrollY >= top) {
            current = section.getAttribute('id');
        }
    });
    // Clear all active states
    document.querySelectorAll('.nav-links .nav-link').forEach(l => l.classList.remove('active'));
    // Set active on matching link (direct or dropdown item)
    allNavLinks.forEach(link => {
        if (link.getAttribute('href') === '#' + current) {
            link.classList.add('active');
            // If inside a dropdown, also activate the parent
            const dropdown = link.closest('.nav-dropdown');
            if (dropdown) {
                dropdown.querySelector('.nav-link--dropdown').classList.add('active');
            }
        }
    });
}

window.addEventListener('scroll', updateActiveLink);
updateActiveLink();

// Mobile hamburger menu — see nav.html for the canonical handler. The
// earlier duplicate here bound to a stale `#mobile-menu` id and double-
// toggled the hamburger's `.active` class on every click, leaving the
// icon stuck as an X once the two listeners drifted out of sync.

// Scroll-triggered fade-in with IntersectionObserver
const fadeObserver = new IntersectionObserver(
    (entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                fadeObserver.unobserve(entry.target);
            }
        });
    },
    { threshold: 0.1, rootMargin: '0px 0px -40px 0px' }
);

document.querySelectorAll('.fade-in, .fade-in-group').forEach(el => {
    fadeObserver.observe(el);
});

// Smooth scroll for nav links (supplement CSS smooth scroll)
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth' });
        }
    });
});

// Show More / Show Less for projects
function toggleProjects() {
    const hidden = document.querySelectorAll('.project-hidden');
    const btn = document.getElementById('show-more-btn');
    const isShowing = btn.textContent.trim() === 'Show More Projects';

    hidden.forEach(card => {
        card.style.display = isShowing ? '' : 'none';
    });

    if (isShowing) {
        hidden.forEach(card => card.classList.remove('project-hidden'));
        btn.textContent = 'Show Less';
    } else {
        const grid = document.getElementById('project-grid');
        const cards = grid.querySelectorAll('.project-card');
        cards.forEach((card, i) => {
            if (i >= 6) {
                card.classList.add('project-hidden');
                card.style.display = 'none';
            }
        });
        btn.textContent = 'Show More Projects';
        document.getElementById('projects').scrollIntoView({ behavior: 'smooth' });
    }
}

// ── GitHub Star Counts ──
(function () {
    const starEls = document.querySelectorAll('.star-count[data-repo]');
    if (!starEls.length) return;

    // Collect unique repos
    const repos = [...new Set([...starEls].map(el => el.dataset.repo))];

    repos.forEach(repo => {
        // Check sessionStorage cache first
        const cached = sessionStorage.getItem('gh-stars-' + repo);
        if (cached !== null) {
            updateStars(repo, cached);
            return;
        }

        fetch('https://api.github.com/repos/' + repo, { headers: { Accept: 'application/vnd.github.v3+json' } })
            .then(r => r.ok ? r.json() : null)
            .then(data => {
                if (!data) return;
                const count = data.stargazers_count;
                sessionStorage.setItem('gh-stars-' + repo, count);
                updateStars(repo, count);
            })
            .catch(() => {});
    });

    function updateStars(repo, count) {
        document.querySelectorAll('.star-count[data-repo="' + repo + '"]').forEach(el => {
            el.textContent = Number(count) >= 1000 ? (Number(count) / 1000).toFixed(1) + 'k' : count;
        });
    }
})();

// ── Scroll Progress Bar ──
const scrollProgress = document.getElementById('scroll-progress');
window.addEventListener('scroll', () => {
    const scrollTop = window.scrollY;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const progress = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
    scrollProgress.style.width = progress + '%';
});

// Typing Animation removed — anti-pattern: forces reader to wait for
// content they could already see. Eye-tracking shows interaction delays
// >400ms cause disengagement; typewriter effects are 1-3s.

// ── Magnetic Hover + 3D Tilt — REMOVED 2026-04 ──
// The mousemove-driven magnetic translate on social icons and the
// perspective-rotate on .tilt-card both read as "Webflow template"
// in 2026. Replaced with CSS-only subtle hover lift (see
// animations.css `.tilt-card:hover` and components.css `.social-icon:hover`).
// Native CSS hover reads as more confident; JS mousemove handlers
// also burn the main thread and conflict with view-transitions.

// ── Cursor-aware accent spotlight on cards (Linear pattern) ──
// Sets --mx/--my as CSS pixel values inside the hovered card so the
// pseudo-element radial-gradient tracks the cursor. Cheap: only fires
// when actually hovering a .tilt-card; coalesces with rAF so we set
// at most once per frame. CSS in animations.css does the painting.
(function () {
    if (window.matchMedia('(hover: none)').matches) return;
    const cards = document.querySelectorAll('.tilt-card');
    if (!cards.length) return;
    let pending = null;
    cards.forEach(card => {
        card.addEventListener('pointermove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = ((e.clientX - rect.left) / rect.width) * 100;
            const y = ((e.clientY - rect.top) / rect.height) * 100;
            if (pending) cancelAnimationFrame(pending);
            pending = requestAnimationFrame(() => {
                card.style.setProperty('--mx', x + '%');
                card.style.setProperty('--my', y + '%');
                pending = null;
            });
        }, { passive: true });
        card.addEventListener('pointerleave', () => {
            card.style.removeProperty('--mx');
            card.style.removeProperty('--my');
        });
    });
})();

// ── Animated Timeline ──
(function () {
    const timeline = document.querySelector('.timeline');
    if (!timeline) return;

    // Animate the vertical line drawing
    const timelineObserver = new IntersectionObserver(
        (entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    timeline.classList.add('timeline-visible');
                    timelineObserver.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.1 }
    );
    timelineObserver.observe(timeline);

    // Animate individual dots
    const itemObserver = new IntersectionObserver(
        (entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('timeline-item-visible');
                    itemObserver.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.2, rootMargin: '0px 0px -50px 0px' }
    );

    document.querySelectorAll('.timeline-item').forEach(item => {
        itemObserver.observe(item);
    });
})();
