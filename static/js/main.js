// CiteVerify - Main Application JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss messages after 5 seconds
    document.querySelectorAll('[data-dismiss]').forEach(el => {
        setTimeout(() => {
            el.style.transition = 'opacity 0.5s ease';
            el.style.opacity = '0';
            setTimeout(() => el.remove(), 500);
        }, 5000);
    });

    // File input preview
    const fileInput = document.querySelector('input[type="file"]');
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const preview = document.getElementById('file-preview');
            if (preview && this.files[0]) {
                preview.textContent = this.files[0].name;
                preview.classList.remove('hidden');
            }
        });
    }

    // Textarea auto-resize
    document.querySelectorAll('textarea').forEach(textarea => {
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });
    });
});
