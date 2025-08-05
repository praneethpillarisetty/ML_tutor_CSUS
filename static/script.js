// API base URL
const API_BASE = '';

// Utility function to show toast notifications
function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toastContainer') || createToastContainer();
    
    const toastId = 'toast-' + Date.now();
    const toast = document.createElement('div');
    toast.id = toastId;
    toast.className = `toast align-items-center text-bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // Remove toast element after it's hidden
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '1100';
    document.body.appendChild(container);
    return container;
}

// Add progress log
document.getElementById('addLogForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const formData = {
        email: document.getElementById('email').value,
        student_id: document.getElementById('studentId').value,
        week: document.getElementById('week').value,
        exercise: document.getElementById('exercise').value,
        status: document.getElementById('status').value,
        feedback: document.getElementById('feedback').value
    };
    
    try {
        const response = await fetch(`${API_BASE}/log`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showToast('Progress log added successfully!', 'success');
            this.reset();
            // Refresh the logs display
            fetchLogs();
        } else {
            showToast(`Error: ${result.error}`, 'danger');
        }
    } catch (error) {
        showToast(`Network error: ${error.message}`, 'danger');
    }
});

// Fetch and display logs
async function fetchLogs(filters = {}) {
    try {
        let url = `${API_BASE}/logs`;
        const params = new URLSearchParams();
        
        if (filters.email) params.append('email', filters.email);
        if (filters.student_id) params.append('student_id', filters.student_id);
        if (filters.week) params.append('week', filters.week);
        
        if (params.toString()) {
            url += '?' + params.toString();
        }
        
        const response = await fetch(url);
        const result = await response.json();
        
        if (response.ok) {
            displayLogs(result.logs, result.total_count);
        } else {
            showToast(`Error fetching logs: ${result.error}`, 'danger');
        }
    } catch (error) {
        showToast(`Network error: ${error.message}`, 'danger');
    }
}

// Display logs in a table
function displayLogs(logs, totalCount) {
    const container = document.getElementById('resultsContainer');
    const countBadge = document.getElementById('resultCount');
    
    countBadge.textContent = `${totalCount} entries`;
    
    if (logs.length === 0) {
        container.innerHTML = `
            <div class="text-center text-muted">
                <i class="bi bi-inbox display-1"></i>
                <p class="mt-2">No logs found matching the current filters.</p>
            </div>
        `;
        return;
    }
    
    let tableHTML = `
        <div class="table-responsive">
            <table class="table table-striped table-hover">
                <thead class="table-dark">
                    <tr>
                        <th>Email</th>
                        <th>Student ID</th>
                        <th>Week</th>
                        <th>Exercise</th>
                        <th>Status</th>
                        <th>Feedback</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    logs.forEach(log => {
        const statusBadge = getStatusBadge(log.Status);
        tableHTML += `
            <tr>
                <td>${log.Email}</td>
                <td><code>${log['Student ID']}</code></td>
                <td>${log.Week}</td>
                <td><strong>${log.Exercise}</strong></td>
                <td>${statusBadge}</td>
                <td class="text-truncate" style="max-width: 200px;" title="${log.Feedback}">${log.Feedback}</td>
            </tr>
        `;
    });
    
    tableHTML += `
                </tbody>
            </table>
        </div>
    `;
    
    container.innerHTML = tableHTML;
}

function getStatusBadge(status) {
    const statusLower = status.toLowerCase();
    let badgeClass = 'bg-secondary';
    
    switch (statusLower) {
        case 'completed':
            badgeClass = 'bg-success';
            break;
        case 'in_progress':
            badgeClass = 'bg-warning text-dark';
            break;
        case 'not_started':
            badgeClass = 'bg-secondary';
            break;
        case 'submitted':
            badgeClass = 'bg-info';
            break;
        case 'reviewed':
            badgeClass = 'bg-primary';
            break;
    }
    
    return `<span class="badge ${badgeClass}">${status}</span>`;
}

// Filter logs
document.getElementById('filterForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const filters = {
        email: document.getElementById('filterEmail').value,
        student_id: document.getElementById('filterStudentId').value,
        week: document.getElementById('filterWeek').value
    };
    
    fetchLogs(filters);
});

// Clear filters
document.getElementById('clearFilters').addEventListener('click', function() {
    document.getElementById('filterForm').reset();
    fetchLogs();
});

// Delete all logs
document.getElementById('deleteLogsBtn').addEventListener('click', async function() {
    const secretKey = document.getElementById('secretKey').value;
    
    if (!secretKey) {
        showToast('Please enter the secret key', 'warning');
        return;
    }
    
    if (!confirm('Are you sure you want to delete ALL progress logs? This action cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/logs?key=${encodeURIComponent(secretKey)}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showToast('All logs have been cleared successfully!', 'success');
            document.getElementById('secretKey').value = '';
            fetchLogs();
        } else {
            showToast(`Error: ${result.error}`, 'danger');
        }
    } catch (error) {
        showToast(`Network error: ${error.message}`, 'danger');
    }
});

// Load logs when page loads
document.addEventListener('DOMContentLoaded', function() {
    fetchLogs();
});
