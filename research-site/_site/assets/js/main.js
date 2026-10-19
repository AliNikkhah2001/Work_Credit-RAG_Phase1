// ==========================================================================
// Multi-Turn RAG Research - Main JavaScript
// ==========================================================================

(function() {
  'use strict';

  // ==========================================================================
  // Navigation Toggle
  // ==========================================================================
  const navToggle = document.querySelector('.nav-toggle');
  const navMenu = document.querySelector('.nav-list');
  const dropdowns = document.querySelectorAll('.has-dropdown');

  if (navToggle && navMenu) {
    navToggle.addEventListener('click', function() {
      const isOpen = navMenu.classList.toggle('open');
      navToggle.setAttribute('aria-expanded', isOpen);
      document.body.style.overflow = isOpen ? 'hidden' : '';
    });

    // Close menu on link click
    navMenu.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => {
        navMenu.classList.remove('open');
        navToggle.setAttribute('aria-expanded', 'false');
        document.body.style.overflow = '';
      });
    });

    // Close on outside click
    document.addEventListener('click', function(e) {
      if (!e.target.closest('.main-nav')) {
        navMenu.classList.remove('open');
        navToggle.setAttribute('aria-expanded', 'false');
        document.body.style.overflow = '';
      }
    });
  }

  // Dropdown toggles for mobile
  dropdowns.forEach(dropdown => {
    const link = dropdown.querySelector('a');
    link.addEventListener('click', function(e) {
      if (window.innerWidth <= 768) {
        e.preventDefault();
        dropdown.classList.toggle('open');
      }
    });
  });

  // ==========================================================================
  // Smooth Scroll for Anchor Links
  // ==========================================================================
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      const targetId = this.getAttribute('href');
      if (targetId === '#') return;
      const target = document.querySelector(targetId);
      if (target) {
        e.preventDefault();
        const headerOffset = 80;
        const elementPosition = target.getBoundingClientRect().top;
        const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
        window.scrollTo({ top: offsetPosition, behavior: 'smooth' });
      }
    });
  });

  // ==========================================================================
  // Mermaid Diagram Rendering
  // ==========================================================================
  function initMermaid() {
    if (typeof mermaid !== 'undefined') {
      mermaid.initialize({
        startOnLoad: true,
        theme: 'default',
        securityLevel: 'loose',
        flowchart: { 
          useMaxWidth: true, 
          htmlLabels: true,
          curve: 'basis'
        },
        themeVariables: {
          primaryColor: '#2563eb',
          primaryTextColor: '#1e293b',
          primaryBorderColor: '#3b82f6',
          lineColor: '#64748b',
          secondaryColor: '#0ea5e9',
          tertiaryColor: '#f1f5f9'
        }
      });
      
      // Re-render on dynamic content
      const observer = new MutationObserver(() => {
        document.querySelectorAll('.mermaid:not(.mermaid-rendered)').forEach(el => {
          el.classList.add('mermaid-rendered');
        });
      });
      observer.observe(document.body, { childList: true, subtree: true });
    }
  }

  // ==========================================================================
  // Table of Contents Generation
  // ==========================================================================
  function generateTOC() {
    const tocContainer = document.querySelector('.toc-container');
    if (!tocContainer) return;
    
    const headings = document.querySelectorAll('.site-main h2, .site-main h3');
    if (headings.length < 2) return;
    
    let tocHtml = '<nav class="toc" aria-label="Table of Contents"><h4>On this page</h4><ul>';
    let currentLevel = 2;
    
    headings.forEach((heading, index) => {
      const level = parseInt(heading.tagName.charAt(1));
      const id = heading.id || `heading-${index}`;
      if (!heading.id) heading.id = id;
      
      if (level > currentLevel) {
        tocHtml += '<ul>';
      } else if (level < currentLevel) {
        tocHtml += '</ul>'.repeat(currentLevel - level);
      }
      currentLevel = level;
      
      const indent = level === 2 ? '' : '  ';
      tocHtml += `${indent}<li><a href="#${id}">${heading.textContent}</a></li>`;
    });
    
    tocHtml += '</ul></ul></nav>';
    tocContainer.innerHTML = tocHtml;
  }

  // ==========================================================================
  // Copy Code Button
  // ==========================================================================
  function addCopyButtons() {
    document.querySelectorAll('pre').forEach(pre => {
      if (pre.querySelector('.copy-btn')) return;
      
      const btn = document.createElement('button');
      btn.className = 'copy-btn';
      btn.textContent = 'Copy';
      btn.setAttribute('aria-label', 'Copy code to clipboard');
      btn.style.cssText = `
        position: absolute;
        top: 8px;
        right: 8px;
        padding: 4px 8px;
        font-size: 0.75rem;
        background: #334155;
        color: #e2e8f0;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        opacity: 0;
        transition: opacity 0.2s;
      `;
      
      pre.style.position = 'relative';
      pre.appendChild(btn);
      
      pre.addEventListener('mouseenter', () => btn.style.opacity = '1');
      pre.addEventListener('mouseleave', () => btn.style.opacity = '0');
      
      btn.addEventListener('click', async () => {
        const code = pre.querySelector('code').textContent;
        try {
          await navigator.clipboard.writeText(code);
          btn.textContent = 'Copied!';
          btn.style.background = '#10b981';
          setTimeout(() => {
            btn.textContent = 'Copy';
            btn.style.background = '';
          }, 2000);
        } catch (err) {
          btn.textContent = 'Failed';
          setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
        }
      });
    });
  }

  // ==========================================================================
  // Active Navigation Highlighting
  // ==========================================================================
  function highlightActiveNav() {
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-list > li > a').forEach(link => {
      const href = link.getAttribute('href');
      if (href && currentPath.startsWith(href.replace('.html', '')) && href !== '/') {
        link.classList.add('active');
      } else if (href === '/' && (currentPath === '/' || currentPath === '/index.html')) {
        link.classList.add('active');
      }
    });
  }

  // ==========================================================================
  // Mermaid Resize Handler
  // ==========================================================================
  function handleMermaidResize() {
    let resizeTimeout;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(() => {
        if (typeof mermaid !== 'undefined') {
          document.querySelectorAll('.mermaid').forEach(el => {
            el.innerHTML = '';
            el.classList.remove('mermaid-rendered');
          });
          mermaid.init(undefined, document.querySelectorAll('.mermaid'));
        }
      }, 250);
    });
  }

  // ==========================================================================
  // Initialize on DOM Ready
  // ==========================================================================
  document.addEventListener('DOMContentLoaded', function() {
    initMermaid();
    generateTOC();
    addCopyButtons();
    highlightActiveNav();
    handleMermaidResize();
    
    // Add mermaid-rendered class to already rendered diagrams
    document.querySelectorAll('.mermaid').forEach(el => {
      if (el.querySelector('svg')) el.classList.add('mermaid-rendered');
    });
    
    console.log('Multi-Turn RAG Research site initialized');
  });

})();