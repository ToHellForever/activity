document.addEventListener('DOMContentLoaded', function() {
    // По умолчанию показываем форму участника
    showForm('visitor');
});

function showForm(type) {
    const visitorForm = document.getElementById('visitor-form');
    const partnerForm = document.getElementById('partner-form');
    
    if (type === 'partner') {
        visitorForm.style.display = 'none';
        partnerForm.style.display = 'block';
    } else {
        visitorForm.style.display = 'block';
        partnerForm.style.display = 'none';
    }
}
