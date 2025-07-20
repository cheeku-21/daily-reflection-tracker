// This file is intentionally left blank.
document.addEventListener('DOMContentLoaded', function() {
    // Request notification permission
    if ("Notification" in window) {
        Notification.requestPermission();
    }

    // Show success notification if needed
    if (document.body.dataset.showSuccess === 'true') {
        fetch('/notify-success')
            .then(response => response.json())
            .then(data => {
                if (Notification.permission === "granted") {
                    new Notification(data.title, {
                        body: data.body,
                        icon: '/static/success-icon.png'
                    });
                }
            });
    }

    // Schedule evening reminder
    const scheduleReminder = () => {
        const now = new Date();
        const evening = new Date(
            now.getFullYear(),
            now.getMonth(),
            now.getDate(),
            20, // 8 PM
            0,
            0
        );
        
        if (now > evening) {
            evening.setDate(evening.getDate() + 1);
        }
        
        const delay = evening - now;
        
        setTimeout(() => {
            if (Notification.permission === "granted") {
                new Notification("Daily Reflection Reminder", {
                    body: "Don't forget to log your daily tasks!",
                    icon: '/static/reminder-icon.png'
                });
            }
            scheduleReminder(); // Schedule next day's reminder
        }, delay);
    };

    scheduleReminder();
});