/**
 * Minerals Chain Admin Portal - Component Interactions
 * Batch V - Visual Design & Documentation Polish
 */

// ========== AUDIT LOG EXPANSION ==========
document.addEventListener('DOMContentLoaded', function() {
  const auditLogEntries = document.querySelectorAll('.audit-log-entry');

  auditLogEntries.forEach(entry => {
    const header = entry.querySelector('.audit-log-header');
    if (header) {
      header.addEventListener('click', function() {
        entry.classList.toggle('expanded');
      });
    }
  });
});


// ========== TABLE SORTING ==========
function initializeSortableTables() {
  const tables = document.querySelectorAll('.data-table');

  tables.forEach(table => {
    const headers = table.querySelectorAll('th[data-sortable]');

    headers.forEach(header => {
      header.addEventListener('click', function() {
        const column = header.cellIndex;
        const rows = Array.from(table.querySelectorAll('tbody tr'));

        // Remove sort indicators from other headers
        headers.forEach(h => h.classList.remove('asc', 'desc'));

        // Determine sort direction
        const isAsc = header.classList.contains('asc');
        header.classList.toggle('asc', !isAsc);
        header.classList.toggle('desc', isAsc);

        // Sort rows
        rows.sort((a, b) => {
          const aValue = a.cells[column].textContent.trim();
          const bValue = b.cells[column].textContent.trim();

          // Try numeric comparison first
          const aNum = parseFloat(aValue);
          const bNum = parseFloat(bValue);

          if (!isNaN(aNum) && !isNaN(bNum)) {
            return isAsc ? bNum - aNum : aNum - bNum;
          }

          // Fall back to string comparison
          return isAsc
            ? bValue.localeCompare(aValue)
            : aValue.localeCompare(bValue);
        });

        // Re-append sorted rows
        rows.forEach(row => table.appendChild(row));
      });

      // Add pointer cursor to indicate sortability
      header.style.cursor = 'pointer';
    });
  });
}

// Initialize on page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeSortableTables);
} else {
  initializeSortableTables();
}


// ========== DOCUMENT VIEWER CONTROLS ==========
function initializeDocumentViewer() {
  const viewers = document.querySelectorAll('.document-viewer-container');

  viewers.forEach(viewer => {
    const prevBtn = viewer.querySelector('.pagination-btn:nth-of-type(1)');
    const nextBtn = viewer.querySelector('.pagination-btn:nth-of-type(3)');
    const pageInput = viewer.querySelector('.pagination-input');
    const frame = viewer.querySelector('.document-preview-frame');

    if (prevBtn && nextBtn && pageInput) {
      prevBtn.addEventListener('click', function() {
        const currentPage = parseInt(pageInput.value) || 1;
        if (currentPage > 1) {
          pageInput.value = currentPage - 1;
          // Trigger page change event
          pageInput.dispatchEvent(new Event('change'));
        }
      });

      nextBtn.addEventListener('click', function() {
        const currentPage = parseInt(pageInput.value) || 1;
        pageInput.value = currentPage + 1;
        pageInput.dispatchEvent(new Event('change'));
      });
    }

    // Zoom controls
    const zoomInBtn = viewer.querySelector('.document-viewer-tool-btn:nth-of-type(1)');
    const zoomOutBtn = viewer.querySelector('.document-viewer-tool-btn:nth-of-type(2)');
    const downloadBtn = viewer.querySelector('.document-viewer-tool-btn:nth-of-type(3)');
    const printBtn = viewer.querySelector('.document-viewer-tool-btn:nth-of-type(4)');

    let zoomLevel = 100;

    if (zoomInBtn) {
      zoomInBtn.addEventListener('click', function() {
        zoomLevel = Math.min(200, zoomLevel + 10);
        if (frame) frame.style.transform = `scale(${zoomLevel / 100})`;
      });
    }

    if (zoomOutBtn) {
      zoomOutBtn.addEventListener('click', function() {
        zoomLevel = Math.max(50, zoomLevel - 10);
        if (frame) frame.style.transform = `scale(${zoomLevel / 100})`;
      });
    }

    if (downloadBtn) {
      downloadBtn.addEventListener('click', function() {
        const src = frame?.src;
        if (src) {
          const a = document.createElement('a');
          a.href = src;
          a.download = 'document.pdf';
          a.click();
        }
      });
    }

    if (printBtn) {
      printBtn.addEventListener('click', function() {
        window.print();
      });
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeDocumentViewer);
} else {
  initializeDocumentViewer();
}


// ========== TOOLTIP INITIALIZATION ==========
function initializeTooltips() {
  const tooltips = document.querySelectorAll('[title]');

  tooltips.forEach(element => {
    if (!element.classList.contains('help-icon') && !element.classList.contains('document-viewer-tool-btn')) {
      return; // Skip default browser tooltips
    }
  });
}


// ========== FORM VALIDATION ==========
function validateForm(formElement) {
  const inputs = formElement.querySelectorAll('input[required], textarea[required], select[required]');
  let isValid = true;

  inputs.forEach(input => {
    if (!input.value.trim()) {
      input.style.borderColor = '#ef4444';
      isValid = false;
    } else {
      input.style.borderColor = '';
    }
  });

  return isValid;
}


// ========== ANIMATION UTILITIES ==========
function fadeIn(element, duration = 300) {
  element.style.opacity = '0';
  element.style.transition = `opacity ${duration}ms ease`;

  setTimeout(() => {
    element.style.opacity = '1';
  }, 10);
}

function fadeOut(element, duration = 300) {
  element.style.transition = `opacity ${duration}ms ease`;
  element.style.opacity = '0';

  setTimeout(() => {
    element.style.display = 'none';
  }, duration);
}


// ========== RESPONSIVE TABLE HANDLER ==========
function makeTablesResponsive() {
  const tables = document.querySelectorAll('.data-table');

  tables.forEach(table => {
    const rows = table.querySelectorAll('tr');
    const headerCells = table.querySelectorAll('thead th');

    rows.forEach((row, index) => {
      if (index === 0) return; // Skip header

      const cells = row.querySelectorAll('td');
      cells.forEach((cell, cellIndex) => {
        const headerText = headerCells[cellIndex]?.textContent.trim();
        if (headerText && window.innerWidth < 768) {
          cell.setAttribute('data-label', headerText);
        }
      });
    });
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', makeTablesResponsive);
} else {
  makeTablesResponsive();
}

window.addEventListener('resize', makeTablesResponsive);


// ========== NOTIFICATION SYSTEM ==========
function showNotification(message, type = 'info', duration = 3000) {
  const notification = document.createElement('div');
  notification.className = `notification notification-${type}`;
  notification.textContent = message;
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 16px 20px;
    border-radius: 8px;
    z-index: 10000;
    background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
    color: white;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
  `;

  document.body.appendChild(notification);
  fadeIn(notification);

  setTimeout(() => {
    fadeOut(notification, 300);
    setTimeout(() => notification.remove(), 300);
  }, duration);
}


// ========== CONFIRM DIALOG ==========
function showConfirmDialog(title, message, onConfirm, onCancel) {
  const dialog = document.createElement('div');
  dialog.className = 'confirm-dialog';
  dialog.innerHTML = `
    <div style="
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 9999;
    ">
      <div style="
        background: white;
        border-radius: 8px;
        padding: 24px;
        max-width: 400px;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
      ">
        <h3 style="margin: 0 0 12px 0; color: #111827; font-size: 18px;">${title}</h3>
        <p style="margin: 0 0 20px 0; color: #6b7280; font-size: 14px;">${message}</p>
        <div style="display: flex; gap: 12px; justify-content: flex-end;">
          <button class="btn btn-secondary" id="cancel-btn">Cancel</button>
          <button class="btn btn-primary" id="confirm-btn">Confirm</button>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(dialog);

  const confirmBtn = dialog.querySelector('#confirm-btn');
  const cancelBtn = dialog.querySelector('#cancel-btn');

  confirmBtn.addEventListener('click', () => {
    dialog.remove();
    if (onConfirm) onConfirm();
  });

  cancelBtn.addEventListener('click', () => {
    dialog.remove();
    if (onCancel) onCancel();
  });
}


// Export functions for use in other scripts
window.MineralsAdmin = {
  fadeIn,
  fadeOut,
  validateForm,
  showNotification,
  showConfirmDialog,
  initializeSortableTables,
  initializeDocumentViewer
};
