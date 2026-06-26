document.addEventListener('DOMContentLoaded', function() {
    // По умолчанию показываем форму участника
    showForm('visitor');
    
    // Добавляем поля пароля в форму участника при отправке
    document.getElementById('visitor-form').addEventListener('submit', function(e) {
        // Генерируем случайный пароль если пустой
        const password1 = this.querySelector('input[name="password1"]');
        const password2 = this.querySelector('input[name="password2"]');
        
        if (!password1.value) {
            const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*';
            let password = '';
            for (let i = 0; i < 12; i++) {
                password += chars.charAt(Math.floor(Math.random() * chars.length));
            }
            password1.value = password;
            password2.value = password;
        }
    });
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