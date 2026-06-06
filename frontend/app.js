// Main UI script

const API_BASE = '';
let currentReview = null;

// View Navigation

document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const viewName = btn.dataset.view;
        switchView(viewName);
    });
});

function switchView(viewName) {
    // Update nav buttons
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`[data-view="${viewName}"]`)?.classList.add('active');

    // Update views
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(`view-${viewName}`)?.classList.add('active');

    // Load data for the view
    if (viewName === 'history') loadHistory();
    if (viewName === 'stats') loadStats();
}

// Form Submission

async function submitReview() {
    const input = document.getElementById('pr-url-input');
    const url = input.value.trim();

    if (!url) {
        showInputError('Please enter a GitHub PR URL');
        return;
    }

    if (!isValidPRUrl(url)) {
        showInputError('Invalid URL. Use format: https://github.com/owner/repo/pull/123');
        return;
    }

    showLoading();

    try {
        const response = await fetch(`${API_BASE}/api/review`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pr_url: url }),
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        const review = await response.json();
        currentReview = review;
        showResults(review);

    } catch (error) {
        showError(error.message);
    }
}

function isValidPRUrl(url) {
    return /(?:https?:\/\/)?github\.com\/[^/]+\/[^/]+\/pull\/\d+/.test(url);
}

// Allow Enter key to submit
document.getElementById('pr-url-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') submitReview();
});

// State Management

function showInputError(message) {
    const hint = document.getElementById('input-hint');
    hint.textContent = message;
    hint.classList.add('error');
    setTimeout(() => {
        hint.textContent = 'Supports any public GitHub repository';
        hint.classList.remove('error');
    }, 3000);
}

function showLoading() {
    const btn = document.getElementById('review-btn');
    btn.classList.add('loading');
    btn.disabled = true;

    document.getElementById('loading-section').classList.remove('hidden');
    document.getElementById('results-section').classList.add('hidden');
    document.getElementById('error-section').classList.add('hidden');

    setStatus('loading', 'Reviewing...');
}

function showResults(review) {
    document.getElementById('loading-section').classList.add('hidden');
    document.getElementById('error-section').classList.add('hidden');
    document.getElementById('results-section').classList.remove('hidden');

    const btn = document.getElementById('review-btn');
    btn.classList.remove('loading');
    btn.disabled = false;

    setStatus('ready', 'Ready');
    renderResults(review);
}

function showError(message) {
    document.getElementById('loading-section').classList.add('hidden');
    document.getElementById('results-section').classList.add('hidden');
    document.getElementById('error-section').classList.remove('hidden');

    document.getElementById('error-message').textContent = message;

    const btn = document.getElementById('review-btn');
    btn.classList.remove('loading');
    btn.disabled = false;

    setStatus('error', 'Error');
}

function resetView() {
    document.getElementById('results-section').classList.add('hidden');
    document.getElementById('error-section').classList.add('hidden');
    document.getElementById('loading-section').classList.add('hidden');

    document.getElementById('pr-url-input').value = '';
    document.getElementById('pr-url-input').focus();
    setStatus('ready', 'Ready');
    currentReview = null;
}

function setStatus(state, text) {
    const dot = document.getElementById('status-dot');
    const label = document.getElementById('status-text');
    dot.className = 'status-dot';
    if (state === 'loading') dot.classList.add('loading');
    if (state === 'error') dot.classList.add('error');
    label.textContent = text;
}

// Render Results

function renderResults(review) {
    // PR header
    document.getElementById('result-repo').textContent = review.pr.repo_full_name;
    document.getElementById('result-title').textContent = review.pr.title || 'Untitled PR';
    document.getElementById('result-author').textContent = `by ${review.pr.author}`;
    document.getElementById('result-branches').textContent =
        `${review.pr.head_branch} → ${review.pr.base_branch}`;
    document.getElementById('result-time').textContent =
        `${review.stats.review_time_seconds}s · ${review.stats.files_reviewed} files`;

    // Summary
    document.getElementById('summary-text').textContent = review.summary;

    // Severity counts
    const counts = { critical: 0, warning: 0, info: 0, suggestion: 0 };
    review.findings.forEach(f => { counts[f.severity]++; });

    document.querySelector('#stat-critical .stat-count').textContent = counts.critical;
    document.querySelector('#stat-warning .stat-count').textContent = counts.warning;
    document.querySelector('#stat-info .stat-count').textContent = counts.info;
    document.querySelector('#stat-suggestion .stat-count').textContent = counts.suggestion;

    // Reset filter
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    document.querySelector('[data-filter="all"]').classList.add('active');

    // Render findings
    renderFindings(review.findings);
}

function renderFindings(findings) {
    const container = document.getElementById('findings-list');

    if (findings.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🎉</div>
                <p>No issues found! This code looks great.</p>
            </div>
        `;
        return;
    }

    // Sort: critical > warning > info > suggestion
    const priority = { critical: 0, warning: 1, info: 2, suggestion: 3 };
    const sorted = [...findings].sort((a, b) => priority[a.severity] - priority[b.severity]);

    container.innerHTML = sorted.map((finding, index) => `
        <div class="finding-card severity-${finding.severity}" data-category="${finding.category}" id="finding-${index}">
            <div class="finding-header" onclick="toggleFinding(${index})">
                <div class="finding-left">
                    <div class="finding-title-row">
                        <span class="severity-badge ${finding.severity}">${finding.severity}</span>
                        <span class="category-badge">${finding.category}</span>
                        <span class="finding-title">${escapeHtml(finding.title)}</span>
                    </div>
                    <div class="finding-file">
                        ${escapeHtml(finding.file)}${finding.line_start ? `:${finding.line_start}` : ''}${finding.line_end && finding.line_end !== finding.line_start ? `-${finding.line_end}` : ''}
                    </div>
                </div>
                <div class="finding-chevron">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                        <path d="M4 6L8 10L12 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </div>
            </div>
            <div class="finding-body">
                <div class="finding-description">${escapeHtml(finding.description)}</div>
                ${finding.suggestion ? `
                    <div class="finding-suggestion">
                        <div class="finding-suggestion-label">💡 Suggested Fix</div>
                        <div class="finding-suggestion-text">${escapeHtml(finding.suggestion)}</div>
                    </div>
                ` : ''}
                ${finding.code_snippet ? `
                    <pre class="finding-code">${escapeHtml(finding.code_snippet)}</pre>
                ` : ''}
            </div>
        </div>
    `).join('');
}

function toggleFinding(index) {
    const card = document.getElementById(`finding-${index}`);
    card.classList.toggle('expanded');
}

function filterFindings(category) {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`[data-filter="${category}"]`).classList.add('active');

    if (!currentReview) return;

    const filtered = category === 'all'
        ? currentReview.findings
        : currentReview.findings.filter(f => f.category === category);

    renderFindings(filtered);
}

// History Tab

async function loadHistory() {
    try {
        const response = await fetch(`${API_BASE}/api/reviews`);
        const reviews = await response.json();
        renderHistory(reviews);
    } catch (error) {
        console.error('Failed to load history:', error);
    }
}

function renderHistory(reviews) {
    const container = document.getElementById('history-list');

    if (!reviews || reviews.length === 0) {
        container.innerHTML = `
            <div class="empty-state" id="history-empty">
                <div class="empty-icon">📋</div>
                <p>No reviews yet. Submit a PR to get started!</p>
            </div>
        `;
        return;
    }

    container.innerHTML = reviews.map(review => `
        <div class="history-item" onclick="viewHistoryReview('${review.id}')">
            <div class="history-left">
                <div class="history-title">${escapeHtml(review.pr_title || 'Untitled PR')}</div>
                <div class="history-repo">${escapeHtml(review.repo)}</div>
            </div>
            <div class="history-right">
                <div class="history-findings">
                    ${review.critical_count > 0 ? `<span class="history-badge critical">${review.critical_count} critical</span>` : ''}
                    ${review.warning_count > 0 ? `<span class="history-badge warning">${review.warning_count} warnings</span>` : ''}
                    <span style="font-size: 13px; color: var(--text-muted)">${review.total_findings} total</span>
                </div>
            </div>
        </div>
    `).join('');
}

async function viewHistoryReview(reviewId) {
    try {
        const response = await fetch(`${API_BASE}/api/reviews/${reviewId}`);
        const review = await response.json();
        currentReview = review;

        switchView('review');
        document.getElementById('results-section').classList.remove('hidden');
        renderResults(review);
    } catch (error) {
        console.error('Failed to load review:', error);
    }
}

// Analytics Tab

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/api/stats`);
        const stats = await response.json();
        renderStats(stats);
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

function renderStats(stats) {
    document.getElementById('analytics-total-reviews').textContent = stats.total_reviews;
    document.getElementById('analytics-total-findings').textContent = stats.total_findings;
    document.getElementById('analytics-critical').textContent = stats.total_critical;
    document.getElementById('analytics-avg-time').textContent = `${stats.avg_review_time}s`;
    document.getElementById('analytics-avg-findings').textContent = stats.avg_findings_per_review;
    document.getElementById('analytics-warnings').textContent = stats.total_warnings;
}

// Helpers

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// Init

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('pr-url-input').focus();
    init3DBackground();
});

// 3D Background Rain Animation
function init3DBackground() {
    const canvas = document.getElementById('bg-canvas');
    if (!canvas) return;

    // Check if THREE is loaded
    if (typeof THREE === 'undefined') {
        console.error('Three.js is not loaded.');
        return;
    }

    // 1. Scene setup
    const scene = new THREE.Scene();

    // 2. Camera setup
    const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.z = 15;

    // 3. Renderer setup
    const renderer = new THREE.WebGLRenderer({
        canvas: canvas,
        alpha: true,      // Transparent background so body background shows
        antialias: true
    });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    // 4. Lights (necessary for standard materials, making it feel fully 3D)
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.6);
    dirLight1.position.set(5, 15, 7);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x818cf8, 0.4); // soft purple/indigo tint
    dirLight2.position.set(-5, -5, 5);
    scene.add(dirLight2);

    // 5. Generate Textures for the symbols (no coin backing)
    const textures = {
        github: createSymbolTexture('github'),
        branch: createSymbolTexture('branch'),
        pr: createSymbolTexture('pr'),
        merge: createSymbolTexture('merge')
    };

    function createSymbolTexture(type) {
        const canvas = document.createElement('canvas');
        canvas.width = 256;
        canvas.height = 256;
        const ctx = canvas.getContext('2d');

        // Clear canvas with full transparency (original symbol only)
        ctx.clearRect(0, 0, 256, 256);

        // Beautiful metallic/glowing gradient matching the theme
        const grad = ctx.createLinearGradient(30, 30, 226, 226);
        grad.addColorStop(0, '#818cf8');   // light indigo
        grad.addColorStop(0.5, '#6366f1'); // primary indigo
        grad.addColorStop(1, '#8b5cf6');   // purple

        ctx.fillStyle = grad;
        ctx.strokeStyle = grad;
        ctx.lineWidth = 14;                // bold visible outline
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';

        // Add a subtle drop shadow to simulate a soft glow
        ctx.shadowColor = 'rgba(99, 102, 241, 0.4)';
        ctx.shadowBlur = 12;

        if (type === 'github') {
            // Official GitHub Octocat silhouette path
            const pathData = "M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.341-3.369-1.341-.454-1.155-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025.55-.153 1.137-.23 1.715-.233.578.003 1.165.08 1.715.233 1.91-1.294 2.75-1.025 2.75-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C17.137 20.166 20 16.42 20 12c0-5.523-4.477-10-10-10z";
            const path = new Path2D(pathData);
            ctx.save();
            ctx.translate(128 - 95, 128 - 95);
            ctx.scale(7.9, 7.9); // scale standard 24px path to fill canvas
            ctx.fill(path);
            ctx.restore();
        } else if (type === 'branch') {
            ctx.beginPath();
            ctx.moveTo(90, 60);
            ctx.lineTo(90, 196);
            ctx.stroke();

            ctx.beginPath();
            ctx.moveTo(90, 140);
            ctx.bezierCurveTo(90, 100, 170, 110, 170, 70);
            ctx.stroke();

            // Nodes
            ctx.beginPath();
            ctx.arc(90, 60, 15, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();

            ctx.beginPath();
            ctx.arc(90, 196, 15, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();

            ctx.beginPath();
            ctx.arc(170, 70, 15, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
        } else if (type === 'pr') {
            ctx.beginPath();
            ctx.moveTo(85, 60);
            ctx.lineTo(85, 196);
            ctx.stroke();

            ctx.beginPath();
            ctx.moveTo(170, 100);
            ctx.lineTo(170, 196);
            ctx.stroke();

            ctx.beginPath();
            ctx.moveTo(85, 140);
            ctx.bezierCurveTo(85, 100, 170, 120, 170, 100);
            ctx.stroke();

            // Nodes
            ctx.beginPath();
            ctx.arc(85, 60, 15, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();

            ctx.beginPath();
            ctx.arc(85, 196, 15, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();

            ctx.beginPath();
            ctx.arc(170, 196, 15, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
        } else if (type === 'merge') {
            ctx.beginPath();
            ctx.moveTo(90, 60);
            ctx.lineTo(90, 196);
            ctx.stroke();

            ctx.beginPath();
            ctx.moveTo(170, 110);
            ctx.bezierCurveTo(170, 140, 90, 130, 90, 155);
            ctx.stroke();

            // Nodes
            ctx.beginPath();
            ctx.arc(90, 60, 15, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();

            ctx.beginPath();
            ctx.arc(90, 196, 15, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();

            ctx.beginPath();
            ctx.arc(170, 110, 15, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
        }

        const texture = new THREE.CanvasTexture(canvas);
        texture.minFilter = THREE.LinearFilter;
        return texture;
    }

    // 6. Geometry & Material (Double-sided plane to render original symbols)
    const symbolGeom = new THREE.PlaneGeometry(1.6, 1.6);

    // 7. Spawn symbols
    const particles = [];
    const numParticles = 48; // perfect balance for rich coverage
    const symbolTypes = ['github', 'branch', 'pr', 'merge'];

    for (let i = 0; i < numParticles; i++) {
        const type = symbolTypes[Math.floor(Math.random() * symbolTypes.length)];
        const texture = textures[type];

        // Create specific material for this symbol plane
        const material = new THREE.MeshStandardMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide,  // Render symbol on front & back
            metalness: 0.1,
            roughness: 0.5,
            opacity: 0.65,           // Semi-transparent so it remains clean in the background
            depthWrite: false        // Prevents ugly blocky transparency sorting borders
        });

        const mesh = new THREE.Mesh(symbolGeom, material);
        scene.add(mesh);

        const particleData = {
            mesh: mesh,
            yVelocity: 0,
            rotXSpeed: 0,
            rotYSpeed: 0,
            rotZSpeed: 0
        };

        // Initialize position (distribute initially across height)
        resetParticle(particleData, true);
        particles.push(particleData);
    }

    function resetParticle(particleData, initial = false) {
        const z = Math.random() * 12 - 9; // depth from -9 to +3
        const fovRad = (camera.fov * Math.PI) / 360;
        const visibleHeight = 2 * Math.tan(fovRad) * (camera.position.z - z);
        const visibleWidth = visibleHeight * camera.aspect;

        particleData.mesh.position.z = z;
        particleData.mesh.position.x = (Math.random() - 0.5) * (visibleWidth + 2);

        if (initial) {
            // Randomly scatter vertically at startup
            particleData.mesh.position.y = (Math.random() - 0.5) * (visibleHeight + 4);
        } else {
            // Spawn above top edge
            particleData.mesh.position.y = visibleHeight / 2 + 1.5;
        }

        // Falling velocity (faster for closer objects due to Z depth projection)
        const zNormalized = (z + 9) / 12; // 0 (far) to 1 (near)
        particleData.yVelocity = 0.015 + zNormalized * 0.025 + Math.random() * 0.015;

        // Tumbling speeds (planes spin and twist in 3D space)
        particleData.rotXSpeed = 0.01 + Math.random() * 0.02;
        particleData.rotYSpeed = 0.005 + Math.random() * 0.015;
        particleData.rotZSpeed = (Math.random() - 0.5) * 0.01;

        // Scale based on depth
        const scale = 0.5 + zNormalized * 0.5; // scale from 0.5 to 1.0
        particleData.mesh.scale.set(scale, scale, scale);

        // Random starting rotation
        particleData.mesh.rotation.set(
            Math.random() * Math.PI,
            Math.random() * Math.PI,
            Math.random() * Math.PI
        );
    }

    // 8. Animation loop
    function animate() {
        requestAnimationFrame(animate);

        particles.forEach(particleData => {
            // Move down
            particleData.mesh.position.y -= particleData.yVelocity;

            // Apply rotations
            particleData.mesh.rotation.x += particleData.rotXSpeed;
            particleData.mesh.rotation.y += particleData.rotYSpeed;
            particleData.mesh.rotation.z += particleData.rotZSpeed;

            // Reset when falling below bottom
            const fovRad = (camera.fov * Math.PI) / 360;
            const visibleHeight = 2 * Math.tan(fovRad) * (camera.position.z - particleData.mesh.position.z);
            if (particleData.mesh.position.y < -visibleHeight / 2 - 1.5) {
                resetParticle(particleData, false);
            }
        });

        renderer.render(scene, camera);
    }

    animate();

    // 9. Handle window resizing
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    });
}

