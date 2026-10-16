/**
 * Campus Facility Maintenance — Phase 4 Frontend Application Logic
 * Visual Language: MongoDB Atlas Developer Dashboard & Docs
 * Connects directly to authoritative FastAPI backend and locked Phase 3 services.
 */

'use strict';

const API_BASE = '/api';

// Application State
const state = {
  currentUser: null,
  currentView: 'dashboard',
  lookups: null,
  stats: {},
  requests: [],
  assignments: [],
  workLogs: [],
  materials: [],
  costs: [],
  currentReport: 'pending-requests',
  demoAccounts: [],
  demoRoleFilter: 'all',
  demoSearchQuery: '',
  demoViewMode: 'cards',
};

// Utilities
function showToast(message, isError = false) {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast ${isError ? 'toast-error' : ''}`;
  toast.innerHTML = `<span>${isError ? '✗' : '✓'}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 200);
  }, 4000);
}

function formatCurrency(amount) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(amount);
}

function formatDate(isoStr) {
  if (!isoStr) return '—';
  const d = new Date(isoStr);
  return d.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getStatusTagClass(statusName) {
  switch (statusName) {
    case 'Open': return 'tag-status-open';
    case 'Assigned': return 'tag-status-assigned';
    case 'In Progress': return 'tag-status-in-progress';
    case 'On Hold': return 'tag-status-on-hold';
    case 'Closed': return 'tag-status-closed';
    default: return 'tag-category';
  }
}

function getPriorityTagClass(priorityLevel) {
  switch (priorityLevel) {
    case 'Critical': return 'tag-priority-critical';
    case 'High': return 'tag-priority-high';
    case 'Medium': return 'tag-priority-medium';
    case 'Low': return 'tag-priority-low';
    default: return 'tag-category';
  }
}

// API Calls
async function apiGet(endpoint) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ message: res.statusText }));
      throw new Error(err.message || 'API request failed');
    }
    return await res.json();
  } catch (err) {
    showToast(err.message, true);
    throw err;
  }
}

async function apiPost(endpoint, body) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ message: res.statusText }));
      throw new Error(err.message || 'API operation failed');
    }
    return await res.json();
  } catch (err) {
    showToast(err.message, true);
    throw err;
  }
}

async function apiPatch(endpoint, body) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ message: res.statusText }));
      throw new Error(err.message || 'API operation failed');
    }
    return await res.json();
  } catch (err) {
    showToast(err.message, true);
    throw err;
  }
}

// Demo Authentication, Registration & Role Identity
function switchAuthTab(tab) {
  const signinTab = document.getElementById('tab-auth-signin');
  const registerTab = document.getElementById('tab-auth-register');
  const signinPane = document.getElementById('auth-signin-pane');
  const registerPane = document.getElementById('auth-register-pane');
  const errBanner = document.getElementById('login-error-banner');

  if (errBanner) errBanner.style.display = 'none';

  if (tab === 'register') {
    if (signinTab) {
      signinTab.style.borderBottom = '2px solid transparent';
      signinTab.style.color = 'var(--text-muted)';
    }
    if (registerTab) {
      registerTab.style.borderBottom = '2px solid var(--accent-green)';
      registerTab.style.color = 'var(--text-primary)';
    }
    if (signinPane) signinPane.style.display = 'none';
    if (registerPane) registerPane.style.display = 'block';
  } else {
    if (signinTab) {
      signinTab.style.borderBottom = '2px solid var(--accent-green)';
      signinTab.style.color = 'var(--text-primary)';
    }
    if (registerTab) {
      registerTab.style.borderBottom = '2px solid transparent';
      registerTab.style.color = 'var(--text-muted)';
    }
    if (signinPane) signinPane.style.display = 'block';
    if (registerPane) registerPane.style.display = 'none';
  }
}

// All 14 Authoritative Demo Profiles
const FALLBACK_DEMO_PROFILES = [
  // Admin (1 Profile)
  { id: 7, name: 'Col. Rajesh Nair (Retd)', email: 'rajesh.nair@campus.edu', role: 'Facility Manager', portal_role: 'admin' },
  // Requesters (7 Community Profiles)
  { id: 1, name: 'Dr. Ramesh Sundaram', email: 'ramesh.sundaram@campus.edu', role: 'Faculty', portal_role: 'requester' },
  { id: 2, name: 'Prof. Ananya Sen', email: 'ananya.sen@campus.edu', role: 'Faculty', portal_role: 'requester' },
  { id: 3, name: 'Vikramaditya Roy', email: 'vikram.roy@campus.edu', role: 'Student', portal_role: 'requester' },
  { id: 4, name: 'Priya Sharma', email: 'priya.sharma@campus.edu', role: 'Student', portal_role: 'requester' },
  { id: 5, name: 'Manohar Lal (Lab Tech)', email: 'manohar.lal@campus.edu', role: 'Staff', portal_role: 'requester' },
  { id: 6, name: 'Sunita Kulkarni (Warden)', email: 'sunita.k@campus.edu', role: 'Staff', portal_role: 'requester' },
  { id: 8, name: 'Amitav Ghosh', email: 'amitav.ghosh@campus.edu', role: 'Student', portal_role: 'requester' },
  // Technicians (6 Operational Disciplines)
  { id: 1, name: 'Mahesh Chandra', email: 'mahesh.tech@campus.edu', department: 'Electrical Maintenance', role: 'Technician (Electrical Maintenance)', portal_role: 'technician' },
  { id: 2, name: 'Dinesh Kumar Verma', email: 'dinesh.tech@campus.edu', department: 'Plumbing & Hydraulics', role: 'Technician (Plumbing & Hydraulics)', portal_role: 'technician' },
  { id: 3, name: 'Gurpreet Singh', email: 'gurpreet.tech@campus.edu', department: 'HVAC & Refrigeration', role: 'Technician (HVAC & Refrigeration)', portal_role: 'technician' },
  { id: 4, name: 'Arunachalam P.', email: 'arun.tech@campus.edu', department: 'Civil & Carpentry', role: 'Technician (Civil & Carpentry)', portal_role: 'technician' },
  { id: 5, name: 'Nadeem Akhtar', email: 'nadeem.tech@campus.edu', department: 'Network Infrastructure', role: 'Technician (Network Infrastructure)', portal_role: 'technician' },
  { id: 6, name: 'Suresh Patil', email: 'suresh.tech@campus.edu', department: 'Laboratory Utilities', role: 'Technician (Laboratory Utilities)', portal_role: 'technician' },
];

function getDemoProfileMeta(account) {
  if (account.portal_role === 'admin') {
    return {
      type: 'Admin',
      badgeClass: 'badge-admin',
      badgeLabel: 'Admin',
      icon: '🛡️',
      subtext: 'Facility Manager (Admin)',
    };
  }
  if (account.portal_role === 'technician') {
    const dept = account.department || account.role || '';
    let badgeClass = 'badge-tech-electrical';
    let badgeLabel = 'Electrical';
    let icon = '⚡';
    if (dept.includes('Electrical')) {
      badgeClass = 'badge-tech-electrical';
      badgeLabel = 'Electrical';
      icon = '⚡';
    } else if (dept.includes('Plumbing')) {
      badgeClass = 'badge-tech-plumbing';
      badgeLabel = 'Plumbing';
      icon = '🚰';
    } else if (dept.includes('HVAC')) {
      badgeClass = 'badge-tech-hvac';
      badgeLabel = 'HVAC';
      icon = '❄️';
    } else if (dept.includes('Civil') || dept.includes('Carpentry')) {
      badgeClass = 'badge-tech-civil';
      badgeLabel = 'Civil';
      icon = '🪵';
    } else if (dept.includes('Network')) {
      badgeClass = 'badge-tech-network';
      badgeLabel = 'Network';
      icon = '🌐';
    } else if (dept.includes('Laboratory')) {
      badgeClass = 'badge-tech-lab';
      badgeLabel = 'Lab Utils';
      icon = '🔬';
    }
    return {
      type: 'Technician',
      badgeClass,
      badgeLabel,
      icon,
      subtext: account.department || account.role || 'Technician',
    };
  }
  // Requester
  let badgeClass = 'badge-student';
  let icon = '🎒';
  if (account.role === 'Faculty') {
    badgeClass = 'badge-faculty';
    icon = '🎓';
  } else if (account.role === 'Staff') {
    badgeClass = 'badge-staff';
    icon = '🏢';
  }
  return {
    type: 'Requester',
    badgeClass,
    badgeLabel: account.role || 'Requester',
    icon,
    subtext: account.role || 'Requester',
  };
}

function setDemoViewMode(mode) {
  state.demoViewMode = mode;
  try {
    localStorage.setItem('facility_demo_view_mode', mode);
  } catch (e) {}

  const btnCards = document.getElementById('toggle-view-cards');
  const btnPills = document.getElementById('toggle-view-pills');
  if (btnCards) btnCards.classList.toggle('active', mode === 'cards');
  if (btnPills) btnPills.classList.toggle('active', mode === 'pills');

  renderDemoProfileButtons();
}

function filterDemoRole(role) {
  state.demoRoleFilter = role;
  const chips = document.querySelectorAll('.demo-filter-chip');
  chips.forEach((c) => {
    c.classList.toggle('active', c.getAttribute('data-filter') === role);
  });
  renderDemoProfileButtons();
}

function filterDemoProfilesSearch(query) {
  state.demoSearchQuery = (query || '').trim().toLowerCase();
  const clearBtn = document.getElementById('demo-search-clear');
  if (clearBtn) {
    clearBtn.style.display = state.demoSearchQuery ? 'block' : 'none';
  }
  renderDemoProfileButtons();
}

function clearDemoSearch() {
  const searchInput = document.getElementById('demo-search-input');
  if (searchInput) searchInput.value = '';
  filterDemoProfilesSearch('');
}

function renderProfileButton(a, isPill) {
  const meta = getDemoProfileMeta(a);
  if (isPill) {
    return `
      <button type="button" class="btn-profile-pill" onclick="quickLogin('${a.email}')" title="Sign in as ${a.name} (${a.email}) • No password">
        <span class="micro-role-badge ${meta.badgeClass}">${meta.icon} ${meta.badgeLabel}</span>
        <span class="pill-name">${a.name}</span>
        <span class="pill-arrow">→</span>
      </button>
    `;
  }
  return `
    <button type="button" class="btn-profile-small" onclick="quickLogin('${a.email}')" title="1-Click login as ${a.name} (${a.email}) • No password">
      <div class="btn-profile-top">
        <span class="micro-role-badge ${meta.badgeClass}">${meta.icon} ${meta.badgeLabel}</span>
        <span class="profile-arrow">→</span>
      </div>
      <div class="profile-name">${a.name}</div>
      <div class="profile-email">${a.email}</div>
    </button>
  `;
}

function renderDemoProfileButtons() {
  const container = document.getElementById('demo-profiles-container');
  if (!container) return;

  const accounts = (state.demoAccounts && state.demoAccounts.length > 0)
    ? state.demoAccounts
    : FALLBACK_DEMO_PROFILES;

  // Update counts
  const adminCount = accounts.filter(a => a.portal_role === 'admin').length;
  const reqCount = accounts.filter(a => a.portal_role === 'requester').length;
  const techCount = accounts.filter(a => a.portal_role === 'technician').length;

  const cntAll = document.getElementById('filter-cnt-all');
  const cntAdmin = document.getElementById('filter-cnt-admin');
  const cntReq = document.getElementById('filter-cnt-requester');
  const cntTech = document.getElementById('filter-cnt-technician');
  const badgeTotal = document.getElementById('demo-total-badge');

  if (cntAll) cntAll.textContent = accounts.length;
  if (cntAdmin) cntAdmin.textContent = adminCount;
  if (cntReq) cntReq.textContent = reqCount;
  if (cntTech) cntTech.textContent = techCount;
  if (badgeTotal) badgeTotal.textContent = `${accounts.length} profiles`;

  // Filter accounts
  let filtered = accounts;
  if (state.demoRoleFilter && state.demoRoleFilter !== 'all') {
    filtered = filtered.filter(a => a.portal_role === state.demoRoleFilter);
  }
  if (state.demoSearchQuery) {
    const q = state.demoSearchQuery;
    filtered = filtered.filter(a =>
      (a.name && a.name.toLowerCase().includes(q)) ||
      (a.email && a.email.toLowerCase().includes(q)) ||
      (a.role && a.role.toLowerCase().includes(q)) ||
      (a.department && a.department.toLowerCase().includes(q))
    );
  }

  if (filtered.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 20px 10px; color: var(--text-muted); font-size: 12px;">
        <div>No matching profiles found for "${state.demoSearchQuery}".</div>
        <button type="button" class="btn btn-secondary" onclick="clearDemoSearch()" style="margin-top: 8px; padding: 4px 10px; font-size: 11px;">
          Clear Search
        </button>
      </div>
    `;
    return;
  }

  const isPills = state.demoViewMode === 'pills';

  // If filtered by specific role or searching, render single section
  if (state.demoRoleFilter !== 'all' || state.demoSearchQuery) {
    container.innerHTML = `
      <div class="${isPills ? 'quick-btn-pills' : 'quick-btn-grid'}">
        ${filtered.map(a => renderProfileButton(a, isPills)).join('')}
      </div>
    `;
    return;
  }

  // Otherwise render grouped sections in the exact order: Admin, Requesters, Technicians
  const admins = filtered.filter(a => a.portal_role === 'admin');
  const requesters = filtered.filter(a => a.portal_role === 'requester').sort((a, b) => (a.id || 0) - (b.id || 0));
  const techs = filtered.filter(a => a.portal_role === 'technician').sort((a, b) => (a.id || 0) - (b.id || 0));

  let html = '';

  if (admins.length > 0) {
    html += `
      <div class="demo-group-heading">
        <span>🛡️ Admin & Facility Management (${admins.length})</span>
      </div>
      <div class="${isPills ? 'quick-btn-pills' : 'quick-btn-grid'}" style="margin-bottom: 8px;">
        ${admins.map(a => renderProfileButton(a, isPills)).join('')}
      </div>
    `;
  }

  if (requesters.length > 0) {
    html += `
      <div class="demo-group-heading">
        <span>👤 Campus Community Requesters (${requesters.length})</span>
      </div>
      <div class="${isPills ? 'quick-btn-pills' : 'quick-btn-grid'}" style="margin-bottom: 8px;">
        ${requesters.map(a => renderProfileButton(a, isPills)).join('')}
      </div>
    `;
  }

  if (techs.length > 0) {
    html += `
      <div class="demo-group-heading">
        <span>🔧 Field Technicians (${techs.length})</span>
      </div>
      <div class="${isPills ? 'quick-btn-pills' : 'quick-btn-grid'}">
        ${techs.map(a => renderProfileButton(a, isPills)).join('')}
      </div>
    `;
  }

  container.innerHTML = html;
}

async function showLoginScreen() {
  const overlay = document.getElementById('login-overlay');
  if (!overlay) return;
  overlay.style.display = 'flex';
  const errBanner = document.getElementById('login-error-banner');
  if (errBanner) errBanner.style.display = 'none';
  switchAuthTab('signin');

  // Load saved view mode preference
  try {
    const savedMode = localStorage.getItem('facility_demo_view_mode');
    if (savedMode === 'pills' || savedMode === 'cards') {
      state.demoViewMode = savedMode;
    }
  } catch (e) {}

  const btnCards = document.getElementById('toggle-view-cards');
  const btnPills = document.getElementById('toggle-view-pills');
  if (btnCards) btnCards.classList.toggle('active', state.demoViewMode === 'cards');
  if (btnPills) btnPills.classList.toggle('active', state.demoViewMode === 'pills');

  // Initial render immediately using fallback profiles
  if (!state.demoAccounts || state.demoAccounts.length === 0) {
    state.demoAccounts = FALLBACK_DEMO_PROFILES;
  }
  renderDemoProfileButtons();

  // Populate dynamic accounts from server
  try {
    const accounts = await apiGet('/auth/demo-accounts');
    if (accounts && accounts.length > 0) {
      state.demoAccounts = accounts;
      renderDemoProfileButtons();

      // Legacy fallback container population
      const usersContainer = document.getElementById('demo-chips-users');
      const techsContainer = document.getElementById('demo-chips-techs');
      if (usersContainer) {
        usersContainer.innerHTML = accounts.filter(a => a.portal_role !== 'technician').map(a => `
          <div class="demo-chip" onclick="quickLogin('${a.email}')">
            <div class="demo-chip-info">
              <span class="demo-chip-name">${a.name}</span>
              <span class="demo-chip-email">${a.email}</span>
            </div>
            <span class="micro-tag ${a.portal_role === 'admin' ? 'tag-priority-critical' : 'tag-status-assigned'}">[${a.role}]</span>
          </div>
        `).join('');
      }
      if (techsContainer) {
        techsContainer.innerHTML = accounts.filter(a => a.portal_role === 'technician').map(t => `
          <div class="demo-chip" onclick="quickLogin('${t.email}')">
            <div class="demo-chip-info">
              <span class="demo-chip-name">${t.name}</span>
              <span class="demo-chip-email">${t.email}</span>
            </div>
            <span class="micro-tag tag-status-in-progress">[${t.department || t.role}]</span>
          </div>
        `).join('');
      }
    }
  } catch (err) {
    console.warn('Failed to load dynamic demo accounts, using fallbacks', err);
  }
}

async function submitDemoLogin() {
  const emailInput = document.getElementById('login-email-input');
  const errBanner = document.getElementById('login-error-banner');
  const submitBtn = document.getElementById('btn-login-submit');
  const email = emailInput ? emailInput.value.trim() : '';

  if (!email) return;

  const originalBtnText = submitBtn ? submitBtn.innerHTML : 'Continue →';
  if (submitBtn) {
    submitBtn.innerHTML = 'Signing in...';
    submitBtn.disabled = true;
  }

  try {
    const user = await apiPost('/auth/demo-login', { email });
    state.currentUser = user;
    sessionStorage.setItem('facility_demo_user', JSON.stringify(user));
    document.getElementById('login-overlay').style.display = 'none';
    renderUserInterfaceForRole();
    showToast(`Logged in as ${user.full_name} (${user.role_name})`);
  } catch (err) {
    if (errBanner) {
      errBanner.textContent = err.message || 'Login failed. Please enter a valid registered campus email.';
      errBanner.style.display = 'block';
    }
  } finally {
    if (submitBtn) {
      submitBtn.innerHTML = originalBtnText;
      submitBtn.disabled = false;
    }
  }
}

async function submitRegistration() {
  const nameInput = document.getElementById('reg-fullname');
  const emailInput = document.getElementById('reg-email');
  const phoneInput = document.getElementById('reg-phone');
  const roleSelect = document.getElementById('reg-account-type');
  const errBanner = document.getElementById('login-error-banner');

  if (errBanner) errBanner.style.display = 'none';

  const full_name = nameInput ? nameInput.value.trim() : '';
  const email = emailInput ? emailInput.value.trim() : '';
  const phone = phoneInput ? phoneInput.value.trim() : '';
  const account_type = roleSelect ? roleSelect.value : '';

  try {
    const user = await apiPost('/auth/register', {
      full_name,
      email,
      phone: phone || null,
      account_type,
    });

    state.currentUser = user;
    sessionStorage.setItem('facility_demo_user', JSON.stringify(user));
    document.getElementById('login-overlay').style.display = 'none';
    renderUserInterfaceForRole();
    try {
      state.lookups = await apiGet('/lookups');
      populateModalDropdowns();
    } catch (e) {
      // Non-blocking lookup refresh
    }
    showToast(`Account registered successfully! Welcome, ${user.full_name} (${user.role_name})`);
  } catch (err) {
    if (errBanner) {
      errBanner.textContent = err.message || 'Registration failed. Please review your input.';
      errBanner.style.display = 'block';
    }
  }
}

function quickLogin(email) {
  const emailInput = document.getElementById('login-email-input');
  if (emailInput) {
    emailInput.value = email;
    submitDemoLogin();
  }
}

function logoutDemoUser() {
  stopTechnicianPolling();
  sessionStorage.removeItem('facility_demo_user');
  state.currentUser = null;
  showLoginScreen();
}

function renderUserInterfaceForRole() {
  const user = state.currentUser;
  if (!user) return;

  // 1. Topbar user badge
  const avatar = document.getElementById('topbar-avatar');
  const username = document.getElementById('topbar-username');
  if (avatar) {
    const parts = user.full_name.split(' ');
    const initials = parts.length > 1 ? parts[0][0] + parts[1][0] : user.full_name.substring(0, 2);
    avatar.textContent = initials.toUpperCase();
  }
  if (username) {
    const badgeClass = user.portal_role === 'admin' ? 'tag-priority-critical' : (user.portal_role === 'technician' ? 'tag-status-in-progress' : 'tag-status-assigned');
    username.innerHTML = `
      <span>${user.full_name}</span>
      <span class="micro-tag ${badgeClass}" style="margin-left: 6px;">[${user.role_name}]</span>
    `;
  }

  // 2. Sidebar Navigation by Role
  const sidebarNav = document.getElementById('sidebar-nav');
  if (sidebarNav) {
    if (user.portal_role === 'admin') {
      sidebarNav.innerHTML = `
        <div class="nav-section-title">Operations</div>
        <a class="nav-item active" href="#dashboard" id="nav-dashboard">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
          Dashboard
        </a>
        <a class="nav-item" href="#requests" id="nav-requests">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
          Requests
        </a>
        <a class="nav-item" href="#assignments" id="nav-assignments">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          Assignments
        </a>

        <div class="nav-section-title" style="margin-top: 16px;">Inventory & Ledger</div>
        <a class="nav-item" href="#materials" id="nav-materials">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m21 16-9 5-9-5V8l9-5 9 5v8z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
          Materials & Stock
        </a>
        <a class="nav-item" href="#costs" id="nav-costs">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
          Cost Ledger
        </a>

        <div class="nav-section-title" style="margin-top: 16px;">Quality & Reports</div>
        <a class="nav-item" href="#reports" id="nav-reports">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
          SLA & Reports
        </a>
      `;
    } else if (user.portal_role === 'requester') {
      sidebarNav.innerHTML = `
        <div class="nav-section-title">My Maintenance Portal</div>
        <a class="nav-item active" href="#requester-dashboard" id="nav-requester-dashboard">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
          Dashboard
        </a>
        <a class="nav-item" href="#requester-requests" id="nav-requester-requests">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
          My Requests
        </a>

        <div class="nav-section-title" style="margin-top: 16px;">Quick Actions</div>
        <a class="nav-item" href="#action-report" onclick="openRequesterCreateModal(); return false;" style="color: var(--accent-green);">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
          + Report a Problem
        </a>
      `;
    } else if (user.portal_role === 'technician') {
      sidebarNav.innerHTML = `
        <div class="nav-section-title">Field Operations</div>
        <a class="nav-item active" href="#technician-dashboard" id="nav-technician-dashboard">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
          Technician Dashboard
        </a>
        <a class="nav-item" href="#technician-assignments" id="nav-technician-assignments">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          My Assignments
        </a>
        <a class="nav-item" href="#technician-work-logs" id="nav-technician-work-logs">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          My Work Logs
        </a>
        <a class="nav-item" href="#technician-materials" id="nav-technician-materials">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m21 16-9 5-9-5V8l9-5 9 5v8z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
          Material Requests
        </a>
      `;
    }
    setupNavigation();
  }

  // 3. Load initial view
  if (user.portal_role === 'admin') {
    switchView('dashboard');
  } else if (user.portal_role === 'requester') {
    switchView('requester-dashboard');
  } else if (user.portal_role === 'technician') {
    switchView('technician-dashboard');
  }
}

// Initialization & Data Loading
async function initApp() {
  try {
    state.lookups = await apiGet('/lookups');
    populateModalDropdowns();
    setupEventHandlers();

    // Check existing demo user session
    const saved = sessionStorage.getItem('facility_demo_user');
    if (saved) {
      try {
        state.currentUser = JSON.parse(saved);
        renderUserInterfaceForRole();
      } catch (e) {
        showLoginScreen();
      }
    } else {
      showLoginScreen();
    }
  } catch (err) {
    console.error('Initialization error:', err);
  }
}

function setupNavigation() {
  const navItems = document.querySelectorAll('.sidebar-nav .nav-item');
  navItems.forEach((item) => {
    item.addEventListener('click', (e) => {
      const href = item.getAttribute('href');
      if (href && href.startsWith('#') && !href.startsWith('#action-')) {
        e.preventDefault();
        navItems.forEach((n) => n.classList.remove('active'));
        item.classList.add('active');
        const target = href.replace('#', '');
        switchView(target);
      }
    });
  });
}

async function switchView(viewName) {
  state.currentView = viewName;
  if (viewName !== 'technician-dashboard') {
    stopTechnicianPolling();
  }
  const contentArea = document.getElementById('view-container');
  if (!contentArea) return;

  switch (viewName) {
    // Admin Views
    case 'dashboard':
      await loadDashboard();
      break;
    case 'requests':
      await loadRequestsView();
      break;
    case 'assignments':
      await loadAssignmentsView();
      break;
    case 'materials':
      await loadMaterialsView();
      break;
    case 'costs':
      await loadCostsView();
      break;
    case 'reports':
      await loadReportsView();
      break;

    // Requester Views
    case 'requester-dashboard':
      await loadRequesterDashboardView();
      break;
    case 'requester-requests':
      await loadRequesterRequestsView();
      break;

    // Technician Views
    case 'technician-dashboard':
      await loadTechnicianDashboardView();
      break;
    case 'technician-assignments':
      await loadTechnicianAssignmentsView();
      break;
    case 'technician-work-logs':
      await loadTechnicianWorkLogsView();
      break;
    case 'technician-materials':
      await loadTechnicianMaterialsView();
      break;

    default:
      if (state.currentUser?.portal_role === 'requester') {
        await loadRequesterDashboardView();
      } else if (state.currentUser?.portal_role === 'technician') {
        await loadTechnicianDashboardView();
      } else {
        await loadDashboard();
      }
  }
}

// View: Dashboard
async function loadDashboard() {
  const stats = await apiGet('/dashboard/stats');
  state.stats = stats;
  const requests = await apiGet('/requests?limit=10');
  state.requests = requests;

  const container = document.getElementById('view-container');
  container.innerHTML = `
    <div class="workspace-header">
      <div class="workspace-title-group">
        <h1>Campus Facility Operations Dashboard</h1>
        <p>Real-time lifecycle monitoring, technician workloads, inventory ledger, and SLA metrics</p>
      </div>
      <button class="btn btn-primary" onclick="openModal('modal-create-request')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        + Create Request
      </button>
    </div>

    <div class="metrics-grid">
      <div class="stat-card">
        <div class="stat-header">
          <span class="stat-label">Open Requests</span>
          <span class="stat-indicator" style="background-color: #0288d1;"></span>
        </div>
        <div class="stat-value">${stats.open_requests}</div>
        <div class="stat-subtext">Awaiting technician assignment</div>
      </div>

      <div class="stat-card">
        <div class="stat-header">
          <span class="stat-label">Active Jobs</span>
          <span class="stat-indicator" style="background-color: #f57f17;"></span>
        </div>
        <div class="stat-value">${stats.active_jobs}</div>
        <div class="stat-subtext">Dispatched or underway</div>
      </div>

      <div class="stat-card">
        <div class="stat-header">
          <span class="stat-label">On Hold</span>
          <span class="stat-indicator" style="background-color: #e65100;"></span>
        </div>
        <div class="stat-value">${stats.on_hold}</div>
        <div class="stat-subtext">Awaiting specialized parts</div>
      </div>

      <div class="stat-card">
        <div class="stat-header">
          <span class="stat-label">Resolved & Closed</span>
          <span class="stat-indicator" style="background-color: #00ed64;"></span>
        </div>
        <div class="stat-value">${stats.closed}</div>
        <div class="stat-subtext">Verified with resolution audit</div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <h2 class="panel-title">Recent Maintenance Requests</h2>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-secondary" style="font-size: 12px; padding: 5px 12px;" onclick="switchView('requests')">View All Requests →</button>
        </div>
      </div>
      <div class="table-responsive">
        ${renderRequestsTable(requests)}
      </div>
    </div>
  `;
}

// View: Requests
async function loadRequestsView() {
  const requests = await apiGet('/requests?limit=100');
  state.requests = requests;

  const container = document.getElementById('view-container');
  container.innerHTML = `
    <div class="workspace-header">
      <div class="workspace-title-group">
        <h1>Maintenance Requests Ledger</h1>
        <p>Complete record of requests across campus educational blocks and facilities</p>
      </div>
      <button class="btn btn-primary" onclick="openModal('modal-create-request')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        + Create Request
      </button>
    </div>

    <div class="panel">
      <div class="panel-header" style="flex-wrap: wrap; gap: 12px;">
        <div style="display: flex; gap: 8px; flex: 1; min-width: 300px;">
          <input type="text" id="requests-filter-search" class="form-control" placeholder="Filter by number, description, requester..." onkeyup="filterRequestsTable()">
        </div>
        <div style="display: flex; gap: 8px;">
          <select id="requests-filter-status" class="form-control" style="width: 140px;" onchange="filterRequestsTable()">
            <option value="">All Statuses</option>
            ${state.lookups.statuses.map(s => `<option value="${s.status_name}">${s.status_name}</option>`).join('')}
          </select>
          <select id="requests-filter-priority" class="form-control" style="width: 140px;" onchange="filterRequestsTable()">
            <option value="">All Priorities</option>
            ${state.lookups.priorities.map(p => `<option value="${p.priority_level}">${p.priority_level}</option>`).join('')}
          </select>
        </div>
      </div>
      <div class="table-responsive" id="requests-table-container">
        ${renderRequestsTable(requests)}
      </div>
    </div>
  `;
}

function renderRequestsTable(requests) {
  if (!requests || requests.length === 0) {
    return `<div style="padding: 32px; text-align: center; color: var(--text-muted);">No requests match the selected criteria.</div>`;
  }

  return `
    <table class="data-table" id="requests-data-table">
      <thead>
        <tr>
          <th>Request ID</th>
          <th>Description</th>
          <th>Location</th>
          <th>Category</th>
          <th>Priority</th>
          <th>Status</th>
          <th>Requested By</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        ${requests.map(r => `
          <tr>
            <td><span class="identifier-mono">${r.request_number}</span></td>
            <td style="max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${r.description}">${r.description}</td>
            <td>${r.building_name} • Rm ${r.room_number}</td>
            <td><span class="micro-tag tag-category">${r.category_name}</span></td>
            <td><span class="micro-tag ${getPriorityTagClass(r.priority_level)}">[${r.priority_level.toUpperCase()}]</span></td>
            <td><span class="micro-tag ${getStatusTagClass(r.status_name)}">[${r.status_name.toUpperCase()}]</span></td>
            <td>${r.requester_name}</td>
            <td>
              <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 11px;" onclick="viewRequestDetail(${r.request_id})">Manage</button>
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function filterRequestsTable() {
  const query = (document.getElementById('requests-filter-search')?.value || '').toLowerCase();
  const statusFilter = document.getElementById('requests-filter-status')?.value || '';
  const priorityFilter = document.getElementById('requests-filter-priority')?.value || '';

  const filtered = state.requests.filter(r => {
    const matchesQuery = !query ||
      r.request_number.toLowerCase().includes(query) ||
      r.description.toLowerCase().includes(query) ||
      r.requester_name.toLowerCase().includes(query) ||
      r.building_name.toLowerCase().includes(query);
    const matchesStatus = !statusFilter || r.status_name === statusFilter;
    const matchesPriority = !priorityFilter || r.priority_level === priorityFilter;
    return matchesQuery && matchesStatus && matchesPriority;
  });

  const container = document.getElementById('requests-table-container');
  if (container) {
    container.innerHTML = renderRequestsTable(filtered);
  }
}

// View: Reports & Analytics (Backed by EXACT Phase 2 PostgreSQL Views)
async function loadReportsView() {
  const container = document.getElementById('view-container');
  container.innerHTML = `
    <div class="workspace-header">
      <div class="workspace-title-group">
        <h1>Analytics & Operational Reports</h1>
        <p>Live authoritative reporting powered directly by locked Phase 2 PostgreSQL views</p>
      </div>
    </div>

    <div class="tabs-header">
      <button class="tab-btn ${state.currentReport === 'pending-requests' ? 'active' : ''}" onclick="switchReportTab('pending-requests')">Pending Requests (vw_pending_requests)</button>
      <button class="tab-btn ${state.currentReport === 'request-ageing' ? 'active' : ''}" onclick="switchReportTab('request-ageing')">Request Ageing SLA (vw_request_ageing)</button>
      <button class="tab-btn ${state.currentReport === 'technician-workload' ? 'active' : ''}" onclick="switchReportTab('technician-workload')">Technician Workload (vw_technician_workload)</button>
      <button class="tab-btn ${state.currentReport === 'building-maintenance-cost' ? 'active' : ''}" onclick="switchReportTab('building-maintenance-cost')">Building Costs (vw_building_maintenance_cost)</button>
      <button class="tab-btn ${state.currentReport === 'material-usage' ? 'active' : ''}" onclick="switchReportTab('material-usage')">Material Usage (vw_material_usage)</button>
      <button class="tab-btn ${state.currentReport === 'feedback-summary' ? 'active' : ''}" onclick="switchReportTab('feedback-summary')">Feedback Summary (vw_feedback_summary)</button>
    </div>

    <div class="panel">
      <div class="panel-body" id="report-content-body">
        <div style="padding: 24px; text-align: center;">Loading view data...</div>
      </div>
    </div>
  `;

  renderActiveReport();
}

async function switchReportTab(reportName) {
  state.currentReport = reportName;
  document.querySelectorAll('.tabs-header .tab-btn').forEach(btn => btn.classList.remove('active'));
  event.target.classList.add('active');
  await renderActiveReport();
}

async function renderActiveReport() {
  const body = document.getElementById('report-content-body');
  if (!body) return;

  const data = await apiGet(`/reports/${state.currentReport}`);

  if (state.currentReport === 'pending-requests') {
    body.innerHTML = `
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Request Number</th>
              <th>Category</th>
              <th>Priority</th>
              <th>Location</th>
              <th>Requester</th>
              <th>Status</th>
              <th>Days Open</th>
              <th>Assigned Technician</th>
            </tr>
          </thead>
          <tbody>
            ${data.map(r => `
              <tr>
                <td><span class="identifier-mono">${r.request_number}</span></td>
                <td><span class="micro-tag tag-category">${r.category_name}</span></td>
                <td><span class="micro-tag ${getPriorityTagClass(r.priority_level)}">[${r.priority_level}]</span></td>
                <td>${r.building_name} • Rm ${r.room_number}</td>
                <td>${r.requester_name}</td>
                <td><span class="micro-tag ${getStatusTagClass(r.current_status)}">[${r.current_status}]</span></td>
                <td style="font-weight: 600;">${r.days_open} days</td>
                <td>${r.assigned_technician}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  } else if (state.currentReport === 'request-ageing') {
    body.innerHTML = `
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Request Number</th>
              <th>Status</th>
              <th>Priority</th>
              <th>SLA Benchmark</th>
              <th>Hours Elapsed</th>
              <th>SLA Performance</th>
              <th>Ageing Bracket</th>
              <th>Location</th>
            </tr>
          </thead>
          <tbody>
            ${data.map(r => `
              <tr>
                <td><span class="identifier-mono">${r.request_number}</span></td>
                <td><span class="micro-tag ${getStatusTagClass(r.request_status)}">[${r.request_status}]</span></td>
                <td><span class="micro-tag ${getPriorityTagClass(r.priority_level)}">[${r.priority_level}]</span></td>
                <td>${r.sla_target_hours} hrs</td>
                <td style="font-weight: 600;">${r.hours_open} hrs</td>
                <td>
                  <span class="micro-tag ${r.sla_performance_status.includes('BREACHED') || r.sla_performance_status.includes('OVERDUE') ? 'tag-priority-critical' : 'tag-status-closed'}">
                    ${r.sla_performance_status}
                  </span>
                </td>
                <td><span class="micro-tag tag-category">${r.ageing_bracket}</span></td>
                <td>${r.building_name} • Rm ${r.room_number}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  } else if (state.currentReport === 'technician-workload') {
    body.innerHTML = `
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Technician</th>
              <th>Department</th>
              <th>Labor Rate</th>
              <th>Total Assignments</th>
              <th>Active Jobs</th>
              <th>Completed Jobs</th>
              <th>Total Labor Hours</th>
              <th>Labor Value Generated</th>
            </tr>
          </thead>
          <tbody>
            ${data.map(r => `
              <tr>
                <td style="font-weight: 600;">${r.full_name}</td>
                <td><span class="micro-tag tag-category">${r.department}</span></td>
                <td>${formatCurrency(r.labor_rate)}/hr</td>
                <td>${r.total_assignments}</td>
                <td><span class="micro-tag tag-status-in-progress">${r.active_assignments}</span></td>
                <td><span class="micro-tag tag-status-closed">${r.completed_assignments}</span></td>
                <td style="font-weight: 600;">${r.total_hours_worked} hrs</td>
                <td style="font-weight: 700; color: #00684a;">${formatCurrency(r.total_labor_value_generated)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  } else if (state.currentReport === 'building-maintenance-cost') {
    body.innerHTML = `
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Building Name</th>
              <th>Campus Location</th>
              <th>Total Requests</th>
              <th>Material Cost</th>
              <th>Labor Cost</th>
              <th>Service / Misc Cost</th>
              <th>Total Maintenance Expenditure</th>
            </tr>
          </thead>
          <tbody>
            ${data.map(r => `
              <tr>
                <td style="font-weight: 600;">${r.building_name}</td>
                <td>${r.location}</td>
                <td>${r.total_requests_count}</td>
                <td>${formatCurrency(r.material_cost)}</td>
                <td>${formatCurrency(r.labor_cost)}</td>
                <td>${formatCurrency(r.service_cost + r.misc_cost)}</td>
                <td style="font-weight: 700; color: #00684a;">${formatCurrency(r.total_maintenance_expenditure)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  } else if (state.currentReport === 'material-usage') {
    body.innerHTML = `
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Material Name</th>
              <th>Unit</th>
              <th>Unit Cost</th>
              <th>Current Warehouse Stock</th>
              <th>Total Qty Consumed</th>
              <th>Total Material Cost</th>
              <th>Jobs Used In</th>
            </tr>
          </thead>
          <tbody>
            ${data.map(r => `
              <tr>
                <td style="font-weight: 600;">${r.material_name}</td>
                <td>${r.unit}</td>
                <td>${formatCurrency(r.unit_cost)}</td>
                <td style="font-weight: 700; color: ${r.current_warehouse_stock <= 5 ? '#b71c1c' : '#001e2b'};">
                  ${r.current_warehouse_stock}
                </td>
                <td>${r.total_quantity_used}</td>
                <td style="font-weight: 700; color: #00684a;">${formatCurrency(r.total_material_cost)}</td>
                <td>${r.total_work_orders_used_in}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  } else if (state.currentReport === 'feedback-summary') {
    body.innerHTML = `
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Building Name</th>
              <th>Category</th>
              <th>Total Evaluations</th>
              <th>Average Rating (1-5)</th>
              <th>Lowest Rating</th>
              <th>Highest Rating</th>
            </tr>
          </thead>
          <tbody>
            ${data.map(r => `
              <tr>
                <td style="font-weight: 600;">${r.building_name}</td>
                <td><span class="micro-tag tag-category">${r.category_name}</span></td>
                <td>${r.total_evaluations}</td>
                <td style="font-weight: 700; color: #f57f17;">★ ${r.average_rating} / 5.0</td>
                <td>${r.lowest_rating}</td>
                <td>${r.highest_rating}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  }
}

// View: Assignments View
async function loadAssignmentsView() {
  const assignments = await apiGet('/assignments');
  const container = document.getElementById('view-container');
  container.innerHTML = `
    <div class="workspace-header">
      <div class="workspace-title-group">
        <h1>Technician Assignments</h1>
        <p>Active technician work orders and scheduling allocations</p>
      </div>
      <button class="btn btn-primary" onclick="openModal('modal-create-assignment')">
        + Assign Technician
      </button>
    </div>

    <div class="panel">
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Assignment ID</th>
              <th>Request</th>
              <th>Technician</th>
              <th>Department</th>
              <th>Assigned Date</th>
              <th>Due Date</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${assignments.map(a => `
              <tr>
                <td><span class="identifier-mono">#${a.assignment_id}</span></td>
                <td><span class="identifier-mono">${a.request_number}</span></td>
                <td style="font-weight: 600;">${a.technician_name}</td>
                <td><span class="micro-tag tag-category">${a.technician_department}</span></td>
                <td>${formatDate(a.assigned_date)}</td>
                <td>${formatDate(a.due_date)}</td>
                <td><span class="micro-tag ${getStatusTagClass(a.assignment_status)}">[${a.assignment_status.toUpperCase()}]</span></td>
                <td>
                  <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px;" onclick="openWorkLogModal(${a.assignment_id})">Log Work</button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// View: Materials View
async function loadMaterialsView() {
  const materials = await apiGet('/materials');
  const container = document.getElementById('view-container');
  container.innerHTML = `
    <div class="workspace-header">
      <div class="workspace-title-group">
        <h1>Inventory Materials Catalog</h1>
        <p>Warehouse parts and supplies with live row-locked stock tracking</p>
      </div>
      <button class="btn btn-primary" onclick="openModal('modal-requisition-material')">
        Requisition Material
      </button>
    </div>

    <div class="panel">
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Material ID</th>
              <th>Material Name</th>
              <th>Unit</th>
              <th>Unit Cost</th>
              <th>Current Stock Qty</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${materials.map(m => `
              <tr>
                <td><span class="identifier-mono">MAT-${String(m.material_id).padStart(3, '0')}</span></td>
                <td style="font-weight: 600;">${m.material_name}</td>
                <td>${m.unit}</td>
                <td>${formatCurrency(m.unit_cost)}</td>
                <td style="font-weight: 700; font-size: 14px; color: ${m.stock_qty <= 5 ? '#c62828' : '#001e2b'};">${m.stock_qty}</td>
                <td>
                  <span class="micro-tag ${m.stock_qty <= 5 ? 'tag-priority-critical' : 'tag-status-closed'}">
                    ${m.stock_qty <= 5 ? '[LOW STOCK]' : '[IN STOCK]'}
                  </span>
                </td>
                <td>
                  <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px;" onclick="prepareRequisition(${m.material_id})">Issue Part</button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// View: Costs View
async function loadCostsView() {
  const costs = await apiGet('/costs');
  const container = document.getElementById('view-container');
  container.innerHTML = `
    <div class="workspace-header">
      <div class="workspace-title-group">
        <h1>Financial Cost Ledger</h1>
        <p>Authoritative single recorded financial ledger for facility maintenance expenditures</p>
      </div>
    </div>

    <div class="panel">
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Cost ID</th>
              <th>Request Number</th>
              <th>Cost Type</th>
              <th>Amount</th>
              <th>Date</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            ${costs.map(c => `
              <tr>
                <td><span class="identifier-mono">#${c.cost_id}</span></td>
                <td><span class="identifier-mono">${c.request_number}</span></td>
                <td><span class="micro-tag tag-category">${c.cost_type}</span></td>
                <td style="font-weight: 700; color: #00684a;">${formatCurrency(c.amount)}</td>
                <td>${formatDate(c.cost_date)}</td>
                <td>${c.description || '—'}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// Modal Form Operations
function populateModalDropdowns() {
  if (!state.lookups) return;

  // Categories
  const catSelect = document.getElementById('modal-req-category');
  if (catSelect) {
    catSelect.innerHTML = state.lookups.categories.map(c => `<option value="${c.category_id}">${c.category_name}</option>`).join('');
  }

  // Priorities
  const prioSelect = document.getElementById('modal-req-priority');
  if (prioSelect) {
    prioSelect.innerHTML = state.lookups.priorities.map(p => `<option value="${p.priority_id}">${p.priority_level} (${p.response_time_hr}h SLA)</option>`).join('');
  }

  // Rooms
  const roomSelect = document.getElementById('modal-req-room');
  if (roomSelect) {
    roomSelect.innerHTML = state.lookups.rooms.map(r => `<option value="${r.room_id}">${r.building_name} • Room ${r.room_number}</option>`).join('');
  }

  // Requesters
  const reqUserSelect = document.getElementById('modal-req-user');
  if (reqUserSelect) {
    reqUserSelect.innerHTML = state.lookups.users.map(u => `<option value="${u.user_id}">${u.full_name} (${u.email})</option>`).join('');
  }

  // Technicians
  const techSelect = document.getElementById('modal-assign-tech');
  if (techSelect) {
    techSelect.innerHTML = state.lookups.technicians.map(t => `<option value="${t.technician_id}">${t.full_name} (${t.department})</option>`).join('');
  }

  // Materials
  const matSelect = document.getElementById('modal-req-mat-id');
  if (matSelect) {
    matSelect.innerHTML = state.lookups.materials.map(m => `<option value="${m.material_id}">${m.material_name} (${m.stock_qty} in stock @ ${formatCurrency(m.unit_cost)})</option>`).join('');
  }
}

function openModal(modalId) {
  const el = document.getElementById(modalId);
  if (el) el.classList.add('active');
}

function closeModal(modalId) {
  const el = document.getElementById(modalId);
  if (el) el.classList.remove('active');
}

// Request Detail Modal & Stepper
async function viewRequestDetail(requestId) {
  const req = await apiGet(`/requests/${requestId}`);
  const history = await apiGet(`/requests/${requestId}/history`);
  let feedback = null;
  if (req.status_name === 'Closed') {
    feedback = await apiGet(`/requests/${requestId}/feedback`).catch(() => null);
  }

  const modalBody = document.getElementById('modal-detail-body');
  if (!modalBody) return;

  const statuses = ['Open', 'Assigned', 'In Progress', 'On Hold', 'Closed'];
  const currentIndex = statuses.indexOf(req.status_name);

  modalBody.innerHTML = `
    <!-- Stepper -->
    <div class="lifecycle-stepper">
      ${statuses.map((s, idx) => {
        const isCurrent = s === req.status_name;
        const isCompleted = idx < currentIndex || (req.status_name === 'Closed' && s !== 'On Hold');
        return `
          <div class="step-item ${isCurrent ? 'active' : isCompleted ? 'completed' : ''}">
            <div class="step-circle">${idx + 1}</div>
            <span>${s}</span>
          </div>
          ${idx < statuses.length - 1 ? `<div class="step-connector ${isCompleted ? 'completed' : ''}"></div>` : ''}
        `;
      }).join('')}
    </div>

    <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 20px;">
      <div>
        <h4 style="font-size: 14px; font-weight: 700; margin-bottom: 8px;">Request Summary</h4>
        <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">${req.description}</p>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 12px; margin-bottom: 20px;">
          <div><strong style="color: var(--text-muted);">Request ID:</strong> <span class="identifier-mono">${req.request_number}</span></div>
          <div><strong style="color: var(--text-muted);">Submitted:</strong> ${formatDate(req.request_date)}</div>
          <div><strong style="color: var(--text-muted);">Location:</strong> ${req.building_name} • Room ${req.room_number}</div>
          <div><strong style="color: var(--text-muted);">Requester:</strong> ${req.requester_name}</div>
          <div><strong style="color: var(--text-muted);">Category:</strong> <span class="micro-tag tag-category">${req.category_name}</span></div>
          <div><strong style="color: var(--text-muted);">Priority:</strong> <span class="micro-tag ${getPriorityTagClass(req.priority_level)}">[${req.priority_level}]</span></div>
          ${req.asset_name ? `<div><strong style="color: var(--text-muted);">Asset:</strong> ${req.asset_name} ${req.asset_type ? `(${req.asset_type})` : ''}</div>` : ''}
          <div><strong style="color: var(--text-muted);">Assignment:</strong> <span style="font-style: italic; color: var(--text-secondary);">${req.assignment_id ? `Assigned (#${req.assignment_id})` : 'Unassigned (Incoming)'}</span></div>
        </div>

        ${req.status_name === 'Closed' ? `
          <div style="background-color: var(--tag-closed-bg); padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--tag-closed-border); margin-bottom: 16px;">
            <div style="font-weight: 700; color: var(--tag-closed-text); font-size: 12px; margin-bottom: 4px;">Resolution Summary</div>
            <div style="font-size: 13px; color: var(--text-primary);">${req.resolution_description || 'Resolved'}</div>
            <div style="font-size: 11px; color: var(--text-muted); margin-top: 6px;">Closed by User #${req.closed_by} on ${formatDate(req.closed_date)}</div>
          </div>
        ` : ''}

        ${feedback ? `
          <div style="background-color: #fffde7; padding: 12px; border-radius: var(--radius-sm); border: 1px solid #fff59d; margin-bottom: 16px;">
            <div style="font-weight: 700; color: #f57f17; font-size: 12px; margin-bottom: 4px;">Requester Satisfaction Evaluation</div>
            <div style="font-size: 14px; font-weight: 700; color: #f57f17;">★ ${feedback.rating} / 5</div>
            <div style="font-size: 13px; color: var(--text-primary); margin-top: 4px;">${feedback.comments || 'No comments left.'}</div>
          </div>
        ` : ''}
      </div>

      <!-- Action Panel -->
      <div style="border-left: 1px solid var(--ws-border-subtle); padding-left: 16px;">
        <h4 style="font-size: 13px; font-weight: 700; margin-bottom: 12px;">Operational Actions</h4>
        <div style="display: flex; flex-direction: column; gap: 8px;">
          ${state.currentUser?.portal_role === 'admin' && req.status_name === 'Open' ? `
            <button class="btn btn-primary" onclick="prepareAssignFromDetail(${req.request_id})">Assign Technician</button>
          ` : ''}
          ${state.currentUser?.portal_role === 'technician' && req.status_name === 'Open' ? `
            <div style="font-size: 12px; color: var(--text-muted); font-style: italic; padding: 4px 0;">
              Awaiting dispatch by facility operations management.
            </div>
          ` : ''}
          ${state.currentUser?.portal_role === 'admin' && req.status_name === 'Assigned' ? `
            <button class="btn btn-primary" onclick="advanceStatus(${req.request_id}, 'In Progress')">Start Work (In Progress)</button>
          ` : ''}
          ${state.currentUser?.portal_role === 'admin' && req.status_name === 'In Progress' ? `
            <button class="btn btn-secondary" onclick="advanceStatus(${req.request_id}, 'On Hold')">Put On Hold</button>
            <button class="btn btn-primary" onclick="prepareCloseFromDetail(${req.request_id})">Close Request</button>
          ` : ''}
          ${state.currentUser?.portal_role === 'admin' && req.status_name === 'On Hold' ? `
            <button class="btn btn-secondary" onclick="advanceStatus(${req.request_id}, 'In Progress')">Resume Work</button>
            <button class="btn btn-primary" onclick="prepareCloseFromDetail(${req.request_id})">Close Request</button>
          ` : ''}
          ${state.currentUser?.portal_role === 'requester' && req.status_name === 'Closed' && !feedback && req.requested_by === state.currentUser?.user_id ? `
            <button class="btn btn-primary" onclick="prepareFeedbackFromDetail(${req.request_id})">Submit Feedback</button>
          ` : ''}
        </div>

        <h4 style="font-size: 13px; font-weight: 700; margin-top: 24px; margin-bottom: 8px;">Audit Trail</h4>
        <div style="font-size: 11px; max-height: 180px; overflow-y: auto;">
          ${history.map(h => `
            <div style="padding: 6px 0; border-bottom: 1px solid var(--ws-border-subtle);">
              <div><strong style="color: #00684a;">[${h.status_name}]</strong> by User #${h.changed_by}</div>
              <div style="color: var(--text-muted);">${formatDate(h.changed_date)}</div>
              ${h.remarks ? `<div style="font-style: italic; color: var(--text-secondary);">${h.remarks}</div>` : ''}
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `;

  openModal('modal-request-detail');
}

// Action Handlers
async function submitCreateRequest(e) {
  e.preventDefault();
  const description = document.getElementById('modal-req-desc').value;
  const category_id = parseInt(document.getElementById('modal-req-category').value, 10);
  const priority_id = parseInt(document.getElementById('modal-req-priority').value, 10);
  const room_id = parseInt(document.getElementById('modal-req-room').value, 10);
  let requested_by = parseInt(document.getElementById('modal-req-user').value, 10);

  if (state.currentUser && state.currentUser.portal_role === 'requester') {
    requested_by = state.currentUser.user_id;
  }

  try {
    const created = await apiPost('/requests', {
      description,
      category_id,
      priority_id,
      room_id,
      requested_by,
    });
    showToast(`Created Request ${created.request_number}`);
    closeModal('modal-create-request');
    document.getElementById('form-create-request')?.reset();
    switchView(state.currentView);
  } catch (err) {
    // Toast handles error
  }
}

async function advanceStatus(requestId, newStatus) {
  const changed_by = state.currentUser ? (state.currentUser.user_id || 7) : 7;
  try {
    await apiPost(`/requests/${requestId}/status`, {
      new_status: newStatus,
      changed_by,
      remarks: `Transitioned to ${newStatus} via Operations Portal`,
    });
    showToast(`Request #${requestId} moved to ${newStatus}`);
    viewRequestDetail(requestId);
  } catch (err) {
    // Toast handles error
  }
}

function prepareCloseFromDetail(requestId) {
  document.getElementById('modal-close-req-id').value = requestId;
  openModal('modal-close-request');
}

async function submitCloseRequest(e) {
  e.preventDefault();
  const requestId = parseInt(document.getElementById('modal-close-req-id').value, 10);
  const resolution_description = document.getElementById('modal-close-resolution').value;
  const actor_id = state.currentUser ? (state.currentUser.user_id || 7) : 7;

  try {
    await apiPost(`/requests/${requestId}/close`, {
      closed_by: actor_id,
      changed_by: actor_id,
      resolution_description,
      closed_date: new Date().toISOString(),
      remarks: 'Closed via Facility Operations Management Portal',
    });
    showToast(`Request #${requestId} successfully Closed.`);
    closeModal('modal-close-request');
    viewRequestDetail(requestId);
  } catch (err) {
    // Toast handles error
  }
}

function prepareFeedbackFromDetail(requestId) {
  document.getElementById('modal-fb-req-id').value = requestId;
  openModal('modal-feedback');
}

async function submitFeedback(e) {
  e.preventDefault();
  const requestId = parseInt(document.getElementById('modal-fb-req-id').value, 10);
  const rating = parseInt(document.getElementById('modal-fb-rating').value, 10);
  const comments = document.getElementById('modal-fb-comments').value;
  const user_id = state.currentUser ? (state.currentUser.user_id || 1) : 1;

  try {
    await apiPost(`/requests/${requestId}/feedback`, {
      user_id,
      rating,
      comments,
      feedback_date: new Date().toISOString(),
    });
    showToast('Feedback submitted successfully!');
    closeModal('modal-feedback');
    if (state.currentUser?.portal_role === 'requester') {
      viewRequesterRequestDetail(requestId);
    } else {
      viewRequestDetail(requestId);
    }
  } catch (err) {
    // Toast handles error
  }
}

function prepareRequisition(materialId) {
  document.getElementById('modal-req-mat-id').value = materialId;
  openModal('modal-requisition-material');
}

async function submitRequisition(e) {
  e.preventDefault();
  const material_id = parseInt(document.getElementById('modal-req-mat-id').value, 10);
  const quantity_used = parseFloat(document.getElementById('modal-req-qty').value);
  const work_log_id = parseInt(document.getElementById('modal-req-wl-id').value, 10);

  try {
    await apiPost('/materials/usage', {
      material_id,
      quantity_used,
      work_log_id,
      issued_by: 1,
      description: 'Requisitioned via Developer Operations Dashboard',
    });
    showToast('Material stock decremented & ledger cost recorded!');
    closeModal('modal-requisition-material');
    switchView(state.currentView);
  } catch (err) {
    // Toast handles error
  }
}

function openWorkLogModal(assignmentId) {
  document.getElementById('modal-wl-assign-id').value = assignmentId;
  openModal('modal-add-worklog');
}

async function submitWorkLog(e) {
  e.preventDefault();
  const assignment_id = parseInt(document.getElementById('modal-wl-assign-id').value, 10);
  const work_description = document.getElementById('modal-wl-desc').value;
  const hours_spent = parseFloat(document.getElementById('modal-wl-hours').value);

  try {
    await apiPost('/work-logs', {
      assignment_id,
      work_description,
      hours_spent,
      work_date: new Date().toISOString(),
    });
    showToast('Work log recorded!');
    closeModal('modal-add-worklog');
    switchView(state.currentView);
  } catch (err) {
    // Toast handles error
  }
}

function prepareAssignFromDetail(requestId) {
  document.getElementById('modal-assign-req-id').value = requestId;
  openModal('modal-create-assignment');
}

async function submitCreateAssignment(e) {
  e.preventDefault();
  const request_id = parseInt(document.getElementById('modal-assign-req-id').value, 10);
  const technician_id = parseInt(document.getElementById('modal-assign-tech').value, 10);
  const due_date = document.getElementById('modal-assign-due').value;

  try {
    await apiPost('/assignments', {
      request_id,
      technician_id,
      assigned_date: new Date().toISOString(),
      due_date: due_date ? new Date(due_date).toISOString() : null,
      status: 'Assigned',
    });
    // Advance request to Assigned
    await apiPost(`/requests/${request_id}/status`, {
      new_status: 'Assigned',
      changed_by: 7,
      remarks: 'Technician dispatched',
    });
    showToast('Technician assigned successfully!');
    closeModal('modal-create-assignment');
    viewRequestDetail(request_id);
  } catch (err) {
    // Toast handles error
  }
}

// =============================================================================
// REQUESTER PORTAL VIEWS & LOGIC
// =============================================================================

async function loadRequesterDashboardView() {
  const user = state.currentUser;
  if (!user) return;

  const data = await apiGet(`/requester/${user.user_id}/dashboard`);
  const container = document.getElementById('view-container');
  container.innerHTML = `
    <div class="workspace-header">
      <div class="workspace-title-group">
        <h1>Welcome, ${user.full_name}</h1>
        <p>${user.role_name} Portal • Track and report maintenance issues for campus facilities</p>
      </div>
      <button class="btn btn-primary" onclick="openRequesterCreateModal()">
        + Report a Problem
      </button>
    </div>

    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-label">Total Submitted</div>
        <div class="metric-value">${data.counts.total}</div>
        <div class="metric-subtext">Lifetime requests</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Open / In Progress</div>
        <div class="metric-value" style="color: #0277bd;">${data.counts.open + data.counts.in_progress}</div>
        <div class="metric-subtext">Active attention</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">On Hold</div>
        <div class="metric-value" style="color: #e65100;">${data.counts.on_hold}</div>
        <div class="metric-subtext">Awaiting parts/clearance</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Resolved & Closed</div>
        <div class="metric-value" style="color: #1b5e20;">${data.counts.closed}</div>
        <div class="metric-subtext">Completed repairs</div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">My Recent Maintenance Requests</div>
        <button class="btn btn-secondary btn-sm" onclick="switchView('requester-requests')">
          View All (${data.requests.length}) →
        </button>
      </div>
      <div class="panel-body" style="padding: 0;">
        ${data.requests.length === 0 ? `
          <div class="empty-state-box">
            <h4>No maintenance requests yet</h4>
            <p>Need repairs in your lab, classroom, or hostel room? Submit a request to facility operations.</p>
            <button class="btn btn-primary" onclick="openRequesterCreateModal()">+ Report a Problem</button>
          </div>
        ` : `
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Request ID</th>
                  <th>Description</th>
                  <th>Category</th>
                  <th>Priority</th>
                  <th>Location</th>
                  <th>Submitted</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                ${data.requests.slice(0, 5).map(r => `
                  <tr>
                    <td><span class="identifier-mono">${r.request_number}</span></td>
                    <td style="font-weight: 500; max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                      ${r.description}
                    </td>
                    <td><span class="micro-tag tag-category">${r.category_name}</span></td>
                    <td><span class="micro-tag ${getPriorityTagClass(r.priority_level)}">[${r.priority_level}]</span></td>
                    <td>${r.building_name} • Rm ${r.room_number}</td>
                    <td>${formatDate(r.request_date)}</td>
                    <td><span class="micro-tag ${getStatusTagClass(r.status_name)}">[${r.status_name}]</span></td>
                    <td>
                      <button class="btn btn-secondary btn-sm" onclick="viewRequesterRequestDetail(${r.request_id})">
                        View Details
                      </button>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `}
      </div>
    </div>
  `;
}

async function loadRequesterRequestsView() {
  const user = state.currentUser;
  if (!user) return;

  const requests = await apiGet(`/requests?requested_by=${user.user_id}&limit=100`);
  const container = document.getElementById('view-container');
  container.innerHTML = `
    <div class="workspace-header">
      <div class="workspace-title-group">
        <h1>My Maintenance Requests</h1>
        <p>Complete status history, technician progress, and feedback evaluation</p>
      </div>
      <button class="btn btn-primary" onclick="openRequesterCreateModal()">
        + Report a Problem
      </button>
    </div>

    <div class="panel">
      <div class="panel-body" style="padding: 0;">
        ${requests.length === 0 ? `
          <div class="empty-state-box">
            <h4>No requests found</h4>
            <p>You have not logged any facility requests yet.</p>
            <button class="btn btn-primary" onclick="openRequesterCreateModal()">+ Report a Problem</button>
          </div>
        ` : `
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Request ID</th>
                  <th>Description</th>
                  <th>Category</th>
                  <th>Priority</th>
                  <th>Location</th>
                  <th>Submitted</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                ${requests.map(r => `
                  <tr>
                    <td><span class="identifier-mono">${r.request_number}</span></td>
                    <td style="font-weight: 500;">${r.description}</td>
                    <td><span class="micro-tag tag-category">${r.category_name}</span></td>
                    <td><span class="micro-tag ${getPriorityTagClass(r.priority_level)}">[${r.priority_level}]</span></td>
                    <td>${r.building_name} • Rm ${r.room_number}</td>
                    <td>${formatDate(r.request_date)}</td>
                    <td><span class="micro-tag ${getStatusTagClass(r.status_name)}">[${r.status_name}]</span></td>
                    <td>
                      <button class="btn btn-secondary btn-sm" onclick="viewRequesterRequestDetail(${r.request_id})">
                        View Details
                      </button>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `}
      </div>
    </div>
  `;
}

function openRequesterCreateModal() {
  openModal('modal-create-request');
  if (state.currentUser && state.currentUser.portal_role === 'requester') {
    const userSelect = document.getElementById('modal-req-user');
    if (userSelect) {
      if (!userSelect.querySelector(`option[value="${state.currentUser.user_id}"]`)) {
        const opt = document.createElement('option');
        opt.value = state.currentUser.user_id;
        opt.textContent = `${state.currentUser.full_name} (${state.currentUser.email})`;
        userSelect.appendChild(opt);
      }
      userSelect.value = state.currentUser.user_id;
      userSelect.closest('.form-group').style.display = 'none';
    }
  } else {
    const userGroup = document.getElementById('modal-req-user')?.closest('.form-group');
    if (userGroup) userGroup.style.display = 'block';
  }
}

async function viewRequesterRequestDetail(requestId) {
  const req = await apiGet(`/requests/${requestId}`);
  const history = await apiGet(`/requests/${requestId}/history`);
  let feedback = null;
  if (req.status_name === 'Closed') {
    try {
      feedback = await apiGet(`/requests/${requestId}/feedback`);
    } catch (e) {
      feedback = null;
    }
  }

  const modalBody = document.getElementById('modal-detail-body');
  if (!modalBody) return;

  const isClosed = req.status_name === 'Closed';

  modalBody.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;">
      <div>
        <h2 style="font-size: 20px; font-weight: 700; margin-bottom: 4px; color: var(--text-primary);">
          ${req.request_number}
        </h2>
        <p style="color: var(--text-secondary); font-size: 13px;">
          ${req.building_name} • Floor ${req.floor || '1'} • Room ${req.room_number}
        </p>
      </div>
      <div>
        <span class="micro-tag ${getStatusTagClass(req.status_name)}" style="font-size: 12px; padding: 4px 10px;">
          [${req.status_name}]
        </span>
      </div>
    </div>

    <!-- Stepper -->
    <div class="stepper-container">
      <div class="step-item ${req.status_name === 'Open' ? 'active' : 'completed'}">
        <div class="step-circle">1</div>
        <div class="step-label">Open</div>
      </div>
      <div class="step-connector ${req.status_name !== 'Open' ? 'completed' : ''}"></div>
      <div class="step-item ${req.status_name === 'Assigned' ? 'active' : (['In Progress', 'On Hold', 'Closed'].includes(req.status_name) ? 'completed' : '')}">
        <div class="step-circle">2</div>
        <div class="step-label">Assigned</div>
      </div>
      <div class="step-connector ${['In Progress', 'On Hold', 'Closed'].includes(req.status_name) ? 'completed' : ''}"></div>
      <div class="step-item ${['In Progress', 'On Hold'].includes(req.status_name) ? 'active' : (req.status_name === 'Closed' ? 'completed' : '')}">
        <div class="step-circle">3</div>
        <div class="step-label">${req.status_name === 'On Hold' ? 'On Hold' : 'In Progress'}</div>
      </div>
      <div class="step-connector ${req.status_name === 'Closed' ? 'completed' : ''}"></div>
      <div class="step-item ${req.status_name === 'Closed' ? 'completed' : ''}">
        <div class="step-circle">4</div>
        <div class="step-label">Closed</div>
      </div>
    </div>

    <div class="detail-grid" style="margin-bottom: 24px;">
      <div class="detail-label">Problem Description</div>
      <div class="detail-value" style="font-weight: 500;">${req.description}</div>

      <div class="detail-label">Category & Priority</div>
      <div class="detail-value">
        <span class="micro-tag tag-category">${req.category_name}</span>
        <span class="micro-tag ${getPriorityTagClass(req.priority_level)}">[${req.priority_level}]</span>
      </div>

      <div class="detail-label">Equipment / Asset</div>
      <div class="detail-value">${req.asset_name ? `${req.asset_name} (${req.asset_tag})` : 'General Facility Fixture'}</div>

      <div class="detail-label">Submission Date</div>
      <div class="detail-value">${formatDate(req.request_date)}</div>

      ${isClosed ? `
        <div class="detail-label" style="color: #1b5e20;">Resolution Summary</div>
        <div class="detail-value" style="font-weight: 600; color: #1b5e20;">
          ${req.resolution_description || 'Work completed successfully.'}
        </div>

        <div class="detail-label">Closed Date</div>
        <div class="detail-value">${formatDate(req.closed_date)}</div>
      ` : ''}
    </div>

    <!-- Feedback Section on Closed Requests -->
    ${isClosed ? `
      <div class="panel" style="margin-bottom: 24px; border-color: #a5d6a7; background-color: #f1f8e9;">
        <div class="panel-header" style="background: transparent; border-bottom: 1px solid #c8e6c9;">
          <div class="panel-title" style="color: #1b5e20;">Service Feedback Evaluation</div>
        </div>
        <div class="panel-body">
          ${feedback ? `
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
              <span style="font-size: 20px; color: #f59e0b; letter-spacing: 2px;">
                ${'★'.repeat(feedback.rating)}${'☆'.repeat(5 - feedback.rating)}
              </span>
              <span style="font-weight: 600; color: #1b5e20;">(${feedback.rating} / 5 Stars)</span>
              <span style="color: var(--text-muted); font-size: 12px;">Submitted on ${formatDate(feedback.feedback_date)}</span>
            </div>
            <p style="font-size: 13px; color: var(--text-secondary); margin: 0;">
              ${feedback.comments ? `"${feedback.comments}"` : '<em>No additional comments provided.</em>'}
            </p>
          ` : `
            <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 12px;">
              This maintenance request has been completed. Please rate the quality and timeliness of the repair service:
            </p>
            <button class="btn btn-primary" onclick="prepareFeedbackFromDetail(${req.request_id})">
              ★ Submit Service Feedback
            </button>
          `}
        </div>
      </div>
    ` : ''}

    <!-- Timeline History -->
    <div style="margin-top: 20px;">
      <h4 style="font-size: 14px; font-weight: 600; margin-bottom: 12px; color: var(--text-primary);">
        Lifecycle Activity History
      </h4>
      <div class="timeline">
        ${history.map(h => `
          <div class="timeline-item">
            <div class="timeline-marker"></div>
            <div class="timeline-content">
              <div class="timeline-header">
                <span class="micro-tag ${getStatusTagClass(h.status_name)}">[${h.status_name}]</span>
                <span class="timeline-time">${formatDate(h.changed_date)}</span>
              </div>
              <div class="timeline-body">
                <strong>${h.changed_by_name || 'System Operator'}:</strong> ${h.remarks || 'Status progressed'}
              </div>
            </div>
          </div>
        `).join('')}
      </div>
    </div>
  `;

  openModal('modal-request-detail');
}

// =============================================================================
// TECHNICIAN PORTAL VIEWS & LOGIC
// =============================================================================

let technicianPollInterval = null;

function isAnyModalOpen() {
  return document.querySelector('.modal-backdrop.active, .modal.active') !== null;
}

function startTechnicianPolling() {
  stopTechnicianPolling();
  technicianPollInterval = setInterval(async () => {
    if (!state.currentUser || state.currentUser.portal_role !== 'technician') {
      stopTechnicianPolling();
      return;
    }
    // Only refresh DOM if user is on technician-dashboard and no modal is active
    if (state.currentView === 'technician-dashboard' && !isAnyModalOpen()) {
      try {
        const data = await apiGet(`/technician/${state.currentUser.technician_id}/dashboard`);
        updateTechnicianDashboardContent(data);
      } catch (err) {
        console.warn('Technician polling error:', err);
      }
    }
  }, 5000);
}

function stopTechnicianPolling() {
  if (technicianPollInterval) {
    clearInterval(technicianPollInterval);
    technicianPollInterval = null;
  }
}

function updateTechnicianDashboardContent(data) {
  const metricsGrid = document.getElementById('tech-metrics-grid');
  const incomingBadge = document.getElementById('tech-incoming-badge');
  const incomingBody = document.getElementById('tech-incoming-body');
  const workordersBody = document.getElementById('tech-workorders-body');

  const incomingList = data.incoming_requests || [];
  const incomingCount = incomingList.length;

  if (metricsGrid) {
    metricsGrid.innerHTML = `
      <div class="metric-card" style="border-top: 3px solid #f59e0b;">
        <div class="metric-label">Incoming Requests</div>
        <div class="metric-value" style="color: #d97706;">${data.counts.incoming_requests ?? incomingCount}</div>
        <div class="metric-subtext">Unassigned trade requests</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Active Work Orders</div>
        <div class="metric-value" style="color: #00684a;">${data.counts.active_jobs}</div>
        <div class="metric-subtext">Assigned / in progress</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Completed Jobs</div>
        <div class="metric-value" style="color: #1b5e20;">${data.counts.completed_jobs}</div>
        <div class="metric-subtext">Resolved repairs</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Total Assigned Jobs</div>
        <div class="metric-value">${data.counts.total_assignments}</div>
        <div class="metric-subtext">Lifetime assigned work orders</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Total Labor Hours</div>
        <div class="metric-value" style="color: #0277bd;">${data.counts.total_hours} hrs</div>
        <div class="metric-subtext">Recorded in work logs</div>
      </div>
    `;
  }

  if (incomingBadge) {
    incomingBadge.textContent = `[${incomingCount} Incoming]`;
    incomingBadge.className = `micro-tag ${incomingCount > 0 ? 'tag-priority-high' : 'tag-status-closed'}`;
  }

  if (incomingBody) {
    if (incomingCount === 0) {
      incomingBody.innerHTML = `
        <div class="empty-state-box">
          <h4>No Incoming Requests</h4>
          <p>There are no unassigned requests in your trade category right now. New requests will appear automatically.</p>
        </div>
      `;
    } else {
      incomingBody.innerHTML = `
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Request #</th>
                <th>Category</th>
                <th>Problem Description</th>
                <th>Location</th>
                <th>Asset</th>
                <th>Priority</th>
                <th>Requester</th>
                <th>Request Date</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${incomingList.map(r => `
                <tr>
                  <td><span class="identifier-mono">${r.request_number}</span></td>
                  <td><span class="micro-tag tag-category">${r.category_name}</span></td>
                  <td style="font-weight: 500; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${r.description || ''}">
                    ${r.description || 'Facility Maintenance'}
                  </td>
                  <td>${r.building_name ? `${r.building_name} • Rm ${r.room_number}` : 'Campus Facility'}</td>
                  <td>${r.asset_name ? `${r.asset_name}` : '—'}</td>
                  <td><span class="micro-tag ${getPriorityTagClass(r.priority_level || 'Normal')}">[${r.priority_level || 'Normal'}]</span></td>
                  <td>${r.requester_name || 'Campus Requester'}</td>
                  <td>${formatDate(r.request_date)}</td>
                  <td><span class="micro-tag tag-status-open">[${r.status_name || 'Open'}]</span></td>
                  <td>
                    <button class="btn btn-secondary btn-sm" onclick="viewRequestDetail(${r.request_id})">
                      View Details
                    </button>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    }
  }

  if (workordersBody) {
    const activeAssignments = (data.assignments || []).filter(a => (a.status || a.assignment_status) !== 'Completed');
    if (activeAssignments.length === 0) {
      workordersBody.innerHTML = `
        <div class="empty-state-box">
          <h4>No active work orders</h4>
          <p>You have no pending or in-progress maintenance assignments right now.</p>
        </div>
      `;
    } else {
      workordersBody.innerHTML = `
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Job #</th>
                <th>Request ID</th>
                <th>Problem Description</th>
                <th>Location</th>
                <th>Priority</th>
                <th>Assigned Date</th>
                <th>Due Date</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${activeAssignments.map(a => {
                const aStatus = a.status || a.assignment_status;
                return `
                <tr>
                  <td><span class="identifier-mono">#${a.assignment_id}</span></td>
                  <td><span class="identifier-mono">${a.request_number}</span></td>
                  <td style="font-weight: 500; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${a.description || a.request_description || ''}">
                    ${a.description || a.request_description || 'Facility Maintenance'}
                  </td>
                  <td>${a.building_name ? `${a.building_name} • Rm ${a.room_number}` : 'Campus Facility'}</td>
                  <td><span class="micro-tag ${getPriorityTagClass(a.priority_level || 'Normal')}">[${a.priority_level || 'Normal'}]</span></td>
                  <td>${formatDate(a.assigned_date)}</td>
                  <td style="font-weight: 600;">${formatDate(a.due_date)}</td>
                  <td><span class="micro-tag ${aStatus === 'In Progress' ? 'tag-status-in-progress' : 'tag-status-assigned'}">[${aStatus}]</span></td>
                  <td>
                    <button class="btn btn-primary btn-sm" onclick="openTechnicianJobModal(${a.assignment_id})">
                      Manage Job
                    </button>
                  </td>
                </tr>
              `}).join('')}
            </tbody>
          </table>
        </div>
      `;
    }
  }
}

async function loadTechnicianDashboardView() {
  const user = state.currentUser;
  if (!user) return;

  const data = await apiGet(`/technician/${user.technician_id}/dashboard`);
  const container = document.getElementById('view-container');
  container.innerHTML = `
    <div class="workspace-header">
      <div class="workspace-title-group">
        <h1>Welcome, ${user.full_name}</h1>
        <p>Field Operations Dashboard • Department: <strong>${user.department}</strong> (Rate: ${formatCurrency(user.labor_rate)}/hr)
           • <span style="display: inline-flex; align-items: center; gap: 4px; color: var(--accent-green); font-size: 11px; font-weight: 600;">
               <span style="display:inline-block; width:7px; height:7px; border-radius:50%; background:#00ed64;"></span> Live Polling (5s)
             </span>
        </p>
      </div>
      <div>
        <button class="btn btn-secondary btn-sm" onclick="loadTechnicianDashboardView()">
          ↻ Refresh Now
        </button>
      </div>
    </div>

    <!-- Metrics Grid -->
    <div class="metrics-grid" id="tech-metrics-grid"></div>

    <!-- Section A: Incoming / Unassigned Requests -->
    <div class="panel" style="margin-bottom: 24px; border-left: 4px solid #f59e0b;">
      <div class="panel-header" style="background-color: rgba(245, 158, 11, 0.04);">
        <div>
          <div class="panel-title" style="display: flex; align-items: center; gap: 8px;">
            <span>Incoming / Unassigned Requests</span>
            <span class="micro-tag tag-priority-high" id="tech-incoming-badge">[0 Incoming]</span>
          </div>
          <p style="font-size: 12px; color: var(--text-secondary); margin: 2px 0 0 0;">
            New unassigned requests in your category awaiting assignment dispatch
          </p>
        </div>
      </div>
      <div class="panel-body" style="padding: 0;" id="tech-incoming-body"></div>
    </div>

    <!-- Section B: My Work Orders -->
    <div class="panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">My Work Orders</div>
          <p style="font-size: 12px; color: var(--text-secondary); margin: 2px 0 0 0;">
            Active technician assignments allocated to you
          </p>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="switchView('technician-assignments')">
          View All Assignments (${data.assignments.length}) →
        </button>
      </div>
      <div class="panel-body" style="padding: 0;" id="tech-workorders-body"></div>
    </div>
  `;

  updateTechnicianDashboardContent(data);
  startTechnicianPolling();
}

async function loadTechnicianAssignmentsView() {
  const user = state.currentUser;
  if (!user) return;

  const assignments = await apiGet(`/assignments?technician_id=${user.technician_id}&limit=100`);
  const container = document.getElementById('view-container');
  container.innerHTML = `
    <div class="workspace-header">
      <div class="workspace-title-group">
        <h1>My Work Order Assignments</h1>
        <p>Manage assigned field tasks, update execution status, and log repair progress</p>
      </div>
    </div>

    <div class="panel">
      <div class="panel-body" style="padding: 0;">
        ${assignments.length === 0 ? `
          <div class="empty-state-box">
            <h4>No assignments found</h4>
            <p>You currently have no assignments registered under your technician profile.</p>
          </div>
        ` : `
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Job #</th>
                  <th>Request ID</th>
                  <th>Description</th>
                  <th>Location</th>
                  <th>Priority</th>
                  <th>Assigned Date</th>
                  <th>Due Date</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                ${assignments.map(a => {
                  const aStatus = a.status || a.assignment_status;
                  return `
                  <tr>
                    <td><span class="identifier-mono">#${a.assignment_id}</span></td>
                    <td><span class="identifier-mono">${a.request_number}</span></td>
                    <td style="font-weight: 500;">${a.description || a.request_description || 'Maintenance repair'}</td>
                    <td>${a.building_name ? `${a.building_name} • Rm ${a.room_number}` : 'Campus Facility'}</td>
                    <td><span class="micro-tag ${getPriorityTagClass(a.priority_level || 'Normal')}">[${a.priority_level || 'Normal'}]</span></td>
                    <td>${formatDate(a.assigned_date)}</td>
                    <td>${formatDate(a.due_date)}</td>
                    <td><span class="micro-tag ${aStatus === 'Completed' ? 'tag-status-closed' : (aStatus === 'In Progress' ? 'tag-status-in-progress' : 'tag-status-assigned')}">[${aStatus}]</span></td>
                    <td>
                      <button class="btn btn-primary btn-sm" onclick="openTechnicianJobModal(${a.assignment_id})">
                        Manage Job
                      </button>
                    </td>
                  </tr>
                `}).join('')}
              </tbody>
            </table>
          </div>
        `}
      </div>
    </div>
  `;
}

async function loadTechnicianWorkLogsView() {
  const user = state.currentUser;
  if (!user) return;

  const workLogs = await apiGet(`/work-logs?technician_id=${user.technician_id}&limit=100`);
  const container = document.getElementById('view-container');
  container.innerHTML = `
    <div class="workspace-header">
      <div class="workspace-title-group">
        <h1>My Recorded Work Logs</h1>
        <p>Labor hours and repair descriptions recorded under your assignments</p>
      </div>
    </div>

    <div class="panel">
      <div class="panel-body" style="padding: 0;">
        ${workLogs.length === 0 ? `
          <div class="empty-state-box">
            <h4>No work logs recorded yet</h4>
            <p>Open an active assignment to record labor hours and repair tasks.</p>
          </div>
        ` : `
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Log #</th>
                  <th>Job #</th>
                  <th>Request ID</th>
                  <th>Work Date</th>
                  <th>Work Description</th>
                  <th>Hours Logged</th>
                </tr>
              </thead>
              <tbody>
                ${workLogs.map(w => `
                  <tr>
                    <td><span class="identifier-mono">#${w.work_log_id}</span></td>
                    <td><span class="identifier-mono">#${w.assignment_id}</span></td>
                    <td><span class="identifier-mono">${w.request_number || '—'}</span></td>
                    <td>${formatDate(w.work_date)}</td>
                    <td style="font-weight: 500;">${w.work_description}</td>
                    <td style="font-weight: 700; color: #00684a;">${w.hours_spent} hrs</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `}
      </div>
    </div>
  `;
}

async function loadTechnicianMaterialsView() {
  const user = state.currentUser;
  if (!user) return;

  const materials = await apiGet(`/materials/usage?technician_id=${user.technician_id}&limit=100`);
  const totalSum = materials.reduce((acc, m) => acc + (parseFloat(m.total_cost || m.calculated_usage_cost || 0)), 0);
  const container = document.getElementById('view-container');
  container.innerHTML = `
    <div class="workspace-header">
      <div class="workspace-title-group">
        <h1>Material Requests & Usage Ledger</h1>
        <p>Locked historical material requests, quantities, unit prices, and financial cost accounting</p>
      </div>
    </div>

    <div class="panel">
      <div class="panel-body" style="padding: 0;">
        ${materials.length === 0 ? `
          <div class="empty-state-box">
            <h4>No material requests recorded</h4>
            <p>You have not requisitioned any materials for your assignments yet.</p>
          </div>
        ` : `
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Material Name</th>
                  <th>Quantity</th>
                  <th>Unit Price</th>
                  <th>Total</th>
                  <th>Request #</th>
                  <th>Issued Date</th>
                  <th>Work Log</th>
                </tr>
              </thead>
              <tbody>
                ${materials.map(m => `
                  <tr>
                    <td style="font-weight: 600;">${m.material_name}</td>
                    <td style="font-weight: 700; color: #001e2b;">${m.quantity_used} ${m.material_unit || ''}</td>
                    <td>${formatCurrency(m.unit_price || m.unit_cost)}</td>
                    <td style="font-weight: 700; color: #00684a;">${formatCurrency(m.total_cost || m.calculated_usage_cost || (m.quantity_used * (m.unit_price || m.unit_cost)))}</td>
                    <td><span class="identifier-mono">${m.request_number || ('Req #' + m.request_id)}</span></td>
                    <td>${formatDate(m.issued_date)}</td>
                    <td><span class="identifier-mono">#${m.work_log_id}</span></td>
                  </tr>
                `).join('')}
              </tbody>
              <tfoot>
                <tr style="background: rgba(0, 104, 74, 0.05); font-weight: 700;">
                  <td colspan="3" style="text-align: right;">Total Material Expenditure:</td>
                  <td style="color: #00684a; font-size: 14px;">${formatCurrency(totalSum)}</td>
                  <td colspan="3"></td>
                </tr>
              </tfoot>
            </table>
          </div>
        `}
      </div>
    </div>
  `;
}

async function openTechnicianJobModal(assignmentId) {
  let assignment;
  try {
    assignment = await apiGet(`/assignments/${assignmentId}`);
  } catch (e) {
    assignment = await apiGet(`/assignments?limit=100`).then(list => list.find(a => a.assignment_id === assignmentId));
  }
  if (!assignment) {
    showToast('Assignment not found', true);
    return;
  }
  if (state.currentUser?.portal_role === 'technician' && assignment.technician_id !== state.currentUser.technician_id) {
    showToast('Access denied: Assignment belongs to another technician', true);
    return;
  }
  const req = await apiGet(`/requests/${assignment.request_id}`);
  const workLogs = await apiGet(`/work-logs?assignment_id=${assignmentId}`);
  const currentTechId = state.currentUser?.technician_id || assignment.technician_id;
  const materials = await apiGet(`/materials/usage?technician_id=${currentTechId}`).then(list => {
    const logIds = new Set(workLogs.map(w => w.work_log_id));
    return list.filter(m => logIds.has(m.work_log_id));
  });

  const modalBody = document.getElementById('tech-job-modal-body');
  document.getElementById('tech-job-modal-title').textContent = `Work Order #${assignmentId} — ${req.request_number}`;

  const assignStatus = assignment.status || assignment.assignment_status;

  modalBody.innerHTML = `
    <!-- Top summary banner -->
    <div style="background-color: var(--ws-bg); border: 1px solid var(--ws-border-subtle); border-radius: var(--radius-md); padding: 16px; margin-bottom: 20px;">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
        <div>
          <h3 style="font-size: 16px; font-weight: 700; color: var(--text-primary); margin-bottom: 4px;">
            ${req.description}
          </h3>
          <p style="font-size: 13px; color: var(--text-secondary); margin: 0;">
            ${req.building_name} • Rm ${req.room_number} | Requester: ${req.requester_name || 'Campus Member'}
          </p>
        </div>
        <div style="display: flex; gap: 6px;">
          <span class="micro-tag ${getPriorityTagClass(req.priority_level)}">[${req.priority_level}]</span>
          <span class="micro-tag ${getStatusTagClass(req.status_name)}">[Req: ${req.status_name}]</span>
          <span class="micro-tag ${assignStatus === 'Completed' ? 'tag-status-closed' : (assignStatus === 'In Progress' ? 'tag-status-in-progress' : 'tag-status-assigned')}">[Job: ${assignStatus}]</span>
        </div>
      </div>
      <div style="font-size: 12px; color: var(--text-muted); display: flex; gap: 20px;">
        <span>Assigned: ${formatDate(assignment.assigned_date)}</span>
        <span>Due Target: <strong style="color: var(--text-primary);">${formatDate(assignment.due_date)}</strong></span>
      </div>
    </div>

    <!-- Quick Status Transition Buttons -->
    <div style="margin-bottom: 24px;">
      <h4 style="font-size: 13px; font-weight: 600; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px;">
        Operational Status Actions
      </h4>
      <div style="display: flex; gap: 10px; flex-wrap: wrap;">
        ${assignStatus === 'Assigned' ? `
          <button class="btn btn-primary btn-sm" onclick="technicianAdvanceJobStatus(${assignmentId}, ${req.request_id}, 'In Progress')">
            ▶ Start Work (In Progress)
          </button>
        ` : ''}

        ${req.status_name === 'In Progress' ? `
          <button class="btn btn-secondary btn-sm" onclick="technicianSetRequestStatus(${req.request_id}, 'On Hold', ${assignmentId})">
            ⏸ Place Request On Hold
          </button>
        ` : ''}

        ${req.status_name === 'On Hold' ? `
          <button class="btn btn-primary btn-sm" onclick="technicianSetRequestStatus(${req.request_id}, 'In Progress', ${assignmentId})">
            ▶ Resume Work (In Progress)
          </button>
        ` : ''}

        ${assignStatus !== 'Completed' ? `
          <button class="btn btn-secondary btn-sm" style="border-color: #00684a; color: #00684a;" onclick="technicianMarkJobCompleted(${assignmentId})">
            ✓ Mark Assignment Completed
          </button>
        ` : `
          <span class="micro-tag tag-status-closed" style="padding: 6px 12px;">✓ Assignment Completed</span>
        `}
      </div>
    </div>

    <!-- Tabbed Sections: Work Logs & Materials -->
    <div class="tabs-header" style="margin-bottom: 16px;">
      <button class="tab-btn active" id="tech-tab-logs-btn" onclick="toggleTechJobTab('logs')">
        Labor Work Logs (${workLogs.length})
      </button>
      <button class="tab-btn" id="tech-tab-materials-btn" onclick="toggleTechJobTab('materials')">
        Material Requests (${materials.length})
      </button>
    </div>

    <!-- Tab 1: Work Logs -->
    <div id="tech-tab-logs">
      <div class="table-responsive" style="margin-bottom: 16px;">
        <table class="data-table">
          <thead>
            <tr>
              <th>Log #</th>
              <th>Date</th>
              <th>Work Description</th>
              <th>Hours Spent</th>
            </tr>
          </thead>
          <tbody>
            ${workLogs.length === 0 ? `
              <tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No labor logs recorded yet for this job.</td></tr>
            ` : workLogs.map(w => `
              <tr>
                <td><span class="identifier-mono">#${w.work_log_id}</span></td>
                <td>${formatDate(w.work_date)}</td>
                <td style="font-weight: 500;">${w.work_description}</td>
                <td style="font-weight: 700; color: #00684a;">${w.hours_spent} hrs</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>

      <!-- Add Work Log Form -->
      <div style="background-color: var(--ws-bg); border: 1px solid var(--ws-border-subtle); border-radius: var(--radius-md); padding: 16px;">
        <h5 style="font-size: 13px; font-weight: 600; margin-bottom: 12px; color: var(--text-primary);">
          + Record Labor Hours
        </h5>
        <form onsubmit="event.preventDefault(); technicianSubmitWorkLog(${assignmentId});">
          <div class="form-grid-2">
            <div class="form-group">
              <label style="font-size: 12px;">Work Description *</label>
              <input type="text" id="tech-wl-desc" class="form-control" placeholder="e.g. Replaced ballast and tested circuit" required>
            </div>
            <div class="form-group">
              <label style="font-size: 12px;">Hours Spent *</label>
              <input type="number" id="tech-wl-hours" class="form-control" step="0.25" min="0.25" placeholder="e.g. 1.5" required>
            </div>
          </div>
          <button type="submit" class="btn btn-primary btn-sm" style="margin-top: 8px;">
            Save Work Log
          </button>
        </form>
      </div>
    </div>

    <!-- Tab 2: Material Requests -->
    <div id="tech-tab-materials" style="display: none;">
      <div class="table-responsive" style="margin-bottom: 16px;">
        <table class="data-table">
          <thead>
            <tr>
              <th>Material Name</th>
              <th>Quantity</th>
              <th>Unit Price</th>
              <th>Total</th>
              <th>Date</th>
            </tr>
          </thead>
          <tbody>
            ${materials.length === 0 ? `
              <tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 16px;">No material requests recorded yet for this work order.</td></tr>
            ` : materials.map(m => `
              <tr>
                <td style="font-weight: 600;">${m.material_name}</td>
                <td style="font-weight: 700;">${m.quantity_used} ${m.material_unit || ''}</td>
                <td>${formatCurrency(m.unit_price || m.unit_cost)}</td>
                <td style="font-weight: 700; color: #00684a;">${formatCurrency(m.total_cost || m.calculated_usage_cost || (m.quantity_used * (m.unit_price || m.unit_cost)))}</td>
                <td>${formatDate(m.issued_date)}</td>
              </tr>
            `).join('')}
          </tbody>
          ${materials.length > 0 ? `
            <tfoot>
              <tr style="background: rgba(0, 104, 74, 0.05); font-weight: 700;">
                <td colspan="3" style="text-align: right;">Total Material Expenditure:</td>
                <td style="color: #00684a; font-size: 14px;">${formatCurrency(materials.reduce((acc, m) => acc + parseFloat(m.total_cost || m.calculated_usage_cost || 0), 0))}</td>
                <td></td>
              </tr>
            </tfoot>
          ` : ''}
        </table>
      </div>

      <!-- Submit Material Request Form -->
      <div style="background-color: var(--ws-bg); border: 1px solid var(--ws-border-subtle); border-radius: var(--radius-md); padding: 16px;">
        <h5 style="font-size: 13px; font-weight: 600; margin-bottom: 12px; color: var(--text-primary);">
          + Submit Material Request
        </h5>
        <form onsubmit="event.preventDefault(); technicianSubmitMaterialRequest(${assignmentId});">
          <div class="form-grid-2">
            <div class="form-group">
              <label style="font-size: 12px;">Material Name *</label>
              <input type="text" id="tech-mat-name" list="warehouse-materials-list" class="form-control" placeholder="e.g. Copper Wire, PVC Pipe..." required oninput="onTechMaterialNameChange()">
              <datalist id="warehouse-materials-list">
                ${(state.lookups?.materials || []).map(m => `
                  <option value="${m.material_name}">${m.material_name} (₹${m.unit_cost}/${m.unit})</option>
                `).join('')}
              </datalist>
            </div>
            <div class="form-group">
              <label style="font-size: 12px;">Quantity *</label>
              <input type="number" id="tech-mat-qty" class="form-control" step="1" min="1" placeholder="e.g. 2" required oninput="updateTechMaterialTotalPreview()">
            </div>
          </div>
          <div class="form-grid-2">
            <div class="form-group">
              <label style="font-size: 12px;">Unit Price (₹) *</label>
              <input type="number" id="tech-mat-unit-price" class="form-control" step="0.5" min="0" placeholder="e.g. 450" required oninput="updateTechMaterialTotalPreview()">
            </div>
            <div class="form-group">
              <label style="font-size: 12px;">Recorded Total (Calculated)</label>
              <div id="tech-mat-total-preview" style="padding: 9px 12px; background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); font-weight: 700; color: #00684a; font-size: 13px;">
                ₹0.00
              </div>
            </div>
          </div>
          <div style="display: flex; justify-content: flex-end; margin-top: 12px;">
            <button type="submit" class="btn btn-primary btn-sm">
              Submit Material Request
            </button>
          </div>
        </form>
      </div>
    </div>
  `;

  openModal('modal-technician-job');
}

function updateTechMaterialTotalPreview() {
  const qty = parseFloat(document.getElementById('tech-mat-qty')?.value) || 0;
  const price = parseFloat(document.getElementById('tech-mat-unit-price')?.value) || 0;
  const total = qty * price;
  const previewEl = document.getElementById('tech-mat-total-preview');
  if (previewEl) {
    previewEl.textContent = formatCurrency(total);
  }
}

function onTechMaterialNameChange() {
  const nameInput = document.getElementById('tech-mat-name');
  const priceInput = document.getElementById('tech-mat-unit-price');
  if (!nameInput || !priceInput) return;
  const selectedName = nameInput.value.trim().toLowerCase();
  const matched = (state.lookups?.materials || []).find(m => m.material_name.toLowerCase() === selectedName);
  if (matched && (!priceInput.value || parseFloat(priceInput.value) === 0)) {
    priceInput.value = matched.unit_cost;
  }
  updateTechMaterialTotalPreview();
}

async function technicianSubmitMaterialRequest(assignmentId) {
  const name = document.getElementById('tech-mat-name')?.value?.trim();
  const qty = parseFloat(document.getElementById('tech-mat-qty')?.value);
  const unitPrice = parseFloat(document.getElementById('tech-mat-unit-price')?.value);
  if (!name) {
    showToast('Please enter a valid material name', true);
    return;
  }
  if (isNaN(qty) || qty <= 0) {
    showToast('Quantity must be greater than zero', true);
    return;
  }
  if (isNaN(unitPrice) || unitPrice < 0) {
    showToast('Unit price must be non-negative', true);
    return;
  }

  try {
    const res = await apiPost('/technician/material-requests', {
      assignment_id: assignmentId,
      material_name: name,
      quantity: qty,
      unit_price: unitPrice,
      technician_id: state.currentUser?.technician_id,
    });
    showToast(`Material "${name}" (Qty: ${qty} @ ₹${unitPrice}) recorded! Total: ₹${res.total}`);
    state.lookups = await apiGet('/lookups');
    await openTechnicianJobModal(assignmentId);
    if (state.currentView.includes('technician')) await switchView(state.currentView);
  } catch (err) {
    console.error('Failed to submit material request:', err);
  }
}

function toggleTechJobTab(tab) {
  const logsTab = document.getElementById('tech-tab-logs');
  const matsTab = document.getElementById('tech-tab-materials');
  const logsBtn = document.getElementById('tech-tab-logs-btn');
  const matsBtn = document.getElementById('tech-tab-materials-btn');

  if (tab === 'logs') {
    logsTab.style.display = 'block';
    matsTab.style.display = 'none';
    logsBtn.classList.add('active');
    matsBtn.classList.remove('active');
  } else {
    logsTab.style.display = 'none';
    matsTab.style.display = 'block';
    logsBtn.classList.remove('active');
    matsBtn.classList.add('active');
  }
}

async function technicianAdvanceJobStatus(assignmentId, requestId, newStatus) {
  try {
    await apiPatch(`/assignments/${assignmentId}`, {
      status: newStatus,
      technician_id: state.currentUser?.technician_id,
    });
    await apiPost(`/requests/${requestId}/status`, {
      new_status: newStatus,
      changed_by: 1, // User ID recorded in status history
      remarks: `Technician started work on Assignment #${assignmentId}`,
    });
    showToast(`Work Order #${assignmentId} is now In Progress!`);
    await openTechnicianJobModal(assignmentId);
    if (state.currentView.includes('technician')) await switchView(state.currentView);
  } catch (err) {
    console.error('Failed to advance job status:', err);
  }
}

async function technicianSetRequestStatus(requestId, newStatus, assignmentId) {
  try {
    await apiPost(`/requests/${requestId}/status`, {
      new_status: newStatus,
      changed_by: 1,
      remarks: `Technician transitioned request to ${newStatus}`,
    });
    showToast(`Request status moved to ${newStatus}`);
    await openTechnicianJobModal(assignmentId);
    if (state.currentView.includes('technician')) await switchView(state.currentView);
  } catch (err) {
    console.error('Failed to set request status:', err);
  }
}

async function technicianMarkJobCompleted(assignmentId) {
  try {
    await apiPatch(`/assignments/${assignmentId}`, {
      status: 'Completed',
      technician_id: state.currentUser?.technician_id,
      resolution_description: `Completed by technician ${state.currentUser?.full_name}`,
    });
    showToast(`Assignment #${assignmentId} marked as Completed! Request lifecycle updated to Closed.`);
    await openTechnicianJobModal(assignmentId);
    if (state.currentView.includes('technician')) await switchView(state.currentView);
  } catch (err) {
    console.error('Failed to mark assignment completed:', err);
  }
}

async function technicianSubmitWorkLog(assignmentId) {
  const desc = document.getElementById('tech-wl-desc').value;
  const hours = parseFloat(document.getElementById('tech-wl-hours').value);

  try {
    await apiPost('/work-logs', {
      assignment_id: assignmentId,
      work_description: desc,
      hours_spent: hours,
      work_date: new Date().toISOString(),
    });
    showToast('Work hours recorded successfully!');
    await openTechnicianJobModal(assignmentId);
    if (state.currentView.includes('technician')) await switchView(state.currentView);
  } catch (err) {
    console.error('Failed to submit work log:', err);
  }
}

async function technicianSubmitMaterialUsage(assignmentId) {
  const material_id = parseInt(document.getElementById('tech-mat-id').value, 10);
  const quantity_used = parseFloat(document.getElementById('tech-mat-qty').value);
  const work_log_id = parseInt(document.getElementById('tech-mat-wl-id').value, 10);

  try {
    await apiPost('/materials/usage', {
      work_log_id,
      material_id,
      quantity_used,
      issued_by: state.currentUser.technician_id,
      issued_date: new Date().toISOString(),
      description: `Requisitioned by technician ${state.currentUser.full_name}`,
    });
    showToast('Material issued and warehouse stock decremented!');
    state.lookups = await apiGet('/lookups');
    await openTechnicianJobModal(assignmentId);
    if (state.currentView.includes('technician')) await switchView(state.currentView);
  } catch (err) {
    console.error('Failed to submit material usage:', err);
  }
}

function setupEventHandlers() {
  document.getElementById('form-create-request')?.addEventListener('submit', submitCreateRequest);
  document.getElementById('form-close-request')?.addEventListener('submit', submitCloseRequest);
  document.getElementById('form-feedback')?.addEventListener('submit', submitFeedback);
  document.getElementById('form-requisition')?.addEventListener('submit', submitRequisition);
  document.getElementById('form-worklog')?.addEventListener('submit', submitWorkLog);
  document.getElementById('form-assignment')?.addEventListener('submit', submitCreateAssignment);
}

// Launch
document.addEventListener('DOMContentLoaded', initApp);
