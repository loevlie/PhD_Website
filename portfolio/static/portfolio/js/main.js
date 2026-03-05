// Navbar scroll effect
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
    navbar.classList.toggle('scrolled', window.scrollY > 20);
});

// Active nav link tracking
const sections = document.querySelectorAll('.section, section');
const navLinks = document.querySelectorAll('.nav-links .nav-link');

function updateActiveLink() {
    let current = '';
    sections.forEach(section => {
        const top = section.offsetTop - 100;
        if (window.scrollY >= top) {
            current = section.getAttribute('id');
        }
    });
    navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === '#' + current) {
            link.classList.add('active');
        }
    });
}

window.addEventListener('scroll', updateActiveLink);
updateActiveLink();

// Mobile hamburger menu
const hamburger = document.getElementById('hamburger');
const mobileMenu = document.getElementById('mobile-menu');

hamburger.addEventListener('click', () => {
    hamburger.classList.toggle('active');
    mobileMenu.classList.toggle('open');
    document.body.style.overflow = mobileMenu.classList.contains('open') ? 'hidden' : '';
});

document.querySelectorAll('.mobile-nav-link').forEach(link => {
    link.addEventListener('click', () => {
        hamburger.classList.remove('active');
        mobileMenu.classList.remove('open');
        document.body.style.overflow = '';
    });
});

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

// ── Scroll Progress Bar ──
const scrollProgress = document.getElementById('scroll-progress');
window.addEventListener('scroll', () => {
    const scrollTop = window.scrollY;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const progress = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
    scrollProgress.style.width = progress + '%';
});

// ── Typing Animation ──
(function () {
    const el = document.getElementById('typing-target');
    if (!el) return;
    const text = el.getAttribute('data-text');
    // Decode HTML entities
    const tmp = document.createElement('span');
    tmp.innerHTML = text;
    const decoded = tmp.textContent;
    let i = 0;
    function type() {
        if (i <= decoded.length) {
            el.textContent = decoded.slice(0, i);
            i++;
            setTimeout(type, 45);
        }
    }
    // Start after a short delay so page loads first
    setTimeout(type, 400);
})();

// ── Magnetic Hover on Social Icons ──
(function () {
    if ('ontouchstart' in window) return;
    document.querySelectorAll('.social-icon').forEach(icon => {
        icon.addEventListener('mousemove', (e) => {
            const rect = icon.getBoundingClientRect();
            const cx = rect.left + rect.width / 2;
            const cy = rect.top + rect.height / 2;
            const dx = (e.clientX - cx) * 0.3;
            const dy = (e.clientY - cy) * 0.3;
            icon.style.transform = `translate(${dx}px, ${dy}px)`;
        });
        icon.addEventListener('mouseleave', () => {
            icon.style.transform = '';
        });
    });
})();

// ── Card 3D Tilt on Hover ──
(function () {
    if ('ontouchstart' in window) return;
    document.querySelectorAll('.tilt-card').forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = (e.clientX - rect.left) / rect.width - 0.5;
            const y = (e.clientY - rect.top) / rect.height - 0.5;
            card.style.transform = `perspective(600px) rotateY(${x * 8}deg) rotateX(${-y * 8}deg) translateY(-4px)`;
        });
        card.addEventListener('mouseleave', () => {
            card.style.transform = '';
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
