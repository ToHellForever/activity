// === PARTNER TICKET CHECK ===

document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.attendance-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var eventId = this.dataset.eventId;
            var orderId = this.dataset.orderId;
            var ticketNumber = this.dataset.ticketNumber;

            this.disabled = true;

            fetch("/partner/mark_attendance/" + eventId + "/" + orderId + "/" + ticketNumber + "/", {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(function(response) { return response.json(); })
            .then(function(data) {
                if (data.success) {
                    var newAttended = data.attended;
                    btn.dataset.attended = newAttended;
                    if (newAttended) {
                        btn.className = 'attendance-btn mb-2 btn-outline-success';
                        btn.innerHTML = '<i class="bi bi-check-circle-fill"></i> Билет #' + ticketNumber + ' — посещён';
                    } else {
                        btn.className = 'attendance-btn mb-2';
                        btn.innerHTML = '<i class="bi bi-person-check"></i> Билет #' + ticketNumber + ' — отметить';
                    }
                } else {
                    alert('Произошла ошибка при обновлении статуса.');
                }
            })
            .catch(function() {
                alert('Произошла ошибка сети.');
            })
            .finally(function() {
                btn.disabled = false;
            });
        });
    });

    function getCookie(name) {
        var cookieValue = null;
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
        return cookieValue;
    }
});
