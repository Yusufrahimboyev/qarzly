document.addEventListener('DOMContentLoaded', () => {
    const tg = window.Telegram?.WebApp;
    if (tg) {
        tg.ready();
        tg.expand();
    }

    const btn = document.getElementById('main-btn');
    if (btn && tg) {
        btn.addEventListener('click', () => {
            tg.close();
        });
    }
});
